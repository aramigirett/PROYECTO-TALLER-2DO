-- Ventana "backup" (Copias de Seguridad, Módulo Seguridad). Idempotente; se corre como postgres.
-- Es EXCLUSIVA del Administrador (menu_catalog: solo_admin): no se siembra ningún permiso para otros roles y la matriz de
-- Roles y Permisos no la muestra. Solo hace falta su fila en `menu` (tabla del DER; clave = ventana del catálogo).
INSERT INTO menu (clave, descripcion, orden)
SELECT 'backup', 'Copias de Seguridad', COALESCE((SELECT MAX(orden) FROM menu), 0) + 1
WHERE NOT EXISTS (SELECT 1 FROM menu WHERE clave = 'backup' AND activo = true);
