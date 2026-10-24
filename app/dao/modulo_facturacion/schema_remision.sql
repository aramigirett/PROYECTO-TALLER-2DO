-- Registrar Nota de Remisión — OBJETOS de base de datos (funciones, triggers y vista). NO crea tablas: nota_remision_cab y
-- nota_remision_det las crea el DER (01_migracion_der.sql). Idempotente (CREATE OR REPLACE / DROP TRIGGER IF EXISTS).
-- Orden: 01_migracion_der.sql -> schema_ventas.sql -> este script -> schema_permisos_remision.sql -> schema_permisos_cajero.sql.
-- Aplicar con PGCLIENTENCODING=UTF8 (tiene tildes). Cada objeto documenta propósito, parámetros y excepciones, y lleva COMMENT ON.
--
-- Regla de negocio: la remisión documenta la ENTREGA de mercadería de una Venta de Ítems EMITIDA. NO mueve stock (ya se descontó
-- en el Pedido). Solo se remiten ítems cuyo tipo controla stock, desde el depósito donde está guardado el ítem (items.id_deposito),
-- y la suma remitida (remisiones EMITIDAS) por ítem no puede superar lo facturado. Una remisión ANULADA libera las cantidades.

-- =====================================================================================================================
-- FUNCIÓN: fn_siguiente_numero_remision()
-- Propósito : entregar el próximo número de remisión 'REM-0000001', SIN huecos ni repetidos. Toma el mayor número ya usado en
--             nota_remision_cab (las anuladas conservan el suyo, no se reutiliza) y le suma 1, bajo un bloqueo asesor de la
--             transacción que serializa a los usuarios que emiten a la vez.
-- Parámetros: ninguno. Devuelve VARCHAR (cabe en nota_remision_cab.numero_remision VARCHAR(15)).
-- Excepciones: 'No se pudo generar el número de remisión: <causa>'.
-- Uso       : dentro de la transacción de la remisión: SELECT fn_siguiente_numero_remision();
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_siguiente_numero_remision() RETURNS VARCHAR
LANGUAGE plpgsql
AS $$
DECLARE
    v_ultimo INTEGER;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('nota_remision_cab.numero_remision'));
    SELECT COALESCE(MAX(substring(numero_remision FROM '^REM-([0-9]+)$')::INTEGER), 0) INTO v_ultimo FROM nota_remision_cab;
    RETURN 'REM-' || lpad((v_ultimo + 1)::TEXT, 7, '0');
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'No se pudo generar el número de remisión: %', SQLERRM;
END;
$$;
COMMENT ON FUNCTION fn_siguiente_numero_remision() IS 'Próximo número de remisión (REM-0000001) sin huecos: mayor número usado en nota_remision_cab + 1, con bloqueo asesor de transacción.';

-- =====================================================================================================================
-- TRIGGER: trg_validar_remision_cab  (BEFORE INSERT ON nota_remision_cab)
-- Propósito : la remisión solo puede emitirse sobre una Venta de Ítems EMITIDA. Bloquea la venta (FOR UPDATE), el mismo bloqueo
--             que toma anular la venta, así que una venta no puede anularse mientras se emite su remisión.
-- Parámetros: ninguno propio (usa NEW de nota_remision_cab).
-- Excepciones: 'La venta no existe.'; 'No se puede emitir una remisión de una venta anulada.';
--              'Solo se pueden remitir ventas de ítems.'; 'La fecha de traslado no puede ser anterior a la fecha de emisión.'
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_validar_remision_cab() RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_venta venta_cab%ROWTYPE;
BEGIN
    SELECT * INTO v_venta FROM venta_cab WHERE id_venta = NEW.id_venta FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'La venta no existe.';
    END IF;
    IF v_venta.estado <> 'EMITIDA' THEN
        RAISE EXCEPTION 'No se puede emitir una remisión de una venta anulada.';
    END IF;
    IF v_venta.tipo_venta <> 'ITEMS' THEN
        RAISE EXCEPTION 'Solo se pueden remitir ventas de ítems.';
    END IF;
    IF NEW.fecha_traslado < NEW.fecha_emision::date THEN
        RAISE EXCEPTION 'La fecha de traslado no puede ser anterior a la fecha de emisión.';
    END IF;
    RETURN NEW;
END;
$$;
COMMENT ON FUNCTION fn_validar_remision_cab() IS 'Función del trigger trg_validar_remision_cab: la remisión solo se emite sobre una venta de ítems EMITIDA (la bloquea) y la fecha de traslado no puede ser anterior a la de emisión.';

DROP TRIGGER IF EXISTS trg_validar_remision_cab ON nota_remision_cab;
CREATE TRIGGER trg_validar_remision_cab
    BEFORE INSERT ON nota_remision_cab
    FOR EACH ROW EXECUTE FUNCTION fn_validar_remision_cab();
COMMENT ON TRIGGER trg_validar_remision_cab ON nota_remision_cab IS 'Antes de insertar la remisión: la venta debe ser de ítems y estar EMITIDA (la bloquea FOR UPDATE).';

-- =====================================================================================================================
-- TRIGGER: trg_remision_estado  (BEFORE UPDATE OF estado ON nota_remision_cab)
-- Propósito : una remisión ANULADA no se puede reactivar (reactivarla podría superar lo pendiente de entrega, porque las
--             cantidades que liberó pudieron remitirse en otra remisión).
-- Excepciones: 'Una remisión anulada no se puede reactivar.'
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_remision_estado() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.estado = 'ANULADA' AND NEW.estado <> 'ANULADA' THEN
        RAISE EXCEPTION 'Una remisión anulada no se puede reactivar.';
    END IF;
    RETURN NEW;
END;
$$;
COMMENT ON FUNCTION fn_remision_estado() IS 'Función del trigger trg_remision_estado: impide reactivar una remisión anulada.';

DROP TRIGGER IF EXISTS trg_remision_estado ON nota_remision_cab;
CREATE TRIGGER trg_remision_estado
    BEFORE UPDATE OF estado ON nota_remision_cab
    FOR EACH ROW EXECUTE FUNCTION fn_remision_estado();
COMMENT ON TRIGGER trg_remision_estado ON nota_remision_cab IS 'Impide reactivar una remisión ANULADA.';

-- =====================================================================================================================
-- TRIGGER: trg_validar_remision_det  (BEFORE INSERT OR UPDATE OF id_item, cantidad ON nota_remision_det)
-- Propósito : al insertar el detalle, verificar que
--               * la remisión esté EMITIDA;
--               * el ítem exista, esté en la venta y su tipo CONTROLE stock (los servicios no se entregan);
--               * el ítem esté guardado en el depósito de la remisión (items.id_deposito = nota_remision_cab.id_deposito);
--               * la cantidad no supere lo pendiente de entrega = facturado en la venta - remitido en remisiones EMITIDAS
--                 (sin contar esta misma línea si se modifica).
--             Bloquea la venta (FOR UPDATE): dos remisiones simultáneas de la misma venta se serializan y la segunda ve lo
--             remitido por la primera.
-- Parámetros: ninguno propio (usa NEW de nota_remision_det y su cabecera).
-- Excepciones: 'La remisión no existe.'; 'No se pueden agregar ítems a una remisión anulada.'; 'El ítem no existe.';
--              'El ítem <ÍTEM> no pertenece a la venta.'; 'El ítem <ÍTEM> no se entrega: su tipo no controla stock.';
--              'El ítem <ÍTEM> no está en el depósito seleccionado.';
--              'Cantidad a remitir de <ÍTEM> supera lo pendiente de entrega: N.'
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_validar_remision_det() RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_cab        nota_remision_cab%ROWTYPE;
    v_item       RECORD;
    v_facturado  INTEGER;
    v_remitido   INTEGER;
    v_pendiente  INTEGER;
BEGIN
    SELECT * INTO v_cab FROM nota_remision_cab WHERE id_remision = NEW.id_remision;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'La remisión no existe.';
    END IF;
    IF v_cab.estado <> 'EMITIDA' THEN
        RAISE EXCEPTION 'No se pueden agregar ítems a una remisión anulada.';
    END IF;

    PERFORM 1 FROM venta_cab WHERE id_venta = v_cab.id_venta FOR UPDATE;

    SELECT i.descripcion, i.id_deposito, ti.controla_stock INTO v_item
      FROM items i JOIN tipo_items ti ON ti.id_tipo_item = i.id_tipo_item
     WHERE i.id_item = NEW.id_item;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'El ítem no existe.';
    END IF;

    SELECT COALESCE(SUM(cantidad), 0) INTO v_facturado FROM venta_det WHERE id_venta = v_cab.id_venta AND id_item = NEW.id_item;
    IF v_facturado = 0 THEN
        RAISE EXCEPTION 'El ítem % no pertenece a la venta.', v_item.descripcion;
    END IF;
    IF NOT v_item.controla_stock THEN
        RAISE EXCEPTION 'El ítem % no se entrega: su tipo no controla stock.', v_item.descripcion;
    END IF;
    IF v_item.id_deposito <> v_cab.id_deposito THEN
        RAISE EXCEPTION 'El ítem % no está en el depósito seleccionado.', v_item.descripcion;
    END IF;

    SELECT COALESCE(SUM(d.cantidad), 0) INTO v_remitido
      FROM nota_remision_det d JOIN nota_remision_cab c ON c.id_remision = d.id_remision
     WHERE c.id_venta = v_cab.id_venta AND c.estado = 'EMITIDA' AND d.id_item = NEW.id_item
       AND (TG_OP = 'INSERT' OR d.id_remision_det <> NEW.id_remision_det);
    v_pendiente := v_facturado - v_remitido;
    IF NEW.cantidad > v_pendiente THEN
        RAISE EXCEPTION 'Cantidad a remitir de % supera lo pendiente de entrega: %.', v_item.descripcion, v_pendiente;
    END IF;
    RETURN NEW;
END;
$$;
COMMENT ON FUNCTION fn_validar_remision_det() IS 'Función del trigger trg_validar_remision_det: remisión emitida, ítem de la venta que controla stock, en el depósito de la remisión, y cantidad no mayor a lo pendiente de entrega.';

DROP TRIGGER IF EXISTS trg_validar_remision_det ON nota_remision_det;
CREATE TRIGGER trg_validar_remision_det
    BEFORE INSERT OR UPDATE OF id_item, cantidad ON nota_remision_det
    FOR EACH ROW EXECUTE FUNCTION fn_validar_remision_det();
COMMENT ON TRIGGER trg_validar_remision_det ON nota_remision_det IS 'Al insertar el detalle: no se puede superar lo pendiente de entrega ni remitir ítems de otro depósito o que no controlan stock.';

-- =====================================================================================================================
-- TRIGGER: trg_bloquear_anular_venta_remitida  (BEFORE UPDATE OF estado ON venta_cab)
-- Propósito : red de seguridad en la base: una venta con remisiones EMITIDAS no puede pasar a ANULADA (primero se anulan las
--             remisiones). La API da el mismo mensaje antes de llegar acá.
-- Excepciones: 'No es posible anular, existen remisiones emitidas. Anule primero las remisiones.'
-- =====================================================================================================================
CREATE OR REPLACE FUNCTION fn_bloquear_anular_venta_remitida() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.estado = 'EMITIDA' AND NEW.estado = 'ANULADA'
       AND EXISTS (SELECT 1 FROM nota_remision_cab WHERE id_venta = NEW.id_venta AND estado = 'EMITIDA') THEN
        RAISE EXCEPTION 'No es posible anular, existen remisiones emitidas. Anule primero las remisiones.';
    END IF;
    RETURN NEW;
END;
$$;
COMMENT ON FUNCTION fn_bloquear_anular_venta_remitida() IS 'Función del trigger trg_bloquear_anular_venta_remitida: una venta con remisiones EMITIDAS no se puede anular.';

DROP TRIGGER IF EXISTS trg_bloquear_anular_venta_remitida ON venta_cab;
CREATE TRIGGER trg_bloquear_anular_venta_remitida
    BEFORE UPDATE OF estado ON venta_cab
    FOR EACH ROW EXECUTE FUNCTION fn_bloquear_anular_venta_remitida();
COMMENT ON TRIGGER trg_bloquear_anular_venta_remitida ON venta_cab IS 'Impide anular una venta que tiene remisiones EMITIDAS.';

-- =====================================================================================================================
-- VISTA: v_pendientes_entrega
-- Propósito : por venta e ítem de la venta cuyo tipo controla stock, la cantidad facturada, la remitida (solo remisiones
--             EMITIDAS) y la pendiente de entrega, con el depósito donde está guardado el ítem. Alimenta la pantalla de
--             Nueva Remisión y los controles de la API.
-- Columnas  : id_venta, numero_factura, estado_venta, id_cliente, cliente, ci_ruc, id_item, item, id_deposito, deposito,
--             cantidad_facturada, cantidad_remitida, cantidad_pendiente.
-- =====================================================================================================================
CREATE OR REPLACE VIEW v_pendientes_entrega AS
SELECT v.id_venta,
       v.numero_factura,
       v.estado AS estado_venta,
       cl.id_cliente,
       cl.nombre || COALESCE(' ' || cl.apellido, '') AS cliente,
       cl.ci_ruc,
       i.id_item,
       i.descripcion AS item,
       i.id_deposito,
       dp.descripcion AS deposito,
       f.cantidad AS cantidad_facturada,
       COALESCE(r.cantidad, 0) AS cantidad_remitida,
       f.cantidad - COALESCE(r.cantidad, 0) AS cantidad_pendiente
FROM venta_cab v
JOIN cliente cl ON cl.id_cliente = v.id_cliente
JOIN (SELECT id_venta, id_item, SUM(cantidad)::INTEGER AS cantidad
        FROM venta_det WHERE id_item IS NOT NULL GROUP BY id_venta, id_item) f ON f.id_venta = v.id_venta
JOIN items i ON i.id_item = f.id_item
JOIN tipo_items ti ON ti.id_tipo_item = i.id_tipo_item AND ti.controla_stock = true
JOIN deposito dp ON dp.id_deposito = i.id_deposito
LEFT JOIN (SELECT c.id_venta, d.id_item, SUM(d.cantidad)::INTEGER AS cantidad
             FROM nota_remision_det d JOIN nota_remision_cab c ON c.id_remision = d.id_remision
            WHERE c.estado = 'EMITIDA' GROUP BY c.id_venta, d.id_item) r ON r.id_venta = v.id_venta AND r.id_item = f.id_item
WHERE v.tipo_venta = 'ITEMS';
COMMENT ON VIEW v_pendientes_entrega IS 'Por venta de ítems e ítem que controla stock: cantidad facturada, remitida (remisiones EMITIDAS) y pendiente de entrega, con el depósito del ítem.';
