-- Módulo Facturación: ventana 'caja' (Mantener Caja). Reactivar usa el permiso 'editar'.
-- Los roles no-Administrador la reciben completa. Idempotente.
INSERT INTO permisos (id_rol, ventana, accion)
SELECT r.id_rol, 'caja', a.accion
FROM roles r
CROSS JOIN (VALUES ('ver'), ('nuevo'), ('editar'), ('anular')) AS a(accion)
WHERE r.nombre_rol <> 'Administrador'
ON CONFLICT (id_rol, ventana, accion) DO NOTHING;
