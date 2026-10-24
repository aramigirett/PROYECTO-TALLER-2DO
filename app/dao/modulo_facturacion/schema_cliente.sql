-- Módulo Facturación - Referencial "Mantener Cliente". Idempotente.
-- Usa la tabla existente `paciente` (PK id_paciente; no tiene baja lógica: "paciente activo" = "paciente
-- existente") y auditoria_cambios (con la acción REACTIVACION, ver schema_caja.sql).
--
-- id_paciente es NULL si el cliente no es paciente. Los datos del cliente se COPIAN del paciente al darlo
-- de alta (no se sincronizan). SIN NOMBRE (CI/RUC 44444401-7) es el consumidor final: no se modifica ni se
-- da de baja (se identifica por esa CI/RUC, constante CONSUMIDOR_FINAL_RUC en ClienteDao).

CREATE TABLE IF NOT EXISTS cliente (
    id_cliente  SERIAL PRIMARY KEY,
    id_paciente INTEGER NULL REFERENCES paciente(id_paciente) ON DELETE RESTRICT,
    nombre      VARCHAR(80)  NOT NULL,   -- nombre o razón social
    apellido    VARCHAR(80)  NULL,
    ci_ruc      VARCHAR(20)  NOT NULL,
    telefono    VARCHAR(20)  NULL,
    correo      VARCHAR(100) NULL,
    activo      BOOLEAN NOT NULL DEFAULT true
);

-- Parciales: un cliente anulado no bloquea reutilizar su CI/RUC ni volver a registrar al paciente.
CREATE UNIQUE INDEX IF NOT EXISTS ux_cliente_ci_ruc_activo
    ON cliente (ci_ruc) WHERE activo = true;
CREATE UNIQUE INDEX IF NOT EXISTS ux_cliente_paciente_activo
    ON cliente (id_paciente) WHERE activo = true AND id_paciente IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_cliente_paciente ON cliente (id_paciente);

-- Datos iniciales. El RUC de LABORATORIO DENTAL SONRISA S.A. lleva su dígito verificador correcto
-- (módulo 11 de la SET): 80012345-0. El primer paciente existente (por id) se carga como cliente vinculado,
-- con nombre y apellido en mayúsculas y el resto tal cual; si no hay pacientes, no se inserta.
INSERT INTO cliente (id_paciente, nombre, apellido, ci_ruc, telefono, correo)
SELECT s.id_paciente, s.nombre, s.apellido, s.ci_ruc, s.telefono, s.correo
FROM (
    SELECT NULL::integer AS id_paciente, 'SIN NOMBRE'::text AS nombre, NULL::text AS apellido,
           '44444401-7'::text AS ci_ruc, NULL::text AS telefono, NULL::text AS correo
    UNION ALL SELECT NULL, 'MARÍA',   'GONZÁLEZ', '3456789',    '0981 123456', 'maria.gonzalez@ejemplo.com'
    UNION ALL SELECT NULL, 'CARLOS',  'BENÍTEZ',  '4567890',    '0971 654321', 'carlos.benitez@ejemplo.com'
    UNION ALL SELECT NULL, 'LABORATORIO DENTAL SONRISA S.A.', NULL, '80012345-0', '021 555123', 'facturacion@sonrisa.com.py'
    UNION ALL (SELECT p.id_paciente, UPPER(p.nombre), UPPER(p.apellido), p.cedula_entidad, p.telefono, p.correo
               FROM paciente p ORDER BY p.id_paciente LIMIT 1)
) s
WHERE NOT EXISTS (
    SELECT 1 FROM cliente c
    WHERE c.activo = true
      AND (c.ci_ruc = s.ci_ruc OR (s.id_paciente IS NOT NULL AND c.id_paciente = s.id_paciente))
);
