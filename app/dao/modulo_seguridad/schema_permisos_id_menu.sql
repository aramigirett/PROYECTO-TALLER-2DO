-- OBSOLETO desde la migración 02 (migraciones/02_migracion_requiere_codigo.sql): permisos.ventana ya no existe y los
-- permisos se identifican por permisos.id_menu (FK a menu; menu.clave = ventana del catálogo).
-- Este script ya no crea el trigger de compatibilidad: solo lo elimina si quedara (idempotente).
-- Toda ventana NUEVA del catálogo (menu_catalog.py) necesita su fila en `menu` ANTES de sembrar sus permisos; los seeds
-- insertan por JOIN menu m ON m.clave = <ventana> (ver schema_permisos_cobranzas.sql).
DROP TRIGGER IF EXISTS trg_permisos_resolver_menu ON permisos;
DROP FUNCTION IF EXISTS fn_permisos_resolver_menu();
