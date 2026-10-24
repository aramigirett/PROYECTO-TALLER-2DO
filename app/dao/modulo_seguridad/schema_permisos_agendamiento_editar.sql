-- Etapa 2 (Agendamiento): Paciente, Funcionario y Médico pasan a exponer la
-- acción 'editar' (su PUT es edición de datos maestros). Se otorga a los roles
-- no-Administrador para conservar el comportamiento previo (hasta hoy
-- cualquier rol podía editarlos). Idempotente.
INSERT INTO permisos (id_rol, id_menu, accion)
SELECT x.id_rol, m.id_menu, x.accion
FROM (
SELECT r.id_rol, v.ventana, 'editar'
FROM roles r
CROSS JOIN (VALUES ('paciente'), ('funcionario'), ('medico')) AS v(ventana)
WHERE r.nombre_rol <> 'Administrador'
) AS x(id_rol, ventana, accion)
JOIN menu m ON m.clave = x.ventana AND m.activo = true
ON CONFLICT (id_rol, id_menu, accion) DO NOTHING;
