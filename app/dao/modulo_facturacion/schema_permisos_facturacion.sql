-- Módulo Facturación: ventana 'formacobro' (Mantener Forma de Cobro).
-- Los roles no-Administrador la reciben completa, igual que las demás referenciales.
-- Administrador no necesita filas (bypass en puede()). Idempotente.
INSERT INTO permisos (id_rol, ventana, accion)
SELECT r.id_rol, v.ventana, v.accion
FROM roles r
CROSS JOIN (VALUES
    ('formacobro', 'ver'), ('formacobro', 'nuevo'),
    ('formacobro', 'editar'), ('formacobro', 'anular')
) AS v(ventana, accion)
WHERE r.nombre_rol <> 'Administrador'
ON CONFLICT (id_rol, ventana, accion) DO NOTHING;
