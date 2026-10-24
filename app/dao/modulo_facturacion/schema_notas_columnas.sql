-- Registrar Notas de Crédito y Débito — COLUMNAS NUEVAS sobre nota_credito_debito_cab (tabla del DER). Idempotente.
-- ⚠️ Estas dos columnas NO están en el DER de la tesis: hay que agregarlas al DER (junto con forma_cobro.tipo y cobro_det.numero_referencia).
--   * id_apertura     : apertura de caja en la que se emitió la nota (toda nota exige caja abierta del cajero). Permite anular solo con
--                       la caja de la nota abierta y contar el reintegro dentro de la apertura.
--   * monto_reintegro : parte de una nota de CRÉDITO que se devolvió en EFECTIVO al cliente porque la factura ya estaba pagada
--                       (el trigger trg_preparar_nota la calcula). Es 0 en los débitos y en los créditos que solo reducen saldo.
-- Orden: 01_migracion_der.sql -> este script -> schema_notas.sql. La tabla no tiene filas al momento de crear este script; si las
-- hubiera, id_apertura queda NULL (sin NOT NULL) hasta que se las complete a mano y se vuelva a correr el script.

ALTER TABLE nota_credito_debito_cab ADD COLUMN IF NOT EXISTS id_apertura INTEGER;
ALTER TABLE nota_credito_debito_cab ADD COLUMN IF NOT EXISTS monto_reintegro NUMERIC(12,0) NOT NULL DEFAULT 0;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'nota_cd_id_apertura_fkey') THEN
        ALTER TABLE nota_credito_debito_cab
            ADD CONSTRAINT nota_cd_id_apertura_fkey FOREIGN KEY (id_apertura) REFERENCES apertura_cierre_caja(id_apertura) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_nota_reintegro') THEN
        ALTER TABLE nota_credito_debito_cab
            ADD CONSTRAINT ck_nota_reintegro CHECK (monto_reintegro >= 0 AND monto_reintegro <= total
                                                    AND (tipo_nota = 'CREDITO' OR monto_reintegro = 0));
    END IF;
    IF EXISTS (SELECT 1 FROM nota_credito_debito_cab WHERE id_apertura IS NULL) THEN
        RAISE NOTICE 'Hay notas sin id_apertura: id_apertura queda sin NOT NULL hasta completarlas.';
    ELSE
        ALTER TABLE nota_credito_debito_cab ALTER COLUMN id_apertura SET NOT NULL;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS ix_nota_cd_apertura ON nota_credito_debito_cab (id_apertura);

COMMENT ON COLUMN nota_credito_debito_cab.id_apertura IS 'Apertura de caja en la que se emitió la nota (columna agregada; falta en el DER).';
COMMENT ON COLUMN nota_credito_debito_cab.monto_reintegro IS 'Parte de la nota de crédito devuelta en EFECTIVO al cliente (factura ya pagada). Resta del efectivo del cierre de caja (columna agregada; falta en el DER).';
