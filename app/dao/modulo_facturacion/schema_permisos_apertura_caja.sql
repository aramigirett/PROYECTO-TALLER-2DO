-- Módulo Facturación: ventana 'aperturacaja' (Registrar Apertura y Cierre de Caja).
-- Acciones: ver, nuevo (abrir), anular, estado (cerrar). Son movimientos de dinero: SOLO el rol Cajero las recibe
-- (el Administrador pasa siempre). Recepción y Médico se pueden habilitar desde la matriz de Roles y Permisos.
-- Idempotente.
INSERT INTO permisos (id_rol, ventana, accion)
SELECT r.id_rol, 'aperturacaja', a.accion
FROM roles r
CROSS JOIN (VALUES ('ver'), ('nuevo'), ('anular'), ('estado')) AS a(accion)
WHERE r.nombre_rol = 'Cajero'
ON CONFLICT (id_rol, ventana, accion) DO NOTHING;
