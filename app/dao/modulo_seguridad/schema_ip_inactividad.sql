-- Seguridad de acceso: validación de IP por país y cierre de sesión por inactividad.
-- Idempotente. Aplicar con PGCLIENTENCODING=UTF8.
--
-- auditoria_acceso.pais_detectado: código ISO (2 letras) del país que la base GeoIP asignó a la IP del intento.
--   NULL = IP interna (red de la clínica) o no geolocalizable. Nuevos valores de `resultado` (sin CHECK, VARCHAR(30)):
--     IP_NO_PERMITIDA      acceso rechazado: la IP pertenece a un país no permitido
--     IP_SIN_GEOLOCALIZAR  IP pública que la base GeoIP no resuelve: se permite y se deja constancia
--     CIERRE_INACTIVIDAD   sesión cerrada por el servidor tras SESSION_INACTIVIDAD_MINUTOS sin actividad
-- El filtro del tablero por resultado se apoya en el índice nuevo.
-- ADD COLUMN y CREATE INDEX no disparan trg_auditoria_inmutable (solo bloquea UPDATE/DELETE de filas).

ALTER TABLE auditoria_acceso ADD COLUMN IF NOT EXISTS pais_detectado VARCHAR(2);

COMMENT ON COLUMN auditoria_acceso.pais_detectado IS
    'País (ISO 3166-1 alfa-2) detectado por GeoIP para la IP del intento; NULL si es IP interna o no se pudo geolocalizar.';

CREATE INDEX IF NOT EXISTS ix_auditoria_acceso_resultado ON auditoria_acceso (resultado, fecha_hora DESC);
