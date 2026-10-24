-- Registrar Cobranzas por Forma de Cobro — OBJETOS de base de datos (funciones, triggers y vistas). NO crea tablas: las
-- tablas cobro_cab, cobro_det, cobro_tarjeta y cobro_cheque las crea 01_migracion_der.sql. Idempotente.
-- Orden: 01_migracion_der.sql -> schema_cobranzas_columnas.sql -> este script.
-- Cada objeto documenta propósito, parámetros y excepciones, y lleva COMMENT ON.

-- =====================================================================================================================
-- FUNCIÓN: fn_formato_gs(n)
-- Propósito : formatea un importe en guaraníes con punto de miles (150000 -> '150.000') para los mensajes de error.
-- Parámetros: n NUMERIC. Devuelve TEXT. Sin excepciones (IMMUTABLE).
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_formato_gs(n NUMERIC) RETURNS TEXT
LANGUAGE sql IMMUTABLE
AS $$
    SELECT reverse(regexp_replace(reverse(trunc(n)::text), '(\d{3})(?=\d)', '\1.', 'g'));
$$;
COMMENT ON FUNCTION fn_formato_gs(NUMERIC) IS 'Importe en guaraníes con punto de miles (150000 -> 150.000), para mensajes de error.';

-- =====================================================================================================================
-- FUNCIÓN: fn_siguiente_numero_recibo()
-- Propósito : entregar el próximo número de recibo 'REC-0000001', SIN huecos ni repetidos. No usa una tabla de numeración:
--             toma el mayor número ya usado en cobro_cab (los anulados conservan el suyo, no se reutiliza) y le suma 1,
--             bajo un bloqueo asesor de la transacción que serializa a los cajeros que cobran a la vez.
-- Parámetros: ninguno. Devuelve VARCHAR (cabe en cobro_cab.numero_recibo VARCHAR(15)).
-- Excepciones: 'No se pudo generar el número de recibo: <causa>'.
-- Uso       : dentro de la transacción del cobro: SELECT fn_siguiente_numero_recibo();
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_siguiente_numero_recibo() RETURNS VARCHAR
LANGUAGE plpgsql
AS $$
DECLARE
    v_ultimo INTEGER;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('cobro_cab.numero_recibo'));
    SELECT COALESCE(MAX(substring(numero_recibo FROM '^REC-([0-9]+)$')::INTEGER), 0) INTO v_ultimo FROM cobro_cab;
    RETURN 'REC-' || lpad((v_ultimo + 1)::TEXT, 7, '0');
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'No se pudo generar el número de recibo: %', SQLERRM;
END;
$$;
COMMENT ON FUNCTION fn_siguiente_numero_recibo() IS 'Próximo número de recibo (REC-0000001) sin huecos: mayor número usado en cobro_cab + 1, con bloqueo asesor de transacción.';

-- =====================================================================================================================
-- TRIGGER: trg_aplicar_cobro  (AFTER INSERT OR UPDATE OF estado ON cobro_cab)
-- Propósito : aplicar el cobro a la cuenta a cobrar.
--             * INSERT de un cobro EMITIDO: descuenta el total del saldo; si el saldo llega a 0 la cuenta pasa a PAGADA.
--             * UPDATE EMITIDO -> ANULADO: repone el total al saldo y la cuenta vuelve a PENDIENTE.
-- Parámetros: ninguno propio (usa NEW/OLD de cobro_cab). Bloquea la cuenta con FOR UPDATE.
-- Excepciones: 'La cuenta a cobrar no está pendiente (estado: X).'; 'El monto supera el saldo pendiente de Gs. N.';
--             'Un cobro anulado no se puede reactivar.'; 'No se puede anular el cobro: la cuenta a cobrar está anulada.'
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_aplicar_cobro() RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_cuenta cuenta_cobrar%ROWTYPE;
BEGIN
    SELECT * INTO v_cuenta FROM cuenta_cobrar WHERE id_cuenta = NEW.id_cuenta FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'La cuenta a cobrar % no existe.', NEW.id_cuenta;
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NEW.estado <> 'EMITIDO' THEN
            RETURN NEW;   -- un cobro que nace anulado no mueve el saldo
        END IF;
        IF v_cuenta.estado <> 'PENDIENTE' THEN
            RAISE EXCEPTION 'La cuenta a cobrar no está pendiente (estado: %).', v_cuenta.estado;
        END IF;
        IF NEW.total > v_cuenta.saldo THEN
            RAISE EXCEPTION 'El monto supera el saldo pendiente de Gs. %.', fn_formato_gs(v_cuenta.saldo);
        END IF;
        UPDATE cuenta_cobrar
           SET saldo = saldo - NEW.total,
               estado = CASE WHEN saldo - NEW.total = 0 THEN 'PAGADA' ELSE 'PENDIENTE' END
         WHERE id_cuenta = NEW.id_cuenta;
    ELSIF OLD.estado = 'EMITIDO' AND NEW.estado = 'ANULADO' THEN
        IF v_cuenta.estado = 'ANULADA' THEN
            RAISE EXCEPTION 'No se puede anular el cobro: la cuenta a cobrar está anulada.';
        END IF;
        UPDATE cuenta_cobrar SET saldo = saldo + OLD.total, estado = 'PENDIENTE' WHERE id_cuenta = NEW.id_cuenta;
    ELSIF OLD.estado = 'ANULADO' AND NEW.estado = 'EMITIDO' THEN
        RAISE EXCEPTION 'Un cobro anulado no se puede reactivar.';
    END IF;
    RETURN NEW;
END;
$$;
COMMENT ON FUNCTION fn_aplicar_cobro() IS 'Función del trigger trg_aplicar_cobro: descuenta o repone el saldo de la cuenta a cobrar y la pasa a PAGADA o PENDIENTE.';

DROP TRIGGER IF EXISTS trg_aplicar_cobro ON cobro_cab;
CREATE TRIGGER trg_aplicar_cobro
    AFTER INSERT OR UPDATE OF estado ON cobro_cab
    FOR EACH ROW EXECUTE FUNCTION fn_aplicar_cobro();
COMMENT ON TRIGGER trg_aplicar_cobro ON cobro_cab IS 'Al emitir un cobro descuenta el saldo (y marca PAGADA al llegar a 0); al anularlo repone el saldo y la cuenta vuelve a PENDIENTE.';

-- =====================================================================================================================
-- TRIGGER: trg_validar_cobro  (CONSTRAINT TRIGGER, AFTER INSERT ON cobro_cab, DEFERRABLE INITIALLY DEFERRED)
-- Propósito : red de seguridad que se evalúa AL CONFIRMAR la transacción (cuando ya están insertados cobro_det, cobro_tarjeta
--             y cobro_cheque): (1) la suma de las formas de cobro es igual al total del cobro; (2) cada forma tiene su tipo
--             y sus datos: TARJETA exactamente una fila en cobro_tarjeta, CHEQUE exactamente una en cobro_cheque,
--             TRANSFERENCIA con numero_referencia, y ninguna otra forma lleva datos de más.
-- Parámetros: ninguno propio (usa NEW de cobro_cab).
-- Excepciones: 'La suma de las formas de cobro (Gs. A) no coincide con el total del cobro (Gs. B).';
--             'Faltan o sobran datos en la forma de cobro: <formas>.'
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_validar_cobro() RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_suma NUMERIC;
    v_mal  TEXT;
BEGIN
    SELECT COALESCE(SUM(monto), 0) INTO v_suma FROM cobro_det WHERE id_cobro = NEW.id_cobro;
    IF v_suma <> NEW.total THEN
        RAISE EXCEPTION 'La suma de las formas de cobro (Gs. %) no coincide con el total del cobro (Gs. %).',
                        fn_formato_gs(v_suma), fn_formato_gs(NEW.total);
    END IF;

    SELECT string_agg(COALESCE(f.descripcion, '?') || ' (' || COALESCE(f.tipo, 'sin tipo') || ')', ', ')
      INTO v_mal
      FROM cobro_det d
      JOIN forma_cobro f ON f.id_forma_cobro = d.id_forma_cobro
     WHERE d.id_cobro = NEW.id_cobro
       AND (   f.tipo IS NULL
            OR (f.tipo = 'TRANSFERENCIA' AND COALESCE(btrim(d.numero_referencia), '') = '')
            OR (f.tipo <> 'TRANSFERENCIA' AND d.numero_referencia IS NOT NULL)
            OR ((f.tipo = 'TARJETA') <> EXISTS (SELECT 1 FROM cobro_tarjeta t WHERE t.id_cobro_det = d.id_cobro_det))
            OR ((f.tipo = 'CHEQUE') <> EXISTS (SELECT 1 FROM cobro_cheque c WHERE c.id_cobro_det = d.id_cobro_det)));
    IF v_mal IS NOT NULL THEN
        RAISE EXCEPTION 'Faltan o sobran datos en la forma de cobro: %.', v_mal;
    END IF;
    RETURN NULL;
END;
$$;
COMMENT ON FUNCTION fn_validar_cobro() IS 'Función del trigger diferido trg_validar_cobro: al confirmar, la suma de las formas debe ser el total y cada forma debe tener sus datos (tarjeta, cheque, referencia).';

DROP TRIGGER IF EXISTS trg_validar_cobro ON cobro_cab;
CREATE CONSTRAINT TRIGGER trg_validar_cobro
    AFTER INSERT ON cobro_cab
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_validar_cobro();
COMMENT ON TRIGGER trg_validar_cobro ON cobro_cab IS 'Diferido (al confirmar): suma de formas = total y cada forma con sus datos (tarjeta, cheque, referencia).';

-- =====================================================================================================================
-- FUNCIÓN: fn_total_recaudado(p_id_apertura)
-- Propósito : TODO lo cobrado en una apertura de caja (todas las formas de cobro): suma los cobros EMITIDOS. Lo usa el Cierre
--             de Caja para guardar apertura_cierre_caja.total_recaudado.
-- Parámetros: p_id_apertura INT. Devuelve NUMERIC(12,0); 0 si no hay cobros. Sin excepciones propias (STABLE).
-- FUNCIÓN: fn_total_efectivo_apertura(p_id_apertura)
-- Propósito : solo lo cobrado en EFECTIVO (formas de tipo EFECTIVO) de cobros EMITIDOS de la apertura. El monto de cierre es
--             monto_apertura + este total (tarjetas, cheques y transferencias no son plata en el cajón).
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_total_recaudado(p_id_apertura INT) RETURNS NUMERIC
LANGUAGE sql STABLE
AS $$
    SELECT COALESCE(SUM(total), 0)::NUMERIC(12,0) FROM cobro_cab WHERE id_apertura = p_id_apertura AND estado = 'EMITIDO';
$$;
COMMENT ON FUNCTION fn_total_recaudado(INT) IS 'Total cobrado (todas las formas) en la apertura: suma de los cobros EMITIDOS. Lo usa el Cierre de Caja.';

CREATE OR REPLACE FUNCTION fn_total_efectivo_apertura(p_id_apertura INT) RETURNS NUMERIC
LANGUAGE sql STABLE
AS $$
    SELECT COALESCE(SUM(d.monto), 0)::NUMERIC(12,0)
      FROM cobro_cab c
      JOIN cobro_det d ON d.id_cobro = c.id_cobro
      JOIN forma_cobro f ON f.id_forma_cobro = d.id_forma_cobro
     WHERE c.id_apertura = p_id_apertura AND c.estado = 'EMITIDO' AND f.tipo = 'EFECTIVO';
$$;
COMMENT ON FUNCTION fn_total_efectivo_apertura(INT) IS 'Total cobrado en EFECTIVO en la apertura (cobros EMITIDOS). monto_cierre = monto_apertura + este total.';

-- =====================================================================================================================
-- VISTA: v_resumen_caja
-- Propósito : por apertura de caja, lo cobrado por cada forma de cobro (solo cobros EMITIDOS). Se muestra en el detalle del
--             Cierre de Caja.
-- Columnas  : id_apertura, id_forma_cobro, forma_cobro, tipo_forma, cantidad_pagos, total_cobrado.
-- =====================================================================================================================
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
GROUP BY c.id_apertura, f.id_forma_cobro, f.descripcion, f.tipo;
COMMENT ON VIEW v_resumen_caja IS 'Por apertura de caja: total cobrado por forma de cobro (cobros EMITIDOS). Alimenta el detalle del Cierre de Caja.';

-- =====================================================================================================================
-- VISTA: v_estado_cuenta_cliente (COMPLETADA con los cobros)
-- Cambio    : se agregan AL FINAL total_cobrado, cantidad_cobros y fecha_ultimo_cobro (cobros EMITIDOS de la cuenta). Las
--             columnas anteriores no cambian de nombre ni de lugar. El saldo ya refleja los cobros (lo mueve trg_aplicar_cobro).
-- =====================================================================================================================
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
       cb.fecha_ultimo_cobro
FROM cuenta_cobrar cc
JOIN venta_cab v ON v.id_venta = cc.id_venta
JOIN cliente   c ON c.id_cliente = cc.id_cliente
LEFT JOIN (SELECT id_cuenta, SUM(total) AS total_cobrado, count(*) AS cantidad_cobros, MAX(fecha) AS fecha_ultimo_cobro
             FROM cobro_cab WHERE estado = 'EMITIDO' GROUP BY id_cuenta) cb ON cb.id_cuenta = cc.id_cuenta;
COMMENT ON VIEW v_estado_cuenta_cliente IS 'Estado de cuenta por cliente: una fila por factura (total, saldo, estado de la cuenta, vencimiento), el saldo total pendiente del cliente y lo cobrado (total, cantidad y fecha del último cobro).';
