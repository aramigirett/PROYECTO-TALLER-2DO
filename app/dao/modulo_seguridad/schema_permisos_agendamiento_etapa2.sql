-- Permisos de Paciente, Médico y Funcionario (etapa 2 de la migración de Agendamiento). Idempotente; se corre como postgres (PGCLIENTENCODING=UTF8).
-- Regla de negocio: Médico y Funcionario los gestiona el ADMINISTRADOR (bypass, sin filas); Medico y Recepcion solo los VEN.
-- Paciente: Recepción ver, nuevo y editar; Médico solo ve; anular solo el Administrador. Define el conjunto COMPLETO de estas 3 ventanas para
-- los roles Medico y Recepcion (quita lo que sobra e inserta lo que falta) y no toca ningún otro rol ni ventana. Se audita solo si algo cambia.
BEGIN;

CREATE TEMP TABLE _perm_objetivo (rol VARCHAR(30), ventana VARCHAR(40), accion VARCHAR(20)) ON COMMIT DROP;
INSERT INTO _perm_objetivo VALUES
    ('Medico', 'paciente', 'ver'), ('Medico', 'medico', 'ver'), ('Medico', 'funcionario', 'ver'),
    ('Recepcion', 'paciente', 'ver'), ('Recepcion', 'paciente', 'nuevo'), ('Recepcion', 'paciente', 'editar'),
    ('Recepcion', 'medico', 'ver'), ('Recepcion', 'funcionario', 'ver');

DO $$
DECLARE
    v_ventanas TEXT[] := ARRAY['paciente','medico','funcionario'];
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
                    format('Permisos de Paciente, Médico y Funcionario del rol %s: %s quitados, %s agregados (script schema_permisos_agendamiento_etapa2.sql)',
                           r.nombre_rol, v_quitados, v_agregados),
                    NULL, 'Módulo Seguridad',
                    jsonb_build_object('Permisos quitados', v_quitados), jsonb_build_object('Permisos agregados', v_agregados));
        END IF;
    END LOOP;
END $$;

COMMIT;
