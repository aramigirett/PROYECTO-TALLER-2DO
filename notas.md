# Plan: Registrar Notas de Crédito y Débito

Revisé la base y no modifiqué nada. Hay una diferencia que necesita tu decisión antes de seguir.

## Diferencias entre el prompt y la base
- **`nota_credito_debito_cab` no tiene `id_apertura` ni una columna de reintegro.** Sin ellas no hay forma de saber en qué caja se emitió la nota. Tampoco se puede restar el reintegro del efectivo en el cierre, ni anular "solo con la caja de la nota abierta", ni revertir bien el saldo al anular. No se puede derivar de otras tablas.
- La tabla tiene todo lo demás:
  - cabecera con tipo, número `varchar(15)`, motivo, totales y `id_timbrado`;
  - detalle con `id_item` o `id_tratamiento` (opcionales), cantidad, precio e IVA;
  - CHECK de totales y UNIQUE por `(tipo_nota, numero_nota)`.
- La "Devolución de mercadería" no necesita bandera: un renglón con `id_item` significa que el ítem se devolvió.
- `v_libro_ventas` existe (viene del DER) y nadie la usa en el código. Hoy solo lista facturas.

## Qué se va a hacer
1. **SQL** `schema_notas.sql`, idempotente:
   - `fn_siguiente_numero_nota(tipo)`, con numeración independiente por tipo, formato `001-001-0000001` (establecimiento y punto del timbrado activo) y sin huecos.
   - Trigger `trg_aplicar_nota`:
     - crédito: reduce el saldo y, si ya estaba pagada, el excedente es el reintegro;
     - débito: suma al saldo y la cuenta pagada vuelve a PENDIENTE;
     - anular revierte todo;
     - un crédito no puede superar el total de la factura menos los créditos anteriores.
   - Trigger sobre el detalle: la devolución solo de ítems de la venta que controlan stock, sin superar lo facturado ni lo ya devuelto.
   - `fn_total_recaudado` y `v_resumen_caja` restan el reintegro, y el cierre queda como `monto_apertura + efectivo − reintegros`.
   - `v_estado_cuenta_cliente` suma créditos y débitos.
   - `v_libro_ventas` incluye las notas (créditos en negativo), con una columna nueva al final.
2. **Permisos**: ventana `notacd` con ver, nuevo y anular, fila en `menu` y seed del Cajero. Pasa a 30 filas.
3. **Código**: `NotaCreditoDebitoDao`, API, rutas y la vista Tabler. El servidor calcula totales e IVA como en la factura. Un crédito con devolución repone el stock en la misma transacción, y al anular lo revierte.
4. **PDF** ORIGINAL y DUPLICADO, con la factura de referencia y la marca "ANULADA".
5. **Pantalla**:
   - listado con filtros;
   - Nueva Nota: buscar la factura, ver total, saldo, notas previas y máximo permitido, y renglones con descripción, monto e IVA;
   - para créditos de ventas de ítems, la opción "Devolución de mercadería";
   - Ver y PDF.
6. **Conexiones**:
   - el cierre y el desglose de caja muestran los reintegros;
   - anular una venta con notas emitidas se bloquea;
   - el mensaje "utilice una Nota de Crédito" de ventas y cobros pasa a apuntar a esta pantalla.
7. **Tests**: `smoke_notas.py` y la regresión completa. Además, `resumen_notas.md` y la actualización de `CLAUDE.md`, sin commitear.

## Supuestos técnicos
- La numeración es propia por tipo y no consume el rango de facturas. Solo se exige que el timbrado esté vigente.
- Anular un crédito aumenta el saldo. Anular un débito se bloquea si ya hubo cobros que dejarían el saldo negativo.
- Anular una devolución se bloquea si el stock actual no alcanza para deshacerla.
- Un débito no tiene tope.
- Si las notas llevan renglones libres (sin devolución), cada renglón se guarda con cantidad 1 y el monto como precio.

## Preguntas de negocio
1. ¿Se aprueba agregar dos columnas a `nota_credito_debito_cab` (hay que sumarlas al DER)? Son `id_apertura` (INT NOT NULL, FK a `apertura_cierre_caja`) y `monto_reintegro` (NUMERIC(12,0) NOT NULL DEFAULT 0). Con esto **toda** nota, de crédito o débito, exige caja abierta del cajero. **Recomendación:** sí, igual que con ventas y cobros.
2. Si el reintegro es mayor que el efectivo que hay en la caja (`monto_apertura + efectivo cobrado − reintegros previos`), ¿se bloquea con "No hay efectivo suficiente en la caja para el reintegro" o se permite y el monto de cierre queda negativo? **Recomendación:** bloquear.
