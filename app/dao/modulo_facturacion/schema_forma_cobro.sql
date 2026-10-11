-- Módulo Facturación - Referencial "Mantener Forma de Cobro" y auditoría de cambios.
-- Idempotente: se puede ejecutar más de una vez.

CREATE TABLE IF NOT EXISTS forma_cobro (
    id_forma_cobro SERIAL PRIMARY KEY,
    descripcion    VARCHAR(60) NOT NULL,
    activo         BOOLEAN NOT NULL DEFAULT true
);

-- Parcial: una forma de cobro anulada no bloquea reutilizar su descripción.
CREATE UNIQUE INDEX IF NOT EXISTS ux_forma_cobro_descripcion_activo
    ON forma_cobro (UPPER(descripcion)) WHERE activo = true;

INSERT INTO forma_cobro (descripcion)
SELECT t.v
FROM (VALUES ('EFECTIVO'), ('TARJETA DE CRÉDITO'), ('TARJETA DE DÉBITO'),
             ('TRANSFERENCIA'), ('CHEQUE')) AS t(v)
WHERE NOT EXISTS (
    SELECT 1 FROM forma_cobro f WHERE UPPER(f.descripcion) = t.v AND f.activo = true
);

-- Auditoría genérica de cambios sobre datos (alta, modificación, baja).
-- La reutilizan los demás referenciales de Facturación.
CREATE TABLE IF NOT EXISTS auditoria_cambios (
    id_auditoria_cambio SERIAL PRIMARY KEY,
    fecha_hora          TIMESTAMP NOT NULL DEFAULT NOW(),
    id_usuario          INTEGER REFERENCES usuarios(id_usuario) ON DELETE RESTRICT,
    entidad             VARCHAR(50) NOT NULL,
    id_registro         INTEGER NOT NULL,
    accion              VARCHAR(20) NOT NULL
                        CHECK (accion IN ('ALTA', 'MODIFICACION', 'BAJA')),
    detalle             VARCHAR(255),
    ip                  VARCHAR(45)
);

CREATE INDEX IF NOT EXISTS ix_auditoria_cambios_entidad
    ON auditoria_cambios (entidad, id_registro);
CREATE INDEX IF NOT EXISTS ix_auditoria_cambios_fecha
    ON auditoria_cambios (fecha_hora DESC);
