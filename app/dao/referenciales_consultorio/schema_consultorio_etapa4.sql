-- Módulo Consultorio, etapa 4 (Diagnóstico y Odontograma). Idempotente; se corre como postgres (PGCLIENTENCODING=UTF8) DESPUÉS de un backup.
-- Una base nueva usa schema_consultorio_base.sql, que ya incluye todo esto.
--
-- 1. odontograma: se retira la columna `estado` (Activo / Finalizado / Inactivo) con su CHECK y sus índices; la baja es solo `activo`.
--    odontograma.id_paciente pasa de CASCADE a RESTRICT (estándar: nada se borra en cascada).
-- 2. odontograma_detalle (los hallazgos): baja lógica por renglón (`activo`, para conservar la trazabilidad clínica). El control de duplicados
--    mira solo los renglones ACTIVOS (único parcial pieza + superficie + estado). Superficie O V L M D o T (pieza completa), pieza FDI válida.
--    El FK al odontograma pasa a RESTRICT.
-- 3. estado_dental.aplica_a ('PIEZA' | 'SUPERFICIE'): un hallazgo de pieza completa usa la superficie T; uno de superficie, O V L M o D.
-- 4. diagnosticos: pieza dental FDI válida (opcional), descripción no vacía y, con un trigger diferido, al menos un síntoma por diagnóstico vigente.
BEGIN;

-- ---------- 1. odontograma ----------
DROP INDEX IF EXISTS ux_odontograma_consulta_vigente;
DROP INDEX IF EXISTS idx_odontograma_estado;
ALTER TABLE odontograma DROP CONSTRAINT IF EXISTS odontograma_estado_check;
ALTER TABLE odontograma DROP COLUMN IF EXISTS estado;
ALTER TABLE odontograma DROP CONSTRAINT IF EXISTS odontograma_id_paciente_fkey;
ALTER TABLE odontograma ADD CONSTRAINT odontograma_id_paciente_fkey
    FOREIGN KEY (id_paciente) REFERENCES paciente (id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT;

-- ---------- 3. estado_dental.aplica_a ----------
ALTER TABLE estado_dental ADD COLUMN IF NOT EXISTS aplica_a VARCHAR(10) NOT NULL DEFAULT 'PIEZA';
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_estado_dental_aplica_a') THEN
        ALTER TABLE estado_dental ADD CONSTRAINT chk_estado_dental_aplica_a CHECK (aplica_a IN ('PIEZA', 'SUPERFICIE'));
    END IF;
END $$;
UPDATE estado_dental SET aplica_a = 'SUPERFICIE'
 WHERE descripcion IN ('Caries', 'Obturación', 'Incrustación', 'Sellador', 'Resina', 'Amalgama', 'Fractura') AND aplica_a <> 'SUPERFICIE';
COMMENT ON COLUMN estado_dental.aplica_a IS 'PIEZA = hallazgo de la pieza completa (superficie T); SUPERFICIE = hallazgo de una superficie (O V L M D).';

-- ---------- 2. odontograma_detalle ----------
ALTER TABLE odontograma_detalle ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE odontograma_detalle DROP CONSTRAINT IF EXISTS uk_odontograma_diente_superficie;
DROP INDEX IF EXISTS uk_odontograma_diente_superficie;
CREATE UNIQUE INDEX IF NOT EXISTS uk_odontograma_detalle_activo
    ON odontograma_detalle (id_odontograma, numero_diente, superficie, id_estado_dental) WHERE activo = true;
ALTER TABLE odontograma_detalle DROP CONSTRAINT IF EXISTS odontograma_detalle_id_odontograma_fkey;
ALTER TABLE odontograma_detalle ADD CONSTRAINT odontograma_detalle_id_odontograma_fkey
    FOREIGN KEY (id_odontograma) REFERENCES odontograma (id_odontograma) ON UPDATE CASCADE ON DELETE RESTRICT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_detalle_superficie') THEN
        ALTER TABLE odontograma_detalle ADD CONSTRAINT chk_detalle_superficie CHECK (superficie IN ('O', 'V', 'L', 'M', 'D', 'T'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_detalle_pieza_fdi') THEN
        -- FDI: permanentes 11-18, 21-28, 31-38, 41-48; temporales 51-55, 61-65, 71-75, 81-85
        ALTER TABLE odontograma_detalle ADD CONSTRAINT chk_detalle_pieza_fdi CHECK (
            numero_diente BETWEEN 11 AND 18 OR numero_diente BETWEEN 21 AND 28 OR numero_diente BETWEEN 31 AND 38
            OR numero_diente BETWEEN 41 AND 48 OR numero_diente BETWEEN 51 AND 55 OR numero_diente BETWEEN 61 AND 65
            OR numero_diente BETWEEN 71 AND 75 OR numero_diente BETWEEN 81 AND 85);
    END IF;
END $$;

-- ---------- 4. diagnosticos ----------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_diagnostico_pieza_fdi') THEN
        ALTER TABLE diagnosticos ADD CONSTRAINT chk_diagnostico_pieza_fdi CHECK (
            pieza_dental IS NULL OR pieza_dental ~ '^(1[1-8]|2[1-8]|3[1-8]|4[1-8]|5[1-5]|6[1-5]|7[1-5]|8[1-5])$');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_diagnostico_descripcion') THEN
        ALTER TABLE diagnosticos ADD CONSTRAINT chk_diagnostico_descripcion CHECK (btrim(descripcion_diagnostico) <> '');
    END IF;
END $$;

CREATE OR REPLACE FUNCTION fn_validar_diagnostico_sintoma() RETURNS trigger AS $$
-- Un diagnóstico vigente tiene al menos un síntoma. Se verifica al CONFIRMAR la transacción (el diagnóstico y sus síntomas se insertan juntos).
BEGIN
    IF NEW.activo AND NOT EXISTS (SELECT 1 FROM diagnostico_sintoma WHERE id_diagnostico = NEW.id_diagnostico) THEN
        RAISE EXCEPTION 'El diagnóstico % debe tener al menos un síntoma.', NEW.codigo USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
COMMENT ON FUNCTION fn_validar_diagnostico_sintoma() IS 'Trigger diferido: todo diagnóstico vigente tiene al menos un síntoma (diagnostico_sintoma).';

DROP TRIGGER IF EXISTS trg_diagnostico_con_sintoma ON diagnosticos;
CREATE CONSTRAINT TRIGGER trg_diagnostico_con_sintoma
    AFTER INSERT OR UPDATE OF activo ON diagnosticos
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_validar_diagnostico_sintoma();

COMMIT;
