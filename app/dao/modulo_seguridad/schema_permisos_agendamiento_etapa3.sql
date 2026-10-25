-- Permisos de los movimientos de Agendamiento (etapa 3 de la migración a Tabler). Idempotente; se corre como postgres (PGCLIENTENCODING=UTF8).
-- Regla de negocio: Agenda, Cita y Avisos los opera RECEPCIÓN con todas las acciones de la ventana (ver, nuevo, anular y estado); el Médico solo ve
-- (y en Cita además cambia el estado). Historial Médico del Paciente: Recepción SIN acceso; el Médico lee, crea y anula (solo de sus pacientes
-- atendidos: lo valida el servidor); el Administrador solo lee. Define el conjunto COMPLETO de estas 4 ventanas para los roles Medico y Recepcion
-- (quita lo que sobra e inserta lo que falta) y no toca ningún otro rol ni ventana. Se audita solo si algo cambia.
BEGIN;

CREATE TEMP TABLE _perm_objetivo (rol VARCHAR(30), ventana VARCHAR(40), accion VARCHAR(20)) ON COMMIT DROP;
INSERT INTO _perm_objetivo VALUES
    ('Recepcion', 'agenda', 'ver'), ('Recepcion', 'agenda', 'nuevo'), ('Recepcion', 'agenda', 'anular'),
    ('Recepcion', 'cita', 'ver'), ('Recepcion', 'cita', 'nuevo'), ('Recepcion', 'cita', 'anular'), ('Recepcion', 'cita', 'estado'),
    ('Recepcion', 'avisos', 'ver'), ('Recepcion', 'avisos', 'nuevo'), ('Recepcion', 'avisos', 'anular'), ('Recepcion', 'avisos', 'estado'),
    ('Medico', 'agenda', 'ver'), ('Medico', 'cita', 'ver'), ('Medico', 'cita', 'estado'), ('Medico', 'avisos', 'ver'),
    ('Medico', 'historial', 'ver'), ('Medico', 'historial', 'nuevo'), ('Medico', 'historial', 'anular');

DO $$
DECLARE
    v_ventanas TEXT[] := ARRAY['agenda','cita','avisos','historial'];
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
                    format('Permisos de Agenda, Cita, Avisos e Historial del rol %s: %s quitados, %s agregados (script schema_permisos_agendamiento_etapa3.sql)',
                           r.nombre_rol, v_quitados, v_agregados),
                    NULL, 'Módulo Seguridad',
                    jsonb_build_object('Permisos quitados', v_quitados), jsonb_build_object('Permisos agregados', v_agregados));
        END IF;
    END LOOP;
END $$;

COMMIT;
