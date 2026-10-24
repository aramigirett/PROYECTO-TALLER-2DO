-- Módulo Facturación - Referencial "Mantener Ítems". Idempotente.
-- Requiere tipo_items y deposito. precio_unitario en guaraníes (sin decimales). iva: 0 = exenta, 5 o 10.
-- El stock (cantidad_disponible) es global; id_deposito indica dónde se guarda el ítem.
--
-- Orden: schema_tipo_items -> schema_deposito -> migracion_items_deposito -> schema_items
-- (en una base que ya tenía items sin depósito, migracion_items_deposito agrega y completa la columna).

CREATE TABLE IF NOT EXISTS items (
    id_item             SERIAL PRIMARY KEY,
    id_tipo_item        INTEGER NOT NULL REFERENCES tipo_items(id_tipo_item) ON DELETE RESTRICT,
    id_deposito         INTEGER NOT NULL,
    descripcion         VARCHAR(100) NOT NULL,
    precio_unitario     NUMERIC(12,0) NOT NULL CHECK (precio_unitario > 0),
    iva                 SMALLINT NOT NULL DEFAULT 10 CHECK (iva IN (0, 5, 10)),
    cantidad_disponible INTEGER NOT NULL DEFAULT 0 CHECK (cantidad_disponible >= 0),
    activo              BOOLEAN NOT NULL DEFAULT true
);

-- (en una base nueva la FK se crea acá; en una migrada ya existe: ver migracion_items_deposito.sql)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_items_deposito') THEN
        ALTER TABLE items ADD CONSTRAINT fk_items_deposito
            FOREIGN KEY (id_deposito) REFERENCES deposito(id_deposito) ON DELETE RESTRICT;
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS ux_items_descripcion_activo
    ON items (UPPER(descripcion)) WHERE activo = true;
CREATE INDEX IF NOT EXISTS ix_items_tipo ON items (id_tipo_item);
CREATE INDEX IF NOT EXISTS ix_items_deposito ON items (id_deposito);

-- Depósito inicial: ORTODONCIA -> DEPÓSITO ORTODONCIA; el resto -> DEPÓSITO PRINCIPAL.
INSERT INTO items (id_tipo_item, id_deposito, descripcion, precio_unitario, iva, cantidad_disponible)
SELECT ti.id_tipo_item, dep.id_deposito, t.d, t.precio, 10, t.stock
FROM (VALUES
    ('HIGIENE BUCAL',              'CEPILLO DENTAL ADULTO',          15000,  50),
    ('HIGIENE BUCAL',              'PASTA DENTAL CON FLÚOR 90G',     18000,  40),
    ('HIGIENE BUCAL',              'HILO DENTAL 50M',                25000,  30),
    ('HIGIENE BUCAL',              'ENJUAGUE BUCAL 500ML',           45000,  20),
    ('ORTODONCIA',                 'KIT DE HIGIENE PARA ORTODONCIA', 60000,  15),
    ('ORTODONCIA',                 'CERA ORTODÓNTICA',               20000,  25),
    ('APARATOLOGÍA Y PROTECCIÓN',  'PROTECTOR BUCAL DEPORTIVO',      80000,  10),
    ('ESTUDIOS RADIOGRÁFICOS',     'RADIOGRAFÍA PANORÁMICA',        120000,   0),
    ('ESTUDIOS RADIOGRÁFICOS',     'RADIOGRAFÍA PERIAPICAL',         40000,   0),
    ('DOCUMENTOS Y CERTIFICADOS',  'CERTIFICADO ODONTOLÓGICO',       50000,   0)
) AS t(tipo, d, precio, stock)
JOIN tipo_items ti ON UPPER(ti.descripcion) = t.tipo AND ti.activo = true
JOIN deposito dep ON dep.activo = true AND UPPER(dep.descripcion) =
        CASE WHEN t.tipo = 'ORTODONCIA' THEN 'DEPÓSITO ORTODONCIA' ELSE 'DEPÓSITO PRINCIPAL' END
WHERE NOT EXISTS (
    SELECT 1 FROM items i WHERE UPPER(i.descripcion) = t.d AND i.activo = true
);
