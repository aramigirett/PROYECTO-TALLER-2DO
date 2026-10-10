-- Una sola fuente de verdad para cédula y correo: viven en funcionario/medico.
-- ETAPA 1 (lecturas): el sistema ya lee ci_ruc y correo de la persona vinculada.
-- Las columnas usuarios.ci_ruc / usuarios.correo quedan como copias muertas (ya no
-- se escriben ni se leen); se borran en la ETAPA 2 (schema_datos_unica_fuente_etapa2.sql).
-- Idempotente. Hacer pg_dump antes de correrlo.

-- La cédula identifica el login: no puede repetirse dentro de medico (funcionario ya
-- tiene funcionario_cedula_key). La unicidad ENTRE funcionario y medico se valida en
-- código al guardar. Falla (a propósito) si hoy hay cédulas repetidas en medico.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'medico'::regclass AND conname = 'medico_cedula_key'
    ) THEN
        ALTER TABLE medico ADD CONSTRAINT medico_cedula_key UNIQUE (cedula);
    END IF;
END $$;

-- Las copias ya no se escriben: dejan de ser obligatorias/únicas. Solo si las columnas
-- todavía existen (la etapa 2 las borra; así este script sigue siendo re-ejecutable).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'usuarios' AND column_name = 'ci_ruc') THEN
        ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_ci_ruc_key;
        ALTER TABLE usuarios ALTER COLUMN ci_ruc DROP NOT NULL;
        ALTER TABLE usuarios ALTER COLUMN correo DROP NOT NULL;
    END IF;
END $$;
