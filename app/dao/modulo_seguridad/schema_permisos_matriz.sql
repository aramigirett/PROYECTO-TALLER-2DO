-- ============================================
-- MODULO SEGURIDAD - CUS "Mantener Menú" (criterio "Accesibilidad")
-- permisos pasa de (rol + nombre_permiso libre) a (rol + ventana + accion),
-- alineado 1 a 1 con las claves `ventana` de app/rutas/modulo_seguridad/
-- menu_catalog.py. Habilita control real de acceso por pantalla y por
-- acción (ver/nuevo/editar/anular) -antes `permisos` solo servía para
-- ocultar resultados del buscador general, nunca gateaba una ruta real.
--
-- La FK sigue viviendo en permisos -> roles (Roles tiene Permisos, Permisos
-- no tiene Roles).
--
-- "Roles y Permisos" (la pantalla matriz en sí) NO tiene fila propia acá:
-- queda siempre exclusiva de Administrador vía @require_admin, fuera de
-- este mecanismo, para que nadie pueda autoconcederse acceso.
-- ============================================

-- Las 2 filas que había en permisos eran datos de prueba (nombre_permiso
-- libre "ver_reportes", sin ninguna ventana real detrás) - no representan
-- nada del nuevo modelo, se descartan.
DELETE FROM permisos;

ALTER TABLE permisos
    ADD COLUMN ventana VARCHAR(60),
    ADD COLUMN accion VARCHAR(20);

ALTER TABLE permisos
    ALTER COLUMN ventana SET NOT NULL,
    ALTER COLUMN accion SET NOT NULL;

ALTER TABLE permisos
    ADD CONSTRAINT chk_permiso_accion CHECK (accion IN ('ver', 'nuevo', 'editar', 'anular'));

ALTER TABLE permisos
    DROP CONSTRAINT uq_permiso_rol_nombre;

ALTER TABLE permisos
    ADD CONSTRAINT uq_permiso_rol_ventana_accion UNIQUE (id_rol, ventana, accion);

ALTER TABLE permisos
    DROP COLUMN nombre_permiso,
    DROP COLUMN descripcion;

-- ============================================
-- Seed de compatibilidad: hasta hoy Agendamiento/Referenciales/Consultorio
-- no tenían NINGUNA restricción de rol en el código (cualquier usuario
-- logueado, sea cual sea su rol, entraba a cualquier pantalla). Para no
-- romper ese comportamiento de un día para el otro, se les otorga a los 3
-- roles no-Administrador acceso total a las 28 ventanas que hoy están
-- abiertas. Administrador NO necesita filas: bypassea el check siempre
-- (ver app/rutas/modulo_seguridad/permisos_contexto.py).
--
-- Usuario y Auditoria (antes @require_admin puro) quedan SIN filas acá:
-- por ahora solo Administrador puede verlas/usarlas, igual que hasta hoy.
-- Quedan disponibles en la matriz por si en el futuro se decide delegar
-- alguna de las dos a otro rol.
-- ============================================
INSERT INTO permisos (id_rol, ventana, accion)
SELECT r.id_rol, v.ventana, v.accion
FROM roles r
CROSS JOIN (VALUES
    -- Agendamiento
    ('agenda', 'ver'), ('agenda', 'nuevo'), ('agenda', 'anular'),
    ('cita', 'ver'), ('cita', 'nuevo'), ('cita', 'anular'),
    ('avisos', 'ver'), ('avisos', 'nuevo'), ('avisos', 'anular'),
    ('paciente', 'ver'), ('paciente', 'nuevo'), ('paciente', 'anular'),
    ('funcionario', 'ver'), ('funcionario', 'nuevo'), ('funcionario', 'anular'),
    ('medico', 'ver'), ('medico', 'nuevo'), ('medico', 'anular'),
    -- Referenciales Agendamiento
    ('ciudad', 'ver'), ('ciudad', 'nuevo'), ('ciudad', 'editar'), ('ciudad', 'anular'),
    ('cargo', 'ver'), ('cargo', 'nuevo'), ('cargo', 'editar'), ('cargo', 'anular'),
    ('consultorio', 'ver'), ('consultorio', 'nuevo'), ('consultorio', 'editar'), ('consultorio', 'anular'),
    ('disponibilidad', 'ver'), ('disponibilidad', 'nuevo'), ('disponibilidad', 'editar'), ('disponibilidad', 'anular'),
    ('especialidad', 'ver'), ('especialidad', 'nuevo'), ('especialidad', 'editar'), ('especialidad', 'anular'),
    ('dia', 'ver'), ('dia', 'nuevo'), ('dia', 'editar'), ('dia', 'anular'),
    ('turno', 'ver'), ('turno', 'nuevo'), ('turno', 'editar'), ('turno', 'anular'),
    -- Referenciales Consultorio
    ('tipodiagnostico', 'ver'), ('tipodiagnostico', 'nuevo'), ('tipodiagnostico', 'editar'), ('tipodiagnostico', 'anular'),
    ('sintoma', 'ver'), ('sintoma', 'nuevo'), ('sintoma', 'editar'), ('sintoma', 'anular'),
    ('tipotratamiento', 'ver'), ('tipotratamiento', 'nuevo'), ('tipotratamiento', 'editar'), ('tipotratamiento', 'anular'),
    ('tipoinsumo', 'ver'), ('tipoinsumo', 'nuevo'), ('tipoinsumo', 'editar'), ('tipoinsumo', 'anular'),
    ('tipoprocedimientomedico', 'ver'), ('tipoprocedimientomedico', 'nuevo'), ('tipoprocedimientomedico', 'editar'), ('tipoprocedimientomedico', 'anular'),
    ('medicamento', 'ver'), ('medicamento', 'nuevo'), ('medicamento', 'editar'), ('medicamento', 'anular'),
    ('tipoestudio', 'ver'), ('tipoestudio', 'nuevo'), ('tipoestudio', 'editar'), ('tipoestudio', 'anular'),
    ('tipoanalisis', 'ver'), ('tipoanalisis', 'nuevo'), ('tipoanalisis', 'editar'), ('tipoanalisis', 'anular'),
    -- Módulo Consultorio
    ('consulta', 'ver'), ('consulta', 'nuevo'), ('consulta', 'anular'),
    ('fichamedica', 'ver'), ('fichamedica', 'editar'), ('fichamedica', 'anular'),
    ('diagnostico', 'ver'), ('diagnostico', 'nuevo'), ('diagnostico', 'anular'),
    ('historial', 'ver'), ('historial', 'nuevo'), ('historial', 'anular'),
    ('odontograma', 'ver'), ('odontograma', 'nuevo'), ('odontograma', 'anular'),
    ('tratamiento', 'ver'), ('tratamiento', 'nuevo'), ('tratamiento', 'anular'),
    ('receta', 'ver'), ('receta', 'nuevo'), ('receta', 'anular'),
    ('ordenestudio', 'ver'), ('ordenestudio', 'nuevo'), ('ordenestudio', 'anular'),
    ('ordenanalisis', 'ver'), ('ordenanalisis', 'nuevo'), ('ordenanalisis', 'anular'),
    ('justificativomedico', 'ver'), ('justificativomedico', 'nuevo'), ('justificativomedico', 'anular')
) AS v(ventana, accion)
WHERE r.nombre_rol <> 'Administrador';
