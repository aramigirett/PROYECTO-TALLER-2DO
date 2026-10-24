-- Registrar Notas de Crédito y Débito — OBJETOS de base de datos (funciones, triggers y vistas). NO crea tablas: las crea el DER
-- (01_migracion_der.sql) y schema_notas_columnas.sql les suma id_apertura y monto_reintegro. Idempotente.
-- Orden: 01_migracion_der.sql -> schema_cobranzas.sql -> schema_notas_columnas.sql -> este script -> schema_permisos_notas.sql
--        -> schema_permisos_cajero.sql. Aplicar con PGCLIENTENCODING=UTF8 (tiene tildes).
-- Cada objeto documenta propósito, parámetros y excepciones, y lleva COMMENT ON.
--
-- Reglas de negocio:
--   * Toda nota se vincula a una venta EMITIDA y a su cuenta a cobrar, y se emite con una caja ABIERTA del cajero.
--   * CRÉDITO: el total no puede superar (total de la factura - créditos EMITIDOS anteriores). Primero reduce el saldo pendiente; lo que
--     excede el saldo (factura ya pagada) es un REINTEGRO EN EFECTIVO al cliente, que sale de la caja y RESTA del efectivo del cierre.
--   * DÉBITO: suma al saldo; si la cuenta estaba PAGADA vuelve a PENDIENTE.
--   * Anular (solo con la caja de la nota ABIERTA) revierte el efecto sobre el saldo y el reintegro.

-- =====================================================================================================================
-- FUNCIÓN: fn_siguiente_numero_nota(p_tipo)
-- Propósito : entregar el próximo número de nota '001-001-0000001' (establecimiento y punto de expedición del timbrado ACTIVO + 7
--             dígitos), con numeración PROPIA por tipo (CREDITO y DEBITO llevan cada uno su secuencia), correlativa y SIN huecos
--             (mayor número usado del tipo + 1, bajo un bloqueo asesor de transacción; las anuladas conservan el suyo). No consume el
--             rango de numeración de las facturas (timbrado.numero_actual); solo exige que el timbrado esté vigente.
-- Parámetros: p_tipo VARCHAR ('CREDITO' | 'DEBITO'). Devuelve OUT p_id_timbrado INT, OUT p_numero_nota VARCHAR(15).
-- Excepciones: 'Tipo de nota inválido.'; 'No hay timbrado activo'; 'El timbrado aún no está vigente'; 'El timbrado está vencido';
--              'No se pudo generar el número de la nota: <causa>'.
-- Uso       : SELECT * FROM fn_siguiente_numero_nota('CREDITO');
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_siguiente_numero_nota(p_tipo VARCHAR, OUT p_id_timbrado INT, OUT p_numero_nota VARCHAR)
LANGUAGE plpgsql
AS $$
DECLARE
    v_t      timbrado%ROWTYPE;
    v_ultimo INTEGER;
BEGIN
    IF p_tipo NOT IN ('CREDITO', 'DEBITO') THEN
        RAISE EXCEPTION 'Tipo de nota inválido.';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtext('nota_credito_debito_cab.numero_nota.' || p_tipo));
    SELECT * INTO v_t FROM timbrado WHERE activo = true FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No hay timbrado activo';
    END IF;
    IF CURRENT_DATE < v_t.fecha_inicio THEN
        RAISE EXCEPTION 'El timbrado aún no está vigente';
    END IF;
    IF CURRENT_DATE > v_t.fecha_fin THEN
        RAISE EXCEPTION 'El timbrado está vencido';
    END IF;
    SELECT COALESCE(MAX(substring(numero_nota FROM '([0-9]{7})$')::INTEGER), 0) INTO v_ultimo
      FROM nota_credito_debito_cab WHERE tipo_nota = p_tipo;
    p_id_timbrado := v_t.id_timbrado;
    p_numero_nota := btrim(v_t.establecimiento) || '-' || btrim(v_t.punto_expedicion) || '-' || lpad((v_ultimo + 1)::TEXT, 7, '0');
EXCEPTION
    WHEN OTHERS THEN
        IF SQLERRM IN ('Tipo de nota inválido.', 'No hay timbrado activo', 'El timbrado aún no está vigente', 'El timbrado está vencido') THEN
            RAISE;
        END IF;
        RAISE EXCEPTION 'No se pudo generar el número de la nota: %', SQLERRM;
END;
$$;
COMMENT ON FUNCTION fn_siguiente_numero_nota(VARCHAR) IS 'Próximo número de nota (001-001-0000001), numeración propia por tipo (CREDITO/DEBITO), sin huecos, con el establecimiento y punto del timbrado activo vigente.';

-- =====================================================================================================================
-- TRIGGER: trg_preparar_nota  (BEFORE INSERT ON nota_credito_debito_cab)
-- Propósito : validar y completar la nota ANTES de insertarla.
--             * la caja de la nota debe estar ABIERTA (se bloquea FOR UPDATE: serializa los reintegros de una misma caja);
--             * la cuenta a cobrar se bloquea (FOR UPDATE) y su venta debe estar EMITIDA;
--             * CRÉDITO: total <= total de la factura - créditos EMITIDOS anteriores; calcula monto_reintegro = lo que excede el
--               saldo pendiente y, si es mayor a 0, exige efectivo suficiente en la caja (monto de apertura + efectivo neto);
--             * DÉBITO: monto_reintegro = 0.
-- Parámetros: ninguno propio (usa y completa NEW).
-- Excepciones: 'La caja de la nota no está abierta.'; 'La cuenta a cobrar no existe.'; 'No se puede emitir una nota sobre una venta
--              anulada.'; 'El total de la nota de crédito (Gs. A) supera el máximo permitido (Gs. B).';
--              'No hay efectivo suficiente en la caja para el reintegro (disponible Gs. N).'
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_preparar_nota() RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_ap     apertura_cierre_caja%ROWTYPE;
    v_cuenta cuenta_cobrar%ROWTYPE;
    v_venta  venta_cab%ROWTYPE;
    v_max    NUMERIC;
    v_disp   NUMERIC;
BEGIN
    IF NEW.estado <> 'EMITIDA' THEN
        RETURN NEW;
    END IF;
    SELECT * INTO v_ap FROM apertura_cierre_caja WHERE id_apertura = NEW.id_apertura FOR UPDATE;
    IF NOT FOUND OR v_ap.estado <> 'ABIERTA' THEN
        RAISE EXCEPTION 'La caja de la nota no está abierta.';
    END IF;
    SELECT * INTO v_cuenta FROM cuenta_cobrar WHERE id_cuenta = NEW.id_cuenta FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'La cuenta a cobrar no existe.';
    END IF;
    SELECT * INTO v_venta FROM venta_cab WHERE id_venta = v_cuenta.id_venta;
    IF v_venta.estado <> 'EMITIDA' THEN
        RAISE EXCEPTION 'No se puede emitir una nota sobre una venta anulada.';
    END IF;

    IF NEW.tipo_nota = 'CREDITO' THEN
        SELECT v_venta.total - COALESCE(SUM(total), 0) INTO v_max
          FROM nota_credito_debito_cab WHERE id_cuenta = NEW.id_cuenta AND tipo_nota = 'CREDITO' AND estado = 'EMITIDA';
        IF NEW.total > v_max THEN
            RAISE EXCEPTION 'El total de la nota de crédito (Gs. %) supera el máximo permitido (Gs. %).', fn_formato_gs(NEW.total), fn_formato_gs(v_max);
        END IF;
        NEW.monto_reintegro := GREATEST(NEW.total - v_cuenta.saldo, 0);
        IF NEW.monto_reintegro > 0 THEN
            v_disp := v_ap.monto_apertura + fn_total_efectivo_apertura(NEW.id_apertura);
            IF NEW.monto_reintegro > v_disp THEN
                RAISE EXCEPTION 'No hay efectivo suficiente en la caja para el reintegro (disponible Gs. %).', fn_formato_gs(GREATEST(v_disp, 0));
            END IF;
        END IF;
    ELSE
        NEW.monto_reintegro := 0;
    END IF;
    RETURN NEW;
END;
$$;
COMMENT ON FUNCTION fn_preparar_nota() IS 'Función del trigger trg_preparar_nota: caja abierta, venta EMITIDA, máximo del crédito y cálculo/validación del reintegro en efectivo.';

DROP TRIGGER IF EXISTS trg_preparar_nota ON nota_credito_debito_cab;
CREATE TRIGGER trg_preparar_nota
    BEFORE INSERT ON nota_credito_debito_cab
    FOR EACH ROW EXECUTE FUNCTION fn_preparar_nota();
COMMENT ON TRIGGER trg_preparar_nota ON nota_credito_debito_cab IS 'Antes de insertar la nota: caja abierta, venta EMITIDA, máximo del crédito y reintegro en efectivo (con efectivo suficiente).';

-- =====================================================================================================================
-- TRIGGER: trg_aplicar_nota  (AFTER INSERT OR UPDATE OF estado ON nota_credito_debito_cab)
-- Propósito : aplicar o revertir la nota sobre la cuenta a cobrar.
--             * INSERT EMITIDA, CRÉDITO: el saldo baja (total - monto_reintegro); si llega a 0 la cuenta pasa a PAGADA.
--             * INSERT EMITIDA, DÉBITO : el saldo sube en el total y la cuenta vuelve a PENDIENTE (aunque estuviera PAGADA).
--             * UPDATE EMITIDA -> ANULADA (solo con la caja de la nota ABIERTA): CRÉDITO devuelve (total - monto_reintegro) al saldo;
--               DÉBITO resta su total del saldo (si ya hubo cobros y el saldo no alcanza, se rechaza). El reintegro vuelve a la caja
--               solo (las funciones de caja cuentan únicamente notas EMITIDAS).
-- Parámetros: ninguno propio (usa NEW/OLD). Bloquea la cuenta con FOR UPDATE.
-- Excepciones: 'La cuenta a cobrar no existe.'; 'La caja de la nota ya fue cerrada; no se puede anular.';
--              'No se puede anular la nota: la cuenta a cobrar está anulada.';
--              'No se puede anular la nota de débito: el saldo actual (Gs. A) es menor que el débito (Gs. B); ya hay cobros posteriores.';
--              'Una nota anulada no se puede reactivar.'
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_aplicar_nota() RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_cuenta cuenta_cobrar%ROWTYPE;
    v_estado_apertura VARCHAR;
    v_reduce NUMERIC;
    v_nuevo  NUMERIC;
BEGIN
    SELECT * INTO v_cuenta FROM cuenta_cobrar WHERE id_cuenta = NEW.id_cuenta FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'La cuenta a cobrar no existe.';
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NEW.estado <> 'EMITIDA' THEN
            RETURN NEW;
        END IF;
        IF NEW.tipo_nota = 'CREDITO' THEN
            v_nuevo := v_cuenta.saldo - (NEW.total - NEW.monto_reintegro);
            UPDATE cuenta_cobrar SET saldo = v_nuevo, estado = CASE WHEN v_nuevo = 0 THEN 'PAGADA' ELSE 'PENDIENTE' END
             WHERE id_cuenta = NEW.id_cuenta;
        ELSE
            UPDATE cuenta_cobrar SET saldo = saldo + NEW.total, estado = 'PENDIENTE' WHERE id_cuenta = NEW.id_cuenta;
        END IF;
    ELSIF OLD.estado = 'EMITIDA' AND NEW.estado = 'ANULADA' THEN
        SELECT estado INTO v_estado_apertura FROM apertura_cierre_caja WHERE id_apertura = NEW.id_apertura FOR SHARE;
        IF v_estado_apertura IS DISTINCT FROM 'ABIERTA' THEN
            RAISE EXCEPTION 'La caja de la nota ya fue cerrada; no se puede anular.';
        END IF;
        IF v_cuenta.estado = 'ANULADA' THEN
            RAISE EXCEPTION 'No se puede anular la nota: la cuenta a cobrar está anulada.';
        END IF;
        IF NEW.tipo_nota = 'CREDITO' THEN
            v_reduce := OLD.total - OLD.monto_reintegro;
            v_nuevo := v_cuenta.saldo + v_reduce;
            UPDATE cuenta_cobrar SET saldo = v_nuevo, estado = CASE WHEN v_nuevo = 0 THEN 'PAGADA' ELSE 'PENDIENTE' END
             WHERE id_cuenta = NEW.id_cuenta;
        ELSE
            IF v_cuenta.saldo < OLD.total THEN
                RAISE EXCEPTION 'No se puede anular la nota de débito: el saldo actual (Gs. %) es menor que el débito (Gs. %); ya hay cobros posteriores.',
                                fn_formato_gs(v_cuenta.saldo), fn_formato_gs(OLD.total);
            END IF;
            v_nuevo := v_cuenta.saldo - OLD.total;
            UPDATE cuenta_cobrar SET saldo = v_nuevo, estado = CASE WHEN v_nuevo = 0 THEN 'PAGADA' ELSE 'PENDIENTE' END
             WHERE id_cuenta = NEW.id_cuenta;
        END IF;
    ELSIF OLD.estado = 'ANULADA' AND NEW.estado = 'EMITIDA' THEN
        RAISE EXCEPTION 'Una nota anulada no se puede reactivar.';
    END IF;
    RETURN NEW;
END;
$$;
COMMENT ON FUNCTION fn_aplicar_nota() IS 'Función del trigger trg_aplicar_nota: aplica o revierte la nota (crédito reduce el saldo, débito lo aumenta) sobre la cuenta a cobrar.';

DROP TRIGGER IF EXISTS trg_aplicar_nota ON nota_credito_debito_cab;
CREATE TRIGGER trg_aplicar_nota
    AFTER INSERT OR UPDATE OF estado ON nota_credito_debito_cab
    FOR EACH ROW EXECUTE FUNCTION fn_aplicar_nota();
COMMENT ON TRIGGER trg_aplicar_nota ON nota_credito_debito_cab IS 'Aplica la nota a cuenta_cobrar al emitirla (crédito baja el saldo, débito lo sube y reabre la cuenta) y la revierte al anularla.';

-- =====================================================================================================================
-- TRIGGER: trg_validar_nota_det  (BEFORE INSERT ON nota_credito_debito_det)
-- Propósito : los renglones con id_item son DEVOLUCIÓN DE MERCADERÍA (solo nota de crédito, venta de ítems): el ítem debe estar en la
--             factura, su tipo debe controlar stock y la cantidad no puede superar lo facturado menos lo ya devuelto en créditos
--             EMITIDOS. Los renglones de tratamiento no se admiten.
-- Excepciones: 'Las notas no admiten renglones de tratamiento.'; 'Solo una nota de crédito puede devolver mercadería.';
--              'Solo se devuelve mercadería de ventas de ítems.'; 'El ítem <ÍTEM> no pertenece a la factura.';
--              'El ítem <ÍTEM> no repone stock: su tipo no controla stock.';
--              'Cantidad a devolver de <ÍTEM> supera lo facturado pendiente de devolución: N.'
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_validar_nota_det() RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_cab       nota_credito_debito_cab%ROWTYPE;
    v_tipo_v    VARCHAR;
    v_item      RECORD;
    v_facturado INTEGER;
    v_devuelto  INTEGER;
BEGIN
    IF NEW.id_tratamiento IS NOT NULL THEN
        RAISE EXCEPTION 'Las notas no admiten renglones de tratamiento.';
    END IF;
    IF NEW.id_item IS NULL THEN
        RETURN NEW;
    END IF;
    SELECT * INTO v_cab FROM nota_credito_debito_cab WHERE id_nota = NEW.id_nota;
    IF v_cab.tipo_nota <> 'CREDITO' THEN
        RAISE EXCEPTION 'Solo una nota de crédito puede devolver mercadería.';
    END IF;
    SELECT v.tipo_venta INTO v_tipo_v FROM cuenta_cobrar cc JOIN venta_cab v ON v.id_venta = cc.id_venta WHERE cc.id_cuenta = v_cab.id_cuenta;
    IF v_tipo_v <> 'ITEMS' THEN
        RAISE EXCEPTION 'Solo se devuelve mercadería de ventas de ítems.';
    END IF;
    SELECT i.descripcion, ti.controla_stock INTO v_item FROM items i JOIN tipo_items ti ON ti.id_tipo_item = i.id_tipo_item WHERE i.id_item = NEW.id_item;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'El ítem no existe.';
    END IF;
    SELECT COALESCE(SUM(d.cantidad), 0) INTO v_facturado
      FROM venta_det d JOIN cuenta_cobrar cc ON cc.id_venta = d.id_venta WHERE cc.id_cuenta = v_cab.id_cuenta AND d.id_item = NEW.id_item;
    IF v_facturado = 0 THEN
        RAISE EXCEPTION 'El ítem % no pertenece a la factura.', v_item.descripcion;
    END IF;
    IF NOT v_item.controla_stock THEN
        RAISE EXCEPTION 'El ítem % no repone stock: su tipo no controla stock.', v_item.descripcion;
    END IF;
    SELECT COALESCE(SUM(d.cantidad), 0) INTO v_devuelto
      FROM nota_credito_debito_det d JOIN nota_credito_debito_cab c ON c.id_nota = d.id_nota
     WHERE c.id_cuenta = v_cab.id_cuenta AND c.tipo_nota = 'CREDITO' AND c.estado = 'EMITIDA' AND d.id_item = NEW.id_item;
    IF NEW.cantidad > v_facturado - v_devuelto THEN
        RAISE EXCEPTION 'Cantidad a devolver de % supera lo facturado pendiente de devolución: %.', v_item.descripcion, v_facturado - v_devuelto;
    END IF;
    RETURN NEW;
END;
$$;
COMMENT ON FUNCTION fn_validar_nota_det() IS 'Función del trigger trg_validar_nota_det: la devolución de mercadería solo de ítems de la factura que controlan stock, sin superar lo facturado menos lo ya devuelto.';

DROP TRIGGER IF EXISTS trg_validar_nota_det ON nota_credito_debito_det;
CREATE TRIGGER trg_validar_nota_det
    BEFORE INSERT ON nota_credito_debito_det
    FOR EACH ROW EXECUTE FUNCTION fn_validar_nota_det();
COMMENT ON TRIGGER trg_validar_nota_det ON nota_credito_debito_det IS 'Valida la devolución de mercadería (ítem de la factura, controla stock, cantidad pendiente de devolución).';

-- =====================================================================================================================
-- TRIGGER: trg_validar_nota  (CONSTRAINT TRIGGER, AFTER INSERT ON nota_credito_debito_cab, DEFERRABLE INITIALLY DEFERRED)
-- Propósito : red de seguridad que se evalúa AL CONFIRMAR (cuando ya están los renglones): la nota tiene al menos un renglón y los
--             totales por tasa de la cabecera son la suma de los subtotales de sus renglones.
-- Excepciones: 'La nota debe tener al menos un renglón.'; 'Los renglones de la nota no coinciden con sus totales.'
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_validar_nota() RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_n INTEGER; v_ex NUMERIC; v_5 NUMERIC; v_10 NUMERIC;
BEGIN
    SELECT count(*), COALESCE(SUM(subtotal) FILTER (WHERE iva = 0), 0), COALESCE(SUM(subtotal) FILTER (WHERE iva = 5), 0),
           COALESCE(SUM(subtotal) FILTER (WHERE iva = 10), 0)
      INTO v_n, v_ex, v_5, v_10 FROM nota_credito_debito_det WHERE id_nota = NEW.id_nota;
    IF v_n = 0 THEN
        RAISE EXCEPTION 'La nota debe tener al menos un renglón.';
    END IF;
    IF v_ex <> NEW.total_exenta OR v_5 <> NEW.total_gravada_5 OR v_10 <> NEW.total_gravada_10 THEN
        RAISE EXCEPTION 'Los renglones de la nota no coinciden con sus totales.';
    END IF;
    RETURN NULL;
END;
$$;
COMMENT ON FUNCTION fn_validar_nota() IS 'Función del trigger diferido trg_validar_nota: al confirmar, la nota tiene renglones y sus totales por tasa coinciden con ellos.';

DROP TRIGGER IF EXISTS trg_validar_nota ON nota_credito_debito_cab;
CREATE CONSTRAINT TRIGGER trg_validar_nota
    AFTER INSERT ON nota_credito_debito_cab
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_validar_nota();
COMMENT ON TRIGGER trg_validar_nota ON nota_credito_debito_cab IS 'Diferido (al confirmar): la nota tiene renglones y sus totales por tasa coinciden con ellos.';

-- =====================================================================================================================
-- TRIGGER: trg_bloquear_anular_venta_con_notas  (BEFORE UPDATE OF estado ON venta_cab)
-- Propósito : red de seguridad: una venta con notas de crédito o débito EMITIDAS no puede pasar a ANULADA (primero se anulan las notas).
-- Excepciones: 'No es posible anular, existen notas de crédito o débito emitidas. Anúlelas primero.'
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_bloquear_anular_venta_con_notas() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.estado = 'EMITIDA' AND NEW.estado = 'ANULADA'
       AND EXISTS (SELECT 1 FROM nota_credito_debito_cab n JOIN cuenta_cobrar cc ON cc.id_cuenta = n.id_cuenta
                    WHERE cc.id_venta = NEW.id_venta AND n.estado = 'EMITIDA') THEN
        RAISE EXCEPTION 'No es posible anular, existen notas de crédito o débito emitidas. Anúlelas primero.';
    END IF;
    RETURN NEW;
END;
$$;
COMMENT ON FUNCTION fn_bloquear_anular_venta_con_notas() IS 'Función del trigger trg_bloquear_anular_venta_con_notas: una venta con notas EMITIDAS no se puede anular.';

DROP TRIGGER IF EXISTS trg_bloquear_anular_venta_con_notas ON venta_cab;
CREATE TRIGGER trg_bloquear_anular_venta_con_notas
    BEFORE UPDATE OF estado ON venta_cab
    FOR EACH ROW EXECUTE FUNCTION fn_bloquear_anular_venta_con_notas();
COMMENT ON TRIGGER trg_bloquear_anular_venta_con_notas ON venta_cab IS 'Impide anular una venta que tiene notas de crédito o débito EMITIDAS.';

-- =====================================================================================================================
-- FUNCIONES DE CAJA (actualizadas): el reintegro en efectivo de las notas de crédito RESTA del efectivo del cierre.
--   fn_total_reintegros(p_id_apertura)         : reintegros en efectivo de las notas de crédito EMITIDAS de la apertura.
--   fn_total_recaudado(p_id_apertura)          : cobrado (todas las formas, cobros EMITIDOS) MENOS los reintegros = recaudado neto.
--   fn_total_efectivo_apertura(p_id_apertura)  : efectivo cobrado MENOS los reintegros = efectivo neto del cajón.
--   monto_cierre = monto_apertura + fn_total_efectivo_apertura. Sin excepciones propias (STABLE).
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_total_reintegros(p_id_apertura INT) RETURNS NUMERIC
LANGUAGE sql STABLE
AS $$
    SELECT COALESCE(SUM(monto_reintegro), 0)::NUMERIC(12,0)
      FROM nota_credito_debito_cab WHERE id_apertura = p_id_apertura AND tipo_nota = 'CREDITO' AND estado = 'EMITIDA';
$$;
COMMENT ON FUNCTION fn_total_reintegros(INT) IS 'Reintegros en efectivo (notas de crédito EMITIDAS) pagados al cliente desde la apertura de caja.';

CREATE OR REPLACE FUNCTION fn_total_recaudado(p_id_apertura INT) RETURNS NUMERIC
LANGUAGE sql STABLE
AS $$
    SELECT (COALESCE(SUM(total), 0) - fn_total_reintegros(p_id_apertura))::NUMERIC(12,0)
      FROM cobro_cab WHERE id_apertura = p_id_apertura AND estado = 'EMITIDO';
$$;
COMMENT ON FUNCTION fn_total_recaudado(INT) IS 'Recaudado neto de la apertura: cobros EMITIDOS (todas las formas) menos los reintegros en efectivo de las notas de crédito. Lo usa el Cierre de Caja.';

CREATE OR REPLACE FUNCTION fn_total_efectivo_apertura(p_id_apertura INT) RETURNS NUMERIC
LANGUAGE sql STABLE
AS $$
    SELECT (COALESCE(SUM(d.monto), 0) - fn_total_reintegros(p_id_apertura))::NUMERIC(12,0)
      FROM cobro_cab c
      JOIN cobro_det d ON d.id_cobro = c.id_cobro
      JOIN forma_cobro f ON f.id_forma_cobro = d.id_forma_cobro
     WHERE c.id_apertura = p_id_apertura AND c.estado = 'EMITIDO' AND f.tipo = 'EFECTIVO';
$$;
COMMENT ON FUNCTION fn_total_efectivo_apertura(INT) IS 'Efectivo neto de la apertura: cobrado en EFECTIVO (cobros EMITIDOS) menos los reintegros de notas de crédito. monto_cierre = monto_apertura + este total.';

-- VISTA v_resumen_caja (actualizada): además de lo cobrado por forma, una fila REINTEGRO con el total devuelto en efectivo (en negativo).
-- Columnas: id_apertura, id_forma_cobro (NULL en el reintegro), forma_cobro, tipo_forma ('REINTEGRO' en esa fila), cantidad_pagos, total_cobrado.
CREATE OR REPLACE VIEW v_resumen_caja AS
SELECT c.id_apertura,
       f.id_forma_cobro,
       f.descripcion AS forma_cobro,
       f.tipo        AS tipo_forma,
       count(*)      AS cantidad_pagos,
       SUM(d.monto)  AS total_cobrado
FROM cobro_cab c
JOIN cobro_det d   ON d.id_cobro = c.id_cobro
JOIN forma_cobro f ON f.id_forma_cobro = d.id_forma_cobro
WHERE c.estado = 'EMITIDO'
GROUP BY c.id_apertura, f.id_forma_cobro, f.descripcion, f.tipo
UNION ALL
SELECT n.id_apertura,
       NULL::INTEGER,
       'REINTEGRO EN EFECTIVO (NOTAS DE CRÉDITO)'::VARCHAR(60),
       'REINTEGRO'::VARCHAR(15),
       count(*),
       -SUM(n.monto_reintegro)
FROM nota_credito_debito_cab n
WHERE n.tipo_nota = 'CREDITO' AND n.estado = 'EMITIDA' AND n.monto_reintegro > 0
GROUP BY n.id_apertura;
COMMENT ON VIEW v_resumen_caja IS 'Por apertura de caja: total cobrado por forma de cobro (cobros EMITIDOS) y, en una fila aparte de tipo REINTEGRO, lo devuelto en efectivo por notas de crédito (en negativo). Alimenta el detalle del Cierre de Caja.';

-- VISTA v_estado_cuenta_cliente (completada con las notas): se agregan AL FINAL total_notas_credito, total_notas_debito y
-- cantidad_notas (notas EMITIDAS de la cuenta). El saldo ya refleja las notas (lo mueve trg_aplicar_nota).
CREATE OR REPLACE VIEW v_estado_cuenta_cliente AS
SELECT c.id_cliente,
       c.nombre || COALESCE(' ' || c.apellido, '') AS cliente,
       c.ci_ruc,
       v.id_venta,
       v.numero_factura,
       v.fecha,
       v.condicion,
       v.total,
       cc.saldo,
       cc.estado AS estado_cuenta,
       cc.fecha_vencimiento,
       SUM(CASE WHEN cc.estado = 'PENDIENTE' THEN cc.saldo ELSE 0 END)
           OVER (PARTITION BY c.id_cliente) AS saldo_total_cliente,
       COALESCE(cb.total_cobrado, 0)    AS total_cobrado,
       COALESCE(cb.cantidad_cobros, 0)  AS cantidad_cobros,
       cb.fecha_ultimo_cobro,
       COALESCE(nt.total_credito, 0)    AS total_notas_credito,
       COALESCE(nt.total_debito, 0)     AS total_notas_debito,
       COALESCE(nt.cantidad_notas, 0)   AS cantidad_notas
FROM cuenta_cobrar cc
JOIN venta_cab v ON v.id_venta = cc.id_venta
JOIN cliente   c ON c.id_cliente = cc.id_cliente
LEFT JOIN (SELECT id_cuenta, SUM(total) AS total_cobrado, count(*) AS cantidad_cobros, MAX(fecha) AS fecha_ultimo_cobro
             FROM cobro_cab WHERE estado = 'EMITIDO' GROUP BY id_cuenta) cb ON cb.id_cuenta = cc.id_cuenta
LEFT JOIN (SELECT id_cuenta, SUM(total) FILTER (WHERE tipo_nota = 'CREDITO') AS total_credito,
                  SUM(total) FILTER (WHERE tipo_nota = 'DEBITO') AS total_debito, count(*) AS cantidad_notas
             FROM nota_credito_debito_cab WHERE estado = 'EMITIDA' GROUP BY id_cuenta) nt ON nt.id_cuenta = cc.id_cuenta;
COMMENT ON VIEW v_estado_cuenta_cliente IS 'Estado de cuenta por cliente: una fila por factura (total, saldo, estado de la cuenta, vencimiento), el saldo total pendiente del cliente, lo cobrado (total, cantidad y fecha del último cobro) y las notas de crédito y débito EMITIDAS.';

-- VISTA v_libro_ventas (completada con las notas): las notas de crédito y débito EMITIDAS se listan junto a las facturas, con los importes
-- de las notas de crédito en NEGATIVO (restan) y 0 si la nota está ANULADA. Se agrega AL FINAL la columna comprobante
-- ('FACTURA', 'NOTA DE CRÉDITO' o 'NOTA DE DÉBITO'). En las filas de nota, numero_factura contiene el número de la nota.
CREATE OR REPLACE VIEW v_libro_ventas AS
SELECT v.fecha::date AS fecha,
       t.numero_timbrado,
       v.numero_factura,
       c.ci_ruc,
       TRIM(BOTH FROM (c.nombre::text || ' '::text) || COALESCE(c.apellido, ''::character varying)::text) AS cliente,
       v.condicion,
       CASE WHEN v.estado::text = 'ANULADA' THEN 0::numeric ELSE v.total_exenta END AS exenta,
       CASE WHEN v.estado::text = 'ANULADA' THEN 0::numeric ELSE v.total_gravada_5 END AS gravada_5,
       CASE WHEN v.estado::text = 'ANULADA' THEN 0::numeric ELSE v.iva_5 END AS iva_5,
       CASE WHEN v.estado::text = 'ANULADA' THEN 0::numeric ELSE v.total_gravada_10 END AS gravada_10,
       CASE WHEN v.estado::text = 'ANULADA' THEN 0::numeric ELSE v.iva_10 END AS iva_10,
       CASE WHEN v.estado::text = 'ANULADA' THEN 0::numeric ELSE v.total END AS total,
       v.estado,
       'FACTURA'::text AS comprobante
FROM venta_cab v
JOIN cliente c ON c.id_cliente = v.id_cliente
JOIN timbrado t ON t.id_timbrado = v.id_timbrado
UNION ALL
SELECT n.fecha::date,
       t.numero_timbrado,
       n.numero_nota::varchar(15),
       c.ci_ruc,
       TRIM(BOTH FROM (c.nombre::text || ' '::text) || COALESCE(c.apellido, ''::character varying)::text),
       v.condicion,
       CASE WHEN n.estado = 'ANULADA' THEN 0::numeric WHEN n.tipo_nota = 'CREDITO' THEN -n.total_exenta ELSE n.total_exenta END,
       CASE WHEN n.estado = 'ANULADA' THEN 0::numeric WHEN n.tipo_nota = 'CREDITO' THEN -n.total_gravada_5 ELSE n.total_gravada_5 END,
       CASE WHEN n.estado = 'ANULADA' THEN 0::numeric WHEN n.tipo_nota = 'CREDITO' THEN -n.iva_5 ELSE n.iva_5 END,
       CASE WHEN n.estado = 'ANULADA' THEN 0::numeric WHEN n.tipo_nota = 'CREDITO' THEN -n.total_gravada_10 ELSE n.total_gravada_10 END,
       CASE WHEN n.estado = 'ANULADA' THEN 0::numeric WHEN n.tipo_nota = 'CREDITO' THEN -n.iva_10 ELSE n.iva_10 END,
       CASE WHEN n.estado = 'ANULADA' THEN 0::numeric WHEN n.tipo_nota = 'CREDITO' THEN -n.total ELSE n.total END,
       n.estado::varchar(8),
       CASE WHEN n.tipo_nota = 'CREDITO' THEN 'NOTA DE CRÉDITO' ELSE 'NOTA DE DÉBITO' END
FROM nota_credito_debito_cab n
JOIN cuenta_cobrar cc ON cc.id_cuenta = n.id_cuenta
JOIN venta_cab v ON v.id_venta = cc.id_venta
JOIN cliente c ON c.id_cliente = v.id_cliente
JOIN timbrado t ON t.id_timbrado = n.id_timbrado;
COMMENT ON VIEW v_libro_ventas IS 'Libro de ventas: facturas y notas de crédito (en negativo) y débito EMITIDAS, con la columna comprobante. Los comprobantes anulados figuran con importes en 0.';
