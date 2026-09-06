-- ============================================
-- MODULO AGENDAMIENTO - Registrar Agenda Médica
-- Corrección de análisis: ANULAR es baja lógica (ver deleteCabecera/deleteDetalle
-- en AgendaCabeceraDao/AgendaDetalleDao). Los UNIQUE originales eran a nivel de
-- fila física y seguían bloqueando la recreación de una agenda/horario ya
-- anulado. Se convierten en índices únicos PARCIALES que solo consideran las
-- filas activas, para que anular libere la combinación médico+fecha (o
-- cabecera+disponibilidad) para un alta nueva.
-- ============================================

ALTER TABLE agenda_cabecera DROP CONSTRAINT uk_medico_fecha;
CREATE UNIQUE INDEX uk_medico_fecha
    ON agenda_cabecera (id_medico, fecha_agenda)
    WHERE estado <> 'Inactivo';

ALTER TABLE agenda_detalle DROP CONSTRAINT uk_cabecera_disponibilidad;
CREATE UNIQUE INDEX uk_cabecera_disponibilidad
    ON agenda_detalle (id_agenda_cabecera, id_disponibilidad_horaria)
    WHERE estado_detalle <> 'Cancelado';
