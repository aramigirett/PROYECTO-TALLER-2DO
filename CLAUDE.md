# OdontoClinic — Contexto del proyecto para Claude Code

## Qué es
Sistema de gestión de clínica odontológica (tesis universitaria), desarrollado en
Flask (Python) + PostgreSQL, sin ORM (SQL crudo vía psycopg2). Incluye un módulo
de automatización de WhatsApp con Selenium.

## Estructura del proyecto
```
run.py                 → punto de entrada (arranca Flask en modo debug)
paquetes.txt           → dependencias
app/
├── __init__.py         → crea la app Flask y registra TODOS los blueprints
├── conexion/Conexion.py → clase que abre la conexión a PostgreSQL (psycopg2)
├── dao/                 → capa de acceso a datos (SQL crudo, patrón DAO)
├── rutas/               → capa de rutas/controladores (vistas + APIs)
├── Services/            → servicios externos (ej. whatsapp_service.py con Selenium)
├── templates/           → plantillas Jinja2 (base_tabler.html, tema Tabler; SB Admin 2 retirado)
└── static/               → CSS/JS/imágenes
```

## Patrón de 3 capas (repetir SIEMPRE para cada entidad nueva)
1. **DAO** (`app/dao/<modulo>/<Entidad>Dao.py`): SQL crudo con psycopg2. Abre conexión,
   ejecuta la query, hace commit/rollback, cierra conexión. Métodos típicos: `getX`,
   `getXById`, `guardarX`, `updateX`, `deleteX`.
2. **API** (`.../<entidad>_api.py`): Blueprint que expone endpoints REST JSON bajo
   `/api/v1/...`, consumidos por JS del frontend.
3. **Routes** (`.../<entidad>_routes.py`): Blueprint que sirve las vistas HTML.

Agrupaciones existentes bajo `app/rutas/`:
- `referenciales/` — catálogos base (ciudad, país, cargo, día, turno, especialidad, etc.)
- `modulo_agendamiento/` — médico, funcionario, paciente, cita, agenda, odontograma, etc.
- `modulo_consultorio/` — consulta médica, ficha médica, diagnóstico, síntomas.

## Reglas de negocio que NO se deben romper
- **No existe tabla "Persona" genérica.** Médico, Funcionario y Paciente son SIEMPRE
  tablas separadas. Cualquier tabla que necesite vincularse a una persona debe tener
  FKs opcionales separadas (ej. `id_funcionario` NULL, `id_medico` NULL) y no una
  FK única a una tabla "persona".
- Toda tabla nueva debe respetar el balanceo definido en el análisis: lo que aparece
  en la Lista de Archivos del CUS debe aparecer en las secuencias ALTA/ANULAR y en el
  diagrama de clase correspondiente (ya documentado en la tesis; el código debe
  reflejar esas mismas entidades).
- Roles del sistema (Módulo Seguridad): **Administrador, Medico, Recepcion, Cajero**.
- Regla de Roles/Permisos: "Roles puede tener Permisos, pero Permisos no puede tener
  Roles" — la dirección de la asociación importa también en el código (FK en la
  tabla de permisos apuntando a roles, no al revés).


> **Este archivo es la guía compacta.** El detalle de cada etapa y decisión cerrada vive en `docs/` (ver el índice abajo). Las secciones que dicen "ver sección X" y no están acá, están en el archivo de `docs/` indicado en el índice.

## Reglas no negociables (resumen transversal)
- **SQL crudo con psycopg2, sin ORM.** Cada DAO abre su conexión con la clase `Conexion` y la cierra en un `finally`. Credenciales solo en `.env`, nunca en el código.
- **Sin tabla Persona.** Médico, Funcionario y Paciente son tablas separadas; las FKs a personas son opcionales y separadas.
- **CI/RUC y correo de un usuario salen de la persona vinculada** (`SQL_CI_RUC` / `SQL_CORREO` de `UsuarioDao`); las columnas `usuarios.ci_ruc` y `usuarios.correo` no existen.
- **La app corre como `odontoclinic_app`** (mínimo privilegio; las auditorías solo `SELECT`/`INSERT`; sin DDL). `postgres` (`TEST_DB_*`, `ConexionAdmin`) solo para migraciones, creación de roles y tests; nunca en código de la aplicación. No hay DDL en el código Python: el esquema vive en los `schema_*.sql`.
- **Borrado lógico** (`activo`) con **índices únicos PARCIALES** desde el arranque y FK `RESTRICT`; el botón se llama **"Anular"**; baja bloqueada si está en uso (409; la API compara `== "EN_USO"`, nunca `if resultado:`).
- **El servidor decide**: usuario, estado, importes, IVA, número de documento y fecha salen del servidor o de la sesión; lo que mande el navegador para eso se ignora.
- **Validadores en espejo**: cada regla de `utils.py` / `validadores_clinicos.py` tiene su par en `facturacion-validadores.js` / `consultorio-validadores.js`; si cambia una, cambian las dos (hay comparadores JS ↔ Python en los tests).
- **Concurrencia**: verificación y escritura en la misma transacción, con `FOR UPDATE` / `FOR SHARE` bloqueando siempre en el mismo orden (por id) para no generar deadlocks; revalidar el estado dentro de la transacción.
- **Vistas nuevas en `base_tabler.html`** (Bootstrap 5, `fetch` + JS vanilla, SweetAlert2); SB Admin 2 ya no existe en el proyecto.
- **Todo endpoint con `@require_permiso(ventana, acción)`**, botones en `puede(...)`, entrada en `menu_catalog.py`, fila en `menu` y seed de permisos idempotente.
- **Auditoría estructurada** (`detalle_cambios()` + `utils.auditar`) en todo módulo; `auditoria_cambios` y `auditoria_acceso` son inmutables. Nunca se guarda la contraseña ni contenido clínico.
- **Scripts SQL idempotentes**, aplicados con `PGCLIENTENCODING=UTF8` (tienen tildes).
- Los mensajes al usuario llevan datos descriptivos (código, paciente, descripción), nunca IDs crudos.

## Índice de `docs/` (qué hay y cuándo leerlo)
| Archivo | Contenido | Leer cuando… |
|---|---|---|
| `docs/historial_modulos.md` | Facturación completa (referenciales, 7 movimientos, objetos de BD: SP, triggers, vistas) y la tanda de cierre: Etapa A (acceso), B (base de datos) y C (auditoría) | vayas a tocar Facturación, un objeto de BD, el esquema de `auditoria_cambios` o la pantalla de Auditoría |
| `docs/historial_consultorio.md` | Consultorio: estado de los 10 movimientos y 8 referenciales tras la auditoría inicial, Migración 02, y la migración a Tabler (etapas 0 a 7) con todas las decisiones clínicas | vayas a tocar Consultorio (consulta, ficha, diagnóstico, odontograma, tratamiento, sesiones, recetas, órdenes, justificativo) |
| `docs/historial_seguridad_agendamiento.md` | Módulo Seguridad (login, 2FA, bloqueo, recuperación, usuarios, roles), Agendamiento y sus referenciales, rediseño visual y CI/RUC fuente única | vayas a tocar acceso, usuarios, agenda, citas, avisos, historial o los referenciales de Agendamiento |
| `docs/pendientes_referenciales.md` | Lista ordenada de pendientes de referenciales (migrar Caja/Depósito/Cliente al helper, Agendamiento a lógico, Timbrado, etc.) | planifiques el próximo trabajo de referenciales |
| `docs/pendientes_der_cus.md` | "Cambios del DER pendientes de reflejar" y "CUS a actualizar", completas | documentes la tesis o cambies el esquema |
| `docs/backups.md` | Guía de copias de seguridad y restauración | toques backups o restaures |
| `docs/acceso_red.md` | Guía para abrir PostgreSQL a la red local | conectes otra PC a la base |

## Reglas generales aprendidas en Consultorio (aplicar a Facturación también)

1. **Revisar el CUS real antes de asumir que un movimiento se parece a
   otro** — incluso movimientos "parecidos" (Recetas vs Órdenes vs
   Justificativo) tienen diferencias reales de campos, vinculación
   opcional, y mecanismo de estados. Hay un chat de análisis aparte,
   "Diseño del módulo de Consultorio en OdontoClinic", con los CUS ya
   documentados — buscar ahí antes de re-derivar. Puede existir un chat
   equivalente para Facturación, buscarlo antes de asumir que no existe.
2. Un movimiento clínico es **Nuevo + Anular únicamente** por defecto
   (nunca "Modificar" salvo excepción explícita del CUS, como Ficha
   Médica). Un botón **"Ver"** de solo lectura siempre es válido agregar.
   El botón de baja SIEMPRE se llama **"Anular"**, nunca "Eliminar" — y
   si el CUS pide "actualiza el estado a inactivo", es baja lógica real.
3. **Índices únicos parciales** (`WHERE activo = true` o equivalente):
   cualquier `UNIQUE` en una tabla con baja lógica tiene que convertirse
   en parcial DESDE EL ARRANQUE, si no un registro anulado bloquea crear
   uno nuevo en su lugar para siempre (pasó repetidas veces).
4. **Dependencias cruzadas**: cuando una tabla B agrega baja lógica,
   revisar TODOS los `EXISTS`/bloqueos que otras tablas hacen contra B
   para que filtren `activo` — y todos los JOIN de listados contra B, que
   pueden MULTIPLICAR filas visualmente si no filtran (pasó con
   `ConsultaDao.getConsultas()` contra `ficha_medica_consulta`). Conectar
   cualquier `estaEnUso()` que haya quedado documentado como "pendiente,
   esperando a que exista X" apenas X se construya.
5. Revisar si hay botones "Acción Rápida"/cruces con otras pantallas que
   haya que cablear, en vez de dejarlos como placeholder sin conectar.
6. Mensajes de éxito/error con datos descriptivos reales, nunca IDs
   crudos.
7. Probar en el navegador manualmente, no solo confiar en los tests por
   script de Claude Code.
8. Antes de abrir una terminal nueva o pedir que se levante el servidor,
   confirmar que no haya otro `run.py` corriendo de una sesión anterior
   (pasó con 8 procesos zombie acumulados en una sesión larga).



## Estándar de referenciales (aplica a TODOS los módulos)
Todo referencial —nuevo o migrado— cumple estos 6 puntos. Implementación de referencia: **Caja**
(`app/rutas/modulo_facturacion/caja/`, `app/dao/modulo_facturacion/caja/`); con combos, **Adherida/Ítems**.

1. **Vista en `base_tabler.html`** (Bootstrap 5/Tabler, `fetch` + JS vanilla sin jQuery, SweetAlert2,
   formulario en modal, validaciones dentro del modal).
2. **Sin Código visible; descripción en MAYÚSCULAS** (la normaliza el servidor; el ID autonumérico es el único
   identificador). Validadores en `utils.py` con su espejo en `facturacion-validadores.js` (siempre los dos).
3. **Borrado lógico** con columna `activo BOOLEAN NOT NULL DEFAULT true` e **índices únicos PARCIALES
   `WHERE activo = true`** desde el arranque (un registro anulado no puede bloquear crear otro igual).
   FK `RESTRICT`. El botón de baja se llama **"Anular"**, nunca "Eliminar".
4. **Columna Estado** (badge verde "Activo" / gris "Inactivo"), **switch "Mostrar inactivos"** (apagado por
   defecto; `GET ...?inactivos=1` exige `ver`; sin el parámetro la API solo devuelve activos, porque la usan los
   combos de otras pantallas) y **botón "Reactivar"** con confirmación SweetAlert2 en las filas inactivas, con el
   permiso `editar`. Reactivar valida duplicados (y que los registros padre sigan existiendo/activos) en una sola
   transacción y devuelve 409 con mensaje claro. La parte de interfaz se arma con
   `app/static/js/facturacion-listado.js` (`FacturacionListado`: `pedir`, `escapar`, `urlListado`, `badgeEstado`,
   `claseFila`, `acciones`, `anular`, `reactivar`); escrito en ES5 a propósito para poder probarlo fuera del navegador.
5. **Baja bloqueada si está en uso**, con **409** y mensaje claro. `esta_en_uso()` devuelve `False` o el texto del
   motivo; `deleteX()` devuelve `("EN_USO", motivo)`; la verificación y el UPDATE van en la misma transacción con la
   fila bloqueada (`FOR UPDATE`; el alta/edición del hijo toma `FOR SHARE` sobre el padre). Cuando la tabla que
   lo usa todavía no existe, queda un TODO que dice cuál consultar. La API compara el resultado explícitamente
   (nunca `if resultado:` sobre un string).
6. **Auditoría en `auditoria_cambios`** (formato estructurado de la Etapa C: **todo módulo que se migre debe auditar así**, con `detalle_cambios()` + `utils.auditar`, que guardan módulo y los JSON `valores_anteriores`/`valores_nuevos`; ver "Auditoría — tanda de cierre, Etapa C") vía `AuditoriaCambiosDao`/`utils.auditar`: `ALTA`, `MODIFICACION`, `BAJA`
   y `REACTIVACION` (y `CIERRE` para los movimientos que se cierran: Apertura y Cierre de Caja), con `id_usuario`
   de la sesión e `ip` del request (nunca del cliente). El detalle muestra
   NOMBRES (no IDs) y solo lo que cambió; una edición sin cambios no audita.

Además, como en todo endpoint: `@require_permiso(ventana, acción)`, botones envueltos en `puede(...)`, entrada en
`menu_catalog.py` y seed de permisos idempotente (ver "Modelo de permisos").

### Estado actual de los referenciales frente al estándar (verificado en el código y en la base)
| Módulo | Referencial | Borrado hoy | Vista | Falta |
|---|---|---|---|---|
| Facturación | Forma de Cobro, Marca de Tarjeta, Entidad Emisora, Entidad Adherida, Tipo Ítems, Ítems | **Lógico** | Tabler (con `facturacion-listado.js`) | — (cumplen los 6 puntos) |
| Facturación | Cuenta Bancaria | **Lógico** | Tabler (con `facturacion-listado.js`) | — (cumple los 6 puntos) |
| Facturación | Caja, Depósito, Cliente | **Lógico** | Tabler (con su propia copia del código de listado) | — (cumplen los 6 puntos); falta migrarlas al helper y unificar `?inactivas` de Caja |
| Consultorio | Tipo Tratamiento, Tipo Insumo Utilizado, Tipo Procedimiento Médico, Medicamentos, Tipo Estudio, Tipo Análisis | **Lógico** (`activo`, único parcial con `UPPER`) | **Tabler** (etapa 1, `catalogo_api.py` + `CatalogoDao`) | — (cumplen los 6 puntos) |
| Consultorio | Tipo Diagnóstico, Síntomas | **Lógico** (`activo`, único parcial con `UPPER`) | **Tabler** (etapa 2, mismo `CatalogoDao` / `catalogo_api.py`) | — (cumplen los 6 puntos) |
| Agendamiento | Ciudad, Cargo, Consultorio, Disponibilidad Horaria, Especialidad, Día, Turno | **Lógico** (etapa 1 de `agendamiento-tabler`; reutilizan `CatalogoDao` / `crear_api_catalogo`, Disponibilidad con DAO propio) | **Tabler** | — (cumplen los 6 puntos) |
| Agendamiento | Paciente, Funcionario, Médico (datos maestros) | **Lógico** (etapa 2; `PersonaDao`, baja bloqueada con trabajo en curso, 409) | **Tabler** | — |


## Estándar de movimientos (resumen; detalle en `docs/historial_modulos.md` y `docs/historial_consultorio.md`)

### Movimientos de Facturación (Módulo Facturación)
Aperturas de caja, pedidos, ventas, cobros, remisiones, notas de crédito/débito y arqueos. Patrón común:
- **Ventana propia** con acciones `ver` / `nuevo` / `anular` (+ `estado` donde hay un paso más: cerrar caja, marcar depositada). El **Cajero recibe todas** las acciones de cada movimiento (seed `schema_permisos_cajero.sql`: cada movimiento nuevo suma su ventana ahí; el test `smoke_permisos_cajero` falla si falta).
- **Estados finales** (ABIERTA → CERRADA | ANULADA, PENDIENTE → FACTURADO | ANULADO, EMITIDA/EMITIDO → ANULADA/ANULADO): un anulado no se reactiva y **su número no se reutiliza**. Numeración correlativa **sin huecos** (SP o función bajo bloqueo asesor).
- **Caja ABIERTA del cajero** (`FOR SHARE` sobre la apertura) para vender, cobrar o emitir notas; **anular solo mientras la caja del movimiento siga abierta**; si está cerrada: "utilice una Nota de Crédito".
- **Totales, IVA, número, cajero y apertura los calcula el servidor** (`calcular_totales`: IVA incluido en el precio; IVA = gravada10/11 y gravada5/21). Precio, IVA y descripción se **copian al documento** (la factura conserva los suyos aunque el ítem cambie).
- **Stock**: se descuenta SOLO en el Pedido; la Venta no lo toca; la devolución de mercadería (nota de crédito) lo repone.
- **Efectivo del cierre** = apertura + efectivo cobrado − reintegros; tarjetas, cheques y transferencias no cuentan.
- **PDF al vuelo con ReportLab**, sin persistir archivo, patrón `calcular_datos_X` / `dibujar_X` / `generarXPdf`, ORIGINAL y DUPLICADO, marca "ANULADO/A" (se descarga igual).
- **Bloqueos cruzados**: anular un documento padre se bloquea si tiene hijos EMITIDOS (venta con cobros, remisiones o notas; apertura con movimientos).
- Un test `tests/facturacion/smoke_<movimiento>.py` por movimiento, con datos `ZZ` y emisor sin caja real abierta.

### Movimientos de Consultorio (10 movimientos clínicos)
Reglas comunes (con test), vigentes tras la migración a Tabler:
- Solo el **médico de la consulta** crea y anula (`id_medico_sesion()`); consulta `programada` / `en_proceso` **revalidada en la transacción** con la consulta bloqueada (`FOR UPDATE`); paciente y médico heredados de la consulta; referenciales elegidos con `FOR SHARE` rechazando inactivos.
- **Anulación definitiva** (solo los referenciales se reactivan); no se anula con la consulta `finalizada`. Excepción: las **órdenes** (estudios/análisis) avanzan de estado un paso por vez también con la consulta finalizada; el **Justificativo** (`pendiente` → `emitido` | `anulado`) se emite también con la consulta finalizada.
- **Privacidad**: un médico lee solo lo suyo; el **Administrador solo lee**; Recepción solo ve consultas y fichas (sin datos clínicos); el Cajero no accede.
- **Auditoría sin contenido clínico** (quién, cuándo, paciente, N.º de documento y cambios de estado); los PDF sí llevan el contenido y **cada descarga se audita** como `EXPORTACION`.
- Vínculos opcionales (diagnóstico, tratamiento) siempre dentro de la misma consulta. N.º de documento derivado del id (`CON-`, `RCT-`, `OES-`, `OAN-`, `JUS-`).
- Cada pantalla contextual lee `?consulta=<id>` y tiene "Volver a la consulta". Se registra una Consulta desde una cita `Confirmado` sin consulta (la registra un funcionario).
- Los 8 referenciales clínicos los gestionan el Médico y el Administrador; Recepción y Cajero sin permisos.

## Auditoría y privacidad (resumen; detalle en `docs/historial_modulos.md`, "Etapa C")
- **Dos tablas distintas**: `auditoria_acceso` (cada intento de login/2FA/recuperación, con IP, país y actor) y `auditoria_cambios` (ALTA, MODIFICACION, BAJA, REACTIVACION, CIERRE, EXPORTACION). Ambas **inmutables** (`trg_auditoria_inmutable`; la app solo `SELECT`/`INSERT`). Los tests limpian solo lo que generan, con `tests/facturacion/_limpieza.py::borrar_auditoria`.
- **Formato estructurado**: `utils.detalle_cambios()` + `utils.auditar()` guardan `modulo` y los JSON `valores_anteriores` / `valores_nuevos` (solo los campos que cambiaron; una edición sin cambios no audita). Muestra NOMBRES, no IDs. `id_usuario` sale de la sesión e `ip` del request, nunca del cliente.
- **Una entidad nueva debe sumarse a `MODULO_POR_ENTIDAD` y `ETIQUETA_ENTIDAD`** (`app/Services/auditoria_detalle.py`) y, si es un movimiento que se anula, a `ENTIDADES_MOVIMIENTO` (para que su BAJA diga "Anulado"). Si no, se guarda sin módulo y se muestra "Otro".
- **Pantalla "Auditoría de Cambios"** y **Tablero de Accesos**: solo Administrador, solo lectura, filtros, exportación a PDF/CSV (tope 5.000 filas; cada exportación se audita) y alertas (`v_auditoria_anomalias`, umbrales en `auditoria_umbrales`).
- **Qué NO audita todavía** (se suma al migrar): Agendamiento (Paciente, Médico, Funcionario, Agenda, Cita, Avisos, Historial y sus 7 referenciales) y Seguridad (alta/edición/baja de Usuarios, Roles y Permisos).
- **Nunca se guarda**: la contraseña ingresada, el código 2FA, ni contenido clínico (diagnósticos, síntomas, indicaciones, medicamentos, observaciones).
- **Seguridad de acceso vigente**: contraseña compleja (8+, mayúscula, número, símbolo; política duplicada en 3 sitios), bloqueo a los 3 intentos (desbloqueo manual con permiso `desbloquear` o automático a los 15 min), 2FA por correo de 6 dígitos (5 min), recuperación por código (10 min, 5 intentos, 60 s entre envíos), cierre por inactividad a los 30 min con aviso a 120 s (un poller propio debe mandar `X-Sin-Actividad: 1`), IP permitida solo `PY` (privadas siempre; IP pública sin geolocalizar se permite y se audita), cookie `oc_usuario` solo con el CI/RUC. HTTPS no implementado (decisión documentada en el historial).

## Modelo de permisos
- **Permiso = rol + ventana + acción.** Acciones: `ver`, `nuevo`, `editar`, `anular`,
  `estado`. Tabla `permisos` (FK a `roles`, **`id_menu` FK a `menu`** —`menu.clave` = la ventana del catálogo—, único por
  rol + id_menu + acción, CHECK de acción). **La columna `permisos.ventana` ya no existe** (migración 02). Administrador no necesita filas: siempre pasa (bypass en `puede()`).
- **Catálogo único: `app/rutas/modulo_seguridad/menu_catalog.py`.** De ahí salen el
  sidebar, el buscador general y las filas de la matriz de Roles y Permisos. Cada
  entrada declara qué `acciones` expone la ventana. `en_menu: False` = pantalla
  contextual (ej. Sesiones de tratamiento): sin sidebar ni buscador, pero con fila
  en la matriz.
- **Pantalla nueva = una entrada en el catálogo + seed de permisos** (SQL idempotente
  `app/dao/modulo_seguridad/schema_permisos_*.sql`, con `ON CONFLICT DO NOTHING`; los
  roles no-admin reciben lo que ya hacían, para no cortar flujos).
- **Todo endpoint nuevo lleva `@require_permiso(ventana, acción)`** (GET = ver,
  POST = nuevo, PUT = editar, DELETE = anular) y **los botones van envueltos en
  `puede(ventana, acción)`** en el template, incluidas las tarjetas/atajos hacia
  otras ventanas (según el `ver` de la ventana destino).
- **Los GET que alimentan combos o datos de otras pantallas quedan con
  `@require_login`** (si no, quitarle `ver` a una ventana rompería los formularios
  de otras).
- **`estado` vs `anular`:** `estado` es para mover un registro dentro de su flujo
  (estado de cita, confirmar/enviar aviso, actualizar estado de una orden, finalizar
  tratamiento, estado de la consulta). `anular` es solo anular o reactivar (baja
  lógica).
- **Edición de datos sin `editar` en el catálogo = solo Administrador:** si una API
  tiene un PUT de datos pero la ventana no expone `editar`, el endpoint exige
  `editar` igual y nadie más que Administrador lo tiene; se oculta el botón Editar.
  Si hay que delegarlo, se agrega `editar` a la ventana en el catálogo y al seed.
- **Permisos del rol Cajero** (`app/dao/modulo_seguridad/schema_permisos_cajero.sql`, idempotente; define el conjunto
  COMPLETO del Cajero: quita lo que sobra e inserta lo que falta, y solo toca ese rol):
  - **Módulo Facturación (movimientos, hoy `aperturacaja`, `pedidocliente`, `venta`, `cobro`, `remision`, `notacd` y `arqueo`): todas las acciones de la ventana.**
  - **Cliente: `ver`, `nuevo`, `editar`** (sin `anular`).
  - **Forma de Cobro, Marca de Tarjeta, Entidad Emisora, Entidad Adherida, Caja, Depósito, Tipo Ítems, Ítems y Cuenta Bancaria: solo `ver`.**
  - **Agendamiento, Consultorio y Seguridad: ningún permiso.** El Cajero queda con 35 filas de permisos (15 + las 3 de `pedidocliente` + las 3 de `venta` + las 3 de `cobro` + las 3 de `remision` + las 3 de `notacd` + las 4 de `arqueo` + `cuentabancaria` ver).
  - **Cada movimiento NUEVO de Facturación debe sumar su ventana (con todas sus acciones) a ese seed**, y todo
    referencial nuevo de Facturación entra con `ver`. `tests/facturacion/smoke_permisos_cajero.py` falla si el
    catálogo tiene una ventana de "Módulo Facturación" que el Cajero no puede usar por completo.
  - Los GET que alimentan combos siguen con `@require_login`, así que los combos de Facturación funcionan igual.
    Con `nuevo` en Cliente, el Cajero puede usar el buscador de pacientes (`/clientes/pacientes`) sin tener permiso
    sobre la ventana Pacientes (decisión confirmada).
  - Los tests que necesiten anular/crear un referencial deben usar la sesión del Administrador, no la del Cajero.
- **Tabla `menu` y `permisos.id_menu` (DER, migración 02 aplicada):** los permisos se identifican por `permisos.id_menu` (FK a
  `menu`, una fila por ventana, `clave` = la ventana del catálogo); `permisos.ventana` y el trigger de compatibilidad
  `trg_permisos_resolver_menu` se eliminaron. `PermisoDao` lee/otorga/revoca por JOIN a `menu` (solo entradas `activo`) y sigue
  devolviendo el set `(ventana, accion)`, así que `puede()`, `require_permiso`, el menú y el buscador no cambiaron. **Toda
  ventana NUEVA necesita su fila en `menu` ANTES de sembrar permisos**, y los seeds `schema_permisos_*.sql` insertan por
  `JOIN menu m ON m.clave = <ventana>` con `ON CONFLICT (id_rol, id_menu, accion)` (ver `schema_permisos_cobranzas.sql`; los
  tests usan `id_menu = (SELECT id_menu FROM menu WHERE clave='x' AND activo = true)`). `PermisoDao.otorgar` devuelve False si
  la ventana no tiene entrada de menú. `schema_permisos_matriz.sql` quedó como histórico (no volver a ejecutar). El sidebar y el
  buscador siguen saliendo de `menu_catalog.py`: la tabla `menu` todavía no los alimenta. OJO: el catálogo tiene ventanas que
  no están en `menu` (hoy `usuario` y `auditoria`, que son solo
  Administrador): sin fila en `menu` no se les puede otorgar permisos.
- **Roles y Permisos** (la matriz) queda con `@require_admin` fijo y fuera del
  catálogo, para que nadie pueda autoconcederse acceso.
- **Páginas de error propias 403/404/500** (`app/rutas/errores.py`, plantillas en
  `app/templates/errores/`): si la ruta empieza con `/api/` responden JSON; si es
  una vista, HTML. Con sesión extienden `base_tabler.html` (sidebar); sin sesión usan un
  layout standalone Tabler. `require_permiso`/`require_admin` hacen
  `abort(403)` en las vistas (ya no redirigen con flash); el 403 muestra qué ventana
  se intentó abrir cuando `require_permiso` la conoce.

## Tests (carpeta `tests/`, ver `tests/README.md`)
- Scripts de verificación sin pytest, organizados por módulo: `tests/facturacion/` (los 8 referenciales + Ítems, la
  reactivación, `browser_test.py` y la comparación JS↔Python de los validadores), `tests/agendamiento/` (regresión de
  Consultorio y Paciente) y `tests/consultorio/` (hoy solo `smoke_tipo_tratamiento.py`; el resto del módulo
  Consultorio todavía no tiene tests).
- Se corren desde la raíz: `.\.venv\Scripts\python.exe -I tests\<módulo>\smoke_xxx.py`. Terminan con
  `FALLOS: ninguno` o la lista de lo que falló.
- **Usan la base real `odontosisbd`.** Reglas para escribir más: crear datos con prefijo `ZZ` y **borrar solo lo
  creado por el test** (por ID; nunca un `DELETE` por entidad completa: un script viejo de Forma de Cobro borró de
  esa manera la auditoría hecha a mano y por eso no se conservó); restaurar en un `finally` cualquier permiso que se
  quite; no depender de datos que se editan a mano (los `seed` pueden fallar si se renombran desde la pantalla).
- **Los tests importan `from tests._conexion_pruebas import Conexion`** (postgres, `TEST_DB_*`) para preparar y limpiar datos;
  la app y los DAO que ejercitan usan `odontoclinic_app`. Sumó `smoke_permisos_app` y `smoke_backup` (Etapa B).
- `tests/seguridad/smoke_auditoria_consulta.py` y `browser_auditoria.py` (Etapa C, ver "Auditoría — tanda de cierre, Etapa C"); el segundo necesita Edge y recibe una carpeta de salida: `.\.venv\Scripts\python.exe -I tests\seguridad\browser_auditoria.py <carpeta>`.
- `tests/seguridad/` (Etapa A de la tanda de cierre): `smoke_inactividad` (usa también Edge headless para la lógica de
  `inactividad.js`), `smoke_ip_pais` y `smoke_acceso_basico`. Borran solo la auditoría y los códigos 2FA que generan, por ID.
- `browser_test.py` ejecuta las vistas en Edge headless con `fetch` simulado (necesita Edge; la ruta está en la
  constante `EDGE`). No reemplaza probar el guardado real en el navegador (regla 7 de "Reglas generales aprendidas").


## Backups, migraciones y base de datos (resumen; guías en `docs/backups.md` y `docs/acceso_red.md`)
- **Backups**: `app/Services/backup_service.py` (`pg_dump -Fc`, `odontosisbd_AAAAMMDD_HHMMSS.dump`, retención de 7, `backup.log`), `scripts/backup_db.py` y `scripts/backup_diario.bat` (la tarea de las 23:00 la crea quien administra el servidor). `BACKUP_DIR=C:\OdontoClinic\backups`, fuera de OneDrive. Pantalla "Copias de Seguridad" (solo Administrador, auditada); **no restaura** (solo con la guía). La contraseña viaja solo por `PGPASSWORD` del proceso hijo.
- **Tres cuentas de base**: `DB_*` (`odontoclinic_app`, la aplicación), `TEST_DB_*` (`postgres`: migraciones, roles y tests) y `BACKUP_DB_*` (`odontoclinic_backup`, solo lectura). Contraseñas distintas en el `.env`. Crear/cambiar roles: `python -m app.dao.modulo_seguridad.crear_usuario_app`; re-aplicar permisos: `--solo-permisos`.
- **Una tabla de auditoría nueva** hay que agregarla a la lista `v_auditoria` de `schema_usuario_app.sql` y re-aplicarlo.
- **Migraciones** (`migraciones/`, p. ej. `02_migracion_requiere_codigo.sql`): idempotentes, en una transacción, con postgres, **después de un backup** y probadas primero sobre una copia restaurada. Los `schema_*.sql` se aplican con postgres y `PGCLIENTENCODING=UTF8`.
- Orden de scripts de Facturación y de Consultorio: ver el historial correspondiente (`schema_tipo_items` → `schema_deposito` → `migracion_items_deposito` → `schema_items`…; `schema_consultorio_base.sql` + etapas 0 y 2 a 7).
- Tras cambiar `DB_USER` hay que **reiniciar `run.py`**. Antes de levantar el servidor, confirmar que no haya otro `run.py` corriendo de una sesión anterior.
- Dos PostgreSQL conviven en la PC (14 y 16): el servidor de la app es el 14 (`PG_BIN_DIR` apunta a su `bin`).

## Convenciones de código
- SQL crudo con psycopg2, sin ORM.
- Conexión vía `app/conexion/Conexion.py` — reusar esa clase, no crear una nueva.
  Las credenciales salen de `.env` (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`); si falta alguna,
  `Conexion()` falla con un error que nombra la variable. Nunca escribirlas en el código.
  `DB_USER` es `odontoclinic_app` (mínimo privilegio). Para algo que necesite postgres (migraciones, tests) usar
  `app/conexion/ConexionAdmin.py` (`TEST_DB_*`), nunca en código que corra la aplicación.
- Cada DAO abre su propia conexión y la cierra en un `finally`.
- Los blueprints de rutas se registran en `app/__init__.py` bajo `/referenciales/<modulo>`
  o bajo `/api/v1`.
- Seguir el mismo estilo/nombres que los módulos ya existentes (ej. `CiudadDao.py`,
  `ciudad_api.py`, `ciudad_routes.py`) para cualquier módulo nuevo.


## Estado actual de cada módulo (resumen)
- **Seguridad — COMPLETO.** Login + 2FA, bloqueo, recuperación, Usuarios, Roles y Permisos (matriz), Tablero de Accesos, Auditoría de Cambios, Copias de Seguridad y **Mantener Menú** (rama `seguridad-menu`): la tabla `menu` (módulos + ventanas, `solo_admin`, `protegida`) alimenta el sidebar, el buscador y la matriz vía `menu_servicio.py`; `menu_catalog.py` es la semilla y el registro de acciones por ventana. Una ventana NUEVA en el código necesita su entrada en el catálogo + fila en `menu` (se crea desde la pantalla).
- **Agendamiento — migrado a Tabler (rama `agendamiento-tabler`, plan en `plan_agendamiento.md`; 3 etapas hechas).** Base versionada + 7 referenciales con baja lógica; Paciente / Médico / Funcionario con baja lógica (`PersonaDao` + `crear_api_persona`); Agenda, Cita (cupo transaccional), Avisos con envío por WhatsApp Web (sesión persistente) y respaldo por correo, Historial Médico (acceso por rol), Usuarios y Roles/Permisos en Tabler, con auditoría y rechazo de personas y referenciales anulados. Pendiente: probar a mano el envío real por WhatsApp (los tests usan dobles) y, si se quiere retirar `base.html`, migrar las páginas de error.
- **Consultorio — COMPLETO y migrado a Tabler** (rama `consultorio-tabler` cerrada): 10 movimientos + 8 referenciales con baja lógica, 24 tablas versionadas, tests por movimiento. Rediseño visual reciente de la Atención de la Consulta y del Odontograma. Detalle en `docs/historial_consultorio.md`.
- **Facturación — COMPLETO**: 10 referenciales (Forma de Cobro, Marca de Tarjeta, Entidad Emisora, Entidad Adherida, Tipo Ítems, Ítems, Caja, Depósito, Cliente, + Cuenta Bancaria) y los movimientos Apertura/Cierre de Caja, Pedido Cliente, Ventas (ítems y tratamiento), Cobranzas, Nota de Remisión, Notas de Crédito/Débito y Arqueo de Caja. Pendiente: migrar Caja/Depósito/Cliente a `facturacion-listado.js` y unificar `?inactivas` → `?inactivos`; el referencial **Mantener Timbrado** (esperando el CUS); cobrar en el momento de la venta de contado; la fila `#17 "BHDJDGJ"` de `forma_cobro` sin tipo (deja `NOT NULL` de `forma_cobro.tipo` pendiente).
- **Tanda de cierre (rama `finalizando`) — hecha**: Etapa A (acceso), B (base de datos y backups), C (auditoría). Rúbricas del profesor 3, 8 y 9 completas.
- **Deuda general**: reflejar en el DER y en los CUS lo listado en `docs/pendientes_der_cus.md`; cambiar la contraseña de `postgres` (quedó en el historial de git); la ruta suelta `/vista` de `app/__init__.py` falla (`stats` sin definir); el pie del login dice "Conexión segura" sin HTTPS; corregir en el Word de la tesis los 6 CUS de referenciales de Consultorio (ya no tienen Código).

## Cómo trabajar conmigo en este proyecto
- Antes de tocar código existente, mostrame el plan de archivos que vas a crear/modificar.
- Si una decisión de diseño no está clara en este documento, preguntame antes de asumir.
- Priorizá consistencia con el patrón de capas por sobre "mejores prácticas" genéricas
  que rompan la estructura ya usada en el resto del proyecto.
