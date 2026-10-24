-- Permisos de la ventana "pedidocliente" (Registrar Pedido Cliente). Idempotente.
-- Solo el rol Cajero recibe permisos por este seed (ver, nuevo, anular), según la regla del Cajero de CLAUDE.md;
-- el Administrador pasa siempre. Recepción/Médico se habilitan desde la matriz de Roles y Permisos si hace falta.
-- (schema_permisos_cajero.sql define el conjunto completo del Cajero e incluye esta ventana.)
INSERT INTO permisos (id_rol, id_menu, accion)
SELECT x.id_rol, m.id_menu, x.accion
FROM (
SELECT r.id_rol, v.ventana, v.accion
FROM roles r
CROSS JOIN (VALUES
    ('pedidocliente', 'ver'), ('pedidocliente', 'nuevo'), ('pedidocliente', 'anular')
) AS v(ventana, accion)
WHERE r.nombre_rol = 'Cajero'
) AS x(id_rol, ventana, accion)
JOIN menu m ON m.clave = x.ventana AND m.activo = true
ON CONFLICT (id_rol, id_menu, accion) DO NOTHING;
