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
├── templates/           → plantillas Jinja2 (base.html, macros.html, tema SB Admin 2)
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

## Módulo Seguridad (en desarrollo)
Basado en el CUS "Mantener Acceso" ya documentado:
- Primer factor: CI/RUC (= cédula de la persona vinculada, ver sección "CI/RUC y correo")
  + contraseña.
- Segundo factor (2FA): código de 6 dígitos enviado por **correo electrónico**,
  válido por 5 minutos, tabla `token_2fa`.
- Cada intento de acceso (exitoso o fallido) se registra en `auditoria_acceso`
  (usuario, fecha/hora, resultado, IP, acción).
- Esos intentos de acceso deben poder verse en un **Tablero de Administrador**
  dentro del sistema (no alcanza con que estén solo en la base de datos).
  Acceso restringido al rol Administrador.
- No hay validación de IP por país (descartado, es irrelevante para este proyecto).
- El menú del sistema debe tener un buscador general (CUS "Mantener Menú").

## Estado real del Módulo Seguridad (actualizado — COMPLETO)
- ✅ Login + 2FA por correo: terminado y probado end-to-end.
- ✅ Mantener Usuario (alta, edición, baja lógica, reactivar): terminado y probado.
- ✅ Tablero de Administrador (ver auditoria_acceso en pantalla): terminado y probado.
- ✅ Mantener Roles y Permisos: terminado y probado (Roles de solo lectura,
  Permisos con CRUD completo, FK permisos→roles, baja física).
- ⏳ Pendiente para más adelante: Mantener Menú (buscador general, control de
  opciones visibles según permisos). Cuando se encare, revisar si el DELETE
  físico de `permisos` sigue siendo seguro una vez que los ítems de menú
  empiecen a referenciarlos — puede que haya que pasar a baja lógica en ese
  momento.

### Endurecimiento de acceso (rúbrica del profe) — rama acceso-seguridad
- **Contraseña compleja** (`app/rutas/modulo_seguridad/password_policy.py`): mínimo 8
  caracteres, una mayúscula, un número y un símbolo. Se valida en el servidor en el
  alta y la edición de usuario (en edición solo si se escribe una nueva) y en la
  recuperación. La lista de requisitos en tiempo real está duplicada en JS
  (`usuario-index.html` y `recuperar.html`): si cambia la política, cambiar los tres.
- **Bloqueo por intentos fallidos**: 3 fallos consecutivos (`MAX_INTENTOS_FALLIDOS`)
  ponen `usuarios.bloqueado = TRUE` (columnas `intentos_fallidos`, `bloqueado`,
  `fecha_bloqueo`). Una cuenta bloqueada no entra ni con la contraseña correcta.
  - **Desbloqueo manual:** acción de permiso propia `desbloquear` de la ventana
    `usuario` (CHECK de `permisos`, catálogo y matriz). Endpoint
    `PATCH /api/v1/usuarios/<id>/desbloquear`.
  - **Desbloqueo automático:** a los 15 min (`BLOQUEO_MINUTOS` en `UsuarioDao`), en
    el siguiente intento de login.
  - El contador se reinicia solo al completar el login con 2FA, no con el primer
    factor. Reactivar un usuario NO lo desbloquea; recuperar la contraseña SÍ.
- **Alertas por correo** (`email_service.py`, en un hilo aparte para no demorar el
  login; un fallo de SMTP solo se loguea): al usuario en cada intento fallido y al
  bloquearse; a los administradores solo al bloquearse. Destinatarios admin: correos
  de los usuarios con rol Administrador activos (no hay `MAIL_ADMIN`). Los correos
  nunca incluyen la contraseña.
- **Recuperación de contraseña** (`/recuperar` → `/recuperar/codigo` →
  `/recuperar/nueva`, enlace "¿Olvidaste tu contraseña?" en el login): código de 6
  dígitos por correo, de un solo uso, vence a los 10 min, máx. 5 intentos erróneos
  y 60 s entre envíos. Mismo mensaje exista o no el CI/RUC. Al cambiar la
  contraseña se desbloquea la cuenta, se reinician los intentos y se invalidan los
  códigos pendientes. Se audita todo con `accion = 'RECUPERACION'`.
- **`token_2fa.proposito`** (`'LOGIN'` | `'RECUPERACION'`, CHECK): el mecanismo del
  2FA se reutiliza, pero los códigos no son intercambiables. `generar_codigo` y
  `validar_codigo` del 2FA filtran `proposito = 'LOGIN'`; las funciones de
  recuperación filtran `'RECUPERACION'`. Índice parcial sobre códigos no usados.
- **Auditoría** (`auditoria_acceso`):
  - `id_usuario_actor` (FK a `usuarios`, nullable): quién ejecutó la acción cuando
    no es el propio usuario (hoy, el Administrador que desbloquea). El tablero lo
    muestra en la columna "Realizado por".
  - **Filtro por fecha desde/hasta** en el Tablero de Administrador
    (`GET /api/v1/auditoria/intentos?desde=&hasta=`, `hasta` inclusivo, 400 si el
    formato es inválido o `desde > hasta`).
  - **Nunca se guarda la contraseña ingresada.** `ci_ruc_ingresado` se trunca a 20
    caracteres y, si el identificador no corresponde a ningún usuario, solo se
    guarda cuando parece CI/RUC (dígitos con dígito verificador opcional); si no,
    queda `[formato inválido]`, para no persistir una contraseña tipeada en ese
    campo.
- Scripts SQL idempotentes (`app/dao/modulo_seguridad/`): `schema_acceso_seguridad.sql`
  y `schema_permisos_desbloquear.sql`.

Con esto el Módulo Seguridad queda completo. Los próximos módulos a programar
son los funcionales grandes: Agendamiento, Consultorio, Facturación — ya
documentados en el análisis de la tesis.

## Estado real del Módulo Agendamiento (actualizado)
Análisis confirmado con el profesor (4 movimientos balanceados, sin tabla
Persona genérica — siempre Medico/Funcionario/Paciente separados):
- Registrar Agenda Médica
- Gestionar Cita
- Gestionar Avisos y Recordatorios
- Registrar Historial Médico del Paciente

Programación: los 4 movimientos ya estaban programados (routes + DAO), pero
3 de los 4 (Agenda, Cita, Avisos) usaban DELETE físico en el ANULAR, en
contra de lo definido en el análisis (el flujo de "borrado físico" fue
eliminado explícitamente del CUS). Ya corregido:
- ✅ AgendaCabeceraDao / AgendaDetalleDao: ANULAR = baja lógica
  (`estado` / `estado_detalle`). Anular una cabecera cancela en cascada sus
  detalles. Anular un detalle con citas activas asociadas está BLOQUEADO
  (no se puede anular un horario con citas Reservado/Confirmado encima).
- ✅ CitaDao: ANULAR = baja lógica (`estado` en cabecera, `id_estado_cita`
  = 'Cancelado' en detalle). Anular una cita cabecera cancela sus detalles
  en cascada, devolviendo cupo en agenda_detalle si correspondía.
- ✅ AvisosRecordatorioDao: ANULAR = baja lógica (columna `estado` nueva,
  agregada vía ALTER TABLE — no existía antes).
- ✅ HistorialDao: ya estaba correcto desde el principio (baja lógica).
- ✅ Listados: todos los `getX()` ocultan por defecto lo anulado/cancelado
  (mismo criterio que Mantener Usuario).
- ✅ Los UNIQUE constraints de `agenda_cabecera` (medico+fecha) y
  `agenda_detalle` (cabecera+disponibilidad) se convirtieron en índices
  únicos PARCIALES (`WHERE estado <> 'Inactivo'`), para poder reutilizar
  médico+fecha u horario después de anular el registro anterior.
- Probado en navegador de punta a punta por Ara: cascadas, bloqueo de
  horario con citas activas, liberación de cupo, y reutilización de
  médico+fecha tras anular — todo confirmado funcionando.
- Sin restricción de rol todavía (mismo pendiente general documentado
  arriba para los módulos grandes).
- ⏳ Pendiente (no prioritario): el botón sigue diciendo "Eliminar" en la
  interfaz aunque ahora hace baja lógica, no DELETE físico. Cambiar el
  texto a "Anular" queda para la pasada de diseño visual final.
- ⏳ Pendiente: revisar las pantallas de Referenciales de Agendamiento
  (Especialidad, Dias_laborales, Turnos_laborales, Estado, Estado_cita,
  etc.) — programadas pero todavía no auditadas contra el análisis.

## Estado real de las Referenciales de Agendamiento (auditado y cerrado)
- Especialidad, Dia, Turno, Cargo, Consultorio, Disponibilidad Horaria:
  quedan con DELETE físico (decisión: son catálogos base, no necesitan
  historial). Cada deleteX() ahora valida uso antes de borrar (estaEnUso())
  y devuelve 409 con mensaje claro en vez de un error genérico/engañoso.
  ⚠️ **La decisión de DELETE físico quedó SUPERADA por el "Estándar de referenciales"**
  (más abajo): al migrar estas pantallas a Tabler pasan a borrado lógico. Mientras no se
  migren, siguen como están (ver "Pendientes de referenciales").
- "Mantener Estado de Cita" (estado_cita) NO es una referencial real —
  nunca debió tener pantalla propia: es un catálogo de valores fijos del
  negocio (Reservado, Confirmado, Realizado, Cancelado, No Asistió,
  Reprogramado), igual que `roles` en Seguridad. La pantalla rota
  (EstadoCitaDao, routes, API, template, sidebar, entrada en
  menu_catalog.py) fue eliminada por completo. La tabla `estado_cita` en sí
  y su uso correcto en `CitaDao.getEstadosCita()` NO se tocaron.
- 4 FKs corregidas de SET NULL/CASCADE a RESTRICT, para que ningún DELETE
  pueda perder datos en silencio: `medico.id_especialidad`,
  `avisos_recordatorios.codigo` (consultorio), `avisos_recordatorios.id_paciente`,
  `avisos_recordatorios.id_funcionario`.
- Se eliminó además un DAO duplicado sin uso
  (`app/dao/referenciales/disponibilidad_horaria/`).

Con esto, el **Módulo Agendamiento queda completo**: los 4 movimientos con
baja lógica correcta, y las 6 referenciales con DELETE físico protegido.
Próximo módulo grande: Consultorio.

## Estado real del Módulo Consultorio (actualizado — COMPLETO)

Análisis confirmado (10 movimientos + 8 referenciales documentados con el
profesor). Decisión clave resuelta: **Registrar Consulta parte de una Cita
ya reservada en Agendamiento** (estado "Confirmado"), no es un registro
independiente.

### Registrar Consulta — reconstruido para partir de la Cita
- `agenda_cabecera.id_consultorio` (NOT NULL, FK a `consultorio`, RESTRICT):
  el Consultorio ahora se asigna al crear la Agenda del médico, para poder
  heredarse automáticamente en toda la cadena Agenda→Cita→Consulta (esto
  resolvió un hueco del análisis: el CUS asumía que Consultorio se precargaba
  solo, pero nunca se había definido dónde se capturaba por primera vez).
- `consultas_cab.id_cita`: NOT NULL, FK a `cita_detalle.id_cita_detalle`,
  UNIQUE (una cita = una sola consulta).
- Al guardar una Consulta: el backend valida que la cita exista, esté
  "Confirmado", y no tenga consulta previa — todo en una transacción. Paciente
  /Médico/Consultorio/Fecha/Hora se derivan de la cita (el backend nunca
  confía en lo que mande el formulario para esos campos, evita falsificación).
  Al guardar, la cita pasa a "Realizado" automáticamente.
- Campos editables en la Consulta una vez vinculada a la Cita: Fecha y Hora
  son de solo lectura; Duración y Estado (el estado propio de la Consulta:
  programada/en proceso/finalizada — NO el estado de la Cita) sí son editables.
- ANULAR (baja lógica) bloquea con "EN_USO" si la consulta ya tiene Ficha
  Médica, Diagnóstico o Tratamiento asociado.
- Pendiente marcado, no resuelto: `PacienteDao.deletePaciente` es DELETE
  físico y `cita_cabecera.id_paciente` es CASCADE — borrar un paciente con
  citas confirmadas perdería ese historial en cascada. No se tocó (pertenece
  a entidades de Agendamiento ya cerrado), queda anotado para cuando se
  revise Paciente/Médico a fondo.

### Otros hallazgos ya resueltos
- Ficha Médica: **no había duplicación real** — el modal embebido en
  Consulta (carga clínica de 1 ficha) y la pantalla standalone
  `ficha-medica-index` (listado/auditoría transversal con estadísticas) son
  dos usos legítimos y distintos del mismo DAO. No se tocó nada.
- Renombrado interno: la carpeta que servía `TipoDiagnosticoDao` tenía
  nombres internos (blueprint, endpoint, template) que decían literalmente
  "diagnostico", chocando con el módulo real de Diagnósticos Médicos. Se
  renombró todo a `tipodiagnostico`/`tipo-diagnostico-index` — cero cambio
  de comportamiento, solo claridad. La URL del API JSON
  (`/api/v1/diagnosticos...`) NO se tocó a propósito, porque también la
  consume la pantalla de Diagnósticos Médicos.
- `Sintoma` y `TipoDiagnostico`: quedan con DELETE físico (catálogos base),
  pero ahora validan uso antes de borrar (`estaEnUso()` → 409 "EN_USO"),
  mismo patrón que Agendamiento. Se agregó además una FK real
  `consultas_detalle.id_sintoma → sintoma(id_sintoma) ON DELETE RESTRICT`
  (antes solo protegido a nivel de aplicación).

### Odontograma — corregido (3 problemas)
- Estaba mal ubicado en `modulo_agendamiento/` — movido a
  `modulo_consultorio/odontograma/` (solo la carpeta física; blueprint,
  endpoint y prefijo de URL quedaron iguales a propósito, para no romper un
  botón "Ver Odontograma" con URL hardcodeada en
  `diagnosticos-medicos-index.html`).
- ANULAR era DELETE físico pese a que ya existía `cambiarEstadoOdontograma()`
  (baja lógica, con columna `estado` y CHECK Activo/Finalizado/Inactivo) sin
  usar. Corregido para usar baja lógica, y se agregó el filtro
  `estado <> 'Inactivo'` en los listados (si no, la baja lógica se vería
  como que "Eliminar" no hace nada).
- Bug real corregido: `getOdontogramasByPaciente()` usaba una columna
  inexistente (`p.ci` en vez de `p.cedula_entidad`) — tiraba error de SQL en
  cualquier llamada real a `GET /api/v1/odontogramas/paciente/<id>`.
- Pendiente igual que Consulta: `odontograma.id_paciente` es CASCADE, mismo
  riesgo latente que `cita_cabecera.id_paciente` (no resuelto, anotado).

### Las 6 referenciales de Consultorio — todas programadas y probadas
Tipo Tratamiento, Tipo Insumo Utilizado, Tipo Procedimiento Médico,
Medicamentos, Tipo Estudio, Tipo Análisis. Todas usan **baja lógica**
(`activo`), a diferencia de las referenciales de Agendamiento — decisión
confirmada en cada CUS original, no es inconsistencia.

**Tipo Tratamiento: precio (rama `consultorio`).** `tipos_tratamiento.precio NUMERIC(12,0) NOT NULL` con
`CHECK (precio > 0)` (guaraníes, sin decimales; lo usa la Venta de Tratamiento de Facturación). Migración idempotente:
`app/dao/referenciales_consultorio/tipo_tratamiento/schema_tipo_tratamiento_precio.sql` (columna nullable → datos →
NOT NULL y CHECK; si quedara una fila sin precio corta con un mensaje que la nombra). Datos iniciales: 11 tratamientos
odontológicos (LIMPIEZA DENTAL (PROFILAXIS) … IMPLANTE DENTAL).
- **`PRUEBA` (registro de prueba) se anuló por la migración y quedó con precio 1**, aunque tiene 2 tratamientos asociados
  (7 y 9). Es una excepción deliberada: la baja desde la pantalla lo habría bloqueado por estar en uso. Los
  tratamientos siguen listándose (sus `JOIN` no filtran por `activo`); el tipo ya no aparece en el combo de altas.
- API: `precio` obligatorio en POST/PUT con `validar_precio` (compartido con Ítems, `app/rutas/modulo_facturacion/utils.py`)
  y **un único mensaje** para cualquier precio inválido: "El precio debe ser un número entero mayor a 0." (`campo: precio`).
  La vista (todavía SB Admin 2) valida con `FacturacionValidadores.precio` (el mismo JS compartido) y muestra el precio como
  "Gs. 200.000". Esta API sigue normalizando con `strip().upper()` (no colapsa espacios internos, a diferencia de Facturación).
- **IVA (rama `consultorio`)**, igual que en `items`: `tipos_tratamiento.iva SMALLINT NOT NULL DEFAULT 10` con
  `CHECK (iva IN (0, 5, 10))` (0 = exenta). Migración idempotente aparte:
  `app/dao/referenciales_consultorio/tipo_tratamiento/schema_tipo_tratamiento_iva.sql` (los existentes, incluido
  `PRUEBA`, quedan en 10; el orden respecto de la migración de precio es indistinto; volver a correrla no pisa un IVA
  ya editado). La API exige `iva` en POST/PUT con `validar_iva` (compartido con Ítems; mensaje "El IVA debe ser Exenta
  (0), 5% o 10%.", `campo: iva`; el precio se valida primero). La vista tiene el combo IVA (10% por defecto, 5%,
  Exenta) y la columna IVA, y valida con `FacturacionValidadores.iva`.
- Los lectores de `tipos_tratamiento` (Gestionar Tratamientos y el combo de `tratamiento-index.html`) solo usan `id` y
  `descripcion`: no se ven afectados.

**Corrección importante aplicada después de programarlas:** el campo
`codigo` que pedían los CUS originales (Alta con Código + Descripción) fue
sacado por decisión posterior de Ara — **ya no existe** en ninguna de las 6.
Quedan solo con su ID interno autonumérico como identificador, igual que
las referenciales de Agendamiento (Especialidad/Cargo). La validación de
duplicados pasa a hacerse por `descripcion` (o `nombre_comercial` en el
caso de Medicamentos, que nunca tuvo campo Descripción). Se agregó también
un índice único parcial en `insumos.descripcion`, que antes no lo tenía
(solo `codigo` estaba protegido).

⚠️ **Pendiente, no de código:** los CUS documentados en el Word de la tesis
todavía dicen "el encargado de consultorio ingresa el Código y la
Descripción" — hay que corregir esos 6 documentos para que coincidan con
esta decisión, si no queda la misma inconsistencia análisis-vs-código que
venimos evitando, pero al revés.

Dependencias pendientes documentadas en cada DAO (`estaEnUso()` devuelve
`False` por ahora, sin fingir una validación imposible):
- Tipo Insumo Utilizado y Tipo Procedimiento Médico: dependen de
  `sesion_insumos`/`sesiones_tratamiento` (parte de "Gestionar Procedimientos
  e Insumos Utilizados", sin programar). Tipo Procedimiento Médico sí valida
  parcialmente hoy contra `consultas_detalle.id_tipo_procedimiento` (FK real
  ya conectada).
- Medicamentos: depende de `receta_medicamento` ("Generar Recetas e
  Indicaciones", sin programar).
- Tipo Estudio: depende de `orden_estudios` ("Generar Orden de Estudios",
  sin programar).
- Tipo Análisis: depende de `orden_analisis` ("Generar Orden de Análisis",
  sin programar).

### Movimientos grandes — estado real (actualizado)

**5 movimientos auditados y cerrados de punta a punta:** Registrar Consulta,
Gestionar Diagnóstico, Gestión Ficha Médica, Gestionar Odontograma,
Gestionar Tratamientos. Cada uno respeta ahora su CUS real (no lo que se
asumía por "parecido" a otro módulo):

- **Registrar Consulta**: reconstruido para partir de una Cita Confirmada
  (ver sección de arriba). Editable solo Duración/Estado una vez vinculada.
- **Gestionar Diagnóstico**: solo Ver/Anular (se sacó un botón "Modificar"
  que no correspondía a su CUS). Anular ahora es baja lógica real
  (`activo`, antes DELETE físico), con las 2 validaciones que pide el CUS
  (bloquea si tiene Tratamiento asociado, bloquea si la consulta está
  "finalizada"). Bug aparte corregido: `generarCodigo()` (DX-000N) contaba
  mal por año contra un código único global — corregido para no chocar.
- **Gestión Ficha Médica**: Ver/Editar/Anular (Editar SÍ es legítimo acá —
  corrige la misma ficha mientras la consulta sigue abierta, no crea una
  nueva; distinto criterio a Diagnóstico/Tratamiento a propósito). No tenía
  ningún botón Anular conectado — se agregó, con baja lógica real y bloqueo
  si la consulta está "finalizada".
- **Gestionar Odontograma**: Ver/Anular. Reubicado a `modulo_consultorio/`
  (estaba mal puesto en Agendamiento). Baja lógica real (antes DELETE
  físico pese a tener el mecanismo ya construido). Bug de columna
  inexistente (`p.ci`→`p.cedula_entidad`) corregido.
- **Gestionar Tratamientos**: Ver/Anular. Construido de cero ya alineado al
  CUS desde el arranque (parte de Consulta activa, vinculación opcional a
  Diagnóstico, hereda Paciente/Médico/Consultorio, estados
  `pendiente→en_seguimiento→finalizado`+`cancelado`).
- **Generar Recetas e Indicaciones**: Ver/Anular. Cuelga directo de
  Consulta (no de Tratamiento), con vinculación OPCIONAL a Diagnóstico
  y/o Tratamiento de esa misma consulta. Cabecera `recetas`
  (indicaciones_generales) + detalle `receta_medicamento` (dosis,
  frecuencia, duración por medicamento — mínimo 1). Anular bloqueado si
  la consulta está "finalizada" (sin regla de "solo la última", a
  diferencia de Sesiones). Con entrada propia en sidebar (mismo criterio
  que Tratamiento) + 4ª tarjeta de Acción Rápida en Consulta.
  Dependencia cruzada conectada: `MedicamentoDao.estaEnUso()` dejó de ser
  un stub que devolvía `False` fijo — ahora valida contra
  `receta_medicamento` de verdad.
- **Generar Orden de Estudios**: Ver/Anular. Cuelga directo de Consulta,
  vinculación OPCIONAL a Diagnóstico/Tratamiento (igual que Recetas).
  Tabla ÚNICA `orden_estudios` (un solo Tipo de Estudio por orden, sin
  cabecera+detalle) — **sin columna `activo`**, el propio `estado`
  (CHECK: pendiente/enviado/en_proceso/completado/cancelado) hace de baja
  lógica (`cancelado` = anulado). Dos acciones desde la misma pantalla:
  "Actualizar Estado" (avanza UN paso a la vez en la secuencia fija —
  el sistema calcula el siguiente estado, el usuario no elige a cuál
  saltar) y "Anular" (bloqueado si ya está completado/cancelado). Con
  entrada propia en sidebar + 5ª tarjeta de Acción Rápida en Consulta.
  Dependencia cruzada conectada: `TipoEstudioDao.estaEnUso()` valida
  contra `orden_estudios` con `estado <> 'cancelado'`.

**✅ MÓDULO CONSULTORIO COMPLETO — 10 movimientos + 8 referenciales,
todos auditados contra su CUS real y probados de punta a punta:**

Movimientos: Registrar Consulta, Gestionar Diagnóstico, Gestión Ficha
Médica, Gestionar Odontograma, Gestionar Tratamientos, Gestionar
Procedimientos e Insumos Utilizados, Generar Recetas e Indicaciones,
Generar Orden de Estudios, Generar Orden de Análisis, Generar
Justificativo Médico.

Referenciales: Tipo Tratamiento, Tipo Insumo Utilizado, Tipo
Procedimiento Médico, Medicamentos, Tipo Estudio, Tipo Análisis (todas
baja lógica), Especialidad/Día/Turno/Cargo/Consultorio/Disponibilidad
Horaria (de Agendamiento, DELETE físico — ver sección de Agendamiento).

- **Gestionar Procedimientos e Insumos Utilizados**: cuelga de un
  Tratamiento (sin entrada propia en sidebar, acceso siempre contextual).
  Tablas `sesiones_tratamiento`+`sesion_insumos`. `numero_sesion`
  correlativo con único parcial. Primera sesión pasa el tratamiento a
  `en_seguimiento`. Solo se puede anular la última sesión activa, con
  cascada a sus insumos. "Finalizar Tratamiento" vive acá (no en
  Gestionar Tratamientos).
- **Generar Recetas e Indicaciones**: cuelga de Consulta, vinculación
  opcional a Diagnóstico y/o Tratamiento. Cabecera `recetas` + detalle
  `receta_medicamento` (mínimo 1 medicamento). Con entrada propia en
  sidebar + tarjeta de Acción Rápida.
- **Generar Orden de Estudios / Generar Orden de Análisis**: idénticos
  estructuralmente entre sí (solo cambia el catálogo). Tabla única, sin
  `activo` — el propio `estado` (pendiente/enviado/en_proceso/completado/
  cancelado) hace de baja lógica. Dos acciones: "Actualizar Estado"
  (avanza UN paso, secuencial estricto — el sistema calcula el siguiente,
  no se puede saltar) y "Anular" (bloqueado si completado/cancelado).
- **Generar Justificativo Médico**: cuelga de Consulta, vinculación
  opcional SOLO a Diagnóstico (sin Tratamiento, a diferencia de
  Recetas/Órdenes). Campos: Días de Reposo (>0) + Recomendaciones.
  Estados simples `activo`/`anulado` (no la cadena de 4 pasos de las
  Órdenes). **Genera PDF al vuelo con ReportLab** (instalado, sin
  dependencias de sistema — funciona limpio en Windows), sin persistir
  archivo en el servidor — se regenera desde los datos de la BD cada vez.
  Un justificativo anulado sigue siendo descargable, pero con marca
  "ANULADO" visible en rojo (no se bloquea la descarga, sirve de
  respaldo/auditoría). Servicio en `app/Services/justificativo_pdf_service.py`
  — pensado para reutilizar el mismo patrón si en el futuro se agrega PDF
  a Recetas/Órdenes.

**Dependencias cruzadas conectadas a lo largo del módulo** (todos los
`estaEnUso()` que quedaban documentados como "pendiente, esperando a que
exista X" ya fueron conectados apenas esa tabla se construyó):
`TratamientoDao.deleteTratamiento()` bloquea si hay sesiones activas;
`TipoInsumoDao.estaEnUso()` (no existía — bug real, cualquier insumo se
podía anular en uso); `TipoProcedimientoMedicoDao.estaEnUso()` (sumó
`sesiones_tratamiento`); `MedicamentoDao.estaEnUso()` (contra
`receta_medicamento`); `TipoEstudioDao`/`TipoAnalisisDao.estaEnUso()`
(contra sus respectivas órdenes, con `estado <> 'cancelado'`). Bug de
seguridad aparte corregido: `tipo_insumo_api.py` chequeaba `if resultado:`
en vez de comparar contra `"EN_USO"` (permitía anular en uso sin
bloquear, por ser cualquier string "truthy" en Python).

**Mejora de UX aplicada a todo el módulo:** los mensajes de éxito/error
usan datos descriptivos reales (código, fecha+paciente, descripción,
etc.), nunca IDs crudos.

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


## Rediseño visual (en curso)
- Login y Verificación 2FA ya rediseñados (Tabler/Bootstrap 5, tarjeta centrada,
  panel azul marino con foto). Assets locales, sin CDN: app/static/vendor/tabler/,
  img/login-fondo.png, img/2fa-fondo.png, img/logo-diente.png,
  fonts/DancingScript.ttf.
- El resto del sistema sigue en SB Admin 2 (Bootstrap 4). NO mezclar ambos
  frameworks en una misma página.
- **"¿Olvidaste tu contraseña?" SÍ existe**: la recuperación de contraseña está implementada (ver
  "Endurecimiento de acceso"; `/recuperar` → `/recuperar/codigo` → `/recuperar/nueva`, con enlace en el login).
- **"Reenviar código" NO existe** (verificado en el código): ni el 2FA del login (`/verificar-2fa` solo valida el
  código) ni la recuperación tienen endpoint o botón de reenvío. Para recibir un código nuevo en el login hay
  que volver a iniciar sesión (así lo dice el mensaje de código expirado); en la recuperación se repite el paso 1
  (`/recuperar`), con un mínimo de 60 s entre envíos. No agregar un botón "Reenviar código" en la interfaz sin
  crear antes el endpoint en el backend.

- **Toda vista nueva extiende `base_tabler.html`; las vistas viejas se migran al final.**
  Las vistas nuevas usan Bootstrap 5/Tabler, fetch + JS vanilla (sin jQuery) y SweetAlert2.
  Patrón de referencia: `app/rutas/modulo_facturacion/forma_cobro/`.

**Próximo módulo grande: Facturación** — en curso (ver sección "Módulo Facturación").

## CI/RUC y correo: una sola fuente de verdad (rama datos-unica-fuente)
- **El CI/RUC de login y el correo de un usuario NO se guardan en `usuarios`:** se leen
  siempre de la persona vinculada (`COALESCE(f.cedula, m.cedula)` y
  `COALESCE(f.correo, m.correo)`, ver `SQL_CI_RUC`/`SQL_CORREO` en `UsuarioDao`). Login,
  2FA, alertas, recuperación, sesión, tablero y Gestión de Usuarios usan eso. Los dicts
  de `UsuarioDao` siguen exponiendo las claves `ci_ruc` y `correo`.
- **Alta/edición de usuario:** ya no reciben `ci_ruc` ni `correo`. La persona tiene que
  tener cédula y correo cargados para vincularla (`_validar_datos_persona`); al editar
  solo se exige si se cambia de persona. En la grilla y el formulario son de solo lectura
  ("se edita en Funcionario/Médico"). Persona sin correo ⇒ el login muestra error claro.
- **Unicidad de la cédula** (es el login): `funcionario.cedula` y `medico.cedula` tienen
  UNIQUE (`medico_cedula_key` agregado), y entre ambas tablas se valida en código al
  guardar y editar (`cedulaUsadaPorOtro` en `FuncionarioDao`/`MedicoDao`, 409).
- **Cambiar la cédula de una persona con usuario cambia su login:** el PUT responde 409
  con `requiere_confirmacion` (cédula anterior/nueva); el front pide confirmar y reenvía
  con `confirmar_cambio_cedula`. El cambio se audita (`accion = 'CAMBIO_CEDULA'`,
  `ci_ruc_ingresado` = cédula nueva, `resultado` = `ANTES: <anterior>`, actor = quien editó).
- `seed_admin_usuario.py` ya no recibe `--ci-ruc` ni `--correo`: los toma de la persona.
- `auditoria_acceso.ci_ruc_ingresado` es historial de lo tipeado: no se toca.
- **Las columnas `usuarios.ci_ruc` y `usuarios.correo` YA NO EXISTEN** (etapa 2, ✅
  aplicada y probada). Scripts idempotentes: `schema_datos_unica_fuente.sql` (UNIQUE en
  `medico.cedula`; relajaba las columnas, ahora no-op si ya no están) y
  `schema_datos_unica_fuente_etapa2.sql` (`DROP COLUMN IF EXISTS`, sin CASCADE a propósito).
  `schema_seguridad.sql` ya crea `usuarios` sin ellas. Cualquier consulta nueva que
  necesite CI o correo de un usuario debe hacer LEFT JOIN a funcionario/medico y usar
  `SQL_CI_RUC`/`SQL_CORREO` de `UsuarioDao`; nunca `u.ci_ruc`/`u.correo`.
- Si el correo de una persona con usuario cambia, cambia el destino del 2FA (no hay aviso).

## Control de acceso
Ver la sección **"Modelo de permisos"** (más abajo): reemplaza al antiguo control
por rol con `@require_admin` y a la nota de "pendiente de decidir" sobre los
módulos grandes, que ya quedó resuelta.

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
6. **Auditoría en `auditoria_cambios`** vía `AuditoriaCambiosDao`/`utils.auditar`: `ALTA`, `MODIFICACION`, `BAJA`
   y `REACTIVACION` (y `CIERRE` para los movimientos que se cierran: Apertura y Cierre de Caja), con `id_usuario`
   de la sesión e `ip` del request (nunca del cliente). El detalle muestra
   NOMBRES (no IDs) y solo lo que cambió; una edición sin cambios no audita.

Además, como en todo endpoint: `@require_permiso(ventana, acción)`, botones envueltos en `puede(...)`, entrada en
`menu_catalog.py` y seed de permisos idempotente (ver "Modelo de permisos").

### Estado actual de los referenciales frente al estándar (verificado en el código y en la base)
| Módulo | Referencial | Borrado hoy | Vista | Falta |
|---|---|---|---|---|
| Facturación | Forma de Cobro, Marca de Tarjeta, Entidad Emisora, Entidad Adherida, Tipo Ítems, Ítems | **Lógico** | Tabler (con `facturacion-listado.js`) | — (cumplen los 6 puntos) |
| Facturación | Caja, Depósito, Cliente | **Lógico** | Tabler (con su propia copia del código de listado) | — (cumplen los 6 puntos); falta migrarlas al helper y unificar `?inactivas` de Caja |
| Consultorio | Tipo Tratamiento, Tipo Insumo Utilizado, Tipo Procedimiento Médico, Medicamentos, Tipo Estudio, Tipo Análisis | **Lógico** (`activo`, con único parcial) | SB Admin 2 | Vista Tabler, puntos 4 y 6 |
| Consultorio | Tipo Diagnóstico, Síntomas | **Físico** (con `estaEnUso()` → 409) | SB Admin 2 | Pasar a lógico (agregar `activo`, único parcial) y puntos 1, 4 y 6 |
| Agendamiento | Ciudad, Cargo, Consultorio, Disponibilidad Horaria, Especialidad, Día, Turno | **Físico** (con `estaEnUso()` → 409) | SB Admin 2 | Pasar a lógico (agregar `activo`, únicos parciales) y puntos 1, 4 y 6 |
| Agendamiento | Paciente, Funcionario, Médico (datos maestros, no referenciales) | **Físico** (sin validar uso, salvo Paciente→cliente) | SB Admin 2 | Fuera de este estándar; ver riesgos de CASCADE más arriba |

## Pendientes de referenciales (en este orden)
1. **Facturación — migrar Caja, Depósito y Cliente a `facturacion-listado.js`** (hoy cada una tiene su propia copia de
   `pedir`, `escapar`, el badge, los botones y los flujos de SweetAlert2) y **unificar el parámetro de Caja de
   `?inactivas` a `?inactivos`** (el del estándar, que ya usan Depósito, Cliente y los otros 6). Verificado en el
   código: ninguna otra pantalla usa `?inactivas`, solo la propia vista y API de Caja; aun así, al unificar, hacer que
   la API de Caja acepte los dos nombres durante la transición y quitar `inactivas` cuando se confirme que nada lo usa
   (el DAO de Caja también usa `incluir_inactivas`; renombrar a `incluir_inactivos`). Esas 3 vistas ya se probaron
   a mano en el navegador: volver a probarlas después de migrarlas.
   *(El punto 4 del estándar —Estado, "Mostrar inactivos", Reactivar— ya está aplicado a Forma de Cobro, Marca de
   Tarjeta, Entidad Emisora, Entidad Adherida, Tipo Ítems e Ítems: ver "Módulo Facturación".)*
2. **Consultorio — al migrar a Tabler, aplicar el estándar completo** a los 8 referenciales (vista Tabler,
   puntos 4 y 6; Tipo Diagnóstico y Síntomas además pasan de borrado físico a lógico). Los otros 6 ya tienen
   `activo` e índices únicos parciales y bloquean la baja en uso.
3. **Agendamiento — al migrar a Tabler, pasar de borrado físico a lógico y aplicar el estándar completo** a los
   7 referenciales: agregar `activo`, convertir sus `UNIQUE` en índices únicos parciales (y actualizar las
   `estaEnUso()`/JOIN que los consultan, ver regla 4 de las "Reglas generales aprendidas"), vista Tabler,
   puntos 4 y 6. Ojo con `consultorio`: lo referencian `caja` (FK física), agenda, consultas, tratamientos y avisos;
   hoy "consultorio activo" = "consultorio existente" y las cajas lo usan así.
4. ✅ **HECHO — `precio NUMERIC(12,0)` e `iva` en `tipos_tratamiento`** (rama `consultorio`; ver "Tipo Tratamiento:
   precio" más arriba). Queda para la Venta de Tratamiento: guardar el precio y el IVA vigentes en la venta (hoy los
   tratamientos no copian el precio ni el IVA del tipo; si cambian, cambian para todos).
5. **Facturación — nuevo referencial "Mantener Timbrado"** (*pendiente de definir en el análisis*): no programarlo
   hasta tener el CUS (campos, validaciones y reglas de uso). Cuando se programe, cumple el estándar completo.
6. **Facturación — movimientos**: ✅ Registrar Apertura y Cierre de Caja (ver "Movimientos de Facturación");
   el resto de los movimientos (sin empezar) se programa después de los puntos anteriores.

## Módulo Facturación (en curso)
- ✅ **Forma de Cobro** (primer referencial, define el patrón visual de los otros 7):
  tabla `forma_cobro` (sin código, baja lógica `activo`, índice único parcial sobre
  `UPPER(descripcion) WHERE activo`), descripción en MAYÚSCULAS. `esta_en_uso()` es un
  stub que devuelve `False` (TODO: consultar `cobro_cabecera` cuando exista).
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
  `esta_en_uso()` es stub: TODO consultar `cobro_tarjeta`). Helpers compartidos de las APIs
  de Facturación (`normalizar_descripcion`, `auditar`, `error_interno`) en
  `app/rutas/modulo_facturacion/utils.py`.
- ✅ **Entidad Emisora** (banco; `entidad_emisora`, ventana `entidademisora`) y
  **Entidad Adherida** (`entidad_adherida`, ventana `entidadadherida`: procesadora con
  convenio con un banco para una marca, FK RESTRICT a emisora y marca; único parcial sobre
  `(UPPER(descripcion), emisora, marca)`). Ambas con dirección, teléfono y correo obligatorios.
  Datos iniciales de contacto: ficticios, de ejemplo.
  - **Bloqueo de baja:** no se puede anular una emisora ni una marca con una adherida activa
    (409 con mensaje específico). TODOs: `cobro_tarjeta` / `cobro_cheque`.
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
    "Controla stock" (409; evita ítems con stock bajo un tipo que no lo controla). TODO de
    `esta_en_uso` en Ítems: consultar `pedido_venta_det` y `venta_det` cuando existan.
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
    asignados."). TODO: consultar `nota_remision`.
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
  - `esta_en_uso()` es stub: TODO bloquear si hay pedidos o ventas (`pedido_venta_cab`, `venta_cab`).
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
    `("EN_USO", motivo)`, con la verificación y el UPDATE en una transacción (el TODO de `cobro_cabecera` quedó con su mensaje).
  - Las 6 vistas usan `facturacion-listado.js`. Verificadas con un navegador real (Edge headless, `fetch` simulado):
    switch, filas, badges, botón Reactivar, diálogos de SweetAlert2, PATCH/DELETE, recarga y los modales Agregar/Editar.

### Movimientos de Facturación
Menú: **"Módulo Facturación"** (separado de "Referenciales Facturación"). Vista en `base_tabler.html`, permisos y
auditoría como siempre. Las URL siguen la convención del proyecto (`/referenciales/<modulo>`, API en `/api/v1`).

- ✅ **Registrar Apertura y Cierre de Caja** (`apertura_cierre_caja`, ventana `aperturacaja`, acciones `ver`, `nuevo` =
  abrir, `anular`, `estado` = cerrar). Script: `app/dao/modulo_facturacion/schema_apertura_cierre_caja.sql` (+
  `schema_permisos_apertura_caja.sql`). **Solo el rol Cajero recibe los permisos** por el seed (son movimientos de
  dinero; el Administrador pasa siempre; Recepción/Médico se habilitan desde la matriz si hace falta).
  - Estados `ABIERTA → CERRADA | ANULADA` (finales). Índices únicos parciales `WHERE estado = 'ABIERTA'` por cajero
    y por caja: un cajero, una apertura; una caja no se abre dos veces. Mensajes: "Debe cerrar la apertura actual antes
    de abrir una nueva." y "La caja ya está abierta por otro usuario." (la verificación previa da el mensaje; los
    índices son la red de seguridad).
  - **El cajero (`id_usuario`) sale SIEMPRE de la sesión**, nunca del cuerpo del pedido. El Administrador ve todas las
    aperturas; los demás solo las propias (filtro en el servidor). Filtros `?estado=&desde=&hasta=` (hasta inclusivo).
  - **Anular** y **cerrar**: solo la apertura propia o cualquiera si es Administrador, y solo si está `ABIERTA`.
    Anular se bloquea si el turno tiene movimientos (**TODO** `_motivo_con_movimientos`: consultar `cobro_cabecera` /
    `venta_cab` cuando existan). **Cerrar**: `monto_cierre = monto_apertura + total_recaudado`, calculado por el servidor
    (el cliente no manda importes); `GET /aperturas-caja/<id>/cierre` da el detalle previo a confirmar.
    **TODO** `_total_recaudado`: hoy 0; sumar los cobros del turno en `cobro_cabecera` cuando exista.
  - Auditoría: apertura = `ALTA`, anulación = `BAJA`, cierre = **`CIERRE`** (se amplió el CHECK de `auditoria_cambios`).
  - Validador nuevo `validar_monto` (entero **≥ 0**, a diferencia de `validar_precio`) con su espejo `V.monto`; la API
    usa un único mensaje: "El monto de apertura debe ser un número entero mayor o igual a 0."
  - Bloqueo cruzado: no se puede dar de baja una caja con apertura `ABIERTA` (ver Caja).
  - Test: `tests/facturacion/smoke_apertura_caja.py` (usa usuarios REALES con sesiones simuladas y **aborta si alguno
    de ellos tiene una caja abierta de verdad**: cerrarla antes de correrlo).

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
- `browser_test.py` ejecuta las vistas en Edge headless con `fetch` simulado (necesita Edge; la ruta está en la
  constante `EDGE`). No reemplaza probar el guardado real en el navegador (regla 7 de "Reglas generales aprendidas").

## Convenciones de código
- SQL crudo con psycopg2, sin ORM.
- Conexión vía `app/conexion/Conexion.py` — reusar esa clase, no crear una nueva.
- Cada DAO abre su propia conexión y la cierra en un `finally`.
- Los blueprints de rutas se registran en `app/__init__.py` bajo `/referenciales/<modulo>`
  o bajo `/api/v1`.
- Seguir el mismo estilo/nombres que los módulos ya existentes (ej. `CiudadDao.py`,
  `ciudad_api.py`, `ciudad_routes.py`) para cualquier módulo nuevo.

## Modelo de permisos
- **Permiso = rol + ventana + acción.** Acciones: `ver`, `nuevo`, `editar`, `anular`,
  `estado`. Tabla `permisos` (FK a `roles`, único por rol+ventana+acción, CHECK de
  acción). Administrador no necesita filas: siempre pasa (bypass en `puede()`).
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
- **Roles y Permisos** (la matriz) queda con `@require_admin` fijo y fuera del
  catálogo, para que nadie pueda autoconcederse acceso.
- **Páginas de error propias 403/404/500** (`app/rutas/errores.py`, plantillas en
  `app/templates/errores/`): si la ruta empieza con `/api/` responden JSON; si es
  una vista, HTML. Con sesión extienden `base.html` (sidebar); sin sesión usan un
  layout standalone (SB Admin 2). `require_permiso`/`require_admin` hacen
  `abort(403)` en las vistas (ya no redirigen con flash); el 403 muestra qué ventana
  se intentó abrir cuando `require_permiso` la conoce.
- **Pendiente (limpieza al final):** carpetas duplicadas sin uso
  `app/rutas/referenciales/consultorio/` y `app/rutas/referenciales/avisosRecordatorios/`
  (el sistema usa las de `modulo_agendamiento/`).

## Cómo trabajar conmigo en este proyecto
- Antes de tocar código existente, mostrame el plan de archivos que vas a crear/modificar.
- Si una decisión de diseño no está clara en este documento, preguntame antes de asumir.
- Priorizá consistencia con el patrón de capas por sobre "mejores prácticas" genéricas
  que rompan la estructura ya usada en el resto del proyecto.
