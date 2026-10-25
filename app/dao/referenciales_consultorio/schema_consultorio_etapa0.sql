-- Módulo Consultorio, etapa 0 de la migración a Tabler. Idempotente; se corre como postgres (PGCLIENTENCODING=UTF8)
-- DESPUÉS de hacer un backup. Una base nueva usa schema_consultorio_base.sql, que ya incluye todo esto.
--
-- 1. Elimina `consultas_detalle`: superada por Diagnóstico, Tratamiento y Sesiones (no figura en la Lista de Archivos de ningún
--    CUS vigente). Se verifica antes que esté vacía y sin objetos que dependan de ella; si no, corta con un mensaje.
-- 2. `odontograma.activo` (baja lógica del estándar) + único parcial por consulta. `estado` se conserva hasta la etapa 4,
--    donde el odontograma queda solo con Activo/Anulado.
-- 3. Los únicos parciales de los referenciales comparan en MAYÚSCULAS (UPPER), igual que Facturación.
BEGIN;

DO $$
DECLARE
    v_filas BIGINT;
    v_deps  TEXT;
BEGIN
    IF to_regclass('public.consultas_detalle') IS NOT NULL THEN
        EXECUTE 'SELECT COUNT(*) FROM consultas_detalle' INTO v_filas;
        IF v_filas > 0 THEN
            RAISE EXCEPTION 'consultas_detalle tiene % filas: no se elimina.', v_filas;
        END IF;
        SELECT string_agg(conrelid::regclass::text || '.' || conname, ', ') INTO v_deps
          FROM pg_constraint WHERE confrelid = 'consultas_detalle'::regclass;
        IF v_deps IS NOT NULL THEN
            RAISE EXCEPTION 'consultas_detalle está referenciada por: %', v_deps;
        END IF;
        DROP TABLE consultas_detalle;   -- sin CASCADE a propósito: si una vista la usa, falla
    END IF;
END $$;

ALTER TABLE odontograma ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT true;
-- (la columna `estado` se retira en la etapa 4: en una base ya al día este paso no hace nada)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'odontograma' AND column_name = 'estado') THEN
        EXECUTE 'UPDATE odontograma SET activo = false WHERE estado = ''Inactivo'' AND activo = true';
    END IF;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS ux_odontograma_consulta_activo ON odontograma (id_consulta_cab) WHERE activo = true;
COMMENT ON COLUMN odontograma.activo IS 'Baja lógica (estándar). false = anulado. Reemplaza a estado = ''Inactivo''.';

DROP INDEX IF EXISTS uk_tipo_trat_descripcion;
CREATE UNIQUE INDEX uk_tipo_trat_descripcion ON tipos_tratamiento (UPPER(descripcion)) WHERE activo = true;
DROP INDEX IF EXISTS uk_insumos_descripcion;
CREATE UNIQUE INDEX uk_insumos_descripcion ON insumos (UPPER(descripcion)) WHERE activo = true;
DROP INDEX IF EXISTS uk_tipo_proc_descripcion;
CREATE UNIQUE INDEX uk_tipo_proc_descripcion ON tipo_procedimiento_medico (UPPER(descripcion)) WHERE activo = true;
DROP INDEX IF EXISTS uk_medicamento_nombre_comercial;
CREATE UNIQUE INDEX uk_medicamento_nombre_comercial ON medicamentos (UPPER(nombre_comercial)) WHERE activo = true;
DROP INDEX IF EXISTS uk_tipo_analisis_descripcion;
CREATE UNIQUE INDEX uk_tipo_analisis_descripcion ON tipo_analisis (UPPER(descripcion)) WHERE activo = true;
DROP INDEX IF EXISTS uk_tipo_estudio_descripcion;
CREATE UNIQUE INDEX uk_tipo_estudio_descripcion ON tipo_estudio (UPPER(descripcion)) WHERE activo = true;

COMMIT;
