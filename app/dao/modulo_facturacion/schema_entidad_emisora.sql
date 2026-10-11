-- Módulo Facturación - Referencial "Mantener Entidad Emisora" (banco que emite la tarjeta o el cheque).
-- Idempotente. Usa auditoria_cambios (schema_forma_cobro.sql).
-- Los datos de contacto de las filas iniciales son DE EJEMPLO (ficticios).

CREATE TABLE IF NOT EXISTS entidad_emisora (
    id_entidad_emisora SERIAL PRIMARY KEY,
    descripcion VARCHAR(60)  NOT NULL,
    direccion   VARCHAR(150) NOT NULL,
    telefono    VARCHAR(20)  NOT NULL,
    correo      VARCHAR(100) NOT NULL,
    activo      BOOLEAN NOT NULL DEFAULT true
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_entidad_emisora_descripcion_activo
    ON entidad_emisora (UPPER(descripcion)) WHERE activo = true;

INSERT INTO entidad_emisora (descripcion, direccion, telefono, correo)
SELECT t.d, t.dir, t.tel, t.mail
FROM (VALUES
    ('BANCO ITAÚ',                 'Av. Ejemplo 100, Asunción',   '021 000 0001', 'contacto@itau.ejemplo.com.py'),
    ('BANCO CONTINENTAL',          'Av. Ejemplo 200, Asunción',   '021 000 0002', 'contacto@continental.ejemplo.com.py'),
    ('SUDAMERIS BANK',             'Av. Ejemplo 300, Asunción',   '021 000 0003', 'contacto@sudameris.ejemplo.com.py'),
    ('BANCO NACIONAL DE FOMENTO',  'Av. Ejemplo 400, Asunción',   '021 000 0004', 'contacto@bnf.ejemplo.com.py'),
    ('UENO BANK',                  'Av. Ejemplo 500, Asunción',   '021 000 0005', 'contacto@ueno.ejemplo.com.py')
) AS t(d, dir, tel, mail)
WHERE NOT EXISTS (
    SELECT 1 FROM entidad_emisora e WHERE UPPER(e.descripcion) = t.d AND e.activo = true
);
