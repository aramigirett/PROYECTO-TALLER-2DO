-- Módulo Facturación - Referencial "Mantener Tipo Ítems". Idempotente.
-- Usa auditoria_cambios (schema_forma_cobro.sql).

CREATE TABLE IF NOT EXISTS tipo_items (
    id_tipo_item   SERIAL PRIMARY KEY,
    descripcion    VARCHAR(60) NOT NULL,
    controla_stock BOOLEAN NOT NULL DEFAULT true,
    activo         BOOLEAN NOT NULL DEFAULT true
);

-- Parcial: un tipo anulado no bloquea reutilizar su descripción.
CREATE UNIQUE INDEX IF NOT EXISTS ux_tipo_items_descripcion_activo
    ON tipo_items (UPPER(descripcion)) WHERE activo = true;

INSERT INTO tipo_items (descripcion, controla_stock)
SELECT t.d, t.cs
FROM (VALUES
    ('HIGIENE BUCAL', true),
    ('ORTODONCIA', true),
    ('APARATOLOGÍA Y PROTECCIÓN', true),
    ('ESTUDIOS RADIOGRÁFICOS', false),
    ('DOCUMENTOS Y CERTIFICADOS', false)
) AS t(d, cs)
WHERE NOT EXISTS (
    SELECT 1 FROM tipo_items x WHERE UPPER(x.descripcion) = t.d AND x.activo = true
);
