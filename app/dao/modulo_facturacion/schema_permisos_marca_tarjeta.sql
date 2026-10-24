-- Módulo Facturación: ventana 'marcatarjeta' (Mantener Marca de Tarjeta).
-- Los roles no-Administrador la reciben completa. Idempotente.
INSERT INTO permisos (id_rol, id_menu, accion)
SELECT x.id_rol, m.id_menu, x.accion
FROM (
SELECT r.id_rol, v.ventana, v.accion
FROM roles r
CROSS JOIN (VALUES
    ('marcatarjeta', 'ver'), ('marcatarjeta', 'nuevo'),
    ('marcatarjeta', 'editar'), ('marcatarjeta', 'anular')
) AS v(ventana, accion)
WHERE r.nombre_rol <> 'Administrador'
) AS x(id_rol, ventana, accion)
JOIN menu m ON m.clave = x.ventana AND m.activo = true
ON CONFLICT (id_rol, id_menu, accion) DO NOTHING;
