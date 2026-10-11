-- Módulo Facturación - Referencial "Mantener Marca de Tarjeta". Idempotente.
-- Usa auditoria_cambios, creada en schema_forma_cobro.sql.

CREATE TABLE IF NOT EXISTS marca_tarjeta (
    id_marca_tarjeta SERIAL PRIMARY KEY,
    descripcion      VARCHAR(60) NOT NULL,
    activo           BOOLEAN NOT NULL DEFAULT true
);

-- Parcial: una marca anulada no bloquea reutilizar su descripción.
CREATE UNIQUE INDEX IF NOT EXISTS ux_marca_tarjeta_descripcion_activo
    ON marca_tarjeta (UPPER(descripcion)) WHERE activo = true;

INSERT INTO marca_tarjeta (descripcion)
SELECT t.v
FROM (VALUES ('VISA'), ('MASTERCARD'), ('AMERICAN EXPRESS'), ('CABAL'), ('PANAL')) AS t(v)
WHERE NOT EXISTS (
    SELECT 1 FROM marca_tarjeta m WHERE UPPER(m.descripcion) = t.v AND m.activo = true
);
