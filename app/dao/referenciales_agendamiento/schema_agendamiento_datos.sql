-- Datos fijos de Agendamiento: los 6 estados de cita, de los que depende el código (Consultorio compara 'Realizado' y 'Cancelado'; el cupo
-- se descuenta con los estados que ocupan cupo). No es un referencial editable. Idempotente; se aplica como postgres con PGCLIENTENCODING=UTF8
-- después de schema_agendamiento_base.sql. Los 4 roles del sistema se siembran en schema_seguridad_base.sql.
BEGIN;

INSERT INTO estado_cita (id_estado_cita, descripcion, ocupa_cupo)
SELECT v.id, v.descripcion, v.ocupa
  FROM (VALUES (1, 'Reservado', true), (2, 'Confirmado', true), (3, 'Realizado', true),
               (4, 'Cancelado', false), (5, 'No Asistió', false), (6, 'Reprogramado', false)) AS v(id, descripcion, ocupa)
 WHERE NOT EXISTS (SELECT 1 FROM estado_cita e WHERE UPPER(e.descripcion) = UPPER(v.descripcion));

SELECT setval('estado_cita_id_estado_cita_seq', GREATEST((SELECT COALESCE(MAX(id_estado_cita), 1) FROM estado_cita), 1));

COMMIT;
