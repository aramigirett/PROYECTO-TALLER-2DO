-- Módulo Facturación - Referencial "Mantener Depósito" (depósito físico donde se guardan los ítems).
-- Idempotente. Usa auditoria_cambios (schema_forma_cobro.sql, con la acción REACTIVACION de schema_caja.sql).

CREATE TABLE IF NOT EXISTS deposito (
    id_deposito SERIAL PRIMARY KEY,
    descripcion VARCHAR(60)  NOT NULL,
    ubicacion   VARCHAR(100) NOT NULL,
    activo      BOOLEAN NOT NULL DEFAULT true
);

-- Parcial: un depósito anulado no bloquea reutilizar su descripción.
CREATE UNIQUE INDEX IF NOT EXISTS ux_deposito_descripcion_activo
    ON deposito (UPPER(descripcion)) WHERE activo = true;

INSERT INTO deposito (descripcion, ubicacion)
SELECT t.d, t.u
FROM (VALUES
    ('DEPÓSITO PRINCIPAL',  'PLANTA BAJA - DETRÁS DE RECEPCIÓN'),
    ('DEPÓSITO ORTODONCIA', 'PRIMER PISO - SALA DE ORTODONCIA')
) AS t(d, u)
WHERE NOT EXISTS (
    SELECT 1 FROM deposito x WHERE UPPER(x.descripcion) = t.d AND x.activo = true
);
