-- Migración 04: teléfonos en formato nacional (solo dígitos y con el 0 inicial) en TODAS las tablas que tienen teléfono.
-- Idempotente y en una transacción. Se aplica con postgres y PGCLIENTENCODING=UTF8, DESPUÉS de un backup.
-- Qué hace, por cada columna de teléfono:
--   1. Quita espacios, guiones y un "+" inicial.
--   2. Convierte 595XXXXXXXXX (8 o 9 dígitos tras el 595) a 0XXXXXXXXX.
--   3. Guarda el resultado SOLO si es un teléfono válido del formato nuevo: celular ^09\d{8}$ o línea baja ^0[2-8]\d{7,8}$.
--      Un dato viejo que no llegue a ser válido NO se toca (queda tal cual, con un aviso al final): hay que corregirlo a mano desde la pantalla.
-- Columnas: cliente.telefono, consultorio.telefono, empresa.telefono, entidad_adherida.telefono, entidad_emisora.telefono, funcionario.telefono,
-- medico.telefono, paciente.telefono y paciente.telefono_emergencia.
-- Como el resto de las migraciones de datos, NO registra auditoría (no es una acción de un usuario).
BEGIN;

CREATE OR REPLACE FUNCTION pg_temp.tel_nacional(valor text) RETURNS text AS $$
DECLARE d text;
BEGIN
    IF valor IS NULL THEN RETURN NULL; END IF;
    d := regexp_replace(btrim(valor), '[ \-]', '', 'g');
    d := regexp_replace(d, '^\+', '');
    IF d ~ '^595[0-9]{8,9}$' THEN d := '0' || substr(d, 4); END IF;
    IF d ~ '^(09[0-9]{8}|0[2-8][0-9]{7,8})$' THEN RETURN d; END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

DO $$
DECLARE
    c        RECORD;
    n        BIGINT;
    invalidos BIGINT;
BEGIN
    FOR c IN SELECT * FROM (VALUES ('cliente', 'telefono'), ('consultorio', 'telefono'), ('empresa', 'telefono'), ('entidad_adherida', 'telefono'),
                                   ('entidad_emisora', 'telefono'), ('funcionario', 'telefono'), ('medico', 'telefono'), ('paciente', 'telefono'),
                                   ('paciente', 'telefono_emergencia')) AS v(tabla, columna)
    LOOP
        EXECUTE format('UPDATE %1$I SET %2$I = pg_temp.tel_nacional(%2$I) WHERE %2$I IS NOT NULL AND pg_temp.tel_nacional(%2$I) IS NOT NULL AND pg_temp.tel_nacional(%2$I) <> %2$I',
                       c.tabla, c.columna);
        GET DIAGNOSTICS n = ROW_COUNT;
        EXECUTE format('SELECT count(*) FROM %1$I WHERE %2$I IS NOT NULL AND btrim(%2$I) <> '''' AND pg_temp.tel_nacional(%2$I) IS NULL', c.tabla, c.columna) INTO invalidos;
        RAISE NOTICE '%.%: % convertido(s), % con formato no válido (sin tocar)', c.tabla, c.columna, n, invalidos;
    END LOOP;
END $$;

COMMIT;
