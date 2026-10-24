-- =====================================================================
-- OdontoClinic - Migración 02: cambios que REQUIEREN ajustar el código
-- ---------------------------------------------------------------------
-- Correr DESPUÉS de 01_migracion_der.sql y SOLO cuando el código ya
-- use los nombres nuevos (cada bloque dice qué hay que cambiar).
-- Si encuentra datos que no puede completar, se detiene y no cambia nada.
-- =====================================================================
BEGIN;

-- Control: la migración 01 tiene que estar aplicada
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM information_schema.columns
	               WHERE table_name = 'permisos' AND column_name = 'id_menu') THEN
		RAISE EXCEPTION 'Primero hay que ejecutar 01_migracion_der.sql';
	END IF;
END $$;

-- Función auxiliar: corta la migración si una columna tiene nulos
CREATE FUNCTION pg_temp.exigir_sin_nulos(p_tabla text, p_columna text) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE v_cant int;
BEGIN
	EXECUTE format('SELECT count(*) FROM %I WHERE %I IS NULL', p_tabla, p_columna) INTO v_cant;
	IF v_cant > 0 THEN
		RAISE EXCEPTION '%.% tiene % fila(s) sin valor. Completarlas antes de seguir.', p_tabla, p_columna, v_cant;
	END IF;
	EXECUTE format('ALTER TABLE %I ALTER COLUMN %I SET NOT NULL', p_tabla, p_columna);
END $$;

-- ---------------------------------------------------------------------
-- 1. diagnosticos: id_consulta_detalle -> id_consulta_cab
--    Código: guardar id_consulta_cab al registrar el diagnóstico;
--    los síntomas se guardan en diagnostico_sintoma (no en texto).
-- ---------------------------------------------------------------------
ALTER TABLE diagnosticos ADD COLUMN id_consulta_cab int4;
UPDATE diagnosticos d
   SET id_consulta_cab = cd.id_consulta_cab
  FROM consultas_detalle cd
 WHERE cd.id_consulta_detalle = d.id_consulta_detalle;
DO $$ BEGIN PERFORM pg_temp.exigir_sin_nulos('diagnosticos', 'id_consulta_cab'); END $$;
ALTER TABLE diagnosticos ADD CONSTRAINT fk_diag_consulta
    FOREIGN KEY (id_consulta_cab) REFERENCES consultas_cab(id_consulta_cab) ON DELETE RESTRICT;
CREATE INDEX idx_diag_consulta ON diagnosticos (id_consulta_cab);
ALTER TABLE diagnosticos DROP COLUMN id_consulta_detalle;
ALTER TABLE diagnosticos DROP COLUMN sintomas;

-- ---------------------------------------------------------------------
-- 2. odontograma: se asocia a la consulta, no al funcionario
--    Código: guardar id_consulta_cab al crear el odontograma.
--    Los registros existentes se asocian a la consulta del mismo
--    paciente y médico con la fecha más cercana.
-- ---------------------------------------------------------------------
ALTER TABLE odontograma ADD COLUMN id_consulta_cab int4;
UPDATE odontograma o
   SET id_consulta_cab = (
		SELECT c.id_consulta_cab
		  FROM consultas_cab c
		 WHERE c.id_paciente = o.id_paciente
		   AND c.id_medico = o.id_medico
		 ORDER BY abs(c.fecha_cita - o.fecha_registro), c.id_consulta_cab DESC
		 LIMIT 1);
DO $$ BEGIN PERFORM pg_temp.exigir_sin_nulos('odontograma', 'id_consulta_cab'); END $$;
ALTER TABLE odontograma ADD CONSTRAINT odontograma_id_consulta_cab_fkey
    FOREIGN KEY (id_consulta_cab) REFERENCES consultas_cab(id_consulta_cab) ON DELETE RESTRICT;
CREATE INDEX idx_odontograma_consulta ON odontograma (id_consulta_cab);
ALTER TABLE odontograma DROP COLUMN id_funcionario;

-- ---------------------------------------------------------------------
-- 3. consultas_cab.id_funcionario obligatorio
--    Código: completarlo siempre con el funcionario de la sesión.
-- ---------------------------------------------------------------------
DO $$ BEGIN PERFORM pg_temp.exigir_sin_nulos('consultas_cab', 'id_funcionario'); END $$;

-- ---------------------------------------------------------------------
-- 4. estado_dental: "estado" -> "activo" (mismo estándar)
--    Código: cambiar estado_dental.estado por estado_dental.activo.
-- ---------------------------------------------------------------------
UPDATE estado_dental SET estado = true WHERE estado IS NULL;
ALTER TABLE estado_dental RENAME COLUMN estado TO activo;
ALTER TABLE estado_dental ALTER COLUMN activo SET NOT NULL;

-- ---------------------------------------------------------------------
-- 5. permisos: se valida por id_menu (la columna ventana queda vieja)
--    Código: el decorador de permisos busca por menu.clave / id_menu.
-- ---------------------------------------------------------------------
ALTER TABLE permisos DROP COLUMN ventana;

COMMIT;
