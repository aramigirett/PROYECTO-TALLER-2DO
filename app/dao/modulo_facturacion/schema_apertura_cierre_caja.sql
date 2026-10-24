-- Módulo Facturación - Movimiento "Registrar Apertura y Cierre de Caja". Idempotente.
-- Requiere caja (schema_caja.sql), usuarios y auditoria_cambios.
--
-- Una apertura la abre un cajero (id_usuario, SIEMPRE de la sesión) sobre una caja. Estados:
--   ABIERTA -> CERRADA  (cierre: fecha_cierre, total_recaudado y monto_cierre)
--   ABIERTA -> ANULADA  (anulación; bloqueada si ya tiene cobros/ventas del turno)
-- CERRADA y ANULADA son finales. monto_cierre = monto_apertura + total_recaudado.

CREATE TABLE IF NOT EXISTS apertura_cierre_caja (
    id_apertura     SERIAL PRIMARY KEY,
    id_caja         INTEGER NOT NULL REFERENCES caja(id_caja) ON DELETE RESTRICT,
    id_usuario      INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE RESTRICT,
    fecha_apertura  TIMESTAMP NOT NULL DEFAULT now(),
    monto_apertura  NUMERIC(12,0) NOT NULL CHECK (monto_apertura >= 0),
    fecha_cierre    TIMESTAMP NULL,
    total_recaudado NUMERIC(12,0) NULL,
    monto_cierre    NUMERIC(12,0) NULL,
    estado          VARCHAR(10) NOT NULL DEFAULT 'ABIERTA' CHECK (estado IN ('ABIERTA', 'CERRADA', 'ANULADA'))
);

-- Un cajero, una apertura abierta; una caja no se abre dos veces. Parciales: lo cerrado/anulado no bloquea.
CREATE UNIQUE INDEX IF NOT EXISTS ux_apertura_usuario_abierta
    ON apertura_cierre_caja (id_usuario) WHERE estado = 'ABIERTA';
CREATE UNIQUE INDEX IF NOT EXISTS ux_apertura_caja_abierta
    ON apertura_cierre_caja (id_caja) WHERE estado = 'ABIERTA';

CREATE INDEX IF NOT EXISTS ix_apertura_caja ON apertura_cierre_caja (id_caja);
CREATE INDEX IF NOT EXISTS ix_apertura_usuario ON apertura_cierre_caja (id_usuario);
CREATE INDEX IF NOT EXISTS ix_apertura_fecha ON apertura_cierre_caja (fecha_apertura DESC);

-- La auditoría de cambios admite también el cierre de caja (apertura = ALTA, anulación = BAJA).
ALTER TABLE auditoria_cambios DROP CONSTRAINT IF EXISTS auditoria_cambios_accion_check;
ALTER TABLE auditoria_cambios ADD CONSTRAINT auditoria_cambios_accion_check
    CHECK (accion IN ('ALTA', 'MODIFICACION', 'BAJA', 'REACTIVACION', 'CIERRE'));
