-- Permisos de la ventana "arqueo" (Registrar Arqueo de Caja con Recaudación a depositar). Idempotente.
-- Orden: schema_permisos_id_menu.sql (trigger que completa permisos.id_menu) -> este script -> schema_permisos_cajero.sql.
-- El rol Cajero recibe ver, nuevo, anular y estado ("estado" = marcar la recaudación como depositada); el Administrador pasa siempre.
-- Nadie puede arquear su propia caja: lo valida el servidor y sp_registrar_arqueo (no depende de los permisos).

-- La ventana necesita su fila en `menu` (tabla del DER; clave = ventana del catálogo).
INSERT INTO menu (clave, descripcion, orden)
SELECT 'arqueo', 'Arqueo de Caja', COALESCE((SELECT MAX(orden) FROM menu), 0) + 1
WHERE NOT EXISTS (SELECT 1 FROM menu WHERE clave = 'arqueo' AND activo = true);

INSERT INTO permisos (id_rol, ventana, accion)
SELECT r.id_rol, v.ventana, v.accion
FROM roles r
CROSS JOIN (VALUES ('arqueo', 'ver'), ('arqueo', 'nuevo'), ('arqueo', 'anular'), ('arqueo', 'estado')) AS v(ventana, accion)
WHERE r.nombre_rol = 'Cajero'
ON CONFLICT (id_rol, ventana, accion) DO NOTHING;
