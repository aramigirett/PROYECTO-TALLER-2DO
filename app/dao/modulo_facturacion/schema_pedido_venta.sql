-- Registrar Pedido Cliente (Módulo Facturación). Idempotente.
-- El pedido es el paso PREVIO a la Venta de Ítems: el stock se descuenta SOLO acá (al crear el pedido) y se repone
-- al anularlo. La Venta de Ítems se genera desde un pedido PENDIENTE y lo pasa a FACTURADO.
-- Orden: schema_cliente.sql y schema_items.sql antes que este.

CREATE TABLE IF NOT EXISTS pedido_venta_cab (
    id_pedido     SERIAL PRIMARY KEY,
    id_cliente    INT NOT NULL REFERENCES cliente(id_cliente) ON DELETE RESTRICT,
    id_usuario    INT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE RESTRICT,
    fecha_pedido  TIMESTAMP NOT NULL DEFAULT now(),
    observacion   VARCHAR(200),
    total         NUMERIC(12,0) NOT NULL,
    estado        VARCHAR(10) NOT NULL DEFAULT 'PENDIENTE'
                  CONSTRAINT pedido_venta_cab_estado_check CHECK (estado IN ('PENDIENTE', 'FACTURADO', 'ANULADO'))
);

CREATE TABLE IF NOT EXISTS pedido_venta_det (
    id_pedido_det    SERIAL PRIMARY KEY,
    id_pedido        INT NOT NULL REFERENCES pedido_venta_cab(id_pedido) ON DELETE RESTRICT,
    id_item          INT NOT NULL REFERENCES items(id_item) ON DELETE RESTRICT,
    cantidad         INTEGER NOT NULL CONSTRAINT pedido_venta_det_cantidad_check CHECK (cantidad > 0),
    precio_unitario  NUMERIC(12,0) NOT NULL,      -- copiado del ítem al momento del pedido
    iva              SMALLINT NOT NULL CONSTRAINT pedido_venta_det_iva_check CHECK (iva IN (0, 5, 10)),  -- copiado del ítem
    subtotal         NUMERIC(12,0) NOT NULL,
    CONSTRAINT uq_pedido_venta_det_item UNIQUE (id_pedido, id_item)   -- un ítem no se repite en el mismo pedido
);

CREATE INDEX IF NOT EXISTS ix_pedido_cab_cliente ON pedido_venta_cab (id_cliente);
CREATE INDEX IF NOT EXISTS ix_pedido_cab_usuario ON pedido_venta_cab (id_usuario);
CREATE INDEX IF NOT EXISTS ix_pedido_cab_estado  ON pedido_venta_cab (estado);
CREATE INDEX IF NOT EXISTS ix_pedido_cab_fecha   ON pedido_venta_cab (fecha_pedido DESC);
CREATE INDEX IF NOT EXISTS ix_pedido_det_item    ON pedido_venta_det (id_item);
