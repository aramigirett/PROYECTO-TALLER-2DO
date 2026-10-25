-- Etapa 2 de la migración de Agendamiento a Tabler: Paciente, Médico y Funcionario con baja lógica.
-- Idempotente y en una transacción; se aplica como postgres con PGCLIENTENCODING=UTF8, DESPUÉS de un backup y de schema_agendamiento_etapa1.sql.
--   1. La cédula de cada persona pasa de UNIQUE total a único PARCIAL (WHERE activo = true): una persona anulada no bloquea registrar de nuevo
--      esa cédula. Lo mismo el N.º de registro del médico (nuevo único parcial; antes solo lo controlaba el código).
--   2. `medico.fecha_registro` recibe DEFAULT CURRENT_DATE (la fecha la pone el servidor, como en paciente y funcionario).
--   3. `medico.id_especialidad` y `medico.id_ciudad` pasan a NOT NULL (el formulario ya los exigía) si ningún médico las tiene vacías.
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM medico WHERE activo AND num_registro IS NOT NULL GROUP BY UPPER(TRIM(num_registro)) HAVING COUNT(*) > 1) THEN
        RAISE EXCEPTION 'Hay médicos activos con el mismo N.º de registro: corríjalos antes de aplicar este script.';
    END IF;
END $$;

ALTER TABLE paciente    DROP CONSTRAINT IF EXISTS paciente_cedula_entidad_key;
ALTER TABLE medico      DROP CONSTRAINT IF EXISTS medico_cedula_key;
ALTER TABLE funcionario DROP CONSTRAINT IF EXISTS funcionario_cedula_key;

CREATE UNIQUE INDEX IF NOT EXISTS ux_paciente_cedula_activo    ON paciente (UPPER(TRIM(cedula_entidad))) WHERE activo = true;
CREATE UNIQUE INDEX IF NOT EXISTS ux_medico_cedula_activo      ON medico (UPPER(TRIM(cedula))) WHERE activo = true AND cedula IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_medico_registro_activo    ON medico (UPPER(TRIM(num_registro))) WHERE activo = true AND num_registro IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_funcionario_cedula_activo ON funcionario (UPPER(TRIM(cedula))) WHERE activo = true;

ALTER TABLE medico ALTER COLUMN fecha_registro SET DEFAULT CURRENT_DATE;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM medico WHERE id_especialidad IS NULL) THEN
        ALTER TABLE medico ALTER COLUMN id_especialidad SET NOT NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM medico WHERE id_ciudad IS NULL) THEN
        ALTER TABLE medico ALTER COLUMN id_ciudad SET NOT NULL;
    END IF;
END $$;

COMMIT;
