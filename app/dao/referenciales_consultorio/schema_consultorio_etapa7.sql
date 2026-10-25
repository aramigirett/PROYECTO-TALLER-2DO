-- Módulo Consultorio, etapa 7 (Justificativo Médico). Idempotente; se corre como postgres (PGCLIENTENCODING=UTF8) DESPUÉS de un backup.
-- Una base nueva usa schema_consultorio_base.sql, que ya incluye todo esto.
--
-- 1. justificativo_medico.estado: de 'activo' / 'anulado' a 'pendiente' / 'emitido' / 'anulado' (el CUS: el justificativo se registra pendiente, "Generar" lo emite
--    y "Anular" lo anula, definitivo). Estado inicial 'pendiente'. Lo cargado como 'activo' pasa a 'emitido'.
-- 2. Días de reposo de 1 a 365 y un índice por consulta.
BEGIN;

ALTER TABLE justificativo_medico DROP CONSTRAINT IF EXISTS justificativo_medico_estado_check;
UPDATE justificativo_medico SET estado = 'emitido' WHERE estado = 'activo';
ALTER TABLE justificativo_medico ALTER COLUMN estado SET DEFAULT 'pendiente';
ALTER TABLE justificativo_medico ADD CONSTRAINT justificativo_medico_estado_check CHECK (estado IN ('pendiente', 'emitido', 'anulado'));

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_justificativo_dias') THEN
        ALTER TABLE justificativo_medico ADD CONSTRAINT chk_justificativo_dias CHECK (dias_reposo BETWEEN 1 AND 365);
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_justificativo_consulta ON justificativo_medico (id_consulta_cab);
COMMENT ON COLUMN justificativo_medico.estado IS 'pendiente (registrado, borrador) -> emitido (documento oficial) | anulado (definitivo).';

COMMIT;
