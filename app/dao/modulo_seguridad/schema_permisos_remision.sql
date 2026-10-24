-- Permisos de la ventana "remision" (Registrar Nota de Remisión). Idempotente.
-- Orden: schema_permisos_id_menu.sql (trigger que completa permisos.id_menu) -> este script -> schema_permisos_cajero.sql.
-- Solo el rol Cajero recibe permisos por este seed (ver, nuevo, anular); el Administrador pasa siempre.
-- (schema_permisos_cajero.sql define el conjunto completo del Cajero e incluye esta ventana.)

-- La ventana necesita su fila en `menu` (tabla del DER; clave = ventana del catálogo).
INSERT INTO menu (clave, descripcion, orden)
SELECT 'remision', 'Nota de Remisión', COALESCE((SELECT MAX(orden) FROM menu), 0) + 1
WHERE NOT EXISTS (SELECT 1 FROM menu WHERE clave = 'remision' AND activo = true);

INSERT INTO permisos (id_rol, id_menu, accion)
SELECT x.id_rol, m.id_menu, x.accion
FROM (
SELECT r.id_rol, v.ventana, v.accion
FROM roles r
CROSS JOIN (VALUES
    ('remision', 'ver'), ('remision', 'nuevo'), ('remision', 'anular')
) AS v(ventana, accion)
WHERE r.nombre_rol = 'Cajero'
) AS x(id_rol, ventana, accion)
JOIN menu m ON m.clave = x.ventana AND m.activo = true
ON CONFLICT (id_rol, id_menu, accion) DO NOTHING;
