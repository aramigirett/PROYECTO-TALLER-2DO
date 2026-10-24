-- Permisos de la ventana "cuentabancaria" (Mantener Cuenta Bancaria, referencial de Facturación). Idempotente.
-- Orden: schema_permisos_id_menu.sql -> este script -> schema_permisos_cajero.sql. Reactivar usa el permiso 'editar'.
-- El Cajero solo VE (lo define schema_permisos_cajero.sql); el Administrador pasa siempre. Este seed no da nada a los demás roles.

-- La ventana necesita su fila en `menu` (tabla del DER; clave = ventana del catálogo).
INSERT INTO menu (clave, descripcion, orden)
SELECT 'cuentabancaria', 'Cuenta Bancaria', COALESCE((SELECT MAX(orden) FROM menu), 0) + 1
WHERE NOT EXISTS (SELECT 1 FROM menu WHERE clave = 'cuentabancaria' AND activo = true);

INSERT INTO permisos (id_rol, id_menu, accion)
SELECT x.id_rol, m.id_menu, x.accion
FROM (
SELECT r.id_rol, 'cuentabancaria', 'ver'
FROM roles r
WHERE r.nombre_rol = 'Cajero'
) AS x(id_rol, ventana, accion)
JOIN menu m ON m.clave = x.ventana AND m.activo = true
ON CONFLICT (id_rol, id_menu, accion) DO NOTHING;
