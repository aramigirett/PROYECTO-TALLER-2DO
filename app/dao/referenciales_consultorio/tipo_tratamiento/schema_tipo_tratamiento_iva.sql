-- Consultorio - Referencial "Tipo Tratamiento": IVA, igual que en items (0 = exenta, 5 o 10). Idempotente.
-- Lo usa la Venta de Tratamiento (Facturación). Aplicar ANTES del código nuevo (el DAO selecciona `iva`).
-- Orden respecto de schema_tipo_tratamiento_precio.sql: indistinto (los datos iniciales de aquel no llevan IVA y
-- toman el default 10).

-- Con NOT NULL DEFAULT 10, PostgreSQL completa las filas existentes en la misma operación: quedan en 10.
ALTER TABLE tipos_tratamiento ADD COLUMN IF NOT EXISTS iva SMALLINT NOT NULL DEFAULT 10;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_tipos_tratamiento_iva') THEN
        ALTER TABLE tipos_tratamiento ADD CONSTRAINT chk_tipos_tratamiento_iva CHECK (iva IN (0, 5, 10));
    END IF;
END
$$;
