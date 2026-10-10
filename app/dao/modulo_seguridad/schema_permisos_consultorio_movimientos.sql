-- Etapa 4 (movimientos de Consultorio): 'estado' en Consulta, Tratamientos y
-- Ordenes de Estudios/Análisis, y ventana nueva 'sesiontratamiento'
-- (Procedimientos e Insumos). Los roles no-Administrador la reciben completa
-- para no cortar el flujo que hacen hoy. Idempotente.
INSERT INTO permisos (id_rol, ventana, accion)
SELECT r.id_rol, v.ventana, v.accion
FROM roles r
CROSS JOIN (VALUES
    ('consulta', 'estado'), ('tratamiento', 'estado'),
    ('ordenestudio', 'estado'), ('ordenanalisis', 'estado'),
    ('sesiontratamiento', 'ver'), ('sesiontratamiento', 'nuevo'), ('sesiontratamiento', 'anular')
) AS v(ventana, accion)
WHERE r.nombre_rol <> 'Administrador'
ON CONFLICT (id_rol, ventana, accion) DO NOTHING;
