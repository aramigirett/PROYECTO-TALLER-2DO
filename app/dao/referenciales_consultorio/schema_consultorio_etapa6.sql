-- Módulo Consultorio, etapa 6 (Recetas y Órdenes de Estudio / de Análisis). Idempotente; se corre como postgres (PGCLIENTENCODING=UTF8) DESPUÉS de un backup.
-- Una base nueva usa schema_consultorio_base.sql, que ya incluye todo esto.
--
-- 1. receta_medicamento: un mismo medicamento no se repite en una receta (único parcial entre los vigentes; si había repetidos vigentes se deja el primero y
--    se dan de baja los demás) y `activo` NOT NULL (también en recetas).
-- 2. Textos no vacíos (indicaciones de la receta, dosis / frecuencia / duración, motivo de las órdenes): CHECK NOT VALID para no tocar lo cargado antes.
-- 3. Trigger diferido: toda receta vigente tiene al menos un medicamento vigente (la receta y sus medicamentos se insertan juntos).
BEGIN;

UPDATE recetas SET activo = true WHERE activo IS NULL;
ALTER TABLE recetas ALTER COLUMN activo SET NOT NULL;
UPDATE receta_medicamento SET activo = true WHERE activo IS NULL;
ALTER TABLE receta_medicamento ALTER COLUMN activo SET NOT NULL;

UPDATE receta_medicamento rm SET activo = false
 WHERE rm.activo = true
   AND EXISTS (SELECT 1 FROM receta_medicamento o WHERE o.id_receta = rm.id_receta AND o.id_medicamento = rm.id_medicamento AND o.activo = true
                  AND o.id_receta_medicamento < rm.id_receta_medicamento);
CREATE UNIQUE INDEX IF NOT EXISTS uk_receta_medicamento_activo ON receta_medicamento (id_receta, id_medicamento) WHERE activo = true;
CREATE INDEX IF NOT EXISTS idx_receta_medicamento_medicamento ON receta_medicamento (id_medicamento);
CREATE INDEX IF NOT EXISTS idx_receta_consulta ON recetas (id_consulta_cab);
CREATE INDEX IF NOT EXISTS idx_orden_estudios_consulta ON orden_estudios (id_consulta_cab);
CREATE INDEX IF NOT EXISTS idx_orden_analisis_consulta ON orden_analisis (id_consulta_cab);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_receta_indicaciones') THEN
        ALTER TABLE recetas ADD CONSTRAINT chk_receta_indicaciones CHECK (btrim(indicaciones_generales) <> '') NOT VALID;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_receta_medicamento_textos') THEN
        ALTER TABLE receta_medicamento ADD CONSTRAINT chk_receta_medicamento_textos
            CHECK (btrim(dosis) <> '' AND btrim(frecuencia) <> '' AND btrim(duracion) <> '') NOT VALID;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_orden_estudio_motivo') THEN
        ALTER TABLE orden_estudios ADD CONSTRAINT chk_orden_estudio_motivo CHECK (btrim(motivo_orden) <> '') NOT VALID;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_orden_analisis_motivo') THEN
        ALTER TABLE orden_analisis ADD CONSTRAINT chk_orden_analisis_motivo CHECK (btrim(motivo_orden) <> '') NOT VALID;
    END IF;
END $$;

CREATE OR REPLACE FUNCTION fn_validar_receta_medicamento() RETURNS trigger AS $$
-- Una receta vigente tiene al menos un medicamento vigente. Se verifica al CONFIRMAR la transacción (la receta y sus medicamentos se insertan juntos).
BEGIN
    IF NEW.activo AND NOT EXISTS (SELECT 1 FROM receta_medicamento WHERE id_receta = NEW.id_receta AND activo = true) THEN
        RAISE EXCEPTION 'La receta % debe tener al menos un medicamento.', NEW.id_receta USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
COMMENT ON FUNCTION fn_validar_receta_medicamento() IS 'Trigger diferido: toda receta vigente tiene al menos un medicamento (receta_medicamento).';

DROP TRIGGER IF EXISTS trg_receta_con_medicamento ON recetas;
CREATE CONSTRAINT TRIGGER trg_receta_con_medicamento
    AFTER INSERT OR UPDATE OF activo ON recetas
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_validar_receta_medicamento();

COMMIT;
