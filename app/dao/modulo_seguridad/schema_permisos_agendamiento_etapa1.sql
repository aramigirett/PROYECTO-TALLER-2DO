-- Permisos de los 7 referenciales de Agendamiento (etapa 1 de la migración a Tabler). Idempotente; se corre como postgres (PGCLIENTENCODING=UTF8).
--
-- Regla de negocio: Ciudad, Cargo, Especialidad, Consultorio, Día y Turno los gestiona el ADMINISTRADOR (bypass, sin filas); Médico y
-- Recepción solo los VEN. Disponibilidad Horaria es operativa: Recepción ver, nuevo, editar y anular; el Médico solo ve. Este script define el
-- conjunto COMPLETO de estas 7 ventanas para los roles Medico y Recepcion (quita lo que sobra e inserta lo que falta) y no toca ningún otro rol
-- ni ventana (el Cajero sigue sin permisos de Agendamiento). Todo queda auditado en `auditoria_cambios` solo si algo cambia.
BEGIN;

CREATE TEMP TABLE _perm_objetivo (rol VARCHAR(30), ventana VARCHAR(40), accion VARCHAR(20)) ON COMMIT DROP;
INSERT INTO _perm_objetivo VALUES
    ('Medico', 'ciudad', 'ver'), ('Medico', 'cargo', 'ver'), ('Medico', 'especialidad', 'ver'), ('Medico', 'consultorio', 'ver'),
    ('Medico', 'dia', 'ver'), ('Medico', 'turno', 'ver'), ('Medico', 'disponibilidad', 'ver'),
    ('Recepcion', 'ciudad', 'ver'), ('Recepcion', 'cargo', 'ver'), ('Recepcion', 'especialidad', 'ver'), ('Recepcion', 'consultorio', 'ver'),
    ('Recepcion', 'dia', 'ver'), ('Recepcion', 'turno', 'ver'),
    ('Recepcion', 'disponibilidad', 'ver'), ('Recepcion', 'disponibilidad', 'nuevo'), ('Recepcion', 'disponibilidad', 'editar'),
    ('Recepcion', 'disponibilidad', 'anular');

DO $$
DECLARE
    v_ventanas TEXT[] := ARRAY['ciudad','cargo','especialidad','consultorio','dia','turno','disponibilidad'];
    r RECORD;
    v_quitados INT;
    v_agregados INT;
BEGIN
    FOR r IN SELECT id_rol, nombre_rol FROM roles WHERE nombre_rol IN ('Medico', 'Recepcion') ORDER BY nombre_rol LOOP
        WITH sobra AS (
            DELETE FROM permisos p USING menu m
             WHERE p.id_menu = m.id_menu AND p.id_rol = r.id_rol AND m.clave = ANY (v_ventanas)
               AND NOT EXISTS (SELECT 1 FROM _perm_objetivo o WHERE o.rol = r.nombre_rol AND o.ventana = m.clave AND o.accion = p.accion)
            RETURNING 1)
        SELECT COUNT(*) INTO v_quitados FROM sobra;
        WITH falta AS (
            INSERT INTO permisos (id_rol, id_menu, accion)
            SELECT r.id_rol, m.id_menu, o.accion
              FROM _perm_objetivo o JOIN menu m ON m.clave = o.ventana AND m.activo = true
             WHERE o.rol = r.nombre_rol
            ON CONFLICT DO NOTHING
            RETURNING 1)
        SELECT COUNT(*) INTO v_agregados FROM falta;

        IF v_quitados > 0 OR v_agregados > 0 THEN
            INSERT INTO auditoria_cambios (id_usuario, entidad, id_registro, accion, detalle, ip, modulo, valores_anteriores, valores_nuevos)
            VALUES (NULL, 'permisos', r.id_rol, 'MODIFICACION',
                    format('Permisos de los referenciales de Agendamiento del rol %s: %s quitados, %s agregados (script schema_permisos_agendamiento_etapa1.sql)',
                           r.nombre_rol, v_quitados, v_agregados),
                    NULL, 'Módulo Seguridad',
                    jsonb_build_object('Permisos quitados', v_quitados), jsonb_build_object('Permisos agregados', v_agregados));
        END IF;
    END LOOP;
END $$;

COMMIT;
