-- Módulo Facturación - Referencial "Mantener Caja". Idempotente.
-- Usa la tabla existente `consultorio` (PK `codigo`; no tiene baja lógica: "consultorio activo" =
-- "consultorio existente"). Usa auditoria_cambios (schema_forma_cobro.sql).

CREATE TABLE IF NOT EXISTS caja (
    id_caja        SERIAL PRIMARY KEY,
    id_consultorio INTEGER NOT NULL REFERENCES consultorio(codigo) ON DELETE RESTRICT,
    descripcion    VARCHAR(60) NOT NULL,
    activo         BOOLEAN NOT NULL DEFAULT true
);

-- Parcial: una caja anulada no bloquea reutilizar su descripción en el mismo consultorio.
CREATE UNIQUE INDEX IF NOT EXISTS ux_caja_consultorio_descripcion_activo
    ON caja (id_consultorio, UPPER(descripcion)) WHERE activo = true;
CREATE INDEX IF NOT EXISTS ix_caja_consultorio ON caja (id_consultorio);

-- La auditoría de cambios admite también la reactivación de un registro anulado.
ALTER TABLE auditoria_cambios DROP CONSTRAINT IF EXISTS auditoria_cambios_accion_check;
ALTER TABLE auditoria_cambios ADD CONSTRAINT auditoria_cambios_accion_check
    CHECK (accion IN ('ALTA', 'MODIFICACION', 'BAJA', 'REACTIVACION'));

-- Datos iniciales: consultorios ordenados por código.
--   CAJA RECEPCIÓN y CAJA ORTODONCIA -> primer consultorio.
--   CAJA <NOMBRE DEL CONSULTORIO>    -> segundo consultorio (solo si existe).
-- Si no hay consultorios, no inserta nada.
WITH ord AS (
    SELECT codigo, nombre_consultorio, ROW_NUMBER() OVER (ORDER BY codigo) AS rn
    FROM consultorio
),
semilla AS (
    SELECT codigo, 'CAJA RECEPCIÓN'::text AS d FROM ord WHERE rn = 1
    UNION ALL
    SELECT codigo, 'CAJA ORTODONCIA' FROM ord WHERE rn = 1
    UNION ALL
    SELECT codigo, LEFT('CAJA ' || UPPER(TRIM(nombre_consultorio)), 60) FROM ord WHERE rn = 2
)
INSERT INTO caja (id_consultorio, descripcion)
SELECT s.codigo, s.d
FROM semilla s
WHERE NOT EXISTS (
    SELECT 1 FROM caja x
    WHERE x.id_consultorio = s.codigo AND UPPER(x.descripcion) = UPPER(s.d) AND x.activo = true
);
