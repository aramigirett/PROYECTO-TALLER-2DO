-- =====================================================================
-- OdontoClinic - Migración 02: cambios que REQUIEREN ajustar el código
-- ---------------------------------------------------------------------
-- Correr DESPUÉS de 01_migracion_der.sql, con postgres (TEST_DB_*) y
-- DESPUÉS de hacer backup (scripts/backup_db.py). El código de la rama
-- migracion-02 ya usa los nombres nuevos.
-- IDEMPOTENTE (cada bloque se saltea si ya está aplicado) y en UNA sola
-- transacción: si algo falla o encuentra datos que no puede completar,
-- se detiene y no cambia nada.
-- Decisiones de negocio aprobadas:
--   * Diagnósticos 2 y 10 y odontogramas 8 y 9 (datos de prueba, sin
--     consulta vinculable del mismo médico): se borran con sus filas
--     dependientes. Si hubiera OTRAS filas sin migrar, la migración corta.
--   * consultas_cab 6 y 17 sin funcionario: se les asigna el funcionario 3.
--   * Odontograma: uno por consulta (único parcial mientras no esté Inactivo;
--     la tabla no tiene `activo`, su baja lógica es estado = 'Inactivo').
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

-- Función auxiliar: corta la migración si una columna tiene nulos; si no, la vuelve NOT NULL
CREATE OR REPLACE FUNCTION pg_temp.exigir_sin_nulos(p_tabla text, p_columna text) RETURNS void
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
--    Los síntomas pasan a diagnostico_sintoma (el texto libre se elimina).
-- ---------------------------------------------------------------------
DO $$
BEGIN
	IF EXISTS (SELECT 1 FROM information_schema.columns
	           WHERE table_name = 'diagnosticos' AND column_name = 'id_consulta_detalle') THEN
		ALTER TABLE diagnosticos ADD COLUMN IF NOT EXISTS id_consulta_cab int4;
		UPDATE diagnosticos d
		   SET id_consulta_cab = cd.id_consulta_cab
		  FROM consultas_detalle cd
		 WHERE cd.id_consulta_detalle = d.id_consulta_detalle
		   AND d.id_consulta_cab IS NULL;
		-- datos de prueba aprobados para borrar (sin consulta vinculable); diagnostico_sintoma cae por CASCADE
		-- y el resto de las FK es RESTRICT: si alguien los usara, la migración corta.
		DELETE FROM diagnosticos WHERE id_consulta_cab IS NULL AND id_diagnostico IN (2, 10);
		PERFORM pg_temp.exigir_sin_nulos('diagnosticos', 'id_consulta_cab');
		IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_diag_consulta') THEN
			ALTER TABLE diagnosticos ADD CONSTRAINT fk_diag_consulta
			    FOREIGN KEY (id_consulta_cab) REFERENCES consultas_cab(id_consulta_cab) ON DELETE RESTRICT;
		END IF;
		ALTER TABLE diagnosticos DROP COLUMN id_consulta_detalle;
	END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_diag_consulta ON diagnosticos (id_consulta_cab);
ALTER TABLE diagnosticos DROP COLUMN IF EXISTS sintomas;

-- ---------------------------------------------------------------------
-- 2. odontograma: se asocia a la consulta, no al funcionario
--    Un odontograma por consulta (mientras no esté Inactivo).
-- ---------------------------------------------------------------------
DO $$
BEGIN
	IF EXISTS (SELECT 1 FROM information_schema.columns
	           WHERE table_name = 'odontograma' AND column_name = 'id_funcionario') THEN
		ALTER TABLE odontograma ADD COLUMN IF NOT EXISTS id_consulta_cab int4;
		-- mismo paciente y médico, con la consulta de fecha más cercana
		UPDATE odontograma o
		   SET id_consulta_cab = (
				SELECT c.id_consulta_cab
				  FROM consultas_cab c
				 WHERE c.id_paciente = o.id_paciente
				   AND c.id_medico = o.id_medico
				 ORDER BY abs(c.fecha_cita - o.fecha_registro), c.id_consulta_cab DESC
				 LIMIT 1)
		 WHERE o.id_consulta_cab IS NULL;
		-- datos de prueba aprobados para borrar (médico sin consulta propia del paciente)
		DELETE FROM odontograma_detalle
		 WHERE id_odontograma IN (SELECT id_odontograma FROM odontograma
		                           WHERE id_consulta_cab IS NULL AND id_odontograma IN (8, 9));
		DELETE FROM odontograma WHERE id_consulta_cab IS NULL AND id_odontograma IN (8, 9);
		PERFORM pg_temp.exigir_sin_nulos('odontograma', 'id_consulta_cab');
		IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'odontograma_id_consulta_cab_fkey') THEN
			ALTER TABLE odontograma ADD CONSTRAINT odontograma_id_consulta_cab_fkey
			    FOREIGN KEY (id_consulta_cab) REFERENCES consultas_cab(id_consulta_cab) ON DELETE RESTRICT;
		END IF;
		ALTER TABLE odontograma DROP COLUMN id_funcionario;
	END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_odontograma_consulta ON odontograma (id_consulta_cab);
-- uno por consulta: un odontograma Inactivo no impide crear otro para la misma consulta
CREATE UNIQUE INDEX IF NOT EXISTS ux_odontograma_consulta_vigente
    ON odontograma (id_consulta_cab) WHERE estado <> 'Inactivo';

-- ---------------------------------------------------------------------
-- 3. consultas_cab.id_funcionario obligatorio
--    Las consultas 6 y 17 (sin funcionario) quedan con el funcionario 3.
-- ---------------------------------------------------------------------
DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM funcionario WHERE id_funcionario = 3) THEN
		RAISE EXCEPTION 'No existe el funcionario 3 para completar consultas_cab.id_funcionario.';
	END IF;
	UPDATE consultas_cab SET id_funcionario = 3
	 WHERE id_funcionario IS NULL AND id_consulta_cab IN (6, 17);
	PERFORM pg_temp.exigir_sin_nulos('consultas_cab', 'id_funcionario');
END $$;

-- ---------------------------------------------------------------------
-- 4. estado_dental: "estado" -> "activo" (mismo estándar)
-- ---------------------------------------------------------------------
DO $$
BEGIN
	IF EXISTS (SELECT 1 FROM information_schema.columns
	           WHERE table_name = 'estado_dental' AND column_name = 'estado') THEN
		UPDATE estado_dental SET estado = true WHERE estado IS NULL;
		ALTER TABLE estado_dental RENAME COLUMN estado TO activo;
	END IF;
	ALTER TABLE estado_dental ALTER COLUMN activo SET DEFAULT true;
	ALTER TABLE estado_dental ALTER COLUMN activo SET NOT NULL;
END $$;

-- ---------------------------------------------------------------------
-- 5. permisos: se valida por id_menu (menu.clave); la columna ventana se elimina
--    Antes se verifica que id_menu coincida con la ventana en TODAS las filas,
--    para no perder ni cambiar ningún permiso. El trigger de compatibilidad
--    (leía NEW.ventana) deja de tener sentido.
-- ---------------------------------------------------------------------
DO $$
DECLARE v_mal int;
BEGIN
	IF EXISTS (SELECT 1 FROM information_schema.columns
	           WHERE table_name = 'permisos' AND column_name = 'ventana') THEN
		SELECT count(*) INTO v_mal
		  FROM permisos p LEFT JOIN menu m ON m.id_menu = p.id_menu
		 WHERE m.id_menu IS NULL OR m.clave <> p.ventana;
		IF v_mal > 0 THEN
			RAISE EXCEPTION 'permisos: % fila(s) con id_menu que no coincide con su ventana. Corregirlas antes de seguir.', v_mal;
		END IF;
		DROP TRIGGER IF EXISTS trg_permisos_resolver_menu ON permisos;
		DROP FUNCTION IF EXISTS fn_permisos_resolver_menu();
		ALTER TABLE permisos DROP COLUMN ventana;   -- arrastra uq_permiso_rol_ventana_accion
	END IF;
END $$;

COMMIT;
