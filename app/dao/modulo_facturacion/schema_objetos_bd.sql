-- Objetos de base de datos de Ventas y Cuentas a Cobrar: procedimiento almacenado, triggers y vista. Idempotente
-- (CREATE OR REPLACE / DROP TRIGGER IF EXISTS). Requiere schema_empresa_timbrado.sql y schema_ventas.sql.
-- Cada objeto documenta propósito, parámetros y excepciones, y lleva COMMENT ON.

-- =====================================================================================================================
-- PROCEDIMIENTO ALMACENADO: sp_siguiente_numero_factura
-- Propósito : entregar el próximo número de factura del timbrado activo, de forma atómica y sin huecos ni repetidos.
-- Parámetros: OUT p_id_timbrado    INT         -> id del timbrado usado (para guardarlo en venta_cab)
--             OUT p_numero_factura VARCHAR(15) -> 'EEE-PPP-NNNNNNN' (establecimiento-punto-número de 7 dígitos)
-- Excepciones (RAISE EXCEPTION; la API las muestra tal cual):
--             'No hay timbrado activo'
--             'El timbrado aún no está vigente'   (fecha de hoy anterior al inicio de vigencia)
--             'El timbrado está vencido'          (fecha de hoy posterior al fin de vigencia)
--             'Se agotó el rango de numeración del timbrado'
-- Concurrencia: bloquea la fila del timbrado activo con FOR UPDATE; dos ventas simultáneas se serializan y reciben
--             números distintos y consecutivos. Debe llamarse DENTRO de la transacción de la venta: si esta se
--             deshace, el incremento también (no quedan números quemados).
-- Uso       : CALL sp_siguiente_numero_factura(NULL, NULL);
-- =====================================================================================================================
CREATE OR REPLACE PROCEDURE sp_siguiente_numero_factura(OUT p_id_timbrado INT, OUT p_numero_factura VARCHAR)
LANGUAGE plpgsql
AS $$
DECLARE
    v_timbrado  timbrado%ROWTYPE;
    v_siguiente INTEGER;
BEGIN
    SELECT * INTO v_timbrado FROM timbrado WHERE activo = true FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No hay timbrado activo';
    END IF;
    IF current_date < v_timbrado.fecha_inicio THEN
        RAISE EXCEPTION 'El timbrado aún no está vigente';
    END IF;
    IF current_date > v_timbrado.fecha_fin THEN
        RAISE EXCEPTION 'El timbrado está vencido';
    END IF;

    v_siguiente := GREATEST(v_timbrado.numero_actual + 1, v_timbrado.numero_desde);
    IF v_siguiente > v_timbrado.numero_hasta THEN
        RAISE EXCEPTION 'Se agotó el rango de numeración del timbrado';
    END IF;

    UPDATE timbrado SET numero_actual = v_siguiente WHERE id_timbrado = v_timbrado.id_timbrado;

    p_id_timbrado    := v_timbrado.id_timbrado;
    p_numero_factura := v_timbrado.establecimiento || '-' || v_timbrado.punto_expedicion || '-' || lpad(v_siguiente::text, 7, '0');
EXCEPTION
    WHEN raise_exception THEN
        RAISE;   -- los mensajes de negocio de arriba se propagan sin modificar
    WHEN OTHERS THEN
        RAISE EXCEPTION 'No se pudo generar el número de factura: %', SQLERRM USING ERRCODE = SQLSTATE;
END;
$$;

COMMENT ON PROCEDURE sp_siguiente_numero_factura(INT, VARCHAR) IS
    'Entrega el próximo número de factura (EEE-PPP-NNNNNNN) del timbrado activo. Bloquea el timbrado (FOR UPDATE), valida vigencia y rango, incrementa numero_actual. Errores: sin timbrado activo / aún no vigente / vencido / rango agotado.';

-- =====================================================================================================================
-- TRIGGER: trg_generar_cuenta_cobrar  (AFTER INSERT ON venta_cab)
-- Propósito : crear la cuenta a cobrar de cada venta, con saldo = total.
--             Vencimiento: CONTADO = fecha de la venta; CREDITO = fecha de la venta + 30 días.
-- Parámetros: ninguno propio (usa la fila NEW de venta_cab).
-- Excepciones: si la venta ya tuviera cuenta (unique_violation) o falla el alta, se aborta la venta con un mensaje claro.
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_generar_cuenta_cobrar() RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_vencimiento DATE;
BEGIN
    v_vencimiento := CASE WHEN NEW.condicion = 'CREDITO' THEN NEW.fecha::date + 30 ELSE NEW.fecha::date END;
    INSERT INTO cuenta_cobrar (id_venta, id_cliente, monto_total, saldo, fecha_vencimiento, estado)
    VALUES (NEW.id_venta, NEW.id_cliente, NEW.total, NEW.total, v_vencimiento, 'PENDIENTE');
    RETURN NEW;
EXCEPTION
    WHEN unique_violation THEN
        RAISE EXCEPTION 'La venta % ya tiene una cuenta a cobrar.', NEW.id_venta;
    WHEN OTHERS THEN
        RAISE EXCEPTION 'No se pudo generar la cuenta a cobrar de la venta %: %', NEW.id_venta, SQLERRM;
END;
$$;

DROP TRIGGER IF EXISTS trg_generar_cuenta_cobrar ON venta_cab;
CREATE TRIGGER trg_generar_cuenta_cobrar
    AFTER INSERT ON venta_cab
    FOR EACH ROW EXECUTE FUNCTION fn_generar_cuenta_cobrar();

COMMENT ON FUNCTION fn_generar_cuenta_cobrar() IS 'Función del trigger trg_generar_cuenta_cobrar: crea la cuenta a cobrar (saldo = total; vence el mismo día si es contado, a los 30 días si es crédito).';
COMMENT ON TRIGGER trg_generar_cuenta_cobrar ON venta_cab IS 'Después de insertar una venta crea su cuenta a cobrar con saldo = total.';

-- =====================================================================================================================
-- TRIGGER: trg_anular_cuenta_cobrar  (AFTER UPDATE OF estado ON venta_cab, cuando pasa a ANULADA)
-- Propósito : al anular una venta, pasar su cuenta a cobrar a ANULADA.
-- Parámetros: ninguno propio (usa NEW de venta_cab).
-- Excepciones: si falla la actualización de la cuenta se aborta la anulación de la venta.
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_anular_cuenta_cobrar() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE cuenta_cobrar SET estado = 'ANULADA' WHERE id_venta = NEW.id_venta;
    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'No se pudo anular la cuenta a cobrar de la venta %: %', NEW.id_venta, SQLERRM;
END;
$$;

DROP TRIGGER IF EXISTS trg_anular_cuenta_cobrar ON venta_cab;
CREATE TRIGGER trg_anular_cuenta_cobrar
    AFTER UPDATE OF estado ON venta_cab
    FOR EACH ROW
    WHEN (OLD.estado IS DISTINCT FROM NEW.estado AND NEW.estado = 'ANULADA')
    EXECUTE FUNCTION fn_anular_cuenta_cobrar();

COMMENT ON FUNCTION fn_anular_cuenta_cobrar() IS 'Función del trigger trg_anular_cuenta_cobrar: pasa la cuenta a cobrar de la venta a ANULADA.';
COMMENT ON TRIGGER trg_anular_cuenta_cobrar ON venta_cab IS 'Cuando una venta pasa a ANULADA, su cuenta a cobrar pasa a ANULADA.';

-- =====================================================================================================================
-- TRIGGER: trg_auditoria_inmutable  (BEFORE UPDATE OR DELETE en auditoria_cambios y auditoria_acceso)
-- Propósito : la auditoría es inalterable: solo se inserta. Rechaza cualquier UPDATE o DELETE.
-- Parámetros: ninguno.
-- Excepciones: 'Los registros de auditoría no se pueden modificar ni eliminar.'
-- Nota      : los tests de limpieza lo saltan solo en su conexión con SET session_replication_role = replica (requiere
--             superusuario; ver tests/facturacion/_limpieza.py). Pendiente de cierre: usuario de base propio de la
--             aplicación, sin superusuario, para que la app no pueda saltarse este trigger.
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_auditoria_inmutable() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Los registros de auditoría no se pueden modificar ni eliminar.';
    RETURN NULL;   -- no se alcanza; mantiene la firma de una función de trigger BEFORE
END;
$$;

DROP TRIGGER IF EXISTS trg_auditoria_inmutable ON auditoria_cambios;
CREATE TRIGGER trg_auditoria_inmutable
    BEFORE UPDATE OR DELETE ON auditoria_cambios
    FOR EACH ROW EXECUTE FUNCTION fn_auditoria_inmutable();

DROP TRIGGER IF EXISTS trg_auditoria_inmutable ON auditoria_acceso;
CREATE TRIGGER trg_auditoria_inmutable
    BEFORE UPDATE OR DELETE ON auditoria_acceso
    FOR EACH ROW EXECUTE FUNCTION fn_auditoria_inmutable();

COMMENT ON FUNCTION fn_auditoria_inmutable() IS 'Función del trigger trg_auditoria_inmutable: rechaza todo UPDATE o DELETE sobre las tablas de auditoría.';
COMMENT ON TRIGGER trg_auditoria_inmutable ON auditoria_cambios IS 'Impide modificar o eliminar registros de auditoría de cambios.';
COMMENT ON TRIGGER trg_auditoria_inmutable ON auditoria_acceso IS 'Impide modificar o eliminar registros de auditoría de accesos.';

-- =====================================================================================================================
-- VISTA: v_estado_cuenta_cliente
-- Propósito : estado de cuenta por cliente: cada factura con número, fecha, condición, total, saldo y estado de su
--             cuenta a cobrar, más el saldo total pendiente del cliente (sin contar las cuentas anuladas).
-- Columnas  : id_cliente, cliente, ci_ruc, id_venta, numero_factura, fecha, condicion, total, saldo, estado_cuenta,
--             fecha_vencimiento, saldo_total_cliente (se repite en cada fila del cliente).
-- Se completará con los cobros en el próximo movimiento (el saldo baja a medida que se cobra).
-- =====================================================================================================================
-- La vista se crea SOLO si no existe: schema_cobranzas.sql la completa con los cobros (CREATE OR REPLACE agregando columnas
-- al final), y volver a correr este script no debe volver a la versión corta (CREATE OR REPLACE no puede quitar columnas).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_views WHERE schemaname = 'public' AND viewname = 'v_estado_cuenta_cliente') THEN
        EXECUTE $vista$
CREATE VIEW v_estado_cuenta_cliente AS
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
           OVER (PARTITION BY c.id_cliente) AS saldo_total_cliente
FROM cuenta_cobrar cc
JOIN venta_cab v ON v.id_venta = cc.id_venta
JOIN cliente   c ON c.id_cliente = cc.id_cliente
        $vista$;
    END IF;
END $$;

COMMENT ON VIEW v_estado_cuenta_cliente IS 'Estado de cuenta por cliente: una fila por factura (número, fecha, condición, total, saldo, estado de la cuenta) y el saldo total pendiente del cliente.';
