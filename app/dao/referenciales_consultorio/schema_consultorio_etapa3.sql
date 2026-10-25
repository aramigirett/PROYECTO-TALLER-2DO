-- Módulo Consultorio, etapa 3 (Registrar Consulta + Ficha Médica). Idempotente; se corre como postgres (PGCLIENTENCODING=UTF8)
-- DESPUÉS de un backup. Una base nueva usa schema_consultorio_base.sql, que ya incluye todo esto.
--
-- 1. consultas_cab.id_cita: de UNIQUE total a ÚNICO PARCIAL (WHERE activo = true). Una consulta anulada ya no bloquea volver a consultar
--    la misma cita (al anular, la cita vuelve a "Confirmado").
-- 2. consultas_cab.duracion_minutos: entre 1 y 480.
-- 3. ficha_medica_consulta: rangos clínicos aprobados, formato de la presión (SSS/DDD con sistólica > diastólica) y al menos un dato.
--    La regla "al menos un dato" se agrega NOT VALID: no toca una ficha vacía cargada antes (la 15) pero rige para toda ficha nueva o editada.
--    El FK a la consulta pasa de ON DELETE CASCADE a RESTRICT (estándar: nada se borra en cascada).
BEGIN;

ALTER TABLE consultas_cab DROP CONSTRAINT IF EXISTS uk_consulta_cita;
CREATE UNIQUE INDEX IF NOT EXISTS uk_consulta_cita_activa ON consultas_cab (id_cita) WHERE activo = true;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_consulta_duracion') THEN
        ALTER TABLE consultas_cab ADD CONSTRAINT chk_consulta_duracion
            CHECK (duracion_minutos IS NULL OR duracion_minutos BETWEEN 1 AND 480);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_ficha_rangos') THEN
        ALTER TABLE ficha_medica_consulta ADD CONSTRAINT chk_ficha_rangos CHECK (
            (temperatura IS NULL OR temperatura BETWEEN 30 AND 45)
            AND (frecuencia_cardiaca IS NULL OR frecuencia_cardiaca BETWEEN 20 AND 250)
            AND (frecuencia_respiratoria IS NULL OR frecuencia_respiratoria BETWEEN 5 AND 80)
            AND (peso IS NULL OR peso BETWEEN 1 AND 500)
            AND (talla IS NULL OR talla BETWEEN 30 AND 250));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_ficha_presion') THEN
        ALTER TABLE ficha_medica_consulta ADD CONSTRAINT chk_ficha_presion CHECK (
            presion_arterial IS NULL
            OR (presion_arterial ~ '^[0-9]{2,3}/[0-9]{2,3}$'
                AND split_part(presion_arterial, '/', 1)::int BETWEEN 50 AND 300
                AND split_part(presion_arterial, '/', 2)::int BETWEEN 30 AND 200
                AND split_part(presion_arterial, '/', 1)::int > split_part(presion_arterial, '/', 2)::int));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_ficha_con_datos') THEN
        ALTER TABLE ficha_medica_consulta ADD CONSTRAINT chk_ficha_con_datos CHECK (
            num_nonnulls(presion_arterial, temperatura, frecuencia_cardiaca, frecuencia_respiratoria, peso, talla,
                         examen_fisico_general, examen_bucal, observaciones_medico) > 0) NOT VALID;
    END IF;
END $$;

ALTER TABLE ficha_medica_consulta DROP CONSTRAINT IF EXISTS fk_ficha_consulta;
ALTER TABLE ficha_medica_consulta ADD CONSTRAINT fk_ficha_consulta
    FOREIGN KEY (id_consulta_cab) REFERENCES consultas_cab (id_consulta_cab) ON DELETE RESTRICT;

COMMENT ON CONSTRAINT chk_ficha_con_datos ON ficha_medica_consulta IS
    'No se guardan fichas vacías. NOT VALID a propósito: la ficha vacía 15 (anterior a la etapa 3) se conserva hasta que se anule.';
COMMIT;
