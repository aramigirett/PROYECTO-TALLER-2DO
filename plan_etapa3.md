# Etapa 3 — Registrar Consulta + Ficha Médica (plan de archivos, a aprobar)

Rama `consultorio-tabler`. Relevado sobre el código y la base real. **No se modificó nada.** Este archivo no se commitea.
Reglas ya decididas que esta etapa aplica: anulación definitiva, la cita vuelve a `Confirmado` al anular, `id_cita` único parcial, auditoría sin contenido
clínico, la consulta no se anula con Ficha Médica, Diagnóstico o Tratamiento.

## 1. Qué hay hoy (hallazgos que condicionan el plan)

**Registrar Consulta** (`consulta-index.html`, 2.142 líneas tras la etapa 0; `ConsultaDao`, `consulta_api.py`)
- Nueva consulta desde una cita `Confirmado` sin consulta; el funcionario sale de la sesión; paciente/médico/consultorio/fecha/hora se derivan de la cita; la
  cita pasa a `Realizado` en la misma transacción. Esto **está bien y se conserva**.
- **Contradicciones con las reglas confirmadas:**
  1. **No bloquea si el paciente, el médico o el consultorio están inactivos** (las tres tablas tienen `activo`). Hoy solo mira el estado de la cita.
  2. `uk_consulta_cita` es `UNIQUE (id_cita)` total y la comprobación de duplicado no mira `activo`: una cita con consulta anulada **no vuelve a poder consultarse**
     (la cita queda `Realizado`). `getCitasConfirmadasSinConsulta` (Agendamiento) tampoco filtra `activo`.
  3. **Anular no devuelve la cita a `Confirmado`** y no audita. Tampoco bloquea con la consulta `finalizada`; cuenta como "tratamiento" incluso uno `cancelado`; no toma
     bloqueos de fila (un diagnóstico guardado en paralelo puede colarse).
  4. `PUT /consultas/<id>` acepta **cualquier estado** (se puede pasar de `finalizada` a `programada`, o a un valor fuera del flujo), sin validar que la consulta esté
     activa y sin límites de duración.
  5. **Nada de Consultorio audita** (la consulta tampoco).
- Hay 2 consultas en la base (una anulada, una `programada` con ficha vacía).

**Ficha Médica** (`ficha_medica_consulta`; `FichaMedicaDao`, `ficha_medica_api.py`, modal dentro de `consulta-index.html` y pantalla `ficha-medica-index.html`, 784 líneas)
- Validaciones de consistencia que **sí existen hoy**: (a) **una ficha activa por consulta** (índice `uk_ficha_medica_consulta_activa` + chequeo en la API, 400); (b) el IMC
  se calcula en el navegador (`peso / (talla/100)²`, 2 decimales) y es de solo lectura en el formulario; (c) anular se bloquea si la consulta está `finalizada`
  (`CONSULTA_FINALIZADA`, 409); (d) tipos de columna (`temperatura NUMERIC(4,2)`, `peso/talla/imc NUMERIC(5,2)`, `presion_arterial VARCHAR(20)`).
- **Lo que NO existe** (todo es del navegador): rangos clínicos (se acepta temperatura 99 °C o peso negativo), formato de la presión, que el servidor recalcule el IMC (hoy
  confía en el que manda el cliente), exigir al menos un dato (la ficha de la consulta 17 está **completamente vacía**), validar que la consulta exista, esté activa y
  `programada`/`en_proceso` al crear **y al editar** (el `PUT` no mira nada), y auditoría. El FK `fk_ficha_consulta` es `ON DELETE CASCADE` (el estándar pide `RESTRICT`).
- `GET /ficha-medica/consulta/<id>` y `/ficha-medica/<id>` están con `@require_login`: **cualquier usuario con sesión (incluso Cajero) puede leer datos clínicos**.

**Permisos (contradicen la regla "movimientos clínicos solo con rol Médico/Odontólogo")**
- En la matriz, **Recepción tiene los mismos permisos clínicos que Médico** (ficha, diagnóstico, odontograma, tratamiento, receta…), y Médico tiene `consulta nuevo/anular`.
- Los dos usuarios que son médicos (`id_medico` 15 y 19, usuarios 9 y 10) **tienen rol `Recepcion`**; no existe ningún usuario con rol `Medico`. Un chequeo "solo rol Médico" hoy
  dejaría a los médicos reales sin poder cargar nada.
- Registrar Consulta ya exige un usuario vinculado a un **funcionario**; un médico recibe 403 ("Solo un funcionario puede registrar consultas.").

## 2. Qué se migra, qué se reescribe y qué se elimina del template actual

`app/rutas/modulo_consultorio/consulta/templates/consulta-index.html` (2.142 líneas) se **reemplaza** por una versión Tabler de ~400 líneas (patrón de Pedido y Ventas).

| Bloque actual | Líneas | Destino |
|---|---|---|
| `<style>` "médico/clínico" (tema propio, CSS) | ~700 | **Se elimina.** Tabler + `facturacion.css`; lo clínico que haga falta (badges de estado) va en clases de Tabler. |
| Carga de Bootstrap 4, jQuery, DataTables, Font Awesome por CDN | ~10 | **Se elimina** (la base Tabler ya trae Bootstrap 5, FA y SweetAlert2 locales; sin jQuery ni DataTables). |
| 4 tarjetas de estadísticas (JS que recalcula) | ~90 | **Se reescribe**: KPIs de Tabler (hoy, programadas, en proceso, finalizadas) calculados por la API (`GET /consultas/resumen`), no en el navegador. |
| Tabla de consultas (DataTables) | ~80 | **Se reescribe**: tabla Tabler con filtros (estado, paciente o CI, fechas), badge de estado, `Ver` / `Anular`, paginación en el servidor. |
| Modal "Nueva consulta" + selector de cita (`DataTable` de citas confirmadas) | ~200 | **Se migra**: modal Tabler con buscador de citas confirmadas sin consulta (por paciente/CI/fecha) y tarjeta de resumen de la cita elegida. Sin elegir funcionario. |
| Modal "Buscar funcionario" + su DataTable | ~70 | **Se elimina** (código muerto: el funcionario sale de la sesión). |
| Modal "Detalles de consulta" (pestaña Información + 8 tarjetas de acción rápida) | ~170 | **Pasa a la pantalla central** (sección 3). |
| Modal "Ficha médica" embebido (formulario + guardar/anular + IMC) | ~330 | **Se migra a una tarjeta de la pantalla central** (sección 4); el formulario sale del modal. |
| "Editar consulta" (cambiar estado y duración en un formulario) | ~60 | **Se reescribe** como acciones de estado en la pantalla central (`Iniciar atención`, `Finalizar`, `Cancelar`), con las transiciones del servidor. |
| Anular con SweetAlert2 | ~40 | **Se migra** a `FacturacionListado.anular` con el mensaje del servidor (409 con el motivo). |

`ficha-medica-index.html` (784 líneas, SB Admin 2, DataTables + estadísticas) se **reemplaza** por una versión Tabler de ~250 líneas: listado/auditoría transversal de fichas
(filtros paciente, médico, fechas; **sin mostrar valores clínicos en el listado**, solo paciente, médico, fecha y si la ficha está completa), `Ver` y `Anular` (y `Editar`, la
excepción confirmada del CUS), enlace a la consulta.

## 3. Registrar Consulta como pantalla central

Dos pantallas, una sola ventana de permisos (`consulta`):
- **Listado** `/referenciales/consulta/consulta-index` (ya existe): consultas con filtros y KPIs, `Nueva consulta`, `Ver`, `Anular`.
- **Atención de la consulta** `/referenciales/consulta/consulta-detalle/<id>` (**nueva**, contextual: sin entrada de menú ni de matriz, usa `consulta` + `ver`). Es el centro:
  - **Cabecera en tarjeta**: N.º de consulta (`CON-0000017`, derivado del id, sin columna nueva), paciente (con CI), médico, consultorio, fecha y hora de la cita, funcionario que la
    registró, duración y badge de estado (`programada` / `en_proceso` / `finalizada` / `cancelada`).
  - **Acciones de estado** (permiso `estado`) según la transición permitida (sección 5).
  - **Ficha Médica** en una tarjeta propia (una por consulta; formulario o resumen con `Editar`/`Anular`).
  - **Movimientos clínicos** en una grilla de tarjetas, cada una con su **contador de registros vigentes** (solo cantidades, nunca contenido) y el botón `Abrir`, visibles según el
    `ver` de la ventana destino (como hoy): **Diagnósticos, Odontograma, Tratamientos (y desde ahí las Sesiones), Recetas, Orden de Estudios, Orden de Análisis, Justificativo
    Médico**. Los destinos se abren con `?consulta=<id>` (los parámetros que ya leen). Con la consulta `finalizada` o `cancelada` las tarjetas quedan en solo lectura (el botón dice
    "Ver"); con `programada`/`en_proceso` dicen "Abrir". Los destinos siguen en SB Admin 2 hasta sus etapas (4 a 7); cada uno recibe después un enlace "Volver a la consulta".
  - Endpoint nuevo `GET /api/v1/consultas/<id>/resumen` (permiso `consulta ver`): contadores `{ficha, diagnosticos, odontogramas, tratamientos, recetas, ordenes_estudio,
    ordenes_analisis, justificativos}` de registros vigentes, más qué botones permite el estado actual.

## 4. Ficha Médica: una por consulta

- **Reglas**: una ficha activa por consulta (índice parcial existente, ahora también bloqueo `FOR UPDATE` de la consulta al crear); la consulta debe existir, estar activa y en
  `programada`/`en_proceso` **al crear, al editar y al anular** (se revalida dentro de la transacción: si cambió a `cancelada` o `finalizada` mientras se cargaba, 409); la ficha no se
  puede crear si la consulta fue anulada.
- **Validaciones de consistencia (servidor + espejo en el formulario)** — las que existen más las que faltan (los rangos se proponen en la sección 7, pendientes de tu OK):
  - IMC **recalculado por el servidor** (`peso / (talla/100)²`, 2 decimales; el valor del navegador se ignora); si falta peso o talla, el IMC queda vacío.
  - Presión arterial `SSS/DDD` (enteros), con sistólica mayor que diastólica; temperatura, frecuencia cardíaca, frecuencia respiratoria, peso y talla dentro de rangos; textos con
    límite y sin caracteres de control.
  - Al menos un dato en la ficha (no se guardan fichas vacías).
- **Base de datos**: `CHECK` de rangos en `ficha_medica_consulta` (misma regla que el servidor) y `fk_ficha_consulta` pasa de `CASCADE` a `RESTRICT`.
- **Privacidad**: `GET /ficha-medica/consulta/<id>` y `/ficha-medica/<id>` pasan de `@require_login` a `@require_permiso('fichamedica','ver')`; el único lector externo es la propia pantalla.
  El listado transversal (`/fichas-todas`) deja de devolver los valores clínicos (solo paciente, médico, fecha, completa sí/no); el detalle clínico solo en el `GET` por id.
- **Auditoría** (entidad `ficha_medica_consulta`, módulo "Módulo Consultorio"): `ALTA`, `MODIFICACION` y `BAJA` (Activo → Anulado) con paciente, N.º de consulta y quién;
  **sin valores clínicos** (la modificación dice "Ficha médica modificada", sin anterior/nuevo).

## 5. Reglas de Registrar Consulta que se implementan

**Alta** (una transacción, bloqueando la cita `FOR UPDATE`): cita `Confirmado` y sin consulta **activa**; **paciente, médico y consultorio activos** (y el funcionario de la sesión), con
mensajes claros ("El paciente <X> está inactivo."); estado inicial siempre `programada` (lo que mande el navegador se ignora); duración opcional entre 1 y 480 minutos; la cita pasa a `Realizado`.

**Cambio de estado** (`PATCH /consultas/<id>/estado`, permiso `estado`; reemplaza al `PUT` libre): consulta activa, bloqueada `FOR UPDATE`; transiciones del servidor:
`programada → en_proceso → finalizada`, y `programada | en_proceso → cancelada`; `finalizada` y `cancelada` son finales. Puede registrar la duración al finalizar.

**Anular** (`DELETE`, permiso `anular`; definitiva, sin reactivar): bloquea (409 con el motivo) si hay **Ficha Médica, Diagnóstico o Tratamiento** vigentes (los tratamientos
`cancelado` no cuentan). En la misma transacción: `activo = false`, **la cita vuelve a `Confirmado`** (`fecha_cambio_estado = NOW()`; no toca cupos: `Realizado` y `Confirmado` ocupan
el cupo igual) y se audita. Una cita que ya no está `Realizado` (la tocó Agendamiento) no se pisa: se informa.

**Auditoría** (`consultas_cab`): `ALTA` (paciente con CI, médico, fecha de la cita), `MODIFICACION` (solo el cambio de estado, p. ej. `Estado: programada -> en_proceso`), `BAJA`
(Activo → Anulado + "Cita N.º X vuelve a Confirmado"). Nada clínico.

## 6. Archivos

**Base de datos** (idempotente, con backup previo y corrida doble; el `schema_consultorio_base.sql` y su test se actualizan):
- **Nuevo** `app/dao/referenciales_consultorio/schema_consultorio_etapa3.sql`: reemplaza `uk_consulta_cita` por `UNIQUE INDEX ... (id_cita) WHERE activo = true`;
  `CHECK (duracion_minutos IS NULL OR duracion_minutos BETWEEN 1 AND 480)`; CHECKs de rangos de la ficha; `fk_ficha_consulta` → `RESTRICT`.
- **Modifica** `schema_consultorio_base.sql` (se regenera), `CLAUDE.md`, `tests/README.md`.

**Backend**
- **Modifica** `dao/referenciales_consultorio/consulta/ConsultaDao.py` (alta con validaciones y bloqueos; `cambiarEstado`; `anular`; `getResumen`; listado con filtros y KPIs).
- **Modifica** `rutas/modulo_consultorio/consulta/consulta_api.py` (`POST`, `GET` con filtros/KPIs, `PATCH /estado`, `DELETE`, `GET /<id>/resumen`; se quita el `PUT` libre; lookups
  `/consultas/<id>` y `/consultas/activas` se conservan porque los usan Tratamientos y otras pantallas).
- **Modifica** `consulta_routes.py` (+ ruta `consulta-detalle/<id>`).
- **Modifica** `dao/referenciales_consultorio/consulta/FichaMedicaDao.py` y `rutas/.../ficha_medica_api.py` (validaciones, IMC en el servidor, revalidación de la consulta con
  bloqueo, privacidad de las lecturas, auditoría).
- **Modifica** `rutas/modulo_consultorio/utils.py` (+ validadores clínicos de la ficha) y **crea** `app/static/js/consultorio-validadores.js` (espejo; se suma al comparador JS↔Python).
- **Modifica (Agendamiento, 1 línea)** `CitaDao.getCitasConfirmadasSinConsulta`: el `NOT EXISTS` mira solo consultas activas.
- **Modifica** `rutas/modulo_seguridad/permisos_contexto.py` (+ `id_medico_sesion()`; ver sección 7) y, si se aprueba, **nuevo** seed `app/dao/modulo_seguridad/schema_permisos_consultorio_roles.sql`.

**Vistas (Tabler)**
- **Reemplaza** `consulta/templates/consulta-index.html` (listado, KPIs, modal de nueva consulta).
- **Nuevo** `consulta/templates/consulta-detalle.html` (pantalla central + tarjeta de Ficha).
- **Reemplaza** `consulta/templates/ficha-medica-index.html`.
- **Elimina** del repo: nada más (los 700 líneas de CSS y los includes por CDN se van con el reemplazo del template).

**Tests**
- **Nuevo** `tests/consultorio/smoke_consulta.py` (alta y cada bloqueo —cita no confirmada, ya consultada, paciente/médico/consultorio inactivos—, estados y transiciones, anular con
  y sin historial, cita vuelve a `Confirmado`, **reconsultar la misma cita tras anular**, auditoría sin contenido clínico, permisos, concurrencia de dos altas sobre la misma cita).
- **Nuevo** `tests/consultorio/smoke_ficha_medica.py` (una por consulta, validaciones y rangos, IMC del servidor, ficha vacía, consulta `finalizada`/`cancelada`, privacidad de las lecturas,
  auditoría sin valores).
- **Nuevo** `tests/consultorio/browser_consulta.py` (Edge headless: listado, filtros, nueva consulta, pantalla central, ficha) con las claves del JSON en orden alfabético y la baja por HTTP real
  (la lección de la etapa 1).
- **Actualiza** `smoke_migracion02.py`, `smoke_esquema_consultorio.py`, `smoke_permisos_app.py`.

## 7. Commits propuestos dentro de la etapa

1. **Base + backend de Consulta** (script `etapa3`, `ConsultaDao`, API, `CitaDao`, auditoría, `smoke_consulta`).
2. **Ficha Médica** (validadores, DAO/API, privacidad, `smoke_ficha_medica`).
3. **Vistas Tabler** (listado, pantalla central, listado de fichas, `browser_consulta`) y la documentación.

## 8. Decisiones de negocio pendientes (lista corta; con mi recomendación)

1. **Estados de la consulta.** ¿Confirmás `programada → en_proceso → finalizada` y `programada | en_proceso → cancelada`, con `finalizada` y `cancelada` finales? ¿Quién los cambia: el
   **médico** (inicia y finaliza la atención) y **Recepción** solo cancela? *(Recomiendo sí a la secuencia; médico inicia/finaliza, Recepción cancela.)* Y: ¿**`cancelada` ≠ `anulada`**?
   Entiendo `cancelada` = la atención no se realizó pero queda en el historial, y `anulada` = el registro se dio de baja por error y la cita vuelve a `Confirmado`.
2. **Quién carga los movimientos clínicos.** La regla dice "rol Médico/Odontólogo". Hoy los 2 médicos tienen rol `Recepcion` y Recepción tiene todos los permisos clínicos. Propongo:
   (a) pasar los usuarios 9 y 10 al rol `Medico`; (b) quitarle a Recepción los permisos clínicos (queda con Consulta: ver/nuevo/anular y Fichas: ver); (c) el servidor exige que el usuario
   esté vinculado a un médico (`id_medico`) para crear/editar/anular Ficha y, en las etapas siguientes, el resto de los movimientos, **y que sea el médico de esa consulta**. ¿El
   Administrador queda solo con lectura clínica? *(Recomiendo sí a todo; si hay un odontólogo suplente, que el Administrador pueda reasignar el médico de la consulta —fuera de esta etapa.)*
3. **Rangos clínicos de la Ficha** (propuestos; si no estás de acuerdo, decime los tuyos): temperatura 30,0–45,0 °C; frecuencia cardíaca 20–250 lpm; frecuencia respiratoria 5–80 rpm;
   presión sistólica 50–300 y diastólica 30–200 mmHg (sistólica > diastólica); peso 1–500 kg; talla 30–250 cm. Además: **¿se permite una ficha sin ningún dato?** *(Recomiendo no: al menos un dato.)*
4. **Anular una consulta.** Además de Ficha, Diagnóstico y Tratamiento, ¿se bloquea con **Odontograma, Receta, Órdenes o Justificativo** vigentes, y con la consulta **finalizada**?
   *(Recomiendo sí a ambos: si no, quedan registros clínicos colgando de una consulta anulada.)*
5. **Lecturas clínicas abiertas.** Hoy cualquier usuario con sesión puede leer la ficha de cualquier consulta. ¿Lo restrinjo a quien tenga `fichamedica: ver`? *(Recomiendo sí: son datos de salud.)*
6. **Número de consulta visible**: `CON-0000017` derivado del id, sin columna nueva. ¿Está bien como "N.º de documento" para la auditoría y la pantalla? *(Recomiendo sí.)*

Las decisiones 1, 2 y 3 bloquean el código de los commits 1 y 2; la 4, 5 y 6 se resuelven con tu "sí" a las recomendaciones.
