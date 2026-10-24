-- Compatibilidad con 01_migracion_der.sql: esa migración creó la tabla `menu` (una fila por ventana; menu.clave = la ventana del
-- catálogo) y volvió OBLIGATORIO permisos.id_menu (FK a menu). Todo el código existente (PermisoDao de Roles y Permisos, los
-- seeds schema_permisos_*.sql y los tests) inserta permisos por (id_rol, ventana, accion), sin id_menu, y fallaba con
-- "el valor nulo en la columna id_menu viola la restricción de no nulo".
-- Solución mínima y reversible (NO modifica ninguna tabla): un trigger BEFORE INSERT que completa id_menu a partir de
-- menu.clave = NEW.ventana cuando no viene informado. Un INSERT que sí informa id_menu no se toca. Idempotente.
--   Revertir: DROP TRIGGER trg_permisos_resolver_menu ON permisos; DROP FUNCTION fn_permisos_resolver_menu();
-- IMPORTANTE: toda ventana NUEVA del catálogo (menu_catalog.py) necesita su fila en `menu` (clave = ventana) ANTES de sembrar sus
-- permisos; los seeds nuevos la insertan con ON CONFLICT DO NOTHING (ver schema_permisos_cobranzas.sql).

CREATE OR REPLACE FUNCTION fn_permisos_resolver_menu() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.id_menu IS NULL THEN
        SELECT id_menu INTO NEW.id_menu FROM menu WHERE clave = NEW.ventana AND activo = true;
        IF NEW.id_menu IS NULL THEN
            RAISE EXCEPTION 'No existe una entrada de menú activa con la clave "%": agréguela a la tabla menu antes de asignar permisos a esa ventana.', NEW.ventana;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
COMMENT ON FUNCTION fn_permisos_resolver_menu() IS 'Completa permisos.id_menu desde menu.clave = ventana cuando el INSERT no lo informa (compatibilidad con el código anterior a la migración del DER).';

DROP TRIGGER IF EXISTS trg_permisos_resolver_menu ON permisos;
CREATE TRIGGER trg_permisos_resolver_menu
    BEFORE INSERT ON permisos
    FOR EACH ROW EXECUTE FUNCTION fn_permisos_resolver_menu();
COMMENT ON TRIGGER trg_permisos_resolver_menu ON permisos IS 'Si el INSERT no trae id_menu, lo toma de menu.clave = ventana.';
