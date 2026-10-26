-- Migración 05: Agendamiento.
--   1. Historial Médico pasa del módulo "Módulo Consultorio" al módulo "Agendamiento" en la tabla menu (sidebar, buscador y matriz de permisos).
--      El orden dentro de Agendamiento queda al final (70). Los permisos no cambian: se identifican por menu.id_menu, que es el mismo.
--   2. Referencial Día: se agregan SABADO y DOMINGO (si existen anulados, se reactivan).
--   3. Disponibilidad Horaria: el día ya no se elige, se calcula desde dispo_fecha. Las filas existentes cuyo día no coincide con su fecha se
--      corrigen (y también el día copiado en sus horarios de agenda_detalle). Solo si el día correcto existe y está activo en `dias`.
-- Idempotente y en una transacción; se aplica con postgres y PGCLIENTENCODING=UTF8, DESPUÉS de un backup.
BEGIN;

UPDATE menu h
   SET id_menu_padre = p.id_menu, orden = 70
  FROM menu p
 WHERE h.clave = 'historial' AND h.activo
   AND p.id_menu_padre IS NULL AND p.clave IS NULL AND p.activo AND UPPER(p.descripcion) = 'AGENDAMIENTO'
   AND h.id_menu_padre IS DISTINCT FROM p.id_menu;

-- Sábado y domingo
UPDATE dias SET activo = true
 WHERE UPPER(descripcion) IN ('SABADO', 'DOMINGO') AND NOT activo
   AND NOT EXISTS (SELECT 1 FROM dias x WHERE x.activo AND UPPER(x.descripcion) = UPPER(dias.descripcion));
INSERT INTO dias (descripcion)
SELECT v.nombre FROM (VALUES ('SABADO'), ('DOMINGO')) AS v(nombre)
 WHERE NOT EXISTS (SELECT 1 FROM dias x WHERE UPPER(x.descripcion) = v.nombre);

-- El día de cada disponibilidad = el día de la semana de su fecha
CREATE OR REPLACE FUNCTION pg_temp.id_dia_de(f date) RETURNS integer AS $$
    SELECT id_dia FROM dias
     WHERE activo AND UPPER(descripcion) = (ARRAY['LUNES', 'MARTES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'SABADO', 'DOMINGO'])[EXTRACT(ISODOW FROM f)::int]
     ORDER BY id_dia LIMIT 1;
$$ LANGUAGE sql STABLE;

UPDATE disponibilidad_horaria d SET id_dia = pg_temp.id_dia_de(d.dispo_fecha)
 WHERE pg_temp.id_dia_de(d.dispo_fecha) IS NOT NULL AND d.id_dia <> pg_temp.id_dia_de(d.dispo_fecha);
UPDATE agenda_detalle a SET id_dia = d.id_dia
  FROM disponibilidad_horaria d
 WHERE d.id_disponibilidad = a.id_disponibilidad_horaria AND a.id_dia <> d.id_dia;

COMMIT;
