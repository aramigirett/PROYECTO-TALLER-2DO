-- Permisos de la ventana "notacd" (Registrar Notas de Crédito y Débito). Idempotente.
-- Orden: schema_permisos_id_menu.sql (trigger que completa permisos.id_menu) -> este script -> schema_permisos_cajero.sql.
-- Solo el rol Cajero recibe permisos por este seed (ver, nuevo, anular); el Administrador pasa siempre.
-- (schema_permisos_cajero.sql define el conjunto completo del Cajero e incluye esta ventana.)

-- La ventana necesita su fila en `menu` (tabla del DER; clave = ventana del catálogo).
INSERT INTO menu (clave, descripcion, orden)
SELECT 'notacd', 'Notas de Crédito y Débito', COALESCE((SELECT MAX(orden) FROM menu), 0) + 1
WHERE NOT EXISTS (SELECT 1 FROM menu WHERE clave = 'notacd' AND activo = true);

INSERT INTO permisos (id_rol, ventana, accion)
SELECT r.id_rol, v.ventana, v.accion
FROM roles r
CROSS JOIN (VALUES
    ('notacd', 'ver'), ('notacd', 'nuevo'), ('notacd', 'anular')
) AS v(ventana, accion)
WHERE r.nombre_rol = 'Cajero'
ON CONFLICT (id_rol, ventana, accion) DO NOTHING;
