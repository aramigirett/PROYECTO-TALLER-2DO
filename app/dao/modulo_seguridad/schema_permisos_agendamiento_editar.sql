-- Etapa 2 (Agendamiento): Paciente, Funcionario y Médico pasan a exponer la
-- acción 'editar' (su PUT es edición de datos maestros). Se otorga a los roles
-- no-Administrador para conservar el comportamiento previo (hasta hoy
-- cualquier rol podía editarlos). Idempotente.
INSERT INTO permisos (id_rol, ventana, accion)
SELECT r.id_rol, v.ventana, 'editar'
FROM roles r
CROSS JOIN (VALUES ('paciente'), ('funcionario'), ('medico')) AS v(ventana)
WHERE r.nombre_rol <> 'Administrador'
ON CONFLICT (id_rol, ventana, accion) DO NOTHING;
