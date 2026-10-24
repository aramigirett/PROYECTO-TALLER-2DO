-- Migración de los datos iniciales de Tipo Ítems / Ítems a categorías de odontología.
-- Idempotente. Ejecutar DESPUÉS de schema_tipo_items.sql y schema_items.sql (que ya cargan
-- los tipos e ítems nuevos). En una base nueva no hace nada.
--
-- 1) Los ítems que vinieron del seed anterior (bajo PRODUCTO / SERVICIO) pasan a su tipo nuevo,
--    conservando su ID y lo que se haya editado (precio, IVA, stock). Solo cambia el tipo, y
--    siempre dentro de la misma clase de stock (PRODUCTO -> con stock, SERVICIO -> sin stock),
--    así que la cantidad sigue siendo consistente.
-- 2) PRODUCTO y SERVICIO se anulan (baja lógica) si ya no tienen ítems activos. Si alguien creó
--    ítems propios bajo esos tipos, el tipo queda activo hasta que se reasignen o anulen.

UPDATE items i
SET id_tipo_item = n.id_tipo_item
FROM (VALUES
    ('CEPILLO DENTAL ADULTO',          'HIGIENE BUCAL'),
    ('PASTA DENTAL CON FLÚOR 90G',     'HIGIENE BUCAL'),
    ('HILO DENTAL 50M',                'HIGIENE BUCAL'),
    ('ENJUAGUE BUCAL 500ML',           'HIGIENE BUCAL'),
    ('KIT DE HIGIENE PARA ORTODONCIA', 'ORTODONCIA'),
    ('PROTECTOR BUCAL DEPORTIVO',      'APARATOLOGÍA Y PROTECCIÓN'),
    ('RADIOGRAFÍA PANORÁMICA',         'ESTUDIOS RADIOGRÁFICOS'),
    ('CERTIFICADO ODONTOLÓGICO',       'DOCUMENTOS Y CERTIFICADOS')
) AS m(item, tipo)
JOIN tipo_items n ON UPPER(n.descripcion) = m.tipo AND n.activo = true
WHERE i.activo = true
  AND UPPER(i.descripcion) = m.item
  AND i.id_tipo_item <> n.id_tipo_item
  AND i.id_tipo_item IN (SELECT id_tipo_item FROM tipo_items
                         WHERE UPPER(descripcion) IN ('PRODUCTO', 'SERVICIO') AND activo = true);

UPDATE tipo_items t
SET activo = false
WHERE t.activo = true
  AND UPPER(t.descripcion) IN ('PRODUCTO', 'SERVICIO')
  AND NOT EXISTS (SELECT 1 FROM items i WHERE i.id_tipo_item = t.id_tipo_item AND i.activo = true);
