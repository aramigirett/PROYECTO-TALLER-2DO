-- ============================================
-- MODULO AGENDAMIENTO - Avisos y Recordatorios
-- Corrección de análisis: se elimina el borrado físico de avisos_recordatorios,
-- ANULAR pasa a ser baja lógica (igual que agenda_cabecera / cita_cabecera).
-- Las columnas estado_envio / estado_confirmacion existentes son de otro
-- dominio (resultado del envío por WhatsApp / confirmación del paciente) y
-- no sirven para esto, por eso se agrega una columna estado propia.
-- ============================================

ALTER TABLE avisos_recordatorios
    ADD COLUMN estado VARCHAR(20) NOT NULL DEFAULT 'Activo';
