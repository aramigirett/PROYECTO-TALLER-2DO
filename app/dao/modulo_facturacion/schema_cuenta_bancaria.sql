-- Módulo Facturación - Referencial "Mantener Cuenta Bancaria": la cuenta del banco donde se DEPOSITA el dinero de la recaudación
-- (no es el depósito físico de productos, que es la tabla `deposito`). Requiere entidad_emisora (el banco) y recaudacion_depositar.
-- Idempotente. Orden: 01_migracion_der.sql -> schema_entidad_emisora.sql -> este script -> schema_permisos_cuenta_bancaria.sql.
-- ⚠️ Estas dos cosas NO están en el DER de la tesis y hay que agregarlas al DER:
--    * la tabla cuenta_bancaria;
--    * la columna recaudacion_depositar.id_cuenta_bancaria (+ el CHECK que la exige cuando la recaudación está DEPOSITADA).

CREATE TABLE IF NOT EXISTS cuenta_bancaria (
    id_cuenta_bancaria SERIAL PRIMARY KEY,
    id_entidad_emisora INTEGER NOT NULL REFERENCES entidad_emisora(id_entidad_emisora) ON DELETE RESTRICT,
    tipo_cuenta   VARCHAR(15)  NOT NULL CONSTRAINT ck_cuenta_bancaria_tipo CHECK (tipo_cuenta IN ('CORRIENTE', 'CAJA DE AHORRO')),
    numero_cuenta VARCHAR(30)  NOT NULL,
    titular       VARCHAR(100) NOT NULL,
    activo        BOOLEAN NOT NULL DEFAULT true
);

-- Una cuenta ACTIVA por banco y número: una cuenta anulada no impide dar de alta otra igual (índice único PARCIAL).
CREATE UNIQUE INDEX IF NOT EXISTS ux_cuenta_bancaria_banco_numero_activo
    ON cuenta_bancaria (id_entidad_emisora, numero_cuenta) WHERE activo = true;
CREATE INDEX IF NOT EXISTS ix_cuenta_bancaria_emisora ON cuenta_bancaria (id_entidad_emisora);

COMMENT ON TABLE cuenta_bancaria IS 'Cuenta del banco donde se deposita la recaudación (dinero). Distinta de la tabla deposito (depósito físico de productos). Falta en el DER.';

-- Datos iniciales (titular = razón social de la empresa).
INSERT INTO cuenta_bancaria (id_entidad_emisora, tipo_cuenta, numero_cuenta, titular)
SELECT e.id_entidad_emisora, t.tipo, t.numero, (SELECT razon_social FROM empresa LIMIT 1)
FROM (VALUES
    ('BANCO ITAÚ',        'CORRIENTE',      '1020304050'),
    ('BANCO CONTINENTAL', 'CAJA DE AHORRO', '2030405060')
) AS t(banco, tipo, numero)
JOIN entidad_emisora e ON UPPER(e.descripcion) = t.banco AND e.activo = true
WHERE EXISTS (SELECT 1 FROM empresa)
  AND NOT EXISTS (SELECT 1 FROM cuenta_bancaria c WHERE c.id_entidad_emisora = e.id_entidad_emisora AND c.numero_cuenta = t.numero AND c.activo = true);

-- La recaudación depositada guarda en qué cuenta se depositó.
ALTER TABLE recaudacion_depositar ADD COLUMN IF NOT EXISTS id_cuenta_bancaria INTEGER;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'recaudacion_id_cuenta_bancaria_fkey') THEN
        ALTER TABLE recaudacion_depositar
            ADD CONSTRAINT recaudacion_id_cuenta_bancaria_fkey FOREIGN KEY (id_cuenta_bancaria) REFERENCES cuenta_bancaria(id_cuenta_bancaria) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_recaudacion_cuenta') THEN
        ALTER TABLE recaudacion_depositar
            ADD CONSTRAINT ck_recaudacion_cuenta CHECK (estado <> 'DEPOSITADA' OR id_cuenta_bancaria IS NOT NULL) NOT VALID;
        -- NOT VALID + VALIDATE: si hubiera filas DEPOSITADA sin cuenta (hoy la tabla está vacía) el error nombra el problema y no deja el CHECK a medias.
        ALTER TABLE recaudacion_depositar VALIDATE CONSTRAINT ck_recaudacion_cuenta;
    END IF;
END
$$;
CREATE INDEX IF NOT EXISTS ix_recaudacion_cuenta ON recaudacion_depositar (id_cuenta_bancaria);
COMMENT ON COLUMN recaudacion_depositar.id_cuenta_bancaria IS 'Cuenta bancaria en la que se depositó la recaudación (obligatoria si está DEPOSITADA). Columna agregada; falta en el DER.';
