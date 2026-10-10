-- Rúbrica de acceso: bloqueo por intentos fallidos + recuperación de contraseña.
-- Idempotente.

-- Bloqueo de cuenta tras 3 fallos consecutivos (desbloqueo por Administrador
-- o automático a los 15 min, ver BLOQUEO_MINUTOS en UsuarioDao).
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS intentos_fallidos INTEGER NOT NULL DEFAULT 0;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS bloqueado BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS fecha_bloqueo TIMESTAMP NULL;

-- Propósito del código: el mismo mecanismo del 2FA sirve para recuperar la
-- contraseña, pero un código de un propósito no vale para el otro.
ALTER TABLE token_2fa ADD COLUMN IF NOT EXISTS proposito VARCHAR(20) NOT NULL DEFAULT 'LOGIN';
ALTER TABLE token_2fa DROP CONSTRAINT IF EXISTS chk_token_proposito;
ALTER TABLE token_2fa
    ADD CONSTRAINT chk_token_proposito CHECK (proposito IN ('LOGIN', 'RECUPERACION'));

-- Índice parcial: solo los códigos vigentes (no usados) se consultan por usuario+propósito.
CREATE INDEX IF NOT EXISTS idx_token_2fa_vigentes
    ON token_2fa (id_usuario, proposito) WHERE usado = FALSE;

-- Quién realizó la acción cuando no es el propio usuario (ej. el Administrador
-- que desbloquea una cuenta). NULL en los accesos normales.
ALTER TABLE auditoria_acceso
    ADD COLUMN IF NOT EXISTS id_usuario_actor INTEGER NULL REFERENCES usuarios(id_usuario);
