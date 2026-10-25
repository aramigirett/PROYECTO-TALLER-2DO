-- Etapa 1 de la migración de Agendamiento a Tabler: los 7 referenciales con baja lógica y las FK que borraban en cascada.
-- Idempotente y en una transacción; se aplica como postgres con PGCLIENTENCODING=UTF8, DESPUÉS de un backup y de schema_agendamiento_base.sql.
-- Qué hace:
--   1. `activo` en todas las tablas que lo usan (en la base real ya existía en 10 de ellas pero ningún script lo creaba) y el único
--      PARCIAL por texto (WHERE activo = true) de cada referencial. Disponibilidad Horaria recibe `activo` por primera vez.
--   2. Consultorio: el correo (UNIQUE total) pasa a único parcial, y el nombre también.
--   3. Turno suelta su CHECK (queda como cualquier referencial: Día conserva el suyo con los 7 nombres válidos).
--   4. Las FK que borraban en cascada o dejaban NULL pasan a RESTRICT (cambio del DER, ver docs/pendientes_der_cus.md):
--      cita_cabecera.id_paciente, cita_cabecera.id_agenda_cabecera, historial_medico_paciente.id_paciente (CASCADE),
--      medico.id_ciudad y avisos_recordatorios.id_medico (SET NULL). Al recrearlas la base las valida contra los datos existentes.
BEGIN;

-- 1. activo ----------------------------------------------------------------------------------------------------------------
ALTER TABLE ciudades               ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE cargo                  ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE especialidades         ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE consultorio            ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE dias                   ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE turnos                 ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE estado_cita            ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE paciente               ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE medico                 ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE funcionario            ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE disponibilidad_horaria ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT true;

CREATE UNIQUE INDEX IF NOT EXISTS ux_ciudades_descripcion_activo      ON ciudades (UPPER(descripcion)) WHERE activo = true;
CREATE UNIQUE INDEX IF NOT EXISTS ux_cargo_descripcion_activo         ON cargo (UPPER(descripcion)) WHERE activo = true;
CREATE UNIQUE INDEX IF NOT EXISTS ux_especialidades_nombre_activo     ON especialidades (UPPER(nombre_especialidad)) WHERE activo = true;
CREATE UNIQUE INDEX IF NOT EXISTS ux_dias_descripcion_activo          ON dias (UPPER(descripcion)) WHERE activo = true;
CREATE UNIQUE INDEX IF NOT EXISTS ux_turnos_descripcion_activo        ON turnos (UPPER(descripcion)) WHERE activo = true;
CREATE UNIQUE INDEX IF NOT EXISTS ux_estado_cita_descripcion_activo   ON estado_cita (UPPER(descripcion)) WHERE activo = true;

-- 2. Consultorio ------------------------------------------------------------------------------------------------------------
ALTER TABLE consultorio DROP CONSTRAINT IF EXISTS consultorio_correo_key;
CREATE UNIQUE INDEX IF NOT EXISTS ux_consultorio_nombre_activo ON consultorio (UPPER(nombre_consultorio)) WHERE activo = true;
CREATE UNIQUE INDEX IF NOT EXISTS ux_consultorio_correo_activo ON consultorio (LOWER(correo)) WHERE activo = true AND correo IS NOT NULL;

-- 3. Turno: ABM completo (decisión de negocio: está documentado con CUS de Alta, Baja y Modificación) -------------------------
ALTER TABLE turnos DROP CONSTRAINT IF EXISTS chk_turnos;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM turnos WHERE descripcion IS NULL) THEN
        ALTER TABLE turnos ALTER COLUMN descripcion SET NOT NULL;
    END IF;
END $$;

-- 4. Disponibilidad Horaria: el único (médico, fecha, desde, hasta) pasa a parcial -----------------------------------------------
ALTER TABLE disponibilidad_horaria DROP CONSTRAINT IF EXISTS uk_disponibilidad;
CREATE UNIQUE INDEX IF NOT EXISTS ux_disponibilidad_activo
    ON disponibilidad_horaria (id_medico, dispo_fecha, dispo_hora_inicio, dispo_hora_fin) WHERE activo = true;

-- 5. FK que borraban en cascada o dejaban NULL -> RESTRICT ------------------------------------------------------------------------
DO $$
DECLARE
    f RECORD;
BEGIN
    FOR f IN SELECT * FROM (VALUES
        ('cita_cabecera',            'cita_cabecera_id_paciente_fkey',        'FOREIGN KEY (id_paciente) REFERENCES paciente(id_paciente) ON UPDATE CASCADE ON DELETE RESTRICT'),
        ('cita_cabecera',            'cita_cabecera_id_agenda_cabecera_fkey', 'FOREIGN KEY (id_agenda_cabecera) REFERENCES agenda_cabecera(id_agenda_cabecera) ON UPDATE CASCADE ON DELETE RESTRICT'),
        ('historial_medico_paciente','fk_historial_paciente',                 'FOREIGN KEY (id_paciente) REFERENCES paciente(id_paciente) ON DELETE RESTRICT'),
        ('medico',                   'medico_id_ciudad_fkey',                 'FOREIGN KEY (id_ciudad) REFERENCES ciudades(id_ciudad) ON DELETE RESTRICT'),
        ('avisos_recordatorios',     'fk_medico',                             'FOREIGN KEY (id_medico) REFERENCES medico(id_medico) ON UPDATE CASCADE ON DELETE RESTRICT')
    ) AS t(tabla, nombre, definicion) LOOP
        IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = f.nombre AND conrelid = ('public.' || f.tabla)::regclass AND confdeltype <> 'r') THEN
            EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I', f.tabla, f.nombre);
            EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I %s', f.tabla, f.nombre, f.definicion);
        END IF;
    END LOOP;
END $$;

COMMIT;
