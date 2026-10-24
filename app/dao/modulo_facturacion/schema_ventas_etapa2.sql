-- Registrar Ventas — ETAPA 2 (Venta de Tratamiento, factura en PDF). Idempotente. Se corre DESPUÉS de schema_ventas.sql.
-- No crea tablas nuevas: amplía una columna y agrega índices para las consultas nuevas.

-- La descripción de un renglón de tratamiento es la del tipo de tratamiento (hasta 200 caracteres): venta_det.descripcion
-- pasa de VARCHAR(150) a VARCHAR(200) para copiarla completa, sin recortar. Ensanchar un VARCHAR no reescribe la tabla ni
-- afecta a la vista v_estado_cuenta_cliente (que no usa esta columna); correrlo de nuevo no cambia nada.
ALTER TABLE venta_det ALTER COLUMN descripcion TYPE VARCHAR(200);

-- Búsquedas por tratamiento ("¿ya se facturó este tratamiento?") y por ítem.
CREATE INDEX IF NOT EXISTS ix_venta_det_tratamiento ON venta_det (id_tratamiento) WHERE id_tratamiento IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_venta_det_item        ON venta_det (id_item) WHERE id_item IS NOT NULL;

COMMENT ON COLUMN venta_det.descripcion IS 'Descripción copiada al momento de la venta (del ítem o del tipo de tratamiento; hasta 200 caracteres).';
