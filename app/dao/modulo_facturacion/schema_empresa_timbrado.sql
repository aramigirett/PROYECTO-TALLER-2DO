-- Configuración de Facturación: datos de la empresa y timbrado fiscal (sin pantalla; se cargan por script). Idempotente.
-- Los datos iniciales solo se insertan si la tabla está vacía / no existe ese timbrado, para no pisar cambios hechos a mano.

-- ---------------------------------------------------------------------------------------------------------------------
-- empresa: datos del emisor de la factura. Una sola fila (índice único sobre una expresión constante).
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS empresa (
    id_empresa           SERIAL PRIMARY KEY,
    razon_social         VARCHAR(100) NOT NULL,
    ruc                  VARCHAR(20)  NOT NULL,
    direccion            VARCHAR(150) NOT NULL,
    telefono             VARCHAR(20)  NOT NULL,
    actividad_economica  VARCHAR(100) NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_empresa_unica ON empresa ((true));

-- RUC 80099999-1: el dígito verificador sale de calcular_dv_ruc('80099999') (módulo 11 de la SET).
INSERT INTO empresa (razon_social, ruc, direccion, telefono, actividad_economica)
SELECT 'CLÍNICA ODONTOLÓGICA ODONTOCLINIC S.A.', '80099999-1', 'AVDA. MCAL. LÓPEZ 1234 - ASUNCIÓN',
       '021 600 600', 'SERVICIOS ODONTOLÓGICOS'
WHERE NOT EXISTS (SELECT 1 FROM empresa);

COMMENT ON TABLE  empresa IS 'Datos del emisor de las facturas (una sola fila). Se carga por script, sin pantalla.';
COMMENT ON COLUMN empresa.ruc IS 'RUC con dígito verificador (formato 80099999-1), validado con módulo 11 de la SET.';

-- ---------------------------------------------------------------------------------------------------------------------
-- timbrado: autorización de numeración de la SET. Un solo timbrado ACTIVO a la vez (índice único parcial).
-- numero_actual es el ÚLTIMO número emitido (0 = ninguno); el siguiente lo entrega sp_siguiente_numero_factura.
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS timbrado (
    id_timbrado       SERIAL PRIMARY KEY,
    numero_timbrado   CHAR(8)  NOT NULL,
    fecha_inicio      DATE     NOT NULL,
    fecha_fin         DATE     NOT NULL,
    establecimiento   CHAR(3)  NOT NULL,
    punto_expedicion  CHAR(3)  NOT NULL,
    numero_desde      INTEGER  NOT NULL,
    numero_hasta      INTEGER  NOT NULL,
    numero_actual     INTEGER  NOT NULL DEFAULT 0,
    activo            BOOLEAN  NOT NULL DEFAULT true,
    CONSTRAINT ck_timbrado_vigencia CHECK (fecha_fin >= fecha_inicio),
    CONSTRAINT ck_timbrado_rango    CHECK (numero_desde >= 1 AND numero_hasta >= numero_desde),
    CONSTRAINT ck_timbrado_actual   CHECK (numero_actual >= 0 AND numero_actual <= numero_hasta)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_timbrado_activo ON timbrado ((true)) WHERE activo = true;

INSERT INTO timbrado (numero_timbrado, fecha_inicio, fecha_fin, establecimiento, punto_expedicion,
                      numero_desde, numero_hasta, numero_actual, activo)
SELECT '12345678', DATE '2026-10-01', DATE '2027-09-30', '001', '001', 1, 5000, 0, true
WHERE NOT EXISTS (SELECT 1 FROM timbrado WHERE numero_timbrado = '12345678')
  AND NOT EXISTS (SELECT 1 FROM timbrado WHERE activo = true);

COMMENT ON TABLE  timbrado IS 'Timbrado fiscal (SET). Solo uno activo a la vez. Se carga por script, sin pantalla.';
COMMENT ON COLUMN timbrado.numero_actual IS 'Último número de factura emitido (0 = ninguno). Lo incrementa sp_siguiente_numero_factura.';
