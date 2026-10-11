-- Módulo Facturación: ventana 'marcatarjeta' (Mantener Marca de Tarjeta).
-- Los roles no-Administrador la reciben completa. Idempotente.
INSERT INTO permisos (id_rol, ventana, accion)
SELECT r.id_rol, v.ventana, v.accion
FROM roles r
CROSS JOIN (VALUES
    ('marcatarjeta', 'ver'), ('marcatarjeta', 'nuevo'),
    ('marcatarjeta', 'editar'), ('marcatarjeta', 'anular')
) AS v(ventana, accion)
WHERE r.nombre_rol <> 'Administrador'
ON CONFLICT (id_rol, ventana, accion) DO NOTHING;
