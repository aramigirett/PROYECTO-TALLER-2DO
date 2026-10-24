-- Permisos de la ventana "cobro" (Registrar Cobranzas por Forma de Cobro). Idempotente.
-- Orden: schema_permisos_id_menu.sql (trigger que completa permisos.id_menu) -> este script -> schema_permisos_cajero.sql.
-- Solo el rol Cajero recibe permisos por este seed (ver, nuevo, anular), según la regla del Cajero de CLAUDE.md;
-- el Administrador pasa siempre. (schema_permisos_cajero.sql define el conjunto completo del Cajero e incluye esta ventana.)

-- La ventana necesita su fila en `menu` (tabla del DER; clave = ventana del catálogo, igual que las otras 44).
INSERT INTO menu (clave, descripcion, orden)
SELECT 'cobro', 'Cobro', COALESCE((SELECT MAX(orden) FROM menu), 0) + 1
WHERE NOT EXISTS (SELECT 1 FROM menu WHERE clave = 'cobro' AND activo = true);

INSERT INTO permisos (id_rol, id_menu, accion)
SELECT x.id_rol, m.id_menu, x.accion
FROM (
SELECT r.id_rol, v.ventana, v.accion
FROM roles r
CROSS JOIN (VALUES
    ('cobro', 'ver'), ('cobro', 'nuevo'), ('cobro', 'anular')
) AS v(ventana, accion)
WHERE r.nombre_rol = 'Cajero'
) AS x(id_rol, ventana, accion)
JOIN menu m ON m.clave = x.ventana AND m.activo = true
ON CONFLICT (id_rol, id_menu, accion) DO NOTHING;
