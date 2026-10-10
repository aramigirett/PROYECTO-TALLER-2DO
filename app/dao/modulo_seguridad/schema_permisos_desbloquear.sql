-- Sexta acción de permisos: 'desbloquear' (levantar el bloqueo de una cuenta
-- por intentos fallidos, ventana 'usuario'). Idempotente.
-- Sin seed para roles no-Administrador: antes no podían desbloquear nada
-- (la función no existía), así que no hay flujo que cortar. Administrador
-- pasa siempre por el bypass de puede().
ALTER TABLE permisos DROP CONSTRAINT IF EXISTS chk_permiso_accion;
ALTER TABLE permisos
    ADD CONSTRAINT chk_permiso_accion
    CHECK (accion IN ('ver', 'nuevo', 'editar', 'anular', 'estado', 'desbloquear'));
