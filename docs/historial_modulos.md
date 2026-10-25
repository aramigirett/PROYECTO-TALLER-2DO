# Historial de módulos: Facturación y tanda de cierre

> Leer al tocar Facturación, objetos de BD, auditoría o seguridad de acceso/BD. Incluye pendientes y tests de Facturación.
> Movido tal cual desde `CLAUDE.md` (sin cambios de contenido) al reorganizarlo. La guía compacta es `CLAUDE.md`.

## Módulo Facturación (en curso)
- ✅ **Forma de Cobro** (primer referencial, define el patrón visual de los otros 7):
  tabla `forma_cobro` (sin código, baja lógica `activo`, índice único parcial sobre
  `UPPER(descripcion) WHERE activo`), descripción en MAYÚSCULAS. `esta_en_uso()` es un
  ahora consulta `cobro_det` (cobros EMITIDOS) para bloquear la baja; ver "Registrar Cobranzas".
  Scripts: `app/dao/modulo_facturacion/schema_forma_cobro.sql` y
  `schema_permisos_facturacion.sql`. Ventana `formacobro` en el catálogo, módulo
  "Referenciales Facturación".
- **Auditoría de cambios** (`auditoria_cambios` + `AuditoriaCambiosDao`): ALTA /
  MODIFICACION / BAJA con `id_usuario` de la sesión e `ip` del request (nunca del
  cliente). Distinta de `auditoria_acceso`. Los demás referenciales de Facturación
  deben llamarla desde su API. Aún no tiene pantalla de consulta.
- ⏳ **Pendiente:** los referenciales de Consultorio y Agendamiento no registran
  auditoría de cambios: se incorpora al migrarlos (ver "Estándar de referenciales" y
  "Pendientes de referenciales").
- ✅ **Marca de Tarjeta**: calco de Forma de Cobro (`marca_tarjeta`, ventana `marcatarjeta`;
  `esta_en_uso()` ahora consulta `cobro_tarjeta` a través de la adherida; ver "Registrar Cobranzas"). Helpers compartidos de las APIs
  de Facturación (`normalizar_descripcion`, `auditar`, `error_interno`) en
  `app/rutas/modulo_facturacion/utils.py`.
- ✅ **Entidad Emisora** (banco; `entidad_emisora`, ventana `entidademisora`) y
  **Entidad Adherida** (`entidad_adherida`, ventana `entidadadherida`: procesadora con
  convenio con un banco para una marca, FK RESTRICT a emisora y marca; único parcial sobre
  `(UPPER(descripcion), emisora, marca)`). Ambas con dirección, teléfono y correo obligatorios.
  Datos iniciales de contacto: ficticios, de ejemplo.
  - **Bloqueo de baja:** no se puede anular una emisora ni una marca con una adherida activa
    (409 con mensaje específico). Ya consultan los cobros: `cobro_tarjeta` / `cobro_cheque` (ver "Registrar Cobranzas").
  - `esta_en_uso()` ahora devuelve `False` o un texto con el motivo; `deleteX()` devuelve
    `("EN_USO", motivo)`. La verificación y el UPDATE van en una transacción con la fila
    bloqueada (`FOR UPDATE`); el alta/edición de Adherida toma `FOR SHARE` sobre emisora y
    marca, para evitar carreras. Forma de Cobro ya fue alineada al mismo protocolo.
  - **Validadores de formulario** (descripción, dirección, teléfono, correo) en
    `app/rutas/modulo_facturacion/utils.py` **y duplicados** en
    `app/static/js/facturacion-validadores.js`: si cambia una regla, cambiar los dos. Teléfono:
    dígitos, espacios, guiones y `+` inicial; 6 a 20 caracteres y **al menos 6 dígitos reales**.
    Correo: formato válido, se guarda en minúsculas. Reutilizar en Cliente.
  - Las respuestas de error de validación incluyen `campo` para marcarlo en el formulario.
- ✅ **Tipo Ítems** (`tipo_items`, ventana `tipoitem`, con `controla_stock`) e
  **Ítems** (`items`, ventana `item`: tipo, descripción de hasta 100, `precio_unitario` NUMERIC(12,0)
  en guaraníes, `iva` 0/5/10, `cantidad_disponible`).
  - **Datos iniciales (odontología):** tipos HIGIENE BUCAL, ORTODONCIA y APARATOLOGÍA Y PROTECCIÓN
    (con stock); ESTUDIOS RADIOGRÁFICOS y DOCUMENTOS Y CERTIFICADOS (sin stock); 10 ítems. Un seed
    anterior usaba PRODUCTO/SERVICIO: `migracion_seed_odontologia.sql` (idempotente, correr después de
    `schema_tipo_items.sql` y `schema_items.sql`) mueve esos ítems a su tipo nuevo y anula PRODUCTO/SERVICIO.
  - **Stock:** si el tipo no controla stock, la cantidad es SIEMPRE 0 (la API la fuerza y el DAO lo
    reafirma bajo `FOR SHARE` sobre el tipo). El formulario deshabilita el campo. El listado muestra
    "—" en el stock de esos ítems. Al cambiar un ítem a un tipo sin stock, la cantidad pasa a 0.
  - **Bajas:** un tipo con ítems activos no se puede anular, y tampoco se puede cambiar su
    "Controla stock" (409; evita ítems con stock bajo un tipo que no lo controla). `esta_en_uso`
    de Ítems consulta `pedido_venta_det` (solo pedidos PENDIENTES). **Decisión (etapa 2 de Ventas): NO bloquea por ventas
    EMITIDAS (`venta_det`)**: una factura vigente no se puede anular después del cierre de caja, así que el ítem quedaría
    bloqueado para siempre; la factura copia descripción, precio e IVA y la baja es lógica, por lo que no se rompe nada.
  - **Descripción de Ítems** acepta además `, % ( ) + &` (`normalizar_descripcion(..., ampliada=True)`
    y `V.descripcion(v, {max:100, ampliada:true})`). Tipo Ítems y el resto mantienen la regla estricta.
  - Nuevos validadores compartidos (`utils.py` + `facturacion-validadores.js`, siempre en espejo):
    `validar_precio` (entero > 0, hasta 999.999.999.999), `validar_iva`, `validar_cantidad`,
    `validar_booleano`, `entero_id`; en JS `formatoGs()`.
  - La auditoría de Ítems guarda el nombre del tipo, no su ID.
- ✅ **Caja** (`caja`, ventana `caja`): `id_consultorio` → `consultorio(codigo)` (RESTRICT), descripción única
  por consultorio entre las activas. OJO: **la tabla `consultorio` no tiene baja lógica** (PK `codigo`, columna
  `nombre_consultorio`, borrado físico): "consultorio activo" = "consultorio existente". Seeds: CAJA RECEPCIÓN y
  CAJA ORTODONCIA en el 1.º consultorio (por código) y `CAJA <NOMBRE DEL 2.º CONSULTORIO>` en el 2.º.
  - **Primer referencial con reactivación:** `PATCH /api/v1/cajas/<id>/reactivar` (permiso `editar`), acción
    `REACTIVACION` en `auditoria_cambios` (se amplió su CHECK). Valida que el consultorio exista y que no haya
    otra caja activa con la misma descripción. El listado admite `?inactivas=1` (requiere `ver`); sin el parámetro
    solo trae activas (lo usan los combos de otras pantallas). La vista tiene el switch "Mostrar inactivas".
  - `esta_en_uso()` ya bloquea la baja de una caja con una apertura `ABIERTA` en `apertura_cierre_caja` ("No se
    puede dar de baja, la caja tiene una apertura activa."); `deleteCaja` pasó al protocolo transaccional
    (`FOR UPDATE`; abrir una caja toma `FOR SHARE` sobre ella).
  - **Cambio en Agendamiento:** `ConsultorioDao.estaEnUso` ahora cuenta las cajas (activas o inactivas, la FK es
    física) y `motivoEnUso()` da el texto ("No se puede eliminar, el consultorio tiene cajas asociadas."). Además se
    corrigió un bug de `consultorio_api.py`: trataba el `"EN_USO"` del DAO como éxito (200 sin borrar); ahora 409.
- ✅ **Depósito** (`deposito`, ventana `deposito`): el depósito FÍSICO donde se guardan los ítems (NO es una cuenta
  bancaria). `descripcion` + `ubicacion` (mayúsculas), único parcial por descripción, con Estado activo/inactivo,
  switch "Mostrar inactivos" y Reactivar (permiso `editar`, acción `REACTIVACION`): mismo patrón que Caja.
  - **Ítems ahora tienen depósito:** `items.id_deposito NOT NULL` → `deposito` (RESTRICT). El stock sigue siendo
    GLOBAL (`cantidad_disponible`); el depósito solo dice dónde se guarda. Alta/edición de ítem bloquea el depósito
    con `FOR SHARE` (siempre después del tipo, para no generar deadlocks). El formulario de Ítems tiene combo
    Depósito (solo activos) y el listado la columna Depósito.
  - **Baja de depósito** bloqueada con ítems activos ("No se puede dar de baja, el depósito tiene ítems
    asignados."); y, desde Remisión, con remisiones EMITIDAS (ver "Registrar Nota de Remisión").
  - **Migración** `migracion_items_deposito.sql` (idempotente; no hace nada si `items` aún no existe). Orden:
    `schema_tipo_items` → `schema_deposito` → `migracion_items_deposito` → `schema_items` → `schema_permisos_deposito`.
    Asigna ítems de tipo ORTODONCIA a DEPÓSITO ORTODONCIA y el resto a DEPÓSITO PRINCIPAL (solo filas sin depósito).
  - `validar_texto(..., mayusculas=True)` y `V.ubicacion` (espejo en JS) para la ubicación (máx. 100).
- ✅ **Cliente** (`cliente`, ventana `cliente`) — **último referencial: los 8 de Facturación están completos.**
  Usa la tabla existente `paciente` (PK `id_paciente`; `nombre`, `apellido`, `cedula_entidad` → CI/RUC, `telefono`,
  `correo`; sin baja lógica: "paciente activo" = "paciente existente"). `cliente.id_paciente` es NULL si no es paciente
  (FK RESTRICT). Los datos del paciente se COPIAN al dar de alta (se pueden corregir) y no se sincronizan;
  `id_paciente` es inmutable después del alta. Únicos parciales (activos): `ci_ruc` y `id_paciente`.
  - **Alta en 2 pasos:** "¿El cliente ya es paciente?" → buscador (`GET /api/v1/clientes/pacientes?q=`, mín. 2
    caracteres, por cédula o nombre; exige permiso `nuevo` porque expone datos personales) o carga manual.
  - **SIN NOMBRE (consumidor final, CI/RUC `44444401-7`, constante `CONSUMIDOR_FINAL_RUC` en `ClienteDao`):** no se
    modifica ni se da de baja (409). Se identifica por esa CI/RUC.
  - **CI/RUC:** cédula = 5 a 10 dígitos sin verificador; RUC = `dígitos-verificador` validado con módulo 11 de la
    SET, base máxima 11 (`calcular_dv_ruc` en `utils.py` y `calcularDvRuc` en el JS, siempre en espejo).
    OJO: el RUC de ejemplo `80012345-6` es inválido; el correcto es `80012345-0` (el de LABORATORIO DENTAL SONRISA).
  - Nuevos validadores compartidos: `validar_ci_ruc`, `validar_nombre` (mayúsculas; letras, números, espacios y
    `. , - & ' / ( )`), `validar_telefono_opcional`, `validar_correo_opcional` (+ espejo en JS).
  - `esta_en_uso()` ya bloquea si hay pedidos no anulados (`pedido_venta_cab`); TODO: ventas (`venta_cab`).
  - **Cambio en Agendamiento:** `PacienteDao.deletePaciente` devuelve `"EN_USO"` si el paciente es cliente (activo o
    inactivo, FK física) y la API responde 409 "No se puede eliminar, el paciente está registrado como cliente."
    (el riesgo de CASCADE al borrar un paciente con citas sigue sin resolverse, anotado más arriba).
- ✅ **Referenciales de Facturación completos** (Forma de Cobro, Marca de Tarjeta, Entidad Emisora, Entidad Adherida,
  Tipo Ítems, Ítems, Caja, Depósito, Cliente). Siguen los movimientos de Facturación.
- ✅ **Estado / "Mostrar inactivos" / Reactivar** (punto 4 del estándar) aplicado a **Forma de Cobro, Marca de Tarjeta,
  Entidad Emisora, Entidad Adherida, Tipo Ítems e Ítems**, con el patrón de Caja: `GET ...?inactivos=1` (exige `ver`),
  `PATCH .../reactivar` (permiso `editar`, acción `REACTIVACION`), `reactivarX()` en el DAO en una sola transacción
  con la fila bloqueada, 409 con mensaje claro. No hizo falta SQL. Qué valida cada una al reactivar: descripción
  duplicada entre las activas (todas); **Adherida**: además, que la emisora y la marca estén ACTIVAS (una baja de
  emisora/marca solo se bloquea con adheridas *activas*, así que puede haber una adherida inactiva con el padre
  anulado) y el duplicado de (descripción, emisora, marca); **Ítems**: que el tipo y el depósito estén ACTIVOS.
  - **Ítems, stock al reactivar:** si el tipo dejó de controlar stock mientras el ítem estaba anulado (se permite: la
    verificación solo mira ítems *activos*) y el ítem conservaba cantidad, **el stock se pone en 0** y se avisa en el
    mensaje y en el detalle de auditoría (`Stock: N -> 0 (el tipo no controla stock)`). `reactivarItem` devuelve
    `(STOCK_REINICIADO, stock_anterior)` en ese caso.
  - **Forma de Cobro** pasó al protocolo `esta_en_uso()` (`False` o texto) / `deleteFormaCobro()` →
    `("EN_USO", motivo)`, con la verificación y el UPDATE en una transacción (`_motivo_en_uso` ya consulta `cobro_det`).
  - Las 6 vistas usan `facturacion-listado.js`. Verificadas con un navegador real (Edge headless, `fetch` simulado):
    switch, filas, badges, botón Reactivar, diálogos de SweetAlert2, PATCH/DELETE, recarga y los modales Agregar/Editar.

### Movimientos de Facturación
Menú: **"Módulo Facturación"** (separado de "Referenciales Facturación"). Vista en `base_tabler.html`, permisos y
auditoría como siempre. Las URL siguen la convención del proyecto (`/referenciales/<modulo>`, API en `/api/v1`).

- ✅ **Registrar Apertura y Cierre de Caja** (`apertura_cierre_caja`, ventana `aperturacaja`, acciones `ver`, `nuevo` =
  abrir, `anular`, `estado` = cerrar). Script: `app/dao/modulo_facturacion/schema_apertura_cierre_caja.sql` (+
  `schema_permisos_apertura_caja.sql`). **Solo el rol Cajero recibe los permisos** por el seed (son movimientos de
  dinero; el Administrador pasa siempre; Recepción/Médico se habilitan desde la matriz si hace falta). La regla
  completa del Cajero está en "Modelo de permisos".
  - Estados `ABIERTA → CERRADA | ANULADA` (finales). Índices únicos parciales `WHERE estado = 'ABIERTA'` por cajero
    y por caja: un cajero, una apertura; una caja no se abre dos veces. Mensajes: "Debe cerrar la apertura actual antes
    de abrir una nueva." y "La caja ya está abierta por otro usuario." (la verificación previa da el mensaje; los
    índices son la red de seguridad).
  - **El cajero (`id_usuario`) sale SIEMPRE de la sesión**, nunca del cuerpo del pedido. El Administrador ve todas las
    aperturas; los demás solo las propias (filtro en el servidor). Filtros `?estado=&desde=&hasta=` (hasta inclusivo).
  - **Anular** y **cerrar**: solo la apertura propia o cualquiera si es Administrador, y solo si está `ABIERTA`.
    Anular se bloquea si el turno tiene movimientos (`_motivo_con_movimientos`: ventas EMITIDAS y cobros EMITIDOS).
    **Cerrar**: los importes los calcula el servidor (el cliente no manda nada) y `GET /aperturas-caja/<id>/cierre` da el
    detalle previo a confirmar. Desde Cobranzas: `total_recaudado` = TODO lo cobrado (`fn_total_recaudado`) y
    `monto_cierre = monto_apertura + solo el EFECTIVO cobrado` (`fn_total_efectivo_apertura`); el detalle muestra el desglose
    por forma de cobro con `v_resumen_caja` (ver "Registrar Cobranzas").
  - Auditoría: apertura = `ALTA`, anulación = `BAJA`, cierre = **`CIERRE`** (se amplió el CHECK de `auditoria_cambios`).
  - Validador nuevo `validar_monto` (entero **≥ 0**, a diferencia de `validar_precio`) con su espejo `V.monto`; la API
    usa un único mensaje: "El monto de apertura debe ser un número entero mayor o igual a 0."
  - Bloqueo cruzado: no se puede dar de baja una caja con apertura `ABIERTA` (ver Caja).
  - Test: `tests/facturacion/smoke_apertura_caja.py` (usa usuarios REALES con sesiones simuladas y **aborta si alguno
    de ellos tiene una caja abierta de verdad**: cerrarla antes de correrlo).

- ✅ **Registrar Pedido Cliente** (`pedido_venta_cab` + `pedido_venta_det`, ventana `pedidocliente`, acciones `ver`,
  `nuevo`, `anular`). Scripts: `app/dao/modulo_facturacion/schema_pedido_venta.sql` y
  `app/dao/modulo_seguridad/schema_permisos_pedido_cliente.sql` (idempotentes; el Cajero recibe las 3 acciones).
  - **Decisión de análisis:** el Pedido es el paso **PREVIO** a la Venta de Ítems. **El stock se descuenta SOLO en el
    Pedido** (al crearlo) y se repone al anularlo. La Venta de Ítems (próximo movimiento) se generará desde un Pedido
    `PENDIENTE` y lo pasará a `FACTURADO` (la Venta no vuelve a tocar el stock). **La Venta de Tratamiento no usa pedido.**
  - Estados `PENDIENTE → FACTURADO | ANULADO`. `FACTURADO` lo pone la Venta (todavía no existe). Un FACTURADO no se
    anula: 409 "El pedido ya fue facturado; no se puede anular."
  - **Alta (una transacción):** cliente ACTIVO (`FOR SHARE`; SIN NOMBRE vale), al menos un ítem activo, cantidad
    entera > 0, sin ítems repetidos. Los ítems se bloquean con `FOR UPDATE` **en orden de `id_item`** (más el tipo con
    `FOR SHARE`), así dos pedidos con los mismos ítems en distinto orden no se traban. Si el tipo controla stock se
    valida y descuenta ("Stock insuficiente para <ÍTEM>: disponible N, solicitado M.", 409, no cambia nada); si no, ni
    se valida ni se descuenta. **Precio, IVA, subtotal y total los calcula el SERVIDOR desde `items`**; el cajero
    (`id_usuario`) sale de la sesión; cualquier importe/usuario/estado que mande el navegador se ignora.
  - **IVA incluido en el precio.** Totales: Exentas, Gravadas 5% y Gravadas 10% (suma de subtotales por tasa) y Total;
    IVA liquidado = gravadas10/11 y gravadas5/21, redondeado (`calcular_totales` en `PedidoClienteDao`; el JS de la
    vista lo repite solo para mostrarlo en vivo).
  - **Anular:** solo PENDIENTE, con la fila bloqueada; repone el stock de los ítems que controlan stock en la misma
    transacción. Si desde el pedido el tipo del ítem **dejó de controlar stock** no se repone (queda anotado en la
    auditoría: "Sin reposición"). **Cualquiera con permiso `anular` puede anular cualquier pedido**; la auditoría
    registra quién.
  - **Visibilidad:** todos los usuarios con `ver` ven **TODOS** los pedidos (trabajo compartido entre cajeros; la Venta
    debe poder tomar cualquier pedido pendiente). Distinto de Apertura de Caja, que filtra por cajero.
    Filtros `?estado=&cliente=(nombre o CI/RUC)&desde=&hasta=`.
  - **No exige caja abierta** (el pedido no mueve dinero); la apertura la exige la Venta.
  - **Buscadores del formulario** `GET /pedidos-cliente/clientes?q=` y `/items?q=`: piden `nuevo` de esta ventana
    (no el `ver` de Cliente/Ítems). Detalle `GET /<id>`, PDF `GET /<id>/pdf` (ReportLab, `app/Services/pedido_pdf_service.py`;
    un pedido anulado se descarga con la marca "ANULADO").
  - **Conexiones:** `ItemDao.esta_en_uso` bloquea la baja de un ítem en un pedido PENDIENTE ("No se puede dar de baja,
    el ítem está en un pedido pendiente."; `deleteItem` ahora toma `FOR UPDATE` sobre el ítem y verifica en la misma
    transacción; TODO `venta_det`). `ClienteDao.esta_en_uso` bloquea la baja con pedidos no anulados (PENDIENTE o
    FACTURADO; TODO `venta_cab`).
  - Auditoría (`entidad = 'pedido_venta_cab'`): `ALTA` con cliente, cajero, total e ítems (nombres); `BAJA` con el
    stock repuesto.
  - Validadores nuevos en espejo: `validar_cantidad_positiva` (un único mensaje: "La cantidad debe ser un número
    entero mayor a 0.") / `V.cantidadPositiva` y `validar_observacion` (opcional, hasta 200) / `V.observacion`.
  - La Venta de Ítems ya existe (ver "Registrar Ventas"): pasa el pedido `PENDIENTE → FACTURADO` con `FOR UPDATE` sobre
    `pedido_venta_cab` (igual que `anularPedido`) y lo devuelve a `PENDIENTE` si se anula la venta (o lo anula y repone el
    stock si se marca la casilla; esa reposición está en `PedidoClienteDao.anular_y_reponer_en_cursor`, compartida con
    `anularPedido`). `ItemDao.esta_en_uso` NO bloquea por ventas (decisión en "Registrar Ventas — etapa 2").
  - Test: `tests/facturacion/smoke_pedido_cliente.py` (118 chequeos, incluida la concurrencia de stock).

- ✅ **Registrar Ventas y Generar Cuentas a Cobrar — ETAPA 1** (`venta_cab` + `venta_det` + `cuenta_cobrar`, ventana
  `venta`, acciones `ver`, `nuevo`, `anular`; el Cajero las recibe todas). Scripts (idempotentes, en este orden):
  `schema_empresa_timbrado.sql`, `schema_ventas.sql`, `schema_objetos_bd.sql` (SP, triggers, vista) en
  `app/dao/modulo_facturacion/` y `schema_permisos_ventas.sql` en `app/dao/modulo_seguridad/`. Aplicarlos con
  `PGCLIENTENCODING=UTF8` (tienen tildes).
  - **Configuración sin pantalla (por script):** `empresa` (una sola fila: CLÍNICA ODONTOLÓGICA ODONTOCLINIC S.A., RUC
    `80099999-1`, el dígito sale de `calcular_dv_ruc`) y `timbrado` (`12345678`, 2026-10-01 a 2027-09-30, `001-001`, del 1
    al 5000, `numero_actual` 0 = último emitido; un solo activo por índice único parcial).
  - **Nueva venta de ítems:** exige una apertura de caja ABIERTA del cajero ("Debe abrir la caja antes de registrar una
    venta."). Se elige un **Pedido PENDIENTE** (buscador por N.º, cliente o CI/RUC); cliente, ítems, **precio e IVA se copian
    del pedido** (no del ítem actual). Una transacción: toma la apertura (`FOR SHARE`) y el pedido (`FOR UPDATE`, el mismo
    bloqueo que anular pedido), llama a `sp_siguiente_numero_factura`, inserta cabecera y detalle con los totales calculados
    por el servidor (`calcular_totales`: IVA incluido, Exentas/Gravadas 5%/10%, IVA = gravada10/11 y gravada5/21) y pasa el
    pedido a `FACTURADO`. **La venta NO toca el stock** (ya se descontó en el pedido). El trigger crea la cuenta a cobrar.
    Condición Contado (vence el día de la venta) o Crédito (+30 días). El cajero sale de la sesión; cualquier otro dato del
    navegador se ignora. Si algo falla después del SP, el número se deshace (no quedan huecos). El índice único parcial
    `ux_venta_pedido_emitida` (id_pedido WHERE EMITIDA) es la red de seguridad de "un pedido se factura una sola vez".
  - **Anular:** **todos con `ver` ven todas las ventas y cualquiera con `anular` puede anular, PERO solo si la apertura de
    caja de esa venta sigue ABIERTA** (`FOR SHARE` sobre la apertura: un cierre concurrente espera); si ya está cerrada:
    "La caja de esta venta ya fue cerrada; utilice una Nota de Crédito." (409). La venta pasa a `ANULADA` (**el número de
    factura NO se reutiliza**), el trigger anula la cuenta y el pedido vuelve a `PENDIENTE` (se puede volver a facturar).
    `_motivo_con_cobros` es un TODO hasta Cobranzas: "No es posible anular, existen cobros registrados. Utilice una Nota de
    Crédito."
  - **Conexiones:** `AperturaCajaDao._motivo_con_movimientos` bloquea anular una apertura con ventas EMITIDAS;
    `ClienteDao.esta_en_uso` bloquea la baja con ventas no anuladas; un pedido FACTURADO no se anula. La auditoría registra
    `ALTA`/`BAJA` en `venta_cab` y `MODIFICACION` del pedido (PENDIENTE ↔ FACTURADO).
  - **(Resuelto en Cobranzas)** el "¿cobrar ahora?", `_motivo_con_cobros`, `_total_recaudado` de la
    caja (hoy 0) y completar `v_estado_cuenta_cliente` con los cobros. La **Venta de Tratamiento** y la factura en PDF
    se hicieron en la etapa 2 (sección siguiente).
  - Pantalla `venta-index.html` (diseño de `facturacion.css`): listado con filtros (estado, tipo, cliente/N.º de factura,
    fechas), Nueva Venta (aviso de caja, pedido precargado en solo lectura) y Ver en modo comprobante (empresa, timbrado).
    El candado reemplaza a "Anular" cuando la caja de la venta está cerrada. Enter en el buscador nunca envía el formulario.
  - Test: `tests/facturacion/smoke_ventas.py`.
- ✅ **Registrar Ventas — ETAPA 2: Venta de Tratamiento, factura en PDF y ajustes.** Script nuevo (idempotente, después de
  `schema_ventas.sql`): `app/dao/modulo_facturacion/schema_ventas_etapa2.sql` (amplía `venta_det.descripcion` a
  `VARCHAR(200)` —la descripción del tipo de tratamiento se copia COMPLETA, sin recortar— y agrega índices por
  `id_tratamiento` e `id_item`; no crea tablas).
  - **Venta de tratamiento** (`tipo_venta = 'TRATAMIENTO'`, sin pedido; `POST /ventas` con
    `{tipo_venta, id_cliente, id_paciente, ids_tratamiento[], condicion}`): exige caja ABIERTA. Se elige el cliente; si está
    vinculado a un paciente se precarga (se puede cambiar), si no se busca el paciente. Se listan los tratamientos del paciente
    **no cancelados y sin venta EMITIDA** (incluye los finalizados; `GET /ventas/tratamientos?id_paciente=`). Cada renglón:
    descripción del tipo, cantidad 1, **precio e IVA de `tipos_tratamiento` al momento de la venta** (la factura conserva el
    suyo aunque el tipo cambie). Transacción: apertura (`FOR SHARE`), cliente (`FOR SHARE`), tratamientos (`FOR UPDATE` en
    orden de id) → no cancelados, del paciente y sin factura vigente ("El tratamiento <descripción> ya fue facturado en la
    factura <número>."), mismo SP de numeración y mismos totales; el trigger crea la cuenta a cobrar. Buscadores nuevos (piden
    `nuevo`): `GET /ventas/clientes?q=` (trae el paciente vinculado), `/ventas/pacientes?q=` (mín. 2 caracteres: expone datos
    personales) y `/ventas/tratamientos`. La pantalla Nueva Venta tiene un selector de tipo (Ítems desde Pedido / Tratamiento).
  - **Conexión con Consultorio:** `TratamientoDao.deleteTratamiento` (el único camino a `cancelado`) bloquea la fila
    (`FOR UPDATE`) y verifica en la misma transacción que no haya una venta EMITIDA: devuelve `"FACTURADO"` y la API responde
    409 "El tratamiento ya fue facturado; anule primero la factura." (finalizar un tratamiento facturado sigue permitido).
    Facturar y cancelar a la vez nunca pueden ganar los dos (mismo bloqueo de fila).
  - **Anular:** venta de ítems: casilla "Anular también el pedido y reponer el stock", **desmarcada por defecto**
    (`DELETE /ventas/<id>?anular_pedido=1`): desmarcada el pedido vuelve a PENDIENTE (el stock sigue descontado); marcada, en la
    misma transacción la venta queda ANULADA, el pedido ANULADO y el stock repuesto (`anular_y_reponer_en_cursor`; si el tipo ya
    no controla stock no se repone). Venta de tratamiento: al anularla los tratamientos quedan libres (la disponibilidad se
    calcula desde las ventas EMITIDAS; no se guarda estado). Siguen las reglas de caja ABIERTA y sin cobros. La auditoría del
    alta pone el total y la condición ANTES de la lista de tratamientos (el detalle admite 255 caracteres).
  - **Factura en PDF** (`app/Services/factura_pdf_service.py`, ReportLab, al vuelo; `GET /api/v1/ventas/<id>/pdf`, permiso
    `ver`): dividida en `calcular_datos_factura(venta)` (CÁLCULO: dict puro con columnas Exentas/5%/10%, subtotales, total, total
    en letras e IVA liquidado), `dibujar_factura(canvas, datos, copia)` (DIBUJO: solo layout; para mejorar el diseño se toca
    esto) y `generarFacturaPdf(venta)` (arma ORIGINAL — cliente y DUPLICADO — archivo tributario: 2 páginas para una factura
    chica; una factura larga sigue en páginas adicionales por copia, con el pie solo en la última). Cabecera con empresa y
    timbrado, "FACTURA" y el número; pie con subtotales, TOTAL A PAGAR, "SON GUARANÍES: …." y liquidación del IVA. Una factura
    anulada se descarga igual, con la marca "ANULADA" en rojo. Botón PDF en el listado y en el comprobante, y el diálogo al
    guardar ofrece "Ver factura (PDF)".
  - **Número a letras** (`app/Services/numero_letras.py`, función pura; `numero_a_letras` y `monto_en_letras`): 0 a
    999.999.999.999; "UNO" cuando va solo, apócope delante de MIL/MILLONES (VEINTIÚN MIL, UN MILLÓN, TREINTA Y UN MILLONES),
    1.000 = MIL, 100 = CIEN, 0 = CERO.
  - **Decisión: `ItemDao.esta_en_uso` NO bloquea por ítems en ventas EMITIDAS** (ver Tipo Ítems/Ítems): la factura copia
    descripción, precio e IVA, la baja es lógica y una factura vigente no se puede anular después del cierre de caja, así que
    el ítem quedaría bloqueado para siempre. Sigue bloqueando solo por pedidos PENDIENTES.
  - Tests: `tests/facturacion/smoke_numero_letras.py` (sin base de datos) y las secciones de etapa 2 de `smoke_ventas.py`
    (PDF decodificando los streams sin librerías: 2 páginas, número, RUC, total, marca ANULADA; venta de tratamiento incluida la
    doble facturación concurrente; anulación con y sin casilla; bloqueo en Consultorio). Los datos de prueba incluyen un
    paciente, tipos y tratamientos `ZZ`, que se borran por ID.

- ✅ **Registrar Cobranzas por Forma de Cobro** (ventana `cobro`, acciones `ver`, `nuevo`, `anular`; el Cajero las recibe todas).
  Usa las tablas que creó `01_migracion_der.sql` **tal cual**: `cobro_cab` (`id_cuenta`, `id_apertura`, `id_usuario`,
  `numero_recibo` único, `total > 0`, `observacion`, `estado` EMITIDO/ANULADO; **sin `id_cliente`: el cliente sale de la cuenta**),
  `cobro_det` (una fila por forma de cobro), `cobro_tarjeta` (`id_entidad_adherida`, `tipo_tarjeta` CREDITO/DEBITO,
  `ultimos_digitos`, `numero_autorizacion`; **la marca y la emisora salen de la adherida**) y `cobro_cheque` (`id_entidad_emisora`,
  `numero_cheque`, `titular`, `fecha_emision`, `fecha_cobro`). Scripts (idempotentes, en este orden):
  `01_migracion_der.sql` → `schema_cobranzas_columnas.sql` → `schema_cobranzas.sql` (objetos) en `app/dao/modulo_facturacion/`,
  y `schema_permisos_cobranzas.sql` → `schema_permisos_cajero.sql` en `app/dao/modulo_seguridad/` (`schema_permisos_id_menu.sql` quedó obsoleto: ya solo elimina el trigger).
  - ⚠️ **Dos columnas NUEVAS que NO están en el DER de la tesis y hay que agregarlas al DER:**
    **`forma_cobro.tipo`** `VARCHAR(15) NOT NULL CHECK (tipo IN ('EFECTIVO','TARJETA','CHEQUE','TRANSFERENCIA'))` (define qué datos
    pide el cobro y qué cuenta como efectivo en el cierre; combo "Tipo" y columna en la pantalla de Formas de Cobro, obligatorio en la
    API; **no se puede cambiar el tipo de una forma ya usada en cobros**) y **`cobro_det.numero_referencia`** `VARCHAR(30) NULL`
    (número de referencia de la transferencia; obligatorio solo si la forma es TRANSFERENCIA y prohibido en las demás).
    La migración asigna el tipo por la descripción; **`NOT NULL` queda pendiente** hasta que se resuelva la fila que no se pudo
    deducir (`#17 "BHDJDGJ"`): editar su tipo (o darla de baja) y volver a correr `schema_cobranzas_columnas.sql`. Mientras tanto
    el cobro rechaza una forma sin tipo ("La forma de cobro <X> no tiene tipo asignado.").
  - **Cobro** (`POST /cobros`, una transacción): caja ABIERTA del cajero (`FOR SHARE`; "Debe abrir la caja antes de registrar un cobro."),
    cuenta PENDIENTE (`FOR UPDATE`; "La cuenta a cobrar ya está pagada." / "está anulada."), **suma de formas = total** (no se
    acepta un total aparte) y **total ≤ saldo** ("El monto supera el saldo pendiente de Gs. N."). Pagos parciales y varias formas
    juntas (sin vuelto; se puede cobrar una cuenta vencida). Por forma: EFECTIVO solo monto; **TARJETA**: adherida (con marca y
    emisora activas; el tipo crédito/débito se deduce de la descripción de la forma y no puede contradecirla), últimos 4 dígitos y
    autorización; **CHEQUE**: emisora activa, número, titular y fechas (**cheque diferido: la fecha de cobro puede ser futura; la
    de emisión no puede ser posterior a hoy y la de cobro no anterior a la de emisión**); **TRANSFERENCIA**: referencia. Las formas
    y entidades se bloquean con `FOR SHARE` (una baja concurrente espera). El cajero y la apertura salen de la sesión.
  - **Recibo** `REC-0000001`, **sin huecos** (`fn_siguiente_numero_recibo`: mayor número usado + 1 bajo un bloqueo asesor; el
    anulado conserva el suyo). **Recibo de dinero en PDF** (`app/Services/recibo_pdf_service.py`, mismo patrón que la factura:
    `calcular_datos_recibo` / `dibujar_recibo` / `generarReciboPdf`; ORIGINAL y DUPLICADO, marca "ANULADO"), `GET /cobros/<id>/pdf`.
  - **Anular** (`DELETE /cobros/<id>`, cualquiera con `anular`): solo si la apertura del cobro sigue ABIERTA ("La caja de este cobro
    ya fue cerrada; utilice una Nota de Crédito."); el trigger repone el saldo y la cuenta vuelve de PAGADA a PENDIENTE.
  - **Cierre de caja:** `total_recaudado` = todo lo cobrado; **`monto_cierre = monto_apertura + solo el EFECTIVO`** (tarjetas, cheques y
    transferencias no son plata en el cajón); el detalle del cierre muestra el desglose por forma (`v_resumen_caja`).
  - **Conexiones:** la venta ofrece "¿Cobrar ahora?" (abre `/referenciales/cobro/cobro-index?cuenta=<id>`); anular una venta con
    cobros EMITIDOS se bloquea ("No es posible anular, existen cobros registrados. Utilice una Nota de Crédito.", bloqueando antes la
    cuenta `FOR UPDATE`); anular una apertura con cobros se bloquea; `esta_en_uso` de **Forma de Cobro, Marca, Entidad Adherida y
    Entidad Emisora** consulta los cobros EMITIDOS (la Adherida pasó al protocolo transaccional `FOR UPDATE`).
  - **Pantalla** `cobro-index.html`: listado con filtros (estado, cliente/N.º de factura/N.º de recibo, fechas) y Ver/PDF/Anular (candado si la
    caja se cerró); Nuevo Cobro: buscar la cuenta (muestra total, saldo y vencimiento, con aviso "Vencida"), grilla de formas con los campos
    de cada tipo, total en vivo y saldo restante, "Cobrar todo el saldo". Nuevos validadores en espejo: `validar_monto_positivo` /
    `V.montoPositivo`, `validar_codigo` / `V.codigo`, `validar_ultimos_digitos` / `V.ultimosDigitos`.
  - Tests: `tests/facturacion/smoke_cobranzas.py` (usa como cajero al Administrador y un timbrado ZZ INACTIVO: no consume números reales y
    no depende de la caja del Cajero real) y el helper `tests/facturacion/_pdf.py` (leer PDFs de ReportLab sin librerías).
  - **Pendiente:** cobrar en el momento de la venta de contado sin pasar por la pantalla de cobros (la Nota de Crédito y el Arqueo ya existen) y, cuando exista,
    cobrar en el momento de la venta de contado sin pasar por la pantalla de cobros.

- ✅ **Registrar Nota de Remisión** (`nota_remision_cab` + `nota_remision_det` del DER, usadas **tal cual**, ventana `remision`, acciones `ver`,
  `nuevo`, `anular`; el Cajero las recibe todas, queda con 27 filas). Scripts (idempotentes): `app/dao/modulo_facturacion/schema_remision.sql`
  (solo funciones, triggers y vista; ninguna tabla) y `app/dao/modulo_seguridad/schema_permisos_remision.sql` (fila `remision` en `menu` + permisos
  del Cajero), más `schema_permisos_cajero.sql`. Aplicar con `PGCLIENTENCODING=UTF8`.
  - **Negocio:** documenta la ENTREGA de mercadería de una **Venta de Ítems EMITIDA**; **no mueve stock** (ya se descontó en el Pedido). Solo
    entran ítems cuyo tipo **controla stock** (los servicios no aparecen). **Entregas parciales:** lo remitido (remisiones EMITIDAS) por ítem no
    puede superar lo facturado ("Cantidad a remitir de <ÍTEM> supera lo pendiente de entrega: N."). El **depósito de origen se elige a mano**
    (solo activos) y la remisión incluye SOLO los ítems de la venta guardados en ese depósito (`items.id_deposito`; "El ítem <ÍTEM> no está en el
    depósito seleccionado."): si la venta tiene ítems en varios depósitos se emiten remisiones separadas. **Motivo de traslado fijo `VENTA`**
    (lo que mande el navegador se ignora, igual que usuario, número y estado). La cabecera pide además fecha de traslado (no anterior a hoy),
    dirección de llegada (máx. 150) y responsable del traslado (mayúsculas, máx. 80); observación opcional.
  - **Numeración** `REM-0000001` sin huecos (`fn_siguiente_numero_remision`: mayor usado + 1 bajo un bloqueo asesor; la anulada conserva el suyo).
  - **Objetos de BD:** `trg_validar_remision_cab` (BEFORE INSERT: venta de ítems y EMITIDA, la bloquea `FOR UPDATE`), `trg_validar_remision_det`
    (BEFORE INSERT/UPDATE del detalle: remisión emitida, ítem de la venta, que controle stock, en el depósito de la remisión y cantidad ≤ pendiente;
    bloquea la venta, así que dos remisiones simultáneas de la misma venta se serializan), `trg_remision_estado` (una anulada no se reactiva),
    `trg_bloquear_anular_venta_remitida` (red de seguridad en `venta_cab`) y la vista **`v_pendientes_entrega`** (por venta e ítem que controla
    stock: facturado, remitido —solo EMITIDAS— y pendiente, con el depósito). Todo con comentarios y `COMMENT ON`.
  - **Anular** (`DELETE /remisiones/<id>`, cualquiera con `anular`): pasa a `ANULADA` y **libera las cantidades** (la vista solo cuenta EMITIDAS);
    no exige caja abierta (no mueve dinero) y no toca el stock. Todos los usuarios con `ver` ven todas las remisiones.
  - **Conexiones:** anular una **venta** con remisiones EMITIDAS se bloquea (409 "No es posible anular, existen remisiones emitidas. Anule primero las
    remisiones.", también en la base); una venta ANULADA o de tratamiento no admite remisión; `DepositoDao._motivo_en_uso` ya consulta las remisiones
    EMITIDAS (cerró el TODO de `nota_remision`). `ItemDao.esta_en_uso` NO bloquea por remisiones (misma decisión que con las ventas EMITIDAS).
  - **PDF** (`app/Services/remision_pdf_service.py`, mismo patrón que factura y recibo: `calcular_datos_remision` / `dibujar_remision` /
    `generarRemisionPdf`; ORIGINAL y DUPLICADO, continúa en otra página si hay muchos ítems, marca "ANULADA"), `GET /remisiones/<id>/pdf`.
  - **Pantalla** `remision-index.html`: listado con filtros (estado, cliente/N.º de factura/N.º de remisión, fechas) y Ver/PDF/Anular; Nueva Remisión:
    buscar la venta (solo ventas con mercadería pendiente), combo de depósitos (muestra cuántos ítems pendientes tiene cada uno y deshabilita los
    que no tienen), datos del traslado y grilla facturado / ya remitido / pendiente / a remitir, con "Remitir todo lo pendiente".
  - Tests: `tests/facturacion/smoke_remision.py` (158 chequeos; no depende de que alguien tenga una caja abierta: la apertura de prueba se crea por SQL a
    nombre de un usuario libre).
  - **Pendiente:** ninguno propio (la Nota de Crédito/Débito y el Arqueo de Caja ya están hechos).
- ✅ **Registrar Notas de Crédito y Débito** (`nota_credito_debito_cab` + `nota_credito_debito_det` del DER, ventana `notacd`, acciones `ver`,
  `nuevo`, `anular`; el Cajero las recibe todas y queda con 30 filas). Scripts (idempotentes, en este orden): `schema_notas_columnas.sql`,
  `schema_notas.sql` (en `app/dao/modulo_facturacion/`; funciones, triggers y vistas), `schema_permisos_notas.sql` (fila `notacd` en `menu` + permisos
  del Cajero) y `schema_permisos_cajero.sql`. Aplicar con `PGCLIENTENCODING=UTF8`.
  - ⚠️ **Dos columnas NUEVAS en `nota_credito_debito_cab` que NO están en el DER y hay que agregarlas al DER** (junto con `forma_cobro.tipo` y
    `cobro_det.numero_referencia` de Cobranzas): **`id_apertura`** `INT NOT NULL` FK a `apertura_cierre_caja` (RESTRICT; la caja en que se emitió la nota:
    toda nota, de crédito o de débito, exige caja ABIERTA del cajero) y **`monto_reintegro`** `NUMERIC(12,0) NOT NULL DEFAULT 0` (parte de la nota de
    crédito devuelta en efectivo; CHECK: 0 <= reintegro <= total y 0 en los débitos). Sin ellas no se podía anular "solo con la caja de la nota abierta"
    ni restar el reintegro del cierre. La "devolución de mercadería" no necesita bandera: un renglón con `id_item` ES una devolución.
  - **Nota:** toda nota se vincula a una **venta EMITIDA** (por su cuenta a cobrar) y lleva motivo obligatorio (máx. 200) y renglones con descripción,
    monto (IVA incluido) e IVA 0/5/10; **el servidor calcula totales e IVA como en la factura** (`calcular_totales`) y el número, el reintegro, el usuario
    y la caja salen del servidor/sesión (lo que mande el navegador se ignora). Un renglón libre se guarda con cantidad 1 y precio = monto.
  - **Numeración** `001-001-0000001` (establecimiento y punto del **timbrado activo vigente**), **propia por tipo** (CRÉDITO y DÉBITO llevan cada uno la
    suya), correlativa y **sin huecos** (`fn_siguiente_numero_nota(tipo)`: mayor número del tipo + 1 bajo un bloqueo asesor). No consume el rango de las
    facturas (`timbrado.numero_actual`); solo exige vigencia ("No hay timbrado activo", "aún no está vigente", "está vencido").
  - **CRÉDITO:** el total no puede superar (total de la factura − créditos EMITIDOS anteriores) ("El total de la nota de crédito (Gs. A) supera el máximo
    permitido (Gs. B)."). **Primero reduce el saldo pendiente; si la factura ya estaba pagada (o el crédito excede el saldo) el excedente es un REINTEGRO EN
    EFECTIVO** al cliente: sale de la caja, se registra en `monto_reintegro` y **RESTA del efectivo del cierre**. Se **bloquea** si no hay efectivo en
    la caja: "No hay efectivo suficiente en la caja para el reintegro (disponible Gs. N)." (disponible = monto de apertura + efectivo cobrado − reintegros
    previos; se atienden en orden por el bloqueo `FOR UPDATE` de la apertura). **Devolución de mercadería** (opción del crédito sobre ventas de ítems): repone el
    stock de los ítems devueltos en la misma transacción; solo ítems de la factura cuyo tipo controla stock y sin superar lo facturado menos lo ya devuelto
    ("Cantidad a devolver de <ÍTEM> supera lo facturado pendiente de devolución: N."); el precio e IVA salen de la FACTURA.
  - **DÉBITO:** suma al saldo y, si la cuenta estaba PAGADA, vuelve a PENDIENTE; sin tope.
  - **Anular** (`DELETE /notas-credito-debito/<id>`, cualquiera con `anular`): **solo con la caja de la nota ABIERTA** ("La caja de esta nota ya fue cerrada; no
    se puede anular."); revierte el efecto en el saldo (crédito: devuelve lo que había reducido; el reintegro vuelve a la caja solo, porque las funciones de
    caja cuentan únicamente notas EMITIDAS), el stock (se descuenta lo repuesto; si ya no alcanza, 409) y el reintegro. Un **débito** con cobros posteriores
    que dejarían el saldo negativo no se anula. Una nota anulada no se reactiva y su número no se reutiliza.
  - **Objetos de BD** (todos con comentarios y `COMMENT ON`): `fn_siguiente_numero_nota`, `trg_preparar_nota` (BEFORE INSERT: caja abierta —la bloquea—,
    venta EMITIDA, máximo del crédito, cálculo y control del reintegro), `trg_aplicar_nota` (AFTER INSERT/UPDATE de estado: aplica o revierte sobre
    `cuenta_cobrar`), `trg_validar_nota_det` (devolución de mercadería), `trg_validar_nota` (diferido: tiene renglones y totales por tasa coinciden),
    `trg_bloquear_anular_venta_con_notas`, `fn_total_reintegros`; **actualizadas**: `fn_total_recaudado` (cobrado − reintegros), `fn_total_efectivo_apertura`
    (efectivo cobrado − reintegros), `v_resumen_caja` (+ una fila `REINTEGRO` en negativo), `v_estado_cuenta_cliente` (+ `total_notas_credito`,
    `total_notas_debito`, `cantidad_notas` al final) y `v_libro_ventas` (+ las notas, el crédito en NEGATIVO, columna `comprobante` al final).
  - **Cierre de caja:** `monto_cierre = monto_apertura + efectivo cobrado − reintegros`; el detalle muestra "Efectivo cobrado", "Reintegros en efectivo" y el
    desglose por forma con la fila de reintegro; la auditoría del cierre menciona los reintegros.
  - **Conexiones:** anular una **venta** con notas EMITIDAS se bloquea (409 "No es posible anular, existen notas de crédito o débito emitidas. Anúlelas
    primero.", también en la base); anular una **apertura** con notas se bloquea; una venta ANULADA no admite notas. El mensaje "utilice una Nota de Crédito"
    de ventas y cobros con la caja cerrada ya tiene a dónde apuntar.
  - **PDF** (`app/Services/nota_pdf_service.py`): reutiliza el diseño de la factura (`calcular_datos_factura` + `dibujar_factura`, parametrizados con
    `titulo`, `etiqueta_total`, `mostrar_condicion` y `lineas_extra`: factura de referencia, motivo, devolución y reintegro); ORIGINAL y DUPLICADO,
    marca "ANULADA"; `GET /notas-credito-debito/<id>/pdf`.
  - **Pantalla** `nota-index.html`: listado con filtros (tipo, estado, cliente/N.º de factura/N.º de nota, fechas), Ver/PDF/Anular (candado si la caja se
    cerró); Nueva Nota: tipo (crédito/débito), buscar la factura (total, saldo, notas previas y **máximo permitido**), caja con el efectivo disponible,
    motivo, renglones libres o devolución de mercadería (facturado / ya devuelto / pendiente / a devolver) y totales en vivo con el efecto en el saldo y el reintegro.
  - Tests: `tests/facturacion/smoke_notas.py` (205 chequeos; usa como emisor a un Cajero/Administrador SIN caja abierta y una apertura ZZ por SQL: no toca ninguna
    caja real). `smoke_cobranzas.py` ahora también cobra con un usuario sin caja abierta (ya no aborta por la caja real del Administrador).
  - **Pendiente:** ninguno propio (el Arqueo de Caja ya está hecho; ver abajo).

- ✅ **Mantener Cuenta Bancaria** (referencial nuevo, ventana `cuentabancaria` en "Referenciales Facturación"; el Cajero solo `ver`): la cuenta del **banco** donde
  se DEPOSITA el dinero de la recaudación (distinta de la tabla `deposito`, que es el depósito físico de productos). Script (idempotente):
  `app/dao/modulo_facturacion/schema_cuenta_bancaria.sql` + `app/dao/modulo_seguridad/schema_permisos_cuenta_bancaria.sql`.
  - ⚠️ **Hay que sumar al DER:** la tabla **`cuenta_bancaria`** (`id_cuenta_bancaria`, `id_entidad_emisora` FK RESTRICT al banco, `tipo_cuenta` CHECK
    `CORRIENTE`/`CAJA DE AHORRO`, `numero_cuenta` VARCHAR(30), `titular` VARCHAR(100), `activo`) y la columna **`recaudacion_depositar.id_cuenta_bancaria`**
    (INT NULL, FK RESTRICT, más el CHECK `ck_recaudacion_cuenta`: una recaudación DEPOSITADA exige cuenta).
  - Estándar completo: único parcial `(id_entidad_emisora, numero_cuenta) WHERE activo`, titular en MAYÚSCULAS, Estado / "Mostrar inactivos" / Reactivar (valida banco
    activo y duplicado), auditoría. Validador compartido nuevo en espejo: `validar_numero_cuenta` / `V.numeroCuenta` (solo dígitos y guiones, 5 a 30). Datos
    iniciales: CORRIENTE BANCO ITAÚ 1020304050 y CAJA DE AHORRO BANCO CONTINENTAL 2030405060, con la razón social como titular.
  - **En uso:** la baja se bloquea si la cuenta recibió el depósito de una recaudación no anulada, y entonces tampoco se pueden cambiar su banco, tipo ni
    número (solo el titular). `EntidadEmisoraDao._motivo_en_uso` suma las cuentas bancarias activas del banco ("el banco tiene cuentas bancarias asociadas").
  - Tests: `tests/facturacion/smoke_cuenta_bancaria.py` (84 chequeos).

- ✅ **Registrar Arqueo de Caja (con Recaudación a depositar)** (`arqueo_caja` + `arqueo_caja_det` + `recaudacion_depositar` del DER, **usadas tal cual**; ventana `arqueo`,
  acciones `ver`, `nuevo`, `anular` y `estado` = marcar depositada; el Cajero las recibe todas). Scripts (idempotentes, en este orden): `schema_cuenta_bancaria.sql` →
  `schema_arqueo.sql` (en `app/dao/modulo_facturacion/`; funciones, procedimiento, triggers y vista) → `schema_permisos_arqueo.sql` → `schema_permisos_cajero.sql`.
  - **Control POSTERIOR al cierre:** se elige una apertura **CERRADA** sin arqueo REGISTRADO (una sola por apertura; si el arqueo se anula se puede arquear de nuevo).
    **Nadie arquea su propia caja** ("No puede arquear su propia caja; el arqueo debe hacerlo otro usuario."): lo valida la API, `sp_registrar_arqueo` y el trigger
    `trg_validar_arqueo`; el Administrador arquea cualquier apertura salvo las suyas, y el listado de aperturas pendientes ya excluye las del usuario.
  - **Detalle por forma de cobro:** monto del SISTEMA (lo calcula la base con `fn_formas_arqueo` desde `v_resumen_caja`: en la primera forma EFECTIVO suma el fondo
    inicial y resta los reintegros de las notas de crédito), monto CONTADO (lo ingresa quien arquea) y diferencia (sobrante +, faltante −). Se cuentan las formas con
    movimiento más la EFECTIVO; hay que contarlas todas. **Observación obligatoria si ALGUNA forma tiene diferencia** (aunque el total cuadre).
  - **Recaudación a depositar (PENDIENTE):** efectivo contado − fondo inicial (mínimo 0) + cheques contados; tarjetas y transferencias no se depositan; si no hay nada que
    depositar no se genera. **Marcar DEPOSITADA** (permiso `estado`): cuenta bancaria ACTIVA (`FOR SHARE`), N.º de boleta y fecha (ni futura ni anterior al arqueo); una
    recaudación depositada o anulada no cambia de estado. **Anular el arqueo** (permiso `anular`): solo si su recaudación sigue PENDIENTE, y la anula también.
  - **Objetos de BD** (con comentarios y `COMMENT ON`): procedimiento **`sp_registrar_arqueo`** (una transacción: arqueo, detalle y recaudación, con validaciones y bloque
    `EXCEPTION`; se llama con `CALL sp_registrar_arqueo(apertura, usuario, formas[], contados[], observación, NULL, NULL)`), `fn_formas_arqueo`, `fn_forma_efectivo_arqueo`,
    `trg_validar_arqueo` (apertura CERRADA y no propia), `trg_arqueo_estado`, `trg_recaudacion_estado` y la vista **`v_arqueos_diferencias`** (por arqueo: apertura, cajero,
    arqueador, fechas, total sistema, total contado, diferencia y `resultado` CUADRA/SOBRANTE/FALTANTE) para el control del Administrador.
  - **Conexiones:** el listado de aperturas de caja muestra "Con arqueo" / "Sin arqueo" en las CERRADAS (`tiene_arqueo`); `GET /arqueos/aperturas` alimenta la pantalla.
  - **PDF** (`app/Services/arqueo_pdf_service.py`, mismo patrón que recibo y factura): ORIGINAL y DUPLICADO, formas con sistema / contado / diferencia, resultado,
    observación y recaudación (con la cuenta y la boleta si ya se depositó); marca "ANULADO".
  - **Pantalla** `arqueo-index.html`: listado de arqueos con filtros y badge cuadra / sobrante / faltante; sección **Recaudaciones a depositar** con estado y la acción
    "Marcar depositada" (modal con cuenta, boleta y fecha); Nuevo Arqueo con la grilla sistema / contado / diferencia en vivo y la recaudación resultante.
  - Tests: `tests/facturacion/smoke_arqueo.py` (166 chequeos; construye aperturas ZZ CERRADAS con cobros y un reintegro por SQL y no depende de ninguna caja abierta).
  - **Pendiente:** ninguno propio. **Con esto quedan completos los movimientos del Módulo Facturación.**

### Objetos de base de datos (rúbricas de Base de Datos II: procedimientos almacenados, triggers y vistas)
Todos viven en `app/dao/modulo_facturacion/schema_objetos_bd.sql` (idempotente: `CREATE OR REPLACE` y `DROP TRIGGER IF
EXISTS`), con comentarios de propósito, parámetros y excepciones, bloque `BEGIN … EXCEPTION` y `COMMENT ON`.
- **Procedimiento `sp_siguiente_numero_factura(OUT p_id_timbrado INT, OUT p_numero_factura VARCHAR)`** — se llama con
  `CALL sp_siguiente_numero_factura(NULL, NULL)` dentro de la transacción de la venta. Bloquea el timbrado activo
  (`FOR UPDATE`: dos ventas simultáneas se serializan y reciben números consecutivos distintos), valida vigencia y rango,
  incrementa `numero_actual` y devuelve `EEE-PPP-NNNNNNN` (p. ej. `001-001-0000001`). Excepciones con `RAISE EXCEPTION`, que
  la API muestra tal cual: "No hay timbrado activo", "El timbrado aún no está vigente", "El timbrado está vencido", "Se
  agotó el rango de numeración del timbrado". El bloque `EXCEPTION` re-lanza los de negocio y envuelve cualquier otro error.
- **Trigger `trg_generar_cuenta_cobrar`** (`AFTER INSERT ON venta_cab`, función `fn_generar_cuenta_cobrar`): crea la
  `cuenta_cobrar` con `saldo = total` y vencimiento por condición.
- **Trigger `trg_anular_cuenta_cobrar`** (`AFTER UPDATE OF estado ON venta_cab` cuando pasa a ANULADA, función
  `fn_anular_cuenta_cobrar`): pasa la cuenta a ANULADA.
- **Trigger `trg_auditoria_inmutable`** (`BEFORE UPDATE OR DELETE` en `auditoria_cambios` y `auditoria_acceso`, función
  `fn_auditoria_inmutable`): rechaza con "Los registros de auditoría no se pueden modificar ni eliminar." Verificado que
  ningún código de `app/` hace UPDATE/DELETE/TRUNCATE sobre esas tablas (solo INSERT; el test `smoke_ventas` lo vigila).
  **Los tests** borran solo la auditoría que ellos generaron con `tests/facturacion/_limpieza.py::borrar_auditoria`, que
  usa `SET session_replication_role = replica` solo en su conexión (exige superusuario; se revierte al cerrarla).
- **Vista `v_estado_cuenta_cliente`**: una fila por factura (cliente, número, fecha, condición, total, saldo, estado de la
  cuenta, vencimiento) más `saldo_total_cliente` (suma de los saldos PENDIENTES del cliente, sin las cuentas anuladas) y,
  **completada con Cobranzas**, `total_cobrado`, `cantidad_cobros` y `fecha_ultimo_cobro` (cobros EMITIDOS). `schema_objetos_bd.sql` la crea
  solo si no existe y `schema_cobranzas.sql` la completa (`CREATE OR REPLACE` agregando columnas al final).
- **Arqueo de Caja**: procedimiento `sp_registrar_arqueo`, `fn_formas_arqueo`, 3 triggers y la vista `v_arqueos_diferencias` (`schema_arqueo.sql`; ver la sección "Registrar Arqueo de Caja").
- **Notas de Crédito y Débito**: ver la sección "Registrar Notas de Crédito y Débito" (`schema_notas.sql` actualiza `fn_total_recaudado`, `fn_total_efectivo_apertura`, `v_resumen_caja`, `v_estado_cuenta_cliente` y `v_libro_ventas`; correrlo DESPUÉS de `schema_cobranzas.sql`).
- **Cobranzas** (`schema_cobranzas.sql`, solo funciones, triggers y vistas; ninguna tabla): **`trg_aplicar_cobro`** (AFTER INSERT/UPDATE de
  `estado` en `cobro_cab`, función `fn_aplicar_cobro`: descuenta o repone el saldo y pasa la cuenta a PAGADA/PENDIENTE; rechaza
  cuenta no pendiente, total mayor al saldo y reactivar un cobro anulado); **`trg_validar_cobro`** (trigger de restricción DIFERIDO,
  `fn_validar_cobro`: al confirmar, suma de formas = total y cada forma con sus datos de tarjeta/cheque/referencia);
  **`fn_total_recaudado(p_id_apertura)`** (todo lo cobrado), **`fn_total_efectivo_apertura(p_id_apertura)`** (solo efectivo),
  **`fn_siguiente_numero_recibo()`**, `fn_formato_gs(n)` y la vista **`v_resumen_caja`** (por apertura y forma de cobro). Todos con
  comentarios de propósito, parámetros y excepciones y `COMMENT ON`.
- ~~`trg_permisos_resolver_menu`~~ **eliminado por la migración 02** (`permisos.ventana` ya no existe; ver "Migración 02" y "Modelo de permisos").
- ✅ **Hecho en la Etapa B de la tanda de cierre:** la app ya NO se conecta como `postgres` sino como `odontoclinic_app` (sin superusuario, sin UPDATE/DELETE en las auditorías, sin DDL); ver "Base de datos — tanda de cierre, Etapa B". Los tests siguen usando postgres para su limpieza, con `TEST_DB_*`.


## Seguridad de acceso — tanda de cierre, Etapa A (rama `finalizando`)
Cinco puntos de la rúbrica. Tests: `tests/seguridad/` (`smoke_inactividad`, `smoke_ip_pais`, `smoke_acceso_basico`).

1. **Contraseñas:** ya estaban bien. Todas se guardan con `generate_password_hash` de Werkzeug (`scrypt:32768:8:1` con salt
   propio); no hay texto plano ni hash débil, así que no hizo falta migración.
2. **Cierre por inactividad** (`app/rutas/modulo_seguridad/sesion_seguridad.py`, `app/static/js/inactividad.js`,
   `app/templates/_inactividad.html`, incluido en `base.html` y en `base_tabler.html`):
   - **El servidor decide.** Un `before_request` guarda `session['ultima_actividad']` y, pasados
     `SESSION_INACTIVIDAD_MINUTOS` (30) sin actividad, limpia la sesión, audita `CIERRE_INACTIVIDAD` (accion `LOGOUT`) y redirige
     al login con "Sesión cerrada por inactividad" (en `/api/` y en `/sesion/estado|extender`: 401 JSON con
     `codigo: INACTIVIDAD`). Una sesión sin marca (anterior a este control) arranca en su primer request.
   - **El aviso es del cliente:** a `SESSION_AVISO_SEGUNDOS` (120) del vencimiento, el JS consulta `GET /sesion/estado` (no
     renueva; el header `X-Sin-Actividad: 1` tampoco renueva) y muestra un modal propio (no depende de Bootstrap 4/5 ni de
     jQuery) con cuenta regresiva y "Seguir conectado" (`POST /sesion/extender`). Al llegar a 0 va a `/sesion/expirar`, que solo
     cierra si el servidor confirma el vencimiento (otra pestaña puede haber mantenido viva la sesión). La actividad del usuario
     avisa al servidor como mucho una vez por minuto.
   - **Si se agrega un poller o un `fetch` automático** que no sea actividad del usuario, mandarle `X-Sin-Actividad: 1`.
3. **Validación de IP por país** (`app/Services/geoip_service.py`, base local **DB-IP Lite Country**, sin APIs externas):
   - Solo se permite `PAIS_PERMITIDO` (`PY`, código ISO). IP privadas, loopback y link-local = red interna de la clínica:
     siempre permitidas.
   - Es lo **primero** del login (`/login`, `/verificar-2fa` y `/recuperar*`, en el `before_request`): se rechaza antes de leer
     usuario y contraseña, con 403 y el mensaje genérico "No es posible acceder al sistema desde esta ubicación." (sin país ni
     reglas). Solo un POST deja auditoría (un GET suelto no es un intento).
   - **Auditoría** en `auditoria_acceso` (columna nueva `pais_detectado VARCHAR(2)`, NULL = red interna o sin geolocalizar):
     `IP_NO_PERMITIDA` (con el usuario si lo tipeó, IP y país) e `IP_SIN_GEOLOCALIZAR`. Las demás filas del login desde una IP
     pública también llevan el país. El tablero (Gestionar Auditoría) tiene columna País y **filtro por resultado**
     (`GET /api/v1/auditoria/intentos?resultado=`, valor exacto, 400 si el formato es inválido).
   - **IP pública que la base no resuelve (o base ausente): se PERMITE** y queda `IP_SIN_GEOLOCALIZAR` (decisión de negocio: un
     archivo faltante no debe dejar a la clínica afuera; el aviso de base no disponible se loguea una sola vez).
   - **Pruebas:** `IP_SIMULADA` en `.env` reemplaza la IP del cliente, **solo con la app en modo debug** (`app.debug`); fuera de
     debug se ignora. Las IP que se auditan en ese caso son las simuladas.
   - **Base GeoIP:** `geoip/dbip-country-lite.mmdb` (ruta en `GEOIP_DB_PATH`), **no se versiona** (`geoip/` en `.gitignore`). Se
     baja de `https://download.db-ip.com/free/dbip-country-lite-AAAA-MM.mmdb.gz` y se descomprime; DB-IP la actualiza cada mes
     (conviene refrescarla de vez en cuando). Dependencia: `maxminddb` (en `paquetes.txt`).
   - **Atribución (DB-IP Lite es CC-BY 4.0, obligatoria):** "IP Geolocation by DB-IP" — <https://db-ip.com>. Va en una línea
     discreta en el pie del login y acá. Si se reemplaza la base por otra, revisar su licencia.
   - **Tabla `paises` eliminada** (`schema_eliminar_paises.sql`, idempotente; verifica antes que nada la referencie): no tenía
     código ISO ni usos. ⚠️ **Hay que quitar `paises` del DER y agregar `auditoria_acceso.pais_detectado`.**
4. **Recordar usuario:** checkbox en el login. Al completar el 2FA (no antes) se guarda la cookie `oc_usuario` con **solo el
   CI/RUC** (`RECORDAR_USUARIO_DIAS`=30, `HttpOnly`, `SameSite=Lax`, `Secure` si `COOKIE_SECURE=true`); sin marcar, se borra.
   Nunca la contraseña ni el código 2FA. El valor de la cookie solo se usa si tiene forma de CI/RUC. La cookie de sesión de Flask
   también es `HttpOnly` y `SameSite=Lax`.
5. **HTTPS — no se implementa (decisión):** el sistema corre en una red local de la clínica, sin exposición a internet, y el
   proyecto es de tesis; un certificado válido exige un dominio y un servidor público. Hoy la app sirve HTTP
   (`app.run(debug=True)`). **Cómo se activaría en producción:** (a) publicar la app con un servidor WSGI (waitress/gunicorn),
   nunca con el servidor de desarrollo; (b) un **proxy inverso** (Nginx o Caddy) que termine TLS con un certificado (Let's
   Encrypt si hay dominio, o uno interno de la clínica), redirija HTTP→HTTPS y envíe `X-Forwarded-For`/`X-Forwarded-Proto`;
   (c) en la app, envolverla con `werkzeug.middleware.proxy_fix.ProxyFix` (si no, `request.remote_addr` sería la IP del proxy y
   la validación por país y la auditoría quedarían mal), poner `COOKIE_SECURE=true` en `.env` (cookies solo por HTTPS) y agregar
   HSTS en el proxy. OJO: el pie del login dice "Conexión segura"; mientras no haya HTTPS conviene cambiar ese texto.

**Configuración (`.env`; `.env.example` documenta todas las variables sin valores reales):** `SECRET_KEY` (obligatoria: sin ella
la app NO arranca, salvo en modo debug, donde usa una clave efímera con aviso; `run.py` fija `FLASK_DEBUG=1`), `DB_*`,
`SESSION_INACTIVIDAD_MINUTOS`, `SESSION_AVISO_SEGUNDOS`, `PAIS_PERMITIDO`, `GEOIP_DB_PATH`, `IP_SIMULADA`,
`RECORDAR_USUARIO_DIAS`, `COOKIE_SECURE`. `.env` y `geoip/` están en `.gitignore`. El valor fijo de `SECRET_KEY` y las
credenciales de la base se quitaron del código.
- Scripts SQL (idempotentes): `schema_ip_inactividad.sql` (columna `pais_detectado` + índice por `resultado`) y
  `schema_eliminar_paises.sql`.

## Base de datos — tanda de cierre, Etapa B (rama `finalizando`)
Tests: `tests/seguridad/smoke_permisos_app.py` y `smoke_backup.py`. Guías: `docs/backups.md` y `docs/acceso_red.md`.

### Rúbricas del profesor (hojas de evaluación)
1 Acceso · 2 Menú · **3 Base de datos** · 4 Vistas · 5 Procedimientos almacenados · 6 Triggers · 7 Codificación de ventanas ·
**8 Seguridad** · 9 Auditoría.
- ✅ **Rúbrica 3 (Base de datos) — completa con esta etapa:** usuario de la app con mínimo privilegio, backup automático y
  acceso por red documentado.
- ✅ **Rúbrica 8 (Seguridad) — completa con esta etapa:** copias de seguridad y separación de privilegios (suma lo de la Etapa A:
  contraseñas con scrypt, cierre por inactividad, IP por país, recordar usuario, HTTPS justificado).
- ✅ **Rúbrica 9 (Auditoría) — completa con la Etapa C** (consulta, informes y alertas; ver "Auditoría — tanda de cierre, Etapa C").
- Las demás no cambian en esta etapa.

### Usuarios de base de datos (`schema_usuario_app.sql`, idempotente, SIN contraseñas)
- **`odontoclinic_app`** (la usa la aplicación; `DB_USER`/`DB_PASSWORD` del `.env`): `LOGIN`, sin superusuario, `CREATEDB`,
  `CREATEROLE`, `REPLICATION` ni `BYPASSRLS`. `SELECT/INSERT/UPDATE/DELETE` en las tablas; **solo `SELECT` en las vistas**;
  `USAGE/SELECT` en las secuencias; `EXECUTE` en funciones y procedimientos. **`auditoria_cambios` y `auditoria_acceso`: solo
  `SELECT` e `INSERT`** (doble protección junto con `trg_auditoria_inmutable`). Sin `TRUNCATE`, `REFERENCES`, `TRIGGER` ni DDL
  (`CREATE` revocado a `PUBLIC` en el esquema `public`). `ALTER DEFAULT PRIVILEGES FOR ROLE postgres`: lo que cree postgres de
  ahora en más le llega con los mismos permisos.
  - ⚠️ **Una tabla de auditoría NUEVA hay que agregarla a la lista `v_auditoria` del script** (los privilegios por defecto le
    darían `UPDATE/DELETE`) y re-aplicarlo. Los objetos futuros no listados se tratan como tablas normales.
  - **Después de crear tablas/funciones nuevas con postgres no hace falta hacer nada** (privilegios por defecto); si se quiere
    re-aplicar todo: `python -m app.dao.modulo_seguridad.crear_usuario_app --solo-permisos`.
- **`odontoclinic_backup`** (`BACKUP_DB_USER`/`BACKUP_DB_PASSWORD`): `LOGIN` y miembro de `pg_read_all_data` (solo lectura).
- **Crear los roles / cambiar contraseñas:** `python -m app.dao.modulo_seguridad.crear_usuario_app` (como postgres, con
  `TEST_DB_*`; toma las contraseñas de `APP_DB_PASSWORD` / `BACKUP_DB_PASSWORD` o las pide por teclado; mínimo 12 caracteres;
  viajan por la conexión, nunca por línea de comandos).
- **Tres cuentas, tres contraseñas distintas en el `.env`:** `DB_*` (aplicación), `TEST_DB_*` (**postgres**: migraciones,
  creación de roles y tests; `app/conexion/ConexionAdmin.py`) y `BACKUP_DB_*`. La app NUNCA usa `TEST_DB_*`. Las migraciones
  (`schema_*.sql`) se aplican con postgres; los scripts de la app (`seed_admin_usuario`) corren con `odontoclinic_app` y alcanzan.
- **Auditoría del hallazgo de DDL:** se revisó `app/` buscando `CREATE/ALTER/DROP/TRUNCATE`: **no hay DDL en el código Python**
  (ni al arrancar ni en ningún DAO); todo el esquema vive en los `schema_*.sql`.
- ⚠️ La contraseña anterior de `postgres` estuvo escrita en `Conexion.py` desde el primer commit y **sigue en el historial de
  git**: conviene cambiarla (`ALTER ROLE postgres PASSWORD ...` y actualizar `TEST_DB_PASSWORD`).

### Tests con dos conexiones
- Los tests hacen `from tests._conexion_pruebas import Conexion` (en lugar de la de la app): lo que preparan/limpian DIRECTO en
  la base va con postgres (`TEST_DB_*`; necesitan superusuario para `session_replication_role` y bases temporales), mientras la
  app y los DAO que ejercitan van con `odontoclinic_app`. Así cada regresión prueba los permisos reales. Un test nuevo debe
  seguir esta convención.
- `smoke_permisos_app.py` además recorre TODAS las pantallas del menú y las APIs de lectura con el rol de la app (ninguna debe
  dar 500). La ruta suelta `/vista` de `app/__init__.py` renderiza `vista-index.html` sin `stats` y falla con cualquier usuario
  (pendiente aparte, no es de permisos).

### Copias de seguridad (`docs/backups.md`)
- `app/Services/backup_service.py` (`pg_dump -Fc`, nombre `odontosisbd_AAAAMMDD_HHMMSS.dump`, retención de **7**, `backup.log`
  con OK/ERROR, archivo y tamaño; la contraseña solo por `PGPASSWORD` del proceso hijo, nunca en comandos, logs ni errores).
  `scripts/backup_db.py` (código 0/1) y `scripts/backup_diario.bat` para el Programador de tareas a las 23:00 (pasos en la guía;
  la tarea programada **la crea quien administra el servidor**, no el proyecto).
- **`BACKUP_DIR=C:\OdontoClinic\backups`, fuera de OneDrive** (decisión: las copias tienen datos de pacientes y el proyecto está
  en una carpeta sincronizada con la nube). `PG_BIN_DIR` = `bin` de PostgreSQL 14 (la versión del servidor; el `pg_dump` del
  PATH es el 16).
- Pantalla **Copias de Seguridad** (`/referenciales/backup/backup-index`, `/api/v1/backups`, ventana `backup` en el catálogo con
  `solo_admin: True`): lista (fecha, tamaño) y "Generar backup ahora", auditado en `auditoria_cambios` (`entidad='backup'`,
  `ALTA`, `id_registro=0`, el detalle lleva el archivo). **No restaura** (solo con la guía). Ventana EXCLUSIVA del Administrador:
  `puede()` devuelve False para los demás roles, no sale en la matriz de Roles y Permisos y la API de la matriz rechaza otorgarla.
  Seed: `schema_permisos_backup.sql` (solo la fila de `menu`).
- Restauración probada en `odontosisbd_restore_test` (mismas filas, vistas, funciones, triggers y permisos); la prueba está en
  `smoke_backup.py`, que borra la base temporal.

### Acceso por red (`docs/acceso_red.md`, solo guía; no se editó ningún archivo de PostgreSQL)
- Hoy: servidor PostgreSQL 14 en el 5432, `listen_addresses='*'` pero `pg_hba.conf` solo admite localhost, o sea sin acceso por red.
- Para abrirlo: `listen_addresses` a la IP de la red local, UNA línea `host odontosisbd odontoclinic_app <subred>/24 scram-sha-256`
  en `pg_hba.conf`, regla de firewall de Windows para el 5432 solo desde la subred (perfil Privado) y `DB_HOST=<IP del servidor>`
  en el `.env` de la otra PC. Subred de este equipo al escribir la guía: `192.168.100.0/24` (servidor `192.168.100.80`).
- Dos servidores PostgreSQL conviven en la PC (14 y 16): editar siempre la carpeta de la 14.
- Tras cambiar `DB_USER` hay que **reiniciar `run.py`**: un servidor ya iniciado conserva las credenciales viejas.

## Auditoría — tanda de cierre, Etapa C (rama `finalizando`)
Rúbrica 9. Tests: `tests/seguridad/smoke_auditoria_consulta.py` (servidor/API/base) y `tests/seguridad/browser_auditoria.py` (las dos
pantallas en Edge headless con `fetch` simulado). Scripts SQL idempotentes, como postgres, con `PGCLIENTENCODING=UTF8`:
`app/dao/modulo_seguridad/schema_auditoria_estructurada.sql` y `schema_permisos_auditoria_cambios.sql` (+ re-aplicar `schema_usuario_app.sql`,
que ahora deja `auditoria_umbrales` en solo lectura para la app).

### Estructura de `auditoria_cambios` (formato estructurado)
- ⚠️ **Hay que agregar al DER:** `modulo VARCHAR(30) NULL`, `valores_anteriores JSONB NULL`, `valores_nuevos JSONB NULL` (todas con `COMMENT ON`),
  `detalle` pasó de `VARCHAR(255)` a `TEXT` (ya no se corta), la acción `EXPORTACION` en el CHECK, la tabla `auditoria_umbrales` y la vista
  `v_auditoria_anomalias`.
- Las filas anteriores a la Etapa C quedan con `modulo` y JSON en NULL (la tabla es inmutable, no se reescribe): la pantalla deduce el módulo de la
  `entidad` (`MODULO_POR_ENTIDAD` en `app/Services/auditoria_detalle.py`; el filtro por módulo también las alcanza) y arma campo / anterior / nuevo
  con el parser del texto.
- **Cómo se guarda (sin tocar la lógica de cada API):** `utils.detalle_cambios()` devuelve un `DetalleAuditoria` (un `str` con los campos que cambiaron
  pegados) y `utils.auditar()` guarda el módulo y los JSON: **ALTA** solo `valores_nuevos`; **MODIFICACION** solo los campos que cambiaron (una edición sin
  cambios no guarda JSON); **BAJA / REACTIVACION / CIERRE** el estado (`Activo`↔`Inactivo`, `Anulado` en los movimientos, `Abierta`→`Cerrada`). Si una API
  arma el texto a mano (concatenándolo), se separa con `parsear_detalle()` solo si tiene exactamente la forma `Campo: A -> B; ...`; si no, el JSON queda NULL.
  Los booleanos se guardan como `Sí`/`No`. **Una entidad nueva debe sumarse a `MODULO_POR_ENTIDAD` y `ETIQUETA_ENTIDAD`** (si no, se guarda sin módulo y se muestra como "Otro").
- La app sigue con solo `SELECT`/`INSERT` en la tabla y el trigger `trg_auditoria_inmutable` sigue rechazando UPDATE/DELETE (verificado en el test, incluso como postgres).
- **BAJA se sigue guardando como `BAJA`**, pero pantalla, PDF y CSV la muestran como **"Baja / Anulación"** (`ETIQUETA_ACCION`).

### Relevamiento: qué registra hoy en `auditoria_cambios` y qué no
- **Sí registran (19 APIs):** Referenciales de Facturación (Forma de Cobro, Marca de Tarjeta, Entidad Emisora, Entidad Adherida, Tipo Ítems, Ítems, Caja,
  Depósito, Cliente, Cuenta Bancaria); movimientos de Facturación (Apertura y Cierre de Caja, Pedido Cliente, Venta, Cobro, Nota de Remisión, Notas de
  Crédito/Débito, Arqueo y Recaudación a depositar); Seguridad: solo Copias de Seguridad (y ahora las exportaciones de los informes de auditoría).
- **NO registran (se suman en la migración a Tabler, NO en esta etapa):**
  - **Agendamiento:** Paciente, Médico, Funcionario, Agenda (cabecera/detalle), Cita, Avisos y Recordatorios, Historial; referenciales Ciudad, Cargo, Consultorio,
    Disponibilidad Horaria, Especialidad, Día, Turno.
  - **Consultorio:** los 10 movimientos (Consulta, Diagnóstico, Ficha Médica, Odontograma, Tratamiento, Sesiones e Insumos, Receta, Orden de Estudios, Orden de
    Análisis, Justificativo) y los 8 referenciales (Tipo Tratamiento, Tipo Insumo, Tipo Procedimiento, Medicamentos, Tipo Estudio, Tipo Análisis, Tipo Diagnóstico, Síntomas).
  - **Seguridad:** alta/edición/baja de Usuarios y Roles y Permisos (los accesos sí van a `auditoria_acceso`, otra tabla).
  - Al migrar cada uno: auditar con `detalle_cambios()` + `utils.auditar` (formato estructurado) y sumar la entidad a `MODULO_POR_ENTIDAD`/`ETIQUETA_ENTIDAD`
    y, si es un movimiento que se anula, a los de módulo distinto de Referenciales (`ENTIDADES_MOVIMIENTO`) para que su BAJA diga "Anulado".

### Pantalla "Auditoría de Cambios" (solo Administrador)
- Ventana `auditoriacambios` (`solo_admin`, acción `ver`, "Módulo Seguridad"), `base_tabler.html`; fila en `menu` y **ningún** permiso para otros roles; el
  buscador general la encuentra. Archivos: `auditoria_cambios_routes.py` / `auditoria_cambios_api.py` / `templates/auditoria-cambios-index.html` (planos en
  `modulo_seguridad/`, como Backup), `AuditoriaConsultaDao.py` (solo SELECT), `app/Services/auditoria_detalle.py` y `auditoria_pdf_service.py`.
- Filtros: fechas (la pantalla arranca con los últimos 7 días; la API sin fechas no filtra), usuario, módulo, entidad, acción y N.º de registro (este último
  solo llega desde una alerta). Listado paginado (10/25/50/100) de más reciente a más antiguo; modal con la tabla campo / valor anterior / valor nuevo.
- **Solo lectura:** el blueprint solo tiene `GET` (POST/PUT/PATCH/DELETE dan 405).
- **Exportar a PDF y CSV** con los filtros aplicados, tope **5.000 filas** (`TOPE_EXPORTACION`) con aviso en el PDF y el CSV. PDF A4 apaisado, mismo estilo
  que la factura (empresa, título, filtros, emitido el/por). CSV UTF-8 con BOM, separador `;`, textos que empiezan con `= + - @` con comilla (sin fórmulas).
  **Cada exportación válida se audita** (`entidad='auditoria_cambios'` o `'auditoria_acceso'`, acción `EXPORTACION`, `id_registro = 0`, detalle con formato, filas y filtros).
- **Alertas** (`v_auditoria_anomalias`, umbrales en la tabla de una fila `auditoria_umbrales`, que la app solo lee; se cambian con `UPDATE` como postgres):
  `BAJAS_EN_EL_DIA` (5 o más bajas de un usuario en un día), `FUERA_DE_HORARIO` (operaciones, no exportaciones, antes de 07:00, desde 20:00 o en domingo:
  lunes a sábado de 07:00 a 20:00) y `REACTIVACIONES_REPETIDAS` (3 o más del mismo registro en 30 días). Solo mira los últimos 30 días (`ventana_alertas_dias`).
  Sección "Alertas" arriba, con badge con la cantidad; cada alerta aplica sus filtros al listado.

### Tablero de Accesos
- Migrado a Tabler (`auditoria-index.html`; endpoint y ventana `auditoria` iguales). Mismo filtro de fechas + resultado, **exportación a PDF y CSV**
  (`GET /api/v1/auditoria/intentos/exportar`, permiso `ver` de `auditoria`, también auditada) y **enlace cruzado** en ambos sentidos con Auditoría de Cambios
  (llevan las fechas elegidas). En pantalla muestra hasta 1.000 intentos paginados de a 25; la exportación llega a 5.000.

