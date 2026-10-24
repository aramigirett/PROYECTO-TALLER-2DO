# Plan: Registrar Cobranzas por Forma de Cobro — sobre las tablas reales

Estado: **propuesto, pendiente de aprobación y de 4 respuestas de negocio.** No se tocó nada: lo único que se corrió fue de
solo lectura sobre la base. No se creó ni modificó ninguna tabla, y no se ejecutó ni se buscó
`02_migracion_requiere_codigo.sql`.

## Diferencias entre el prompt y la base (se sigue la base)

| Tabla | Prompt | Base real |
|---|---|---|
| `cobro_cab` | `id_cliente` FK | **No existe**: el cliente sale de la cuenta (`cuenta_cobrar.id_cliente`) |
| `cobro_cab` | — | Tiene `numero_recibo` VARCHAR(15) **NOT NULL y UNIQUE**, y `observacion` (200, opcional). La FK de `cobro_det` es `ON DELETE CASCADE`. |
| `cobro_det` | número de referencia de la transferencia | **No hay columna** para guardarlo |
| `cobro_tarjeta` | `id_marca_tarjeta`, `id_entidad_emisora`, `numero_voucher` | **No existen** esas tres columnas. Tiene `id_entidad_adherida`, `tipo_tarjeta` (CREDITO/DEBITO), `ultimos_digitos` (CHAR 4, solo dígitos) y `numero_autorizacion` (20), todas obligatorias. |
| `cobro_cheque` | `fecha_cheque` | Tiene `fecha_emision` y `fecha_cobro` (con CHECK `fecha_cobro >= fecha_emision`), más `titular` (100). Todas obligatorias. |
| `forma_cobro` | — | **No tiene ninguna columna que diga si la forma es tarjeta, cheque, transferencia o efectivo.** |

Consecuencias:
- **Tarjeta:** la marca y la emisora salen de la entidad adherida, así que la incoherencia que mencionaba el prompt no puede
  ocurrir. El cajero elige UNA adherida (se muestra "BANCARD — VISA — BANCO ITAÚ") y se valida que adherida, marca y
  emisora estén activas.
- **Datos de `forma_cobro` a revisar:** hay dos EFECTIVO (el 1 inactivo y el 8 activo) y dos filas que parecen de prueba,
  `TRANSFERENCIANFGNFN` y `BHDJDGJ`. Conviene limpiarlas antes de probar a mano.
- **Más objetos de la migración (fuera de este movimiento):** también aparecieron `arqueo_caja_det`,
  `nota_credito_debito_*`, `nota_remision_*` y la vista `v_libro_ventas`.

## Decisiones de negocio pendientes (4)

1. **¿Cómo se sabe qué forma es tarjeta, cheque o transferencia?** Sin una columna, solo se podría adivinar por el nombre
   (frágil). Recomendación: aplicar el `02_migracion_requiere_codigo.sql`, o pasar su contenido o ruta para leerlo (sin
   ejecutarlo) y adaptar el plan. Con eso también se resuelve de dónde sale el crédito/débito de la tarjeta.
2. **Número de referencia de transferencia:** `cobro_det` no tiene dónde guardarlo. ¿Se omite, lo cubre el 02, o se
   autoriza agregar una columna `numero_referencia`?
3. **Monto de cierre:** según el prompt, `monto_cierre = apertura + TODO lo cobrado`. Eso incluye tarjetas, cheques y
   transferencias, que no son plata física en el cajón. El efectivo se vería aparte en `v_resumen_caja`. ¿Se deja así?
4. **Cheques diferidos:** ¿se aceptan con fecha de cobro futura? Propuesta: sí, y que la fecha de emisión no pueda ser
   posterior a hoy.

## Supuestos técnicos (se toman salvo indicación contraria)

- **Recibo:** `numero_recibo` con formato `REC-0000001`, sin huecos, mediante una función con bloqueo y sin crear tablas.
- **Cobro:** con caja abierta del cajero, cuenta PENDIENTE y total ≤ saldo. Pagos parciales y varias formas en un mismo
  cobro. La suma de las formas debe ser igual al total, sin vuelto. Se puede cobrar una cuenta vencida.
- **Anular:** cualquiera con permiso `anular`, solo si la apertura sigue ABIERTA. Si está cerrada: "Utilice una Nota de
  Crédito."
- **Permisos:** ventana `cobro` con `ver`, `nuevo` y `anular`, y el Cajero las recibe todas.

## Objetos de base de datos (solo funciones, triggers y vistas; ninguna tabla)

- `trg_aplicar_cobro` (AFTER INSERT o UPDATE de `estado` en `cobro_cab`): descuenta o repone el saldo y pasa la cuenta a
  PAGADA o PENDIENTE. Rechaza si la cuenta no está PENDIENTE o si el total supera el saldo.
- `trg_validar_suma_cobro` (agregado): trigger diferido que garantiza al confirmar que la suma de `cobro_det` es igual al
  total del cobro.
- `fn_total_recaudado(p_id_apertura)`: suma los cobros EMITIDOS de la apertura. La usa el Cierre de Caja.
- `fn_siguiente_numero_recibo()`: da el próximo número de recibo.
- `v_resumen_caja`: por apertura y forma de cobro, con la cantidad de cobros y el total. Se muestra en el detalle del
  Cierre.
- `v_estado_cuenta_cliente`: se completa con `total_cobrado`, `cantidad_cobros` y `fecha_ultimo_cobro`. Las columnas se
  agregan al final, así que no rompe nada.
- Todo con comentarios de propósito, parámetros y excepciones, y `COMMENT ON`, en el script idempotente
  `schema_cobranzas.sql`.

## Conexiones (cierre de los TODO)

- **Venta:**
  - Después de guardar, el diálogo ofrece "Cobrar ahora", "Ver factura (PDF)" y "Cerrar". "Cobrar ahora" abre el cobro de
    esa cuenta.
  - `_motivo_con_cobros` bloquea anular la venta si tiene cobros EMITIDOS ("No es posible anular, existen cobros
    registrados. Utilice una Nota de Crédito.").
- **Apertura de Caja:**
  - `_total_recaudado` usa `fn_total_recaudado`.
  - Anular la apertura se bloquea con cobros.
  - El detalle del Cierre muestra `v_resumen_caja`.
- **`esta_en_uso` de Forma de Cobro, Marca, Entidad Adherida y Entidad Emisora:** bloquea la baja si hay cobros EMITIDOS,
  mirando `cobro_det`, `cobro_tarjeta` y `cobro_cheque` (la marca, a través de la adherida).

## Pantalla

Listado de cobros con filtros. Nuevo Cobro: se busca la cuenta por cliente o N.º de factura (muestra total, saldo y
vencimiento), y una grilla de formas de cobro con campos según la forma, total en vivo y saldo restante. Recibo de dinero en
PDF reutilizando el patrón de la factura (ORIGINAL y DUPLICADO, cálculo separado del dibujo).

## Archivos

- **Nuevos (9):** `schema_cobranzas.sql`, `schema_permisos_cobranzas.sql`, `CobroDao.py`, `cobro_api.py`,
  `cobro_routes.py`, `cobro-index.html`, `app/Services/recibo_pdf_service.py`, `smoke_cobranzas.py` y, al final,
  `resumen_cobranzas.md` (sin commitear).
- **Modificados (unos 14):**
  - Sistema: `menu_catalog.py`, `app/__init__.py` y `schema_permisos_cajero.sql`.
  - Ventas: `VentaDao`, `venta_api.py` y `venta-index.html`.
  - Apertura de Caja: `AperturaCajaDao`, su API y su pantalla.
  - Referenciales: los 4 DAO de Forma de Cobro, Marca, Adherida y Emisora.
  - Docs: `CLAUDE.md` y `tests/README.md`.

## Tests (`smoke_cobranzas.py`, más la regresión completa)

- Cobro parcial y cobro combinado.
- Saldo excedido, con el mensaje "El monto supera el saldo pendiente de Gs. N."
- Tarjeta con adherida, marca o emisora inactiva, y tarjeta mal formada.
- Cheque inválido.
- Anular con la caja abierta y con la caja cerrada.
- Los triggers y la función `fn_total_recaudado`.
- Las vistas.
- Un cierre con recaudado real.
- Un cobro y una anulación concurrentes.
- Las conexiones: bloqueos de baja y de anulación de venta y apertura.
- El PDF del recibo.

Los datos de prueba serán `ZZ`, y se borran por ID. Para las formas de cobro `ZZ` se depende de la respuesta a la
pregunta 1.
