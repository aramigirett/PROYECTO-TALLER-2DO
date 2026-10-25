-- Etapa 3 de la migración de Agendamiento a Tabler: Avisos y Recordatorios con envío automático (WhatsApp con respaldo por correo).
-- Idempotente y en una transacción; se aplica como postgres con PGCLIENTENCODING=UTF8, DESPUÉS de un backup y de schema_agendamiento_etapa2.sql.
--   * `id_cita_detalle`: la cita a la que recuerda el aviso (opcional: se puede avisar a un paciente sin cita). Un solo aviso vigente por cita.
--   * `canal_enviado` ('WhatsApp' | 'Correo'), `motivo_error` y `fecha_envio`: cómo salió el aviso y, si falló o se usó el respaldo, por qué.
--   * CHECK del `estado` (Activo | Inactivo) que la tabla no tenía.
BEGIN;

ALTER TABLE avisos_recordatorios ADD COLUMN IF NOT EXISTS id_cita_detalle INTEGER;
ALTER TABLE avisos_recordatorios ADD COLUMN IF NOT EXISTS canal_enviado VARCHAR(20);
ALTER TABLE avisos_recordatorios ADD COLUMN IF NOT EXISTS motivo_error VARCHAR(200);
ALTER TABLE avisos_recordatorios ADD COLUMN IF NOT EXISTS fecha_envio TIMESTAMP;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_aviso_cita' AND conrelid = 'public.avisos_recordatorios'::regclass) THEN
        ALTER TABLE avisos_recordatorios ADD CONSTRAINT fk_aviso_cita FOREIGN KEY (id_cita_detalle)
            REFERENCES cita_detalle(id_cita_detalle) ON UPDATE CASCADE ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_aviso_canal' AND conrelid = 'public.avisos_recordatorios'::regclass) THEN
        ALTER TABLE avisos_recordatorios ADD CONSTRAINT chk_aviso_canal CHECK (canal_enviado IS NULL OR canal_enviado IN ('WhatsApp', 'Correo'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_aviso_estado' AND conrelid = 'public.avisos_recordatorios'::regclass) THEN
        ALTER TABLE avisos_recordatorios ADD CONSTRAINT chk_aviso_estado CHECK (estado IN ('Activo', 'Inactivo'));
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS ux_aviso_cita_vigente ON avisos_recordatorios (id_cita_detalle) WHERE estado <> 'Inactivo' AND id_cita_detalle IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_avisos_cita ON avisos_recordatorios (id_cita_detalle);

COMMIT;
