-- Quinta acción de permisos: 'estado' (cambios de estado del flujo: estado de
-- cita, confirmación/envío de avisos; a futuro Actualizar Estado de órdenes y
-- Finalizar Tratamiento en Consultorio). Idempotente.
ALTER TABLE permisos DROP CONSTRAINT IF EXISTS chk_permiso_accion;
ALTER TABLE permisos
    ADD CONSTRAINT chk_permiso_accion CHECK (accion IN ('ver', 'nuevo', 'editar', 'anular', 'estado'));

-- Los roles no-Administrador ya hacen hoy ese flujo en Cita y Avisos: se les
-- otorga para no cortarlo.
INSERT INTO permisos (id_rol, ventana, accion)
SELECT r.id_rol, v.ventana, 'estado'
FROM roles r
CROSS JOIN (VALUES ('cita'), ('avisos')) AS v(ventana)
WHERE r.nombre_rol <> 'Administrador'
ON CONFLICT (id_rol, ventana, accion) DO NOTHING;
