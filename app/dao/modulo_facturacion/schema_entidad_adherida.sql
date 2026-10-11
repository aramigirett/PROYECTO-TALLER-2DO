-- Módulo Facturación - Referencial "Mantener Entidad Adherida" (procesadora con convenio con un
-- banco para una marca). Requiere entidad_emisora y marca_tarjeta. Idempotente.
-- Los datos de contacto de las filas iniciales son DE EJEMPLO (ficticios).

CREATE TABLE IF NOT EXISTS entidad_adherida (
    id_entidad_adherida SERIAL PRIMARY KEY,
    id_entidad_emisora  INTEGER NOT NULL REFERENCES entidad_emisora(id_entidad_emisora) ON DELETE RESTRICT,
    id_marca_tarjeta    INTEGER NOT NULL REFERENCES marca_tarjeta(id_marca_tarjeta) ON DELETE RESTRICT,
    descripcion VARCHAR(60)  NOT NULL,
    direccion   VARCHAR(150) NOT NULL,
    telefono    VARCHAR(20)  NOT NULL,
    correo      VARCHAR(100) NOT NULL,
    activo      BOOLEAN NOT NULL DEFAULT true
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_entidad_adherida_desc_emisora_marca_activo
    ON entidad_adherida (UPPER(descripcion), id_entidad_emisora, id_marca_tarjeta) WHERE activo = true;
CREATE INDEX IF NOT EXISTS ix_entidad_adherida_emisora ON entidad_adherida (id_entidad_emisora);
CREATE INDEX IF NOT EXISTS ix_entidad_adherida_marca   ON entidad_adherida (id_marca_tarjeta);

INSERT INTO entidad_adherida (id_entidad_emisora, id_marca_tarjeta, descripcion, direccion, telefono, correo)
SELECT e.id_entidad_emisora, m.id_marca_tarjeta, t.d, t.dir, t.tel, t.mail
FROM (VALUES
    ('BANCARD', 'BANCO ITAÚ',        'VISA',  'Av. Ejemplo 600, Asunción', '021 000 0006', 'contacto@bancard.ejemplo.com.py'),
    ('CABAL',   'BANCO CONTINENTAL', 'CABAL', 'Av. Ejemplo 700, Asunción', '021 000 0007', 'contacto@cabal.ejemplo.com.py')
) AS t(d, banco, marca, dir, tel, mail)
JOIN entidad_emisora e ON UPPER(e.descripcion) = t.banco AND e.activo = true
JOIN marca_tarjeta   m ON UPPER(m.descripcion) = t.marca AND m.activo = true
WHERE NOT EXISTS (
    SELECT 1 FROM entidad_adherida a
    WHERE UPPER(a.descripcion) = t.d AND a.id_entidad_emisora = e.id_entidad_emisora
      AND a.id_marca_tarjeta = m.id_marca_tarjeta AND a.activo = true
);
