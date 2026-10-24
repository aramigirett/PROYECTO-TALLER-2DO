-- Permisos de la ventana "pedidocliente" (Registrar Pedido Cliente). Idempotente.
-- Solo el rol Cajero recibe permisos por este seed (ver, nuevo, anular), según la regla del Cajero de CLAUDE.md;
-- el Administrador pasa siempre. Recepción/Médico se habilitan desde la matriz de Roles y Permisos si hace falta.
-- (schema_permisos_cajero.sql define el conjunto completo del Cajero e incluye esta ventana.)
INSERT INTO permisos (id_rol, ventana, accion)
SELECT r.id_rol, v.ventana, v.accion
FROM roles r
CROSS JOIN (VALUES
    ('pedidocliente', 'ver'), ('pedidocliente', 'nuevo'), ('pedidocliente', 'anular')
) AS v(ventana, accion)
WHERE r.nombre_rol = 'Cajero'
ON CONFLICT (id_rol, ventana, accion) DO NOTHING;
