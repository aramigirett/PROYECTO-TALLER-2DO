# Plan: Registrar Ventas, etapa 2 — Venta de Tratamiento, factura en PDF y ajustes

Estado: **propuesto, pendiente de aprobación** (no se tocó ningún archivo del proyecto).

> Nota de corrección: al presentar el plan dije "3 archivos de código y 3 de pruebas o scripts, y unos 12 modificados".
> Esos números no coinciden con las listas. Las listas de abajo son las correctas: **4 archivos nuevos** y **10 modificados**
> (los de los tests existentes de otros módulos no se tocan en esta etapa).

## Lo que se verificó antes de planificar

- `deleteTratamiento` es el único camino que pasa un tratamiento a `cancelado`. Hoy no bloquea la fila: solo mira las
  sesiones activas y devuelve el texto `"EN_USO"`.
- La BD tiene 3 tratamientos, todos del paciente 6 (Javier Acosta, que es el cliente 5). El 13 está pendiente. El 7 y el 9
  están finalizados y son del tipo `PRUEBA`, que está inactivo y cuesta Gs. 1.
- Con el criterio pedido (no cancelados y sin venta EMITIDA), los dos `PRUEBA` aparecerían en el listado de Javier.
- **PDF:** solo está instalado `reportlab` 5.0.1, sin librería para leer PDFs. Para el test se decodifican los streams del
  PDF (ASCII85 + Flate) y se cuentan las páginas con `/Type /Page`. No hace falta instalar nada.
- `tests/consultorio/` tiene `smoke_tipo_tratamiento.py`, que cubre Gestionar Tratamientos. Se corre como regresión y se
  agrega la prueba del bloqueo en `smoke_ventas`.

## Archivos nuevos (4)

- `app/Services/numero_letras.py`: función pura `numero_a_letras(n)`.
- `app/Services/factura_pdf_service.py`, dividido en tres partes:
  - `calcular_datos_factura(venta)`: solo datos. Arma las columnas Exentas, 5% y 10% por renglón, los subtotales, el
    total, el total en letras y la liquidación del IVA.
  - `dibujar_factura(canvas, datos, copia)`: solo layout.
  - `generarFacturaPdf(venta)`: orquesta las dos anteriores.
- `app/dao/modulo_facturacion/schema_ventas_etapa2.sql`: índices en `venta_det(id_tratamiento)` e `(id_item)`, idempotente,
  sin tablas nuevas.
- `tests/facturacion/smoke_numero_letras.py`: test propio, sin base de datos. Prueba 0, 1, 15, 100, 101, 1000, 1.000.000,
  21.500.000 y 999.999.999.999, más unos pocos extras.

## Archivos modificados (10)

- `VentaDao`, `venta_api.py` y `venta-index.html`.
- `PedidoClienteDao`: se extrae la lógica de anular pedido y reponer stock a una función común. `anularPedido` se
  comporta igual que hoy.
- `ItemDao.esta_en_uso`.
- `TratamientoDao.deleteTratamiento` y su API (`tratamiento_api.py`).
- `smoke_ventas.py`.
- `CLAUDE.md` y `tests/README.md`.

## Venta de tratamiento (`tipo_venta = 'TRATAMIENTO'`, sin pedido)

- **Endpoints nuevos** (todos con permiso `nuevo` de `venta`): `GET /ventas/clientes?q=`, `GET /ventas/pacientes?q=`
  (mínimo 2 caracteres) y `GET /ventas/tratamientos?id_paciente=`.
- **Alta:** `POST /ventas` con `tipo_venta: "TRATAMIENTO"` y el cuerpo `{id_cliente, id_paciente, ids_tratamiento[],
  condicion}`. Los tratamientos tienen que ser del paciente indicado.
- **Transacción:**
  - Toma la apertura con `FOR SHARE`.
  - Bloquea los tratamientos con `FOR UPDATE` en orden de id.
  - Verifica que no estén cancelados ni facturados en una venta EMITIDA. El error es "El tratamiento <descripción> ya
    fue facturado en la factura <número>."
  - Llama al SP de numeración.
  - Copia descripción, precio e IVA desde `tipos_tratamiento`, con cantidad 1.
  - Calcula los totales con la misma `calcular_totales`. El trigger crea la cuenta a cobrar.
- **Sin pedido:** no toca el stock ni ningún pedido. Si el cliente está vinculado a un paciente, se precarga, pero con un
  botón "Cambiar".
- **Descripción:** el tipo puede tener hasta 200 caracteres y `venta_det.descripcion` admite 150, así que se recorta a 150
  al copiarla.
- **Pantalla Nueva Venta:** selector de tipo (Ítems desde Pedido / Tratamiento) al inicio.

## Bloqueo en Consultorio

- `deleteTratamiento` pasa a bloquear la fila con `FOR UPDATE` y a verificar, en la misma transacción, que no haya una
  venta EMITIDA.
- Responde 409 "El tratamiento ya fue facturado; anule primero la factura."
- Finalizar un tratamiento facturado sigue permitido: la restricción es solo para cancelar.

## Anular

- **Venta de ítems:** el confirmar tiene la casilla "Anular también el pedido y reponer el stock", desmarcada por defecto.
  - Desmarcada: el pedido vuelve a PENDIENTE, como hoy.
  - Marcada: en una sola transacción la venta queda ANULADA, el pedido ANULADO y el stock repuesto.
  - Va por `DELETE /ventas/<id>?anular_pedido=1`.
  - Se audita `BAJA` en la venta y `BAJA` en el pedido, con el detalle del stock repuesto.
- **Venta de tratamiento:** al anularla, los tratamientos quedan libres solos, porque la disponibilidad se calcula a
  partir de las ventas EMITIDAS. No se guarda ningún estado extra.
- **Condiciones:** siguen valiendo las mismas, caja abierta y sin cobros.

## Factura en PDF

- `GET /api/v1/ventas/<id>/pdf` con permiso `ver`. Un PDF de factura anulada se descarga igual, con la marca "ANULADA" en
  rojo.
- **Dos copias:** una página ORIGINAL (cliente) y otra DUPLICADO (archivo tributario). Si la factura tiene muchos
  renglones, cada copia sigue en páginas adicionales. Para una factura chica son exactamente 2 páginas.
- **Contenido:**
  - Cabecera con los datos de empresa y timbrado, "FACTURA" y el número.
  - Fecha, condición y cliente.
  - Detalle con las columnas Exentas, 5% y 10%.
  - Subtotales, TOTAL A PAGAR, "SON GUARANÍES: …." y la liquidación del IVA.
- **Pantalla:** botón PDF en el listado y en el comprobante. Al guardar una venta aparece un diálogo con "Ver factura
  (PDF)" y "Cerrar".

## Pendiente de la etapa 1

`ItemDao.esta_en_uso` pasa a bloquear también los ítems que están en `venta_det` de ventas EMITIDAS. Con eso, un ítem que
ya se facturó en una factura vigente no se puede dar de baja.

## Tests nuevos en `smoke_ventas.py`

- Venta de tratamiento: sin caja abierta, tratamiento cancelado, tratamiento ya facturado, precio e IVA copiados,
  totales, cuenta a cobrar, anulación y re-facturación.
- Doble facturación concurrente: 3 hilos sobre el mismo tratamiento.
- Anulación con y sin la casilla, con reposición de stock y el pedido en ANULADO o PENDIENTE.
- El bloqueo de Consultorio, más la regresión de `tests/consultorio`.
- PDF: que se genere, que tenga 2 páginas y que contenga el número, el RUC y el total. Además, que una factura anulada
  lleve la marca.
- `ItemDao` con ítems en una venta EMITIDA.

## Supuestos que se toman salvo indicación contraria

1. **Tratamientos incluidos:** entran todos los no cancelados, incluso los finalizados. Por eso los `PRUEBA` (Gs. 1) de
   Javier aparecerían. Si se quiere excluirlos, se puede pedir además que el tipo esté activo.
2. **Cambiar paciente:** con un cliente vinculado, el paciente precargado se puede cambiar. Es el caso de un padre que
   paga por un hijo.
3. **Números a letras:** "UNO" cuando el número va solo, "UN MILLÓN", "VEINTIÚN MILLONES" y "CERO" para el 0. Ejemplo:
   1.000 es "MIL" y 21.500.000 es "VEINTIÚN MILLONES QUINIENTOS MIL".
4. **Ítems facturados:** un ítem que ya está en una factura vigente no se puede dar de baja hasta que esa factura se
   anule. Hoy eso alcanza al CEPILLO, que aparece en las ventas reales.
