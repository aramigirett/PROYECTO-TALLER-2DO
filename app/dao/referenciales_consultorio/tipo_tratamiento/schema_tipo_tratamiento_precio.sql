-- Consultorio - Referencial "Tipo Tratamiento": precio obligatorio (guaraníes, sin decimales).
-- Idempotente. Lo usa la Venta de Tratamiento (Facturación). Aplicar ANTES del código nuevo (el DAO selecciona `precio`).
--
-- Orden (por eso el NOT NULL y el CHECK van al final): 1) columna nullable, 2) datos, 3) NOT NULL y CHECK.

-- 1) Columna
ALTER TABLE tipos_tratamiento ADD COLUMN IF NOT EXISTS precio NUMERIC(12,0);

-- 2a) PRUEBA (registro de prueba): se anula y recibe precio 1 para cumplir el NOT NULL / CHECK. Solo se toca
--     mientras no tenga precio, así que corridas posteriores no la vuelven a modificar. OJO: tiene tratamientos
--     asociados; se anula a propósito por esta migración (la baja desde la pantalla lo bloquearía por estar en uso).
--     Los tratamientos siguen mostrándose: sus JOIN no filtran por `activo`.
UPDATE tipos_tratamiento
SET activo = false, precio = 1
WHERE UPPER(descripcion) = 'PRUEBA' AND precio IS NULL;

-- 2b) Datos iniciales (no se duplican si ya existe uno ACTIVO con la misma descripción)
INSERT INTO tipos_tratamiento (descripcion, precio)
SELECT t.d, t.precio
FROM (VALUES
    ('LIMPIEZA DENTAL (PROFILAXIS)',    200000),
    ('SELLANTES DE FOSAS Y FISURAS',    120000),
    ('RESTAURACIÓN CON RESINA',         250000),
    ('EXTRACCIÓN SIMPLE',               150000),
    ('EXTRACCIÓN DE TERCER MOLAR',      500000),
    ('TRATAMIENTO DE CONDUCTO',         800000),
    ('CORONA DE PORCELANA',            1500000),
    ('BLANQUEAMIENTO DENTAL',          1200000),
    ('INSTALACIÓN DE BRACKETS',        3500000),
    ('CONTROL DE ORTODONCIA',           200000),
    ('IMPLANTE DENTAL',                5000000)
) AS t(d, precio)
WHERE NOT EXISTS (
    SELECT 1 FROM tipos_tratamiento x WHERE UPPER(x.descripcion) = t.d AND x.activo = true
);

-- 3a) Si quedó alguna fila sin precio, se corta con un mensaje claro (no se aplica NOT NULL a ciegas)
DO $$
DECLARE
    sin_precio text;
BEGIN
    SELECT string_agg(id_tipo_tratamiento || ' = ' || descripcion, ', ') INTO sin_precio
    FROM tipos_tratamiento WHERE precio IS NULL;
    IF sin_precio IS NOT NULL THEN
        RAISE EXCEPTION 'Hay tipos de tratamiento sin precio; cargarles uno antes de aplicar NOT NULL: %', sin_precio;
    END IF;
END
$$;

-- 3b) Obligatorio y mayor a 0
ALTER TABLE tipos_tratamiento ALTER COLUMN precio SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_tipos_tratamiento_precio') THEN
        ALTER TABLE tipos_tratamiento ADD CONSTRAINT chk_tipos_tratamiento_precio CHECK (precio > 0);
    END IF;
END
$$;
