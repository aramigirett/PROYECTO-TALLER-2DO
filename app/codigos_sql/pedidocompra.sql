CREATE TABLE estado_de_pedido_compras(
    id_epc SERIAL PRIMARY KEY,
    descripcion VARCHAR(60) UNIQUE NOT NULL
);

CREATE TABLE sucursales(
    id_sucursal SERIAL PRIMARY KEY,
    descripcion VARCHAR(60) UNIQUE NOT NULL
);

CREATE TABLE depositos(
    id_deposito SERIAL PRIMARY KEY,
    descripcion VARCHAR(60) UNIQUE NOT NULL
);

CREATE TABLE sucursal_depositos(
    id_sucursal INTEGER NOT NULL,
    id_deposito INTEGER NOT NULL,
    observaciones VARCHAR(60),
    estado BOOLEAN NOT NULL,
    PRIMARY KEY(id_sucursal, id_deposito),
    FOREIGN KEY(id_sucursal) REFERENCES sucursales(id_sucursal)
    ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY(id_deposito) REFERENCES depositos(id_deposito)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE productos(
    id_producto SERIAL PRIMARY KEY,
    nombre VARCHAR(60) UNIQUE NOT NULL,
    cantidad INTEGER,
    precio_unitario INTEGER
);

CREATE TABLE personas(
    id_persona SERIAL PRIMARY KEY,
    nombres VARCHAR(70) NOT NULL,
    apellidos VARCHAR(70) NOT NULL,
    ci TEXT NOT NULL,
    fechanac DATE,
    creacion_fecha DATE NOT NULL,
    creacion_hora TIME NOT NULL,
    creacion_usuario INTEGER NOT NULL,
    modificacion_fecha DATE,
    modificacion_hora TIME,
    modificacion_usuario INTEGER
);

CREATE TABLE empleados(
    id_empleado INTEGER PRIMARY KEY,
    fecha_ingreso DATE NOT NULL,
    FOREIGN KEY(id_empleado) REFERENCES personas(id_persona)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE usuarios(
    id_usuario INTEGER PRIMARY KEY,
    nickname TEXT NOT NULL,
    clave TEXT NOT NULL,
    estado BOOLEAN NOT NULL
);

CREATE TABLE pedido_de_compra(
    id_pedido_compra SERIAL PRIMARY KEY
    , id_empleado INTEGER NOT NULL
    , id_sucursal INTEGER NOT NULL
    , id_epc INTEGER NOT NULL
    , fecha_pedido DATE NOT NULL
    , id_deposito INTEGER NOT NULL
    , FOREIGN KEY(id_empleado) REFERENCES empleados(id_empleado)
    , FOREIGN KEY(id_sucursal) REFERENCES sucursales(id_sucursal)
    , FOREIGN KEY(id_epc) REFERENCES estado_de_pedido_compras(id_epc)
    , FOREIGN KEY(id_deposito) REFERENCES depositos(id_deposito)
);

CREATE TABLE pedido_de_compra_detalle(
    id_pedido_compra INTEGER NOT NULL
    , id_producto INTEGER NOT NULL
    , cantidad INTEGER NOT NULL
    , PRIMARY KEY(id_pedido_compra, id_producto)
    , FOREIGN KEY(id_pedido_compra) REFERENCES pedido_de_compra(id_pedido_compra)
    , FOREIGN KEY(id_producto) REFERENCES productos(id_producto)
);

ALTER TABLE productos ALTER COLUMN precio_unitario TYPE DECIMAL(10,2);