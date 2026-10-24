-- Registrar Cobranzas: dos columnas NUEVAS sobre las tablas que creó 01_migracion_der.sql. Idempotente.
--   * forma_cobro.tipo            VARCHAR(15) NOT NULL CHECK (tipo IN ('EFECTIVO','TARJETA','CHEQUE','TRANSFERENCIA'))
--   * cobro_det.numero_referencia VARCHAR(30) NULL  (obligatorio solo cuando la forma de cobro es TRANSFERENCIA; lo valida la
--                                                    API y el trigger diferido trg_validar_cobro)
-- ⚠ Estas dos columnas NO están en el DER de la tesis: hay que agregarlas al DER (ver CLAUDE.md).
--
-- forma_cobro.tipo se asigna a las filas existentes por su descripción (EFECTIVO / TARJETA / CHEQUE / TRANSFERENCIA como
-- palabra contenida). Las filas que no se puedan deducir quedan con tipo NULL y se LISTAN con un aviso: hay que corregirlas
-- (editando su tipo o dándolas de baja) y volver a correr este script, que recién entonces pone NOT NULL. Mientras tanto
-- el cobro rechaza esas formas ("La forma de cobro no tiene tipo asignado.").

ALTER TABLE forma_cobro ADD COLUMN IF NOT EXISTS tipo VARCHAR(15);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_forma_cobro_tipo') THEN
        ALTER TABLE forma_cobro ADD CONSTRAINT ck_forma_cobro_tipo
            CHECK (tipo IN ('EFECTIVO', 'TARJETA', 'CHEQUE', 'TRANSFERENCIA'));
    END IF;
END $$;

-- Deducción por descripción (solo las filas sin tipo: volver a correr no pisa un tipo ya elegido).
UPDATE forma_cobro SET tipo = CASE
        WHEN UPPER(descripcion) LIKE '%EFECTIVO%'      THEN 'EFECTIVO'
        WHEN UPPER(descripcion) LIKE '%TARJETA%'       THEN 'TARJETA'
        WHEN UPPER(descripcion) LIKE '%CHEQUE%'        THEN 'CHEQUE'
        WHEN UPPER(descripcion) LIKE '%TRANSFERENCIA%' THEN 'TRANSFERENCIA'
    END
WHERE tipo IS NULL;

-- NOT NULL solo si todas las filas ya tienen tipo; si no, avisa cuáles son.
DO $$
DECLARE
    v_sin_tipo TEXT;
BEGIN
    SELECT string_agg('#' || id_forma_cobro || ' "' || descripcion || '"' || CASE WHEN activo THEN '' ELSE ' (inactiva)' END,
                      ', ' ORDER BY id_forma_cobro)
      INTO v_sin_tipo FROM forma_cobro WHERE tipo IS NULL;
    IF v_sin_tipo IS NULL THEN
        ALTER TABLE forma_cobro ALTER COLUMN tipo SET NOT NULL;
    ELSE
        RAISE NOTICE 'forma_cobro.tipo queda SIN "NOT NULL": no se pudo deducir el tipo de: %. Edite su tipo (o dé de baja la fila) y vuelva a correr este script.', v_sin_tipo;
    END IF;
END $$;

COMMENT ON COLUMN forma_cobro.tipo IS 'Clase de la forma de cobro: EFECTIVO, TARJETA, CHEQUE o TRANSFERENCIA. Define qué datos pide el cobro (tarjeta, cheque, referencia) y qué se suma al efectivo del cierre de caja.';

-- Número de referencia de la transferencia (opcional a nivel de tabla; obligatorio para formas TRANSFERENCIA).
ALTER TABLE cobro_det ADD COLUMN IF NOT EXISTS numero_referencia VARCHAR(30);
COMMENT ON COLUMN cobro_det.numero_referencia IS 'Número de referencia de la transferencia. Obligatorio cuando la forma de cobro es de tipo TRANSFERENCIA; NULL en las demás.';
