-- Módulo Facturación: ventanas 'entidademisora' y 'entidadadherida'.
-- Los roles no-Administrador las reciben completas. Idempotente.
INSERT INTO permisos (id_rol, ventana, accion)
SELECT r.id_rol, v.ventana, a.accion
FROM roles r
CROSS JOIN (VALUES ('entidademisora'), ('entidadadherida')) AS v(ventana)
CROSS JOIN (VALUES ('ver'), ('nuevo'), ('editar'), ('anular')) AS a(accion)
WHERE r.nombre_rol <> 'Administrador'
ON CONFLICT (id_rol, ventana, accion) DO NOTHING;
