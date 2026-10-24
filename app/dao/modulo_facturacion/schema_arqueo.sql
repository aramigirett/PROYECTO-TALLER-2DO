-- Registrar Arqueo de Caja (con Recaudación a depositar) — OBJETOS de base de datos (funciones, procedimiento, triggers y vista).
-- NO crea tablas: arqueo_caja, arqueo_caja_det y recaudacion_depositar las crea el DER (01_migracion_der.sql); schema_cuenta_bancaria.sql
-- le suma a recaudacion_depositar la columna id_cuenta_bancaria. Idempotente.
-- Orden: 01_migracion_der.sql -> schema_cobranzas.sql -> schema_notas.sql -> schema_cuenta_bancaria.sql -> este script
--        -> schema_permisos_arqueo.sql -> schema_permisos_cajero.sql. Aplicar con PGCLIENTENCODING=UTF8 (tiene tildes).
-- Cada objeto documenta propósito, parámetros y excepciones, y lleva COMMENT ON.
--
-- Reglas de negocio:
--   * El arqueo es un control POSTERIOR al cierre: solo se arquea una apertura CERRADA, una sola vez (mientras el arqueo esté REGISTRADO).
--   * Nadie arquea su propia caja: "No puede arquear su propia caja; el arqueo debe hacerlo otro usuario."
--   * Detalle por forma de cobro: monto del SISTEMA (lo calcula la base), monto CONTADO (lo ingresa quien arquea) y diferencia (sobrante +, faltante -).
--     El fondo inicial y los reintegros en efectivo van dentro del efectivo: sistema = cobrado + fondo inicial - reintegros (en la primera forma EFECTIVO).
--   * Observación obligatoria si alguna forma tiene diferencia.
--   * La recaudación a depositar (PENDIENTE) = efectivo contado - fondo inicial (mínimo 0) + cheques contados. Tarjetas y transferencias no se depositan.

-- =====================================================================================================================
-- FUNCIÓN: fn_forma_efectivo_arqueo()
-- Propósito : la forma de cobro de tipo EFECTIVO a la que el arqueo le asigna el fondo inicial y los reintegros (la primera por id,
--             prefiriendo las activas). NULL si no hay ninguna forma EFECTIVO.
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_forma_efectivo_arqueo() RETURNS INT
LANGUAGE sql STABLE
AS $$
    SELECT id_forma_cobro FROM forma_cobro WHERE tipo = 'EFECTIVO' ORDER BY activo DESC, id_forma_cobro LIMIT 1;
$$;
COMMENT ON FUNCTION fn_forma_efectivo_arqueo() IS 'Forma de cobro EFECTIVO que lleva el fondo inicial y los reintegros en el arqueo (la primera por id, prefiriendo las activas).';

-- =====================================================================================================================
-- FUNCIÓN: fn_formas_arqueo(p_id_apertura)
-- Propósito : las formas de cobro que se cuentan en el arqueo de una apertura con el monto según el SISTEMA: las que tuvieron movimiento
--             (v_resumen_caja) más la forma EFECTIVO; en la forma EFECTIVO el monto del sistema suma el fondo inicial y resta los
--             reintegros de las notas de crédito. Efectivo primero, luego por descripción.
-- Parámetros: p_id_apertura INT. Devuelve (id_forma_cobro, forma_cobro, tipo, cobrado, monto_sistema); sin filas si la apertura no existe.
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_formas_arqueo(p_id_apertura INT)
RETURNS TABLE (id_forma_cobro INT, forma_cobro VARCHAR, tipo VARCHAR, cobrado NUMERIC, monto_sistema NUMERIC)
LANGUAGE sql STABLE
AS $$
    WITH ef  AS (SELECT fn_forma_efectivo_arqueo() AS id),
         ap  AS (SELECT monto_apertura FROM apertura_cierre_caja WHERE id_apertura = p_id_apertura),
         mov AS (SELECT r.id_forma_cobro AS id, SUM(r.total_cobrado) AS cobrado
                   FROM v_resumen_caja r WHERE r.id_apertura = p_id_apertura AND r.id_forma_cobro IS NOT NULL GROUP BY r.id_forma_cobro)
    SELECT f.id_forma_cobro, f.descripcion::VARCHAR, f.tipo::VARCHAR, COALESCE(m.cobrado, 0)::NUMERIC,
           (COALESCE(m.cobrado, 0)
            + CASE WHEN f.id_forma_cobro = ef.id THEN (SELECT monto_apertura FROM ap) - fn_total_reintegros(p_id_apertura) ELSE 0 END)::NUMERIC
      FROM forma_cobro f
      CROSS JOIN ef
      LEFT JOIN mov m ON m.id = f.id_forma_cobro
     WHERE EXISTS (SELECT 1 FROM ap) AND (m.id IS NOT NULL OR f.id_forma_cobro = ef.id)
     ORDER BY (f.tipo <> 'EFECTIVO'), f.descripcion;
$$;
COMMENT ON FUNCTION fn_formas_arqueo(INT) IS 'Formas de cobro a contar en el arqueo de una apertura, con el monto del sistema (en efectivo: cobrado + fondo inicial - reintegros).';

-- =====================================================================================================================
-- TRIGGER: trg_validar_arqueo  (BEFORE INSERT ON arqueo_caja)
-- Propósito : no se registra un arqueo de una apertura que no esté CERRADA, ni de la propia caja de quien arquea. Bloquea la apertura
--             (FOR SHARE) mientras se inserta.
-- Excepciones: 'La apertura de caja no existe.'; 'Solo se puede arquear una apertura CERRADA.';
--              'No puede arquear su propia caja; el arqueo debe hacerlo otro usuario.'
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_validar_arqueo() RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_ap apertura_cierre_caja%ROWTYPE;
BEGIN
    IF NEW.estado <> 'REGISTRADO' THEN
        RETURN NEW;
    END IF;
    SELECT * INTO v_ap FROM apertura_cierre_caja WHERE id_apertura = NEW.id_apertura FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'La apertura de caja no existe.';
    END IF;
    IF v_ap.estado <> 'CERRADA' THEN
        RAISE EXCEPTION 'Solo se puede arquear una apertura CERRADA.';
    END IF;
    IF v_ap.id_usuario = NEW.id_usuario THEN
        RAISE EXCEPTION 'No puede arquear su propia caja; el arqueo debe hacerlo otro usuario.';
    END IF;
    RETURN NEW;
END;
$$;
COMMENT ON FUNCTION fn_validar_arqueo() IS 'Función del trigger trg_validar_arqueo: la apertura debe estar CERRADA y no puede ser la caja propia de quien arquea.';

DROP TRIGGER IF EXISTS trg_validar_arqueo ON arqueo_caja;
CREATE TRIGGER trg_validar_arqueo
    BEFORE INSERT ON arqueo_caja
    FOR EACH ROW EXECUTE FUNCTION fn_validar_arqueo();
COMMENT ON TRIGGER trg_validar_arqueo ON arqueo_caja IS 'Antes de insertar el arqueo: la apertura debe estar CERRADA y no ser la propia de quien arquea.';

-- =====================================================================================================================
-- TRIGGER: trg_arqueo_estado  (BEFORE UPDATE OF estado ON arqueo_caja)
-- Propósito : un arqueo ANULADO no se reactiva (la apertura pudo arquearse de nuevo) y no se anula un arqueo cuya recaudación ya fue DEPOSITADA.
-- Excepciones: 'Un arqueo anulado no se puede reactivar.'; 'No se puede anular el arqueo: su recaudación ya fue depositada.'
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_arqueo_estado() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.estado = 'ANULADO' AND NEW.estado <> 'ANULADO' THEN
        RAISE EXCEPTION 'Un arqueo anulado no se puede reactivar.';
    END IF;
    IF NEW.estado = 'ANULADO' AND EXISTS (SELECT 1 FROM recaudacion_depositar WHERE id_arqueo = NEW.id_arqueo AND estado = 'DEPOSITADA') THEN
        RAISE EXCEPTION 'No se puede anular el arqueo: su recaudación ya fue depositada.';
    END IF;
    RETURN NEW;
END;
$$;
COMMENT ON FUNCTION fn_arqueo_estado() IS 'Función del trigger trg_arqueo_estado: un arqueo anulado no se reactiva y no se anula si su recaudación ya está depositada.';

DROP TRIGGER IF EXISTS trg_arqueo_estado ON arqueo_caja;
CREATE TRIGGER trg_arqueo_estado
    BEFORE UPDATE OF estado ON arqueo_caja
    FOR EACH ROW EXECUTE FUNCTION fn_arqueo_estado();
COMMENT ON TRIGGER trg_arqueo_estado ON arqueo_caja IS 'Un arqueo anulado no se reactiva y no se anula con la recaudación depositada.';

-- =====================================================================================================================
-- TRIGGER: trg_recaudacion_estado  (BEFORE UPDATE OF estado ON recaudacion_depositar)
-- Propósito : PENDIENTE es el único estado desde el que se avanza: una recaudación DEPOSITADA o ANULADA no cambia de estado, y solo se
--             deposita la recaudación de un arqueo REGISTRADO.
-- Excepciones: 'Una recaudación depositada o anulada no cambia de estado.'; 'No se puede depositar la recaudación de un arqueo anulado.'
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_recaudacion_estado() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.estado <> 'PENDIENTE' AND NEW.estado <> OLD.estado THEN
        RAISE EXCEPTION 'Una recaudación depositada o anulada no cambia de estado.';
    END IF;
    IF NEW.estado = 'DEPOSITADA' AND NOT EXISTS (SELECT 1 FROM arqueo_caja WHERE id_arqueo = NEW.id_arqueo AND estado = 'REGISTRADO') THEN
        RAISE EXCEPTION 'No se puede depositar la recaudación de un arqueo anulado.';
    END IF;
    RETURN NEW;
END;
$$;
COMMENT ON FUNCTION fn_recaudacion_estado() IS 'Función del trigger trg_recaudacion_estado: solo la recaudación PENDIENTE avanza y solo si su arqueo está REGISTRADO.';

DROP TRIGGER IF EXISTS trg_recaudacion_estado ON recaudacion_depositar;
CREATE TRIGGER trg_recaudacion_estado
    BEFORE UPDATE OF estado ON recaudacion_depositar
    FOR EACH ROW EXECUTE FUNCTION fn_recaudacion_estado();
COMMENT ON TRIGGER trg_recaudacion_estado ON recaudacion_depositar IS 'La recaudación depositada o anulada no cambia de estado; solo se deposita la de un arqueo REGISTRADO.';

-- =====================================================================================================================
-- PROCEDIMIENTO: sp_registrar_arqueo
-- Propósito : registrar un arqueo EN UNA TRANSACCIÓN (la del que llama): inserta el arqueo, su detalle (el monto del sistema lo calcula la
--             base con fn_formas_arqueo) y la recaudación a depositar PENDIENTE. Valida y deja que falle todo junto.
-- Parámetros: IN p_id_apertura INT      apertura CERRADA a arquear
--             IN p_id_usuario   INT      quien arquea (nunca el cajero de la apertura)
--             IN p_formas       INT[]    formas de cobro contadas (todas las de fn_formas_arqueo, sin repetir)
--             IN p_contados     NUMERIC[] monto contado de cada forma (entero >= 0), en el mismo orden
--             IN p_observacion  VARCHAR  obligatoria si alguna forma tiene diferencia (máx. 200)
--             OUT p_id_arqueo INT, OUT p_id_recaudacion INT (NULL si no hay nada que depositar)
-- Uso       : CALL sp_registrar_arqueo(12, 3, ARRAY[1,2], ARRAY[250000, 90000], 'Sin novedades', NULL, NULL);
-- Excepciones (RAISE EXCEPTION, la API las muestra tal cual): 'La apertura de caja no existe.'; 'Solo se puede arquear una apertura CERRADA.';
--   'No puede arquear su propia caja; el arqueo debe hacerlo otro usuario.'; 'La apertura ya tiene un arqueo registrado.';
--   'Debe indicar el monto contado de cada forma de cobro.'; 'Hay formas de cobro repetidas en el arqueo.';
--   'Los montos contados deben ser números enteros mayores o iguales a 0.'; 'Falta contar la forma de cobro: <X>.';
--   'La forma de cobro <X> no corresponde a este arqueo.'; 'El efectivo según el sistema es negativo (Gs. -N): revise las anulaciones de la apertura.';
--   'La observación no puede superar los 200 caracteres.'; 'Debe ingresar una observación: el arqueo tiene diferencias.';
--   'No se pudo registrar el arqueo: <causa>'.
-- =====================================================================================================================
CREATE OR REPLACE PROCEDURE sp_registrar_arqueo(
    IN  p_id_apertura INT, IN p_id_usuario INT, IN p_formas INT[], IN p_contados NUMERIC[], IN p_observacion VARCHAR,
    OUT p_id_arqueo INT, OUT p_id_recaudacion INT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_ap        apertura_cierre_caja%ROWTYPE;
    v_n         INTEGER;
    v_texto     TEXT;
    v_obs       VARCHAR;
    v_total_sis NUMERIC;
    v_total_con NUMERIC;
    v_hay_dif   BOOLEAN;
    v_neg       TEXT;
    v_ef        NUMERIC;
    v_ch        NUMERIC;
    v_monto_ef  NUMERIC;
    v_total_rec NUMERIC;
BEGIN
    p_id_arqueo := NULL; p_id_recaudacion := NULL;
    SELECT * INTO v_ap FROM apertura_cierre_caja WHERE id_apertura = p_id_apertura FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'La apertura de caja no existe.';
    END IF;
    IF v_ap.estado <> 'CERRADA' THEN
        RAISE EXCEPTION 'Solo se puede arquear una apertura CERRADA.';
    END IF;
    IF v_ap.id_usuario = p_id_usuario THEN
        RAISE EXCEPTION 'No puede arquear su propia caja; el arqueo debe hacerlo otro usuario.';
    END IF;
    IF EXISTS (SELECT 1 FROM arqueo_caja WHERE id_apertura = p_id_apertura AND estado = 'REGISTRADO') THEN
        RAISE EXCEPTION 'La apertura ya tiene un arqueo registrado.';
    END IF;

    v_n := COALESCE(array_length(p_formas, 1), 0);
    IF v_n = 0 OR v_n <> COALESCE(array_length(p_contados, 1), 0) THEN
        RAISE EXCEPTION 'Debe indicar el monto contado de cada forma de cobro.';
    END IF;
    IF (SELECT count(DISTINCT x) FROM unnest(p_formas) AS x) <> v_n THEN
        RAISE EXCEPTION 'Hay formas de cobro repetidas en el arqueo.';
    END IF;
    IF EXISTS (SELECT 1 FROM unnest(p_contados) AS c WHERE c IS NULL OR c < 0 OR c <> trunc(c)) THEN
        RAISE EXCEPTION 'Los montos contados deben ser números enteros mayores o iguales a 0.';
    END IF;

    SELECT string_agg(fa.forma_cobro, ', ') INTO v_texto FROM fn_formas_arqueo(p_id_apertura) fa WHERE fa.id_forma_cobro <> ALL (p_formas);
    IF v_texto IS NOT NULL THEN
        RAISE EXCEPTION 'Falta contar la forma de cobro: %.', v_texto;
    END IF;
    SELECT string_agg(COALESCE(f.descripcion, x::TEXT), ', ') INTO v_texto
      FROM unnest(p_formas) AS x LEFT JOIN forma_cobro f ON f.id_forma_cobro = x
     WHERE x NOT IN (SELECT fa.id_forma_cobro FROM fn_formas_arqueo(p_id_apertura) fa);
    IF v_texto IS NOT NULL THEN
        RAISE EXCEPTION 'La forma de cobro % no corresponde a este arqueo.', v_texto;
    END IF;

    SELECT SUM(fa.monto_sistema), SUM(c.monto), bool_or(c.monto <> fa.monto_sistema),
           string_agg(fa.forma_cobro, ', ') FILTER (WHERE fa.monto_sistema < 0),
           SUM(c.monto) FILTER (WHERE fa.tipo = 'EFECTIVO'), SUM(c.monto) FILTER (WHERE fa.tipo = 'CHEQUE')
      INTO v_total_sis, v_total_con, v_hay_dif, v_neg, v_ef, v_ch
      FROM fn_formas_arqueo(p_id_apertura) fa
      JOIN unnest(p_formas, p_contados) AS c(id_forma, monto) ON c.id_forma = fa.id_forma_cobro;
    IF v_neg IS NOT NULL THEN
        RAISE EXCEPTION 'El efectivo según el sistema es negativo (%): revise las anulaciones de la apertura.', v_neg;
    END IF;

    v_obs := NULLIF(btrim(COALESCE(p_observacion, '')), '');
    IF v_obs IS NOT NULL AND length(v_obs) > 200 THEN
        RAISE EXCEPTION 'La observación no puede superar los 200 caracteres.';
    END IF;
    IF v_hay_dif AND v_obs IS NULL THEN
        RAISE EXCEPTION 'Debe ingresar una observación: el arqueo tiene diferencias.';
    END IF;

    INSERT INTO arqueo_caja (id_apertura, id_usuario, total_sistema, total_contado, diferencia, observacion)
    VALUES (p_id_apertura, p_id_usuario, v_total_sis, v_total_con, v_total_con - v_total_sis, v_obs)
    RETURNING id_arqueo INTO p_id_arqueo;

    INSERT INTO arqueo_caja_det (id_arqueo, id_forma_cobro, monto_sistema, monto_contado, diferencia)
    SELECT p_id_arqueo, fa.id_forma_cobro, fa.monto_sistema, c.monto, c.monto - fa.monto_sistema
      FROM fn_formas_arqueo(p_id_apertura) fa
      JOIN unnest(p_formas, p_contados) AS c(id_forma, monto) ON c.id_forma = fa.id_forma_cobro;

    -- Recaudación a depositar: el efectivo contado menos el fondo inicial (nunca negativo) más los cheques contados.
    v_monto_ef  := GREATEST(COALESCE(v_ef, 0) - v_ap.monto_apertura, 0);
    v_total_rec := v_monto_ef + COALESCE(v_ch, 0);
    IF v_total_rec > 0 THEN
        INSERT INTO recaudacion_depositar (id_arqueo, id_usuario, monto_efectivo, monto_cheque, total)
        VALUES (p_id_arqueo, p_id_usuario, v_monto_ef, COALESCE(v_ch, 0), v_total_rec)
        RETURNING id_recaudacion INTO p_id_recaudacion;
    END IF;
EXCEPTION
    WHEN unique_violation THEN
        RAISE EXCEPTION 'La apertura ya tiene un arqueo registrado.';
    WHEN raise_exception THEN
        RAISE;
    WHEN OTHERS THEN
        RAISE EXCEPTION 'No se pudo registrar el arqueo: %', SQLERRM;
END;
$$;
COMMENT ON PROCEDURE sp_registrar_arqueo(INT, INT, INT[], NUMERIC[], VARCHAR) IS 'Registra el arqueo de una apertura CERRADA en una transacción: arqueo, detalle (sistema calculado en la base) y recaudación a depositar PENDIENTE. Nadie arquea su propia caja.';

-- =====================================================================================================================
-- VISTA: v_arqueos_diferencias
-- Propósito : control del Administrador: por arqueo, la apertura, el cajero, las fechas, el total según el sistema, el total contado y la
--             diferencia (con el resultado CUADRA / SOBRANTE / FALTANTE). Incluye todos los estados; para el control use estado = 'REGISTRADO'.
-- Columnas  : id_arqueo, id_apertura, caja, id_cajero, cajero, fecha_apertura, fecha_cierre, fecha_arqueo, id_arqueador, arqueador,
--             total_sistema, total_contado, diferencia, resultado, estado, observacion.
-- =====================================================================================================================
CREATE OR REPLACE VIEW v_arqueos_diferencias AS
SELECT q.id_arqueo,
       q.id_apertura,
       cj.descripcion AS caja,
       a.id_usuario AS id_cajero,
       COALESCE(fc.nombre || ' ' || fc.apellido, mc.nombre || ' ' || mc.apellido) AS cajero,
       a.fecha_apertura,
       a.fecha_cierre,
       q.fecha AS fecha_arqueo,
       q.id_usuario AS id_arqueador,
       COALESCE(fa.nombre || ' ' || fa.apellido, ma.nombre || ' ' || ma.apellido) AS arqueador,
       q.total_sistema,
       q.total_contado,
       q.diferencia,
       CASE WHEN q.diferencia = 0 THEN 'CUADRA' WHEN q.diferencia > 0 THEN 'SOBRANTE' ELSE 'FALTANTE' END AS resultado,
       q.estado,
       q.observacion
FROM arqueo_caja q
JOIN apertura_cierre_caja a ON a.id_apertura = q.id_apertura
JOIN caja cj ON cj.id_caja = a.id_caja
JOIN usuarios uc ON uc.id_usuario = a.id_usuario
LEFT JOIN funcionario fc ON fc.id_funcionario = uc.id_funcionario
LEFT JOIN medico mc ON mc.id_medico = uc.id_medico
JOIN usuarios ua ON ua.id_usuario = q.id_usuario
LEFT JOIN funcionario fa ON fa.id_funcionario = ua.id_funcionario
LEFT JOIN medico ma ON ma.id_medico = ua.id_medico;
COMMENT ON VIEW v_arqueos_diferencias IS 'Control de arqueos: por apertura, cajero, fecha, total del sistema, total contado y diferencia (CUADRA / SOBRANTE / FALTANTE).';
