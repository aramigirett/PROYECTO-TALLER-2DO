-- Etapa 4 (movimientos de Consultorio): 'estado' en Consulta, Tratamientos y
-- Ordenes de Estudios/Análisis, y ventana nueva 'sesiontratamiento'
-- (Procedimientos e Insumos). Los roles no-Administrador la reciben completa
-- para no cortar el flujo que hacen hoy. Idempotente.
INSERT INTO permisos (id_rol, id_menu, accion)
SELECT x.id_rol, m.id_menu, x.accion
FROM (
SELECT r.id_rol, v.ventana, v.accion
FROM roles r
CROSS JOIN (VALUES
    ('consulta', 'estado'), ('tratamiento', 'estado'),
    ('ordenestudio', 'estado'), ('ordenanalisis', 'estado'),
    ('sesiontratamiento', 'ver'), ('sesiontratamiento', 'nuevo'), ('sesiontratamiento', 'anular')
) AS v(ventana, accion)
WHERE r.nombre_rol <> 'Administrador'
) AS x(id_rol, ventana, accion)
JOIN menu m ON m.clave = x.ventana AND m.activo = true
ON CONFLICT (id_rol, id_menu, accion) DO NOTHING;
