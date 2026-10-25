-- Permisos clínicos por rol (etapa 3 de la migración de Consultorio). Idempotente; se corre como postgres (PGCLIENTENCODING=UTF8).
--
-- Regla de negocio: los movimientos clínicos los carga el MÉDICO (el usuario vinculado a un médico y, además, el médico de esa consulta: eso lo
-- valida el servidor). Recepción registra, cancela y anula consultas y solo VE las fichas. Este script define el conjunto COMPLETO de las ventanas
-- clínicas para los roles Medico y Recepcion (quita lo que sobra e inserta lo que falta) y no toca ningún otro rol ni ventana.
-- Además pasa al rol Medico a los usuarios vinculados a un médico que tuvieran rol Recepcion. Todo queda auditado en `auditoria_cambios`
-- (solo cuando algo cambia de verdad, así que volver a correrlo no genera nada).
BEGIN;

CREATE TEMP TABLE _perm_objetivo (rol VARCHAR(30), ventana VARCHAR(40), accion VARCHAR(20)) ON COMMIT DROP;
INSERT INTO _perm_objetivo VALUES
    -- Médico: ve y cambia el estado de la consulta; carga todo lo clínico
    ('Medico', 'consulta', 'ver'), ('Medico', 'consulta', 'estado'),
    ('Medico', 'fichamedica', 'ver'), ('Medico', 'fichamedica', 'nuevo'), ('Medico', 'fichamedica', 'editar'), ('Medico', 'fichamedica', 'anular'),
    ('Medico', 'diagnostico', 'ver'), ('Medico', 'diagnostico', 'nuevo'), ('Medico', 'diagnostico', 'anular'),
    ('Medico', 'odontograma', 'ver'), ('Medico', 'odontograma', 'nuevo'), ('Medico', 'odontograma', 'editar'), ('Medico', 'odontograma', 'anular'),
    ('Medico', 'tratamiento', 'ver'), ('Medico', 'tratamiento', 'nuevo'), ('Medico', 'tratamiento', 'anular'), ('Medico', 'tratamiento', 'estado'),
    ('Medico', 'sesiontratamiento', 'ver'), ('Medico', 'sesiontratamiento', 'nuevo'), ('Medico', 'sesiontratamiento', 'anular'),
    ('Medico', 'receta', 'ver'), ('Medico', 'receta', 'nuevo'), ('Medico', 'receta', 'anular'),
    ('Medico', 'ordenestudio', 'ver'), ('Medico', 'ordenestudio', 'nuevo'), ('Medico', 'ordenestudio', 'anular'), ('Medico', 'ordenestudio', 'estado'),
    ('Medico', 'ordenanalisis', 'ver'), ('Medico', 'ordenanalisis', 'nuevo'), ('Medico', 'ordenanalisis', 'anular'), ('Medico', 'ordenanalisis', 'estado'),
    ('Medico', 'justificativomedico', 'ver'), ('Medico', 'justificativomedico', 'nuevo'), ('Medico', 'justificativomedico', 'anular'),
    -- Recepción: registra, cancela (estado) y anula consultas; de lo clínico solo ve las fichas
    ('Recepcion', 'consulta', 'ver'), ('Recepcion', 'consulta', 'nuevo'), ('Recepcion', 'consulta', 'estado'), ('Recepcion', 'consulta', 'anular'),
    ('Recepcion', 'fichamedica', 'ver');

DO $$
DECLARE
    v_ventanas TEXT[] := ARRAY['consulta','fichamedica','diagnostico','odontograma','tratamiento','sesiontratamiento','receta',
                               'ordenestudio','ordenanalisis','justificativomedico'];
    r RECORD;
    v_quitados INT;
    v_agregados INT;
    v_rol_medico INT := (SELECT id_rol FROM roles WHERE nombre_rol = 'Medico');
BEGIN
    IF v_rol_medico IS NULL THEN
        RAISE EXCEPTION 'No existe el rol Medico.';
    END IF;

    FOR r IN SELECT id_rol, nombre_rol FROM roles WHERE nombre_rol IN ('Medico', 'Recepcion') ORDER BY nombre_rol LOOP
        -- quita lo que sobra
        WITH sobra AS (
            DELETE FROM permisos p USING menu m
             WHERE p.id_menu = m.id_menu AND p.id_rol = r.id_rol AND m.clave = ANY (v_ventanas)
               AND NOT EXISTS (SELECT 1 FROM _perm_objetivo o WHERE o.rol = r.nombre_rol AND o.ventana = m.clave AND o.accion = p.accion)
            RETURNING 1)
        SELECT COUNT(*) INTO v_quitados FROM sobra;
        -- agrega lo que falta
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
                    format('Permisos clínicos de Consultorio del rol %s: %s quitados, %s agregados (script schema_permisos_consultorio_roles.sql)',
                           r.nombre_rol, v_quitados, v_agregados),
                    NULL, 'Módulo Seguridad',
                    jsonb_build_object('Permisos quitados', v_quitados), jsonb_build_object('Permisos agregados', v_agregados));
        END IF;
    END LOOP;

    -- los usuarios vinculados a un médico deben tener el rol Medico
    FOR r IN SELECT u.id_usuario FROM usuarios u JOIN roles ro ON ro.id_rol = u.id_rol
              WHERE u.id_medico IS NOT NULL AND ro.nombre_rol = 'Recepcion' ORDER BY u.id_usuario LOOP
        UPDATE usuarios SET id_rol = v_rol_medico WHERE id_usuario = r.id_usuario;
        INSERT INTO auditoria_cambios (id_usuario, entidad, id_registro, accion, detalle, ip, modulo, valores_anteriores, valores_nuevos)
        VALUES (NULL, 'usuarios', r.id_usuario, 'MODIFICACION',
                'Rol: Recepcion -> Medico (usuario vinculado a un médico; script schema_permisos_consultorio_roles.sql)',
                NULL, 'Módulo Seguridad', jsonb_build_object('Rol', 'Recepcion'), jsonb_build_object('Rol', 'Medico'));
    END LOOP;
END $$;

COMMIT;
