-- Módulo Facturación: ventanas 'tipoitem' (Tipo Ítems) e 'item' (Ítems).
-- Los roles no-Administrador las reciben completas. Idempotente.
INSERT INTO permisos (id_rol, ventana, accion)
SELECT r.id_rol, v.ventana, a.accion
FROM roles r
CROSS JOIN (VALUES ('tipoitem'), ('item')) AS v(ventana)
CROSS JOIN (VALUES ('ver'), ('nuevo'), ('editar'), ('anular')) AS a(accion)
WHERE r.nombre_rol <> 'Administrador'
ON CONFLICT (id_rol, ventana, accion) DO NOTHING;
