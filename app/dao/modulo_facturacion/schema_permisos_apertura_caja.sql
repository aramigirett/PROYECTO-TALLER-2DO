-- Módulo Facturación: ventana 'aperturacaja' (Registrar Apertura y Cierre de Caja).
-- Acciones: ver, nuevo (abrir), anular, estado (cerrar). Son movimientos de dinero: SOLO el rol Cajero las recibe
-- (el Administrador pasa siempre). Recepción y Médico se pueden habilitar desde la matriz de Roles y Permisos.
-- Idempotente.
INSERT INTO permisos (id_rol, id_menu, accion)
SELECT x.id_rol, m.id_menu, x.accion
FROM (
SELECT r.id_rol, 'aperturacaja', a.accion
FROM roles r
CROSS JOIN (VALUES ('ver'), ('nuevo'), ('anular'), ('estado')) AS a(accion)
WHERE r.nombre_rol = 'Cajero'
) AS x(id_rol, ventana, accion)
JOIN menu m ON m.clave = x.ventana AND m.activo = true
ON CONFLICT (id_rol, id_menu, accion) DO NOTHING;
