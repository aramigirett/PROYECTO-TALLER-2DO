# Plan: Registrar Nota de Remisión

Las tablas `nota_remision_cab` y `nota_remision_det` existen en la base. No se modificó nada: solo se leyó.

## Diferencias entre el prompt y la base
- La cabecera tiene campos obligatorios que el prompt no menciona: `id_deposito` (de dónde sale la mercadería), `fecha_traslado`, `motivo_traslado` (por defecto `VENTA`), `direccion_llegada` y `responsable_traslado`. El formulario los va a pedir.
- `uq_remision_det_item` impide repetir un ítem dentro de una misma remisión. Para entregar el mismo ítem varias veces hay que hacer remisiones distintas.
- El CHECK de `auditoria_cambios` ya admite ALTA y BAJA: no hace falta ampliarlo.

## Qué se va a hacer
1. **SQL** `schema_remision.sql`, idempotente y sin tocar tablas:
   - `fn_siguiente_numero_remision()` con formato `REM-0000001`, sin huecos, igual que el recibo.
   - Trigger `trg_validar_remision_det` (BEFORE INSERT en el detalle): bloquea la venta (`FOR UPDATE`) y valida que el ítem esté en la venta, que su tipo controle stock y que no se supere lo pendiente. Mensaje: "Cantidad a remitir de <ÍTEM> supera lo pendiente de entrega: N."
   - Vista `v_pendientes_entrega` (venta, ítem, facturado, remitido, pendiente). Cuenta solo remisiones EMITIDAS.
   - Todo con comentarios y `COMMENT ON`.
2. **Permisos:** entrada `remision` en `menu` y en `menu_catalog.py`, con acciones `ver`, `nuevo` y `anular`. El seed del Cajero pasa a 27 filas.
3. **Código:** `RemisionDao`, API y rutas, y la vista `remision-index.html` en Tabler con `facturacion.css`.
4. **PDF:** `remision_pdf_service.py`, con ORIGINAL y DUPLICADO y marca "ANULADA".
5. **Conexiones:**
   - Anular una venta con remisiones EMITIDAS se bloquea (409).
   - Una venta ANULADA no admite remisión; solo las ventas de Ítems EMITIDAS son remisibles.
   - Anular una remisión libera lo pendiente.
   - `esta_en_uso` de Depósito consulta las remisiones (hoy tiene un TODO).
6. **Pantalla:**
   - Listado con filtros de estado, factura/cliente/N.º de remisión y fechas.
   - Nueva Remisión: buscar la venta, elegir depósito, completar los datos de traslado y una grilla con facturado / ya remitido / a remitir.
   - Ver y PDF.
7. **Tests:** `smoke_remision.py` con el Administrador como cajero y datos ZZ, más la regresión completa y un test de navegador. Al final, `resumen_remision.md` y la actualización de `CLAUDE.md` y `tests/README.md`, sin commitear.

## Supuestos técnicos (se toman salvo que se indique otra cosa)
- Cualquiera con permiso `anular` puede anular una remisión.
- No exige caja abierta, porque no mueve dinero.
- Todos los usuarios con `ver` ven todas las remisiones.
- El responsable se escribe en mayúsculas.
- La fecha de traslado no puede ser anterior a la de emisión.

## Preguntas de negocio
1. ¿El depósito de origen es siempre un dato a elegir en cada remisión, o se asume el de los ítems? Los ítems de una misma venta pueden estar en depósitos distintos. **Recomendación:** elegirlo a mano, con el combo limitado a depósitos activos.
2. ¿Los ítems de tipo sin stock (servicios) simplemente no aparecen en la grilla? **Recomendación:** que no aparezcan.
3. ¿El motivo de traslado queda fijo en `VENTA`, o es un combo con otros motivos (`DEVOLUCIÓN`, `REPARACIÓN`)? **Recomendación:** fijo en `VENTA`, porque el movimiento nace de una venta.
4. ¿El Cajero recibe las tres acciones, como en los otros movimientos? **Recomendación:** sí.

## Pendiente de la sesión anterior
- Confirmar el mensaje de commit de Cobranzas: `Registrar Cobranzas por Forma de Cobro: cobros parciales y combinados, recibo en PDF y cierre de caja`.
