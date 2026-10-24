-- Registrar Ventas y Generar Cuentas a Cobrar (Módulo Facturación) — tablas. Idempotente.
-- Orden: schema_empresa_timbrado, schema_apertura_cierre_caja, schema_pedido_venta, ... y luego este.
-- Los objetos de base de datos (SP, triggers, vista) están en schema_objetos_bd.sql.

CREATE TABLE IF NOT EXISTS venta_cab (
    id_venta          SERIAL PRIMARY KEY,
    id_apertura       INT NOT NULL REFERENCES apertura_cierre_caja(id_apertura) ON DELETE RESTRICT,
    id_cliente        INT NOT NULL REFERENCES cliente(id_cliente) ON DELETE RESTRICT,
    id_usuario        INT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE RESTRICT,
    id_timbrado       INT NOT NULL REFERENCES timbrado(id_timbrado) ON DELETE RESTRICT,
    numero_factura    VARCHAR(15) NOT NULL CONSTRAINT uq_venta_numero_factura UNIQUE,
    fecha             TIMESTAMP NOT NULL DEFAULT now(),
    tipo_venta        VARCHAR(11) NOT NULL CONSTRAINT ck_venta_tipo CHECK (tipo_venta IN ('ITEMS', 'TRATAMIENTO')),
    id_pedido         INT NULL REFERENCES pedido_venta_cab(id_pedido) ON DELETE RESTRICT,
    condicion         VARCHAR(7) NOT NULL CONSTRAINT ck_venta_condicion CHECK (condicion IN ('CONTADO', 'CREDITO')),
    total_exenta      NUMERIC(12,0) NOT NULL,
    total_gravada_5   NUMERIC(12,0) NOT NULL,
    total_gravada_10  NUMERIC(12,0) NOT NULL,
    iva_5             NUMERIC(12,0) NOT NULL,
    iva_10            NUMERIC(12,0) NOT NULL,
    total             NUMERIC(12,0) NOT NULL,
    estado            VARCHAR(8) NOT NULL DEFAULT 'EMITIDA' CONSTRAINT ck_venta_estado CHECK (estado IN ('EMITIDA', 'ANULADA')),
    CONSTRAINT ck_venta_total CHECK (total = total_exenta + total_gravada_5 + total_gravada_10)
);

-- Un pedido se factura UNA sola vez (mientras su venta esté EMITIDA); anulada la venta, el pedido puede volver a facturarse.
CREATE UNIQUE INDEX IF NOT EXISTS ux_venta_pedido_emitida ON venta_cab (id_pedido) WHERE estado = 'EMITIDA';
CREATE INDEX IF NOT EXISTS ix_venta_apertura ON venta_cab (id_apertura);
CREATE INDEX IF NOT EXISTS ix_venta_cliente  ON venta_cab (id_cliente);
CREATE INDEX IF NOT EXISTS ix_venta_fecha    ON venta_cab (fecha DESC);
CREATE INDEX IF NOT EXISTS ix_venta_estado   ON venta_cab (estado);

CREATE TABLE IF NOT EXISTS venta_det (
    id_venta_det     SERIAL PRIMARY KEY,
    id_venta         INT NOT NULL REFERENCES venta_cab(id_venta) ON DELETE RESTRICT,
    id_item          INT NULL REFERENCES items(id_item) ON DELETE RESTRICT,
    id_tratamiento   INT NULL REFERENCES tratamientos(id_tratamiento) ON DELETE RESTRICT,
    descripcion      VARCHAR(150) NOT NULL,
    cantidad         INTEGER NOT NULL CONSTRAINT ck_venta_det_cantidad CHECK (cantidad > 0),
    precio_unitario  NUMERIC(12,0) NOT NULL,
    iva              SMALLINT NOT NULL CONSTRAINT ck_venta_det_iva CHECK (iva IN (0, 5, 10)),
    subtotal         NUMERIC(12,0) NOT NULL,
    -- exactamente uno de los dos: un renglón es un ítem o un tratamiento, nunca ambos ni ninguno
    CONSTRAINT ck_venta_det_item_o_tratamiento CHECK ((id_item IS NOT NULL)::int + (id_tratamiento IS NOT NULL)::int = 1)
);
CREATE INDEX IF NOT EXISTS ix_venta_det_venta ON venta_det (id_venta);

CREATE TABLE IF NOT EXISTS cuenta_cobrar (
    id_cuenta          SERIAL PRIMARY KEY,
    id_venta           INT NOT NULL CONSTRAINT uq_cuenta_venta UNIQUE REFERENCES venta_cab(id_venta) ON DELETE RESTRICT,
    id_cliente         INT NOT NULL REFERENCES cliente(id_cliente) ON DELETE RESTRICT,
    monto_total        NUMERIC(12,0) NOT NULL,
    saldo              NUMERIC(12,0) NOT NULL CONSTRAINT ck_cuenta_saldo CHECK (saldo >= 0),
    fecha_vencimiento  DATE NOT NULL,   -- CONTADO = fecha de la venta; CREDITO = fecha de la venta + 30 días
    estado             VARCHAR(9) NOT NULL DEFAULT 'PENDIENTE'
                       CONSTRAINT ck_cuenta_estado CHECK (estado IN ('PENDIENTE', 'PAGADA', 'ANULADA'))
);
CREATE INDEX IF NOT EXISTS ix_cuenta_cliente ON cuenta_cobrar (id_cliente);
CREATE INDEX IF NOT EXISTS ix_cuenta_estado  ON cuenta_cobrar (estado);

COMMENT ON TABLE  venta_cab IS 'Cabecera de la factura de venta. El número sale de sp_siguiente_numero_factura y no se reutiliza al anular.';
COMMENT ON COLUMN venta_cab.id_apertura IS 'Apertura de caja (ABIERTA) del cajero al momento de la venta; la venta solo se puede anular mientras siga abierta.';
COMMENT ON COLUMN venta_cab.id_pedido IS 'Pedido PENDIENTE que se facturó (ventas de ítems). NULL en la venta de tratamiento, que no usa pedido.';
COMMENT ON COLUMN venta_cab.total IS 'Total con IVA incluido = exenta + gravada 5% + gravada 10%. iva_5 = gravada_5/21 e iva_10 = gravada_10/11.';
COMMENT ON TABLE  venta_det IS 'Renglones de la factura: copia de descripción, precio e IVA al momento de la venta (de un ítem o de un tratamiento).';
COMMENT ON TABLE  cuenta_cobrar IS 'Cuenta a cobrar de cada venta, creada por trg_generar_cuenta_cobrar con saldo = total. Se completa con los cobros.';
