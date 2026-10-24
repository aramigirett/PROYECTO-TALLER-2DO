-- Migración: cada ítem pasa a tener un depósito (items.id_deposito NOT NULL, FK a deposito).
-- Idempotente. Si la tabla items todavía no existe (base nueva) no hace nada: schema_items.sql
-- ya la crea con la columna.
--
-- Orden de ejecución (base nueva o existente):
--   schema_tipo_items -> schema_deposito -> migracion_items_deposito -> schema_items -> schema_permisos_deposito
--
-- Reglas de asignación (solo para filas con id_deposito NULL; no pisa asignaciones ya hechas):
--   * ítems cuyo tipo es ORTODONCIA -> DEPÓSITO ORTODONCIA
--   * el resto (activos e inactivos) -> DEPÓSITO PRINCIPAL
DO $$
BEGIN
    IF to_regclass('public.items') IS NULL THEN
        RETURN;
    END IF;

    ALTER TABLE items ADD COLUMN IF NOT EXISTS id_deposito INTEGER;

    UPDATE items i
    SET id_deposito = (
        SELECT d.id_deposito
        FROM deposito d
        WHERE d.activo = true
          AND UPPER(d.descripcion) = CASE
                WHEN EXISTS (SELECT 1 FROM tipo_items t
                             WHERE t.id_tipo_item = i.id_tipo_item AND UPPER(t.descripcion) = 'ORTODONCIA')
                THEN 'DEPÓSITO ORTODONCIA' ELSE 'DEPÓSITO PRINCIPAL' END
        LIMIT 1
    )
    WHERE i.id_deposito IS NULL;

    -- Si quedara algún ítem sin depósito (faltan los depósitos iniciales), esto falla a propósito.
    ALTER TABLE items ALTER COLUMN id_deposito SET NOT NULL;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_items_deposito') THEN
        ALTER TABLE items ADD CONSTRAINT fk_items_deposito
            FOREIGN KEY (id_deposito) REFERENCES deposito(id_deposito) ON DELETE RESTRICT;
    END IF;

    CREATE INDEX IF NOT EXISTS ix_items_deposito ON items (id_deposito);
END
$$;
