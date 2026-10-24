-- Permisos del rol Cajero. Idempotente. Define el conjunto COMPLETO del rol: quita lo que sobra y agrega lo que
-- falta, en una sola sentencia. Solo toca las filas del rol Cajero (los demás roles no se modifican).
--
-- Regla:
--   * Módulo Facturación (movimientos: hoy aperturacaja, pedidocliente, venta, cobro y remision): TODAS las acciones de la ventana.
--   * Cliente: ver, nuevo y editar (sin anular).
--   * Referenciales de Facturación (Forma de Cobro, Marca de Tarjeta, Entidad Emisora, Entidad Adherida, Caja,
--     Depósito, Tipo Ítems e Ítems): solo ver.
--   * Agendamiento, Consultorio y Seguridad: ningún permiso.
--
-- IMPORTANTE: cada movimiento NUEVO de Facturación debe agregarse acá con todas sus acciones (y todo referencial
-- NUEVO de Facturación, con 'ver'). tests/facturacion/smoke_permisos_cajero.py falla si el catálogo del menú tiene
-- una ventana de "Módulo Facturación" que el Cajero no puede usar por completo.
WITH cajero AS (
    SELECT id_rol FROM roles WHERE nombre_rol = 'Cajero'
),
deseado(ventana, accion) AS (
    VALUES
        -- Módulo Facturación (movimientos)
        ('aperturacaja', 'ver'), ('aperturacaja', 'nuevo'), ('aperturacaja', 'anular'), ('aperturacaja', 'estado'),
        ('pedidocliente', 'ver'), ('pedidocliente', 'nuevo'), ('pedidocliente', 'anular'),
        ('venta', 'ver'), ('venta', 'nuevo'), ('venta', 'anular'),
        ('cobro', 'ver'), ('cobro', 'nuevo'), ('cobro', 'anular'),
        ('remision', 'ver'), ('remision', 'nuevo'), ('remision', 'anular'),
        -- Cliente
        ('cliente', 'ver'), ('cliente', 'nuevo'), ('cliente', 'editar'),
        -- Referenciales de Facturación: solo ver
        ('formacobro', 'ver'), ('marcatarjeta', 'ver'), ('entidademisora', 'ver'), ('entidadadherida', 'ver'),
        ('caja', 'ver'), ('deposito', 'ver'), ('tipoitem', 'ver'), ('item', 'ver')
),
quitar AS (
    DELETE FROM permisos p
    USING cajero c
    WHERE p.id_rol = c.id_rol
      AND NOT EXISTS (SELECT 1 FROM deseado d WHERE d.ventana = p.ventana AND d.accion = p.accion)
    RETURNING p.id_rol
)
INSERT INTO permisos (id_rol, ventana, accion)
SELECT c.id_rol, d.ventana, d.accion
FROM cajero c
CROSS JOIN deseado d
ON CONFLICT (id_rol, ventana, accion) DO NOTHING;
