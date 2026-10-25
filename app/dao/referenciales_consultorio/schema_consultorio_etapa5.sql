-- Módulo Consultorio, etapa 5 (Tratamientos y Sesiones). Idempotente; se corre como postgres (PGCLIENTENCODING=UTF8) DESPUÉS de un backup.
-- Una base nueva usa schema_consultorio_base.sql, que ya incluye todo esto.
--
-- 1. sesiones_tratamiento.id_consulta_cab (NOT NULL, FK RESTRICT): cada sesión se registra DENTRO de una consulta (un tratamiento de varias visitas
--    recibe sesiones en consultas posteriores). Las sesiones anteriores quedan en la consulta que creó su tratamiento.
-- 2. sesion_procedimientos: una sesión tiene uno o más procedimientos (tipo de procedimiento médico). Se retira sesiones_tratamiento.id_tipo_procedimiento
--    (los datos existentes se migran, una fila por sesión). Único parcial por sesión + tipo entre los vigentes; al menos uno por sesión vigente
--    (trigger diferido).
-- 3. sesion_insumos: sin repetir el mismo insumo en una sesión (único parcial entre los vigentes) y cantidad de 1 a 999. Si había un insumo repetido en una
--    misma sesión, se deja un solo renglón con la suma de las cantidades y los demás se dan de baja.
-- 4. Endurecimiento: activo / estado NOT NULL, textos no vacíos, próxima cita no anterior a la sesión, y un trigger que exige que la consulta de la
--    sesión sea del mismo paciente y del mismo médico que el tratamiento.
BEGIN;

-- ---------- 1. sesiones_tratamiento.id_consulta_cab ----------
ALTER TABLE sesiones_tratamiento ADD COLUMN IF NOT EXISTS id_consulta_cab INTEGER;
UPDATE sesiones_tratamiento s SET id_consulta_cab = t.id_consulta_cab
  FROM tratamientos t WHERE t.id_tratamiento = s.id_tratamiento AND s.id_consulta_cab IS NULL;
ALTER TABLE sesiones_tratamiento ALTER COLUMN id_consulta_cab SET NOT NULL;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_sesion_consulta') THEN
        ALTER TABLE sesiones_tratamiento ADD CONSTRAINT fk_sesion_consulta
            FOREIGN KEY (id_consulta_cab) REFERENCES consultas_cab (id_consulta_cab) ON UPDATE CASCADE ON DELETE RESTRICT;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_sesion_consulta ON sesiones_tratamiento (id_consulta_cab);
COMMENT ON COLUMN sesiones_tratamiento.id_consulta_cab IS 'Consulta en la que se registró la sesión (mismo paciente y mismo médico que el tratamiento; puede ser posterior a la que creó el tratamiento).';

-- ---------- 2. sesion_procedimientos ----------
CREATE TABLE IF NOT EXISTS sesion_procedimientos (
    id_sesion_procedimiento SERIAL,
    id_sesion integer NOT NULL,
    id_tipo_procedimiento integer NOT NULL,
    activo boolean NOT NULL DEFAULT true,
    CONSTRAINT sesion_procedimientos_pkey PRIMARY KEY (id_sesion_procedimiento),
    CONSTRAINT sesion_procedimientos_id_sesion_fkey FOREIGN KEY (id_sesion) REFERENCES sesiones_tratamiento(id_sesion) ON DELETE RESTRICT,
    CONSTRAINT sesion_procedimientos_id_tipo_fkey FOREIGN KEY (id_tipo_procedimiento) REFERENCES tipo_procedimiento_medico(id_tipo_procedimiento) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_sesion_procedimiento_activo ON sesion_procedimientos (id_sesion, id_tipo_procedimiento) WHERE activo = true;
CREATE INDEX IF NOT EXISTS idx_sesion_procedimientos_tipo ON sesion_procedimientos (id_tipo_procedimiento);
COMMENT ON TABLE sesion_procedimientos IS 'Procedimientos realizados en una sesión de tratamiento (uno o más por sesión).';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'sesiones_tratamiento' AND column_name = 'id_tipo_procedimiento') THEN
        INSERT INTO sesion_procedimientos (id_sesion, id_tipo_procedimiento, activo)
        SELECT s.id_sesion, s.id_tipo_procedimiento, COALESCE(s.activo, true)
          FROM sesiones_tratamiento s
         WHERE NOT EXISTS (SELECT 1 FROM sesion_procedimientos sp WHERE sp.id_sesion = s.id_sesion);
        ALTER TABLE sesiones_tratamiento DROP COLUMN id_tipo_procedimiento;   -- arrastra su FK
    END IF;
END $$;

-- ---------- 3. sesion_insumos ----------
UPDATE sesion_insumos SET activo = true WHERE activo IS NULL;
ALTER TABLE sesion_insumos ALTER COLUMN activo SET NOT NULL;
WITH repetidos AS (
    SELECT id_sesion, id_insumo, MIN(id_sesion_insumo) AS conserva, SUM(cantidad) AS total
      FROM sesion_insumos WHERE activo = true GROUP BY id_sesion, id_insumo HAVING COUNT(*) > 1),
suma AS (
    UPDATE sesion_insumos si SET cantidad = LEAST(r.total, 999)
      FROM repetidos r WHERE si.id_sesion_insumo = r.conserva RETURNING si.id_sesion_insumo)
UPDATE sesion_insumos si SET activo = false
  FROM repetidos r
 WHERE si.id_sesion = r.id_sesion AND si.id_insumo = r.id_insumo AND si.activo = true AND si.id_sesion_insumo <> r.conserva;
CREATE UNIQUE INDEX IF NOT EXISTS uk_sesion_insumo_activo ON sesion_insumos (id_sesion, id_insumo) WHERE activo = true;
CREATE INDEX IF NOT EXISTS idx_sesion_insumos_insumo ON sesion_insumos (id_insumo);
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_sesion_insumo_cantidad') THEN
        ALTER TABLE sesion_insumos ADD CONSTRAINT chk_sesion_insumo_cantidad CHECK (cantidad BETWEEN 1 AND 999);
    END IF;
END $$;

-- ---------- 4. endurecimiento ----------
UPDATE sesiones_tratamiento SET activo = true WHERE activo IS NULL;
ALTER TABLE sesiones_tratamiento ALTER COLUMN activo SET NOT NULL;
UPDATE tratamientos SET estado = 'pendiente' WHERE estado IS NULL;
ALTER TABLE tratamientos ALTER COLUMN estado SET NOT NULL;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_tratamiento_descripcion') THEN
        ALTER TABLE tratamientos ADD CONSTRAINT chk_tratamiento_descripcion CHECK (btrim(descripcion_tratamiento) <> '') NOT VALID;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_sesion_descripcion') THEN
        ALTER TABLE sesiones_tratamiento ADD CONSTRAINT chk_sesion_descripcion CHECK (btrim(descripcion_procedimiento) <> '') NOT VALID;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_sesion_proxima_cita') THEN
        ALTER TABLE sesiones_tratamiento ADD CONSTRAINT chk_sesion_proxima_cita CHECK (proxima_cita IS NULL OR proxima_cita >= fecha_sesion) NOT VALID;
    END IF;
END $$;

CREATE OR REPLACE FUNCTION fn_validar_sesion_consulta() RETURNS trigger AS $$
-- La consulta en la que se registra una sesión es del mismo paciente y del mismo médico que el tratamiento.
BEGIN
    IF NOT EXISTS (SELECT 1 FROM tratamientos t JOIN consultas_cab c ON c.id_consulta_cab = NEW.id_consulta_cab
                    WHERE t.id_tratamiento = NEW.id_tratamiento AND t.id_paciente = c.id_paciente AND t.id_medico = c.id_medico) THEN
        RAISE EXCEPTION 'La consulta de la sesión debe ser del mismo paciente y del mismo médico que el tratamiento.' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
COMMENT ON FUNCTION fn_validar_sesion_consulta() IS 'Trigger: una sesión se registra en una consulta del mismo paciente y médico que su tratamiento.';

DROP TRIGGER IF EXISTS trg_validar_sesion_consulta ON sesiones_tratamiento;
CREATE TRIGGER trg_validar_sesion_consulta
    BEFORE INSERT ON sesiones_tratamiento
    FOR EACH ROW EXECUTE FUNCTION fn_validar_sesion_consulta();

CREATE OR REPLACE FUNCTION fn_validar_sesion_procedimiento() RETURNS trigger AS $$
-- Una sesión vigente tiene al menos un procedimiento. Se verifica al CONFIRMAR la transacción (la sesión y sus procedimientos se insertan juntos).
BEGIN
    IF NEW.activo AND NOT EXISTS (SELECT 1 FROM sesion_procedimientos WHERE id_sesion = NEW.id_sesion AND activo = true) THEN
        RAISE EXCEPTION 'La sesión % debe tener al menos un procedimiento.', NEW.numero_sesion USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
COMMENT ON FUNCTION fn_validar_sesion_procedimiento() IS 'Trigger diferido: toda sesión vigente tiene al menos un procedimiento (sesion_procedimientos).';

DROP TRIGGER IF EXISTS trg_sesion_con_procedimiento ON sesiones_tratamiento;
CREATE CONSTRAINT TRIGGER trg_sesion_con_procedimiento
    AFTER INSERT OR UPDATE OF activo ON sesiones_tratamiento
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_validar_sesion_procedimiento();

COMMIT;
