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
- **La validación de IP por país YA NO está descartada**: se implementó en la Etapa A de la tanda de cierre
  (ver "Seguridad de acceso" más abajo).
- El menú del sistema debe tener un buscador general (CUS "Mantener Menú").

## Estado real del Módulo Seguridad (actualizado — COMPLETO)
- ✅ Login + 2FA por correo: terminado y probado end-to-end.
- ✅ Mantener Usuario (alta, edición, baja lógica, reactivar): terminado y probado.
- ✅ Tablero de Administrador (ver auditoria_acceso en pantalla): terminado y probado. Etapa C: migrado a Tabler, con exportación y enlace a Auditoría de Cambios.
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
2. ✅ **HECHO — Consultorio**: los 8 referenciales cumplen el estándar completo (etapa 1: 6 con baja lógica; etapa 2: Tipo Diagnóstico y Síntomas, que pasaron
   de borrado físico a lógico).
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
6. **Facturación — movimientos**: ✅ Registrar Apertura y Cierre de Caja y ✅ Registrar Pedido Cliente y ✅ Registrar Ventas (etapas 1 y 2) y ✅ Registrar Cobranzas y ✅ Registrar Nota de Remisión y ✅ Registrar Notas de Crédito y Débito y ✅ Mantener Cuenta Bancaria + ✅ Registrar Arqueo de Caja (ver
   "Movimientos de Facturación");
   el resto de los movimientos (sin empezar) se programa después de los puntos anteriores.

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

## Migración 02 (aplicada, rama `migracion-02`)
Script: `migraciones/02_migracion_requiere_codigo.sql` (idempotente, una transacción, se corre con postgres después del
backup; el original sin cambios queda en `02_migracion_requiere_codigo.original.sql`). Probada primero sobre una copia
restaurada del backup (dos corridas), y recién después aplicada a `odontosisbd`. El código se ajustó en el mismo cambio.
- **`diagnosticos`**: `id_consulta_detalle` → **`id_consulta_cab`** (NOT NULL, FK RESTRICT); se quitó `sintomas` (texto libre).
  Los síntomas se guardan en **`diagnostico_sintoma`** (selección múltiple desde el referencial Síntomas, opcional): alta
  transaccional, `GET` devuelve `sintomas: [{id_sintoma, descripcion_sintoma}]`. Paciente y médico **se derivan de la consulta**
  (el body se ignora); la consulta tiene que estar activa y no finalizada. El diagnóstico se registra solo desde Registrar
  Consulta (la pantalla exige `?consulta=`). `SintomaDao.estaEnUso` ahora también mira `diagnostico_sintoma`. Los DAO de
  Receta, Órdenes, Justificativo, Tratamiento y Consulta validan el diagnóstico por `diagnosticos.id_consulta_cab` (antes por
  `consultas_detalle`, que estaba vacía: hoy esos cruces andaban en falso).
- **`odontograma`**: `id_funcionario` → **`id_consulta_cab`** (NOT NULL, FK RESTRICT). **Uno por consulta**: índice único
  parcial `ux_odontograma_consulta_vigente (id_consulta_cab) WHERE estado <> 'Inactivo'` (la tabla no tiene `activo`: su baja
  lógica es `estado = 'Inactivo'`). Paciente y médico salen de la consulta. El **vigente del paciente es el de su última
  consulta** (`getOdontogramaVigentePaciente`); al crear uno nuevo la pantalla lo **precarga** con ese estado
  (`GET /api/v1/odontogramas/precarga/<id_consulta>`). Entrada desde Registrar Consulta: tarjeta "Odontograma"
  (`odontograma-index?consulta=<id>`). `GET /odontogramas/validar-paciente` pasó a `validar-consulta/<id>`.
- **`consultas_cab.id_funcionario` obligatorio**: sale SIEMPRE de la sesión (`id_funcionario_sesion()` en
  `permisos_contexto.py`); si el usuario no es funcionario (p. ej. un Médico) → 403 "Solo un funcionario puede registrar
  consultas." La consulta la registra Recepción desde la cita; el médico es un dato de la consulta.
- **`estado_dental.estado` → `activo`** (NOT NULL DEFAULT true; el JSON de `/estados-dentales` ahora trae `activo`).
- **`permisos`**: sin `ventana`; ver "Modelo de permisos".
- **Datos migrados:** consultas 6 y 17 → funcionario 3; los diagnósticos 2 y 10 y los odontogramas 8 y 9 (datos de prueba sin
  consulta del mismo médico) se **borraron con sus dependientes** (5 detalles de odontograma). `permisos` conserva sus 339 filas.
- `odontoclinic_app` conserva todos sus privilegios (verificado: SELECT/INSERT/UPDATE/DELETE en las tablas tocadas y en
  `diagnostico_sintoma`). La auditoría y `trg_auditoria_inmutable` no se tocaron.
- Test: `tests/consultorio/smoke_migracion02.py` (esquema, `PermisoDao`, Administrador/Cajero y URL directa, consulta con/sin
  funcionario, diagnóstico con síntomas, odontograma único por consulta con precarga, consulta finalizada).
- ⚠️ **Falta reflejar en el DER:** `diagnosticos` (+`id_consulta_cab`, −`id_consulta_detalle`, −`sintomas`; usa `diagnostico_sintoma`),
  `odontograma` (+`id_consulta_cab`, −`id_funcionario`, único por consulta), `consultas_cab.id_funcionario` NOT NULL,
  `estado_dental.estado` → `activo`, `permisos` sin `ventana` (identificada por `id_menu`). Y el análisis (CUS): Registrar
  Consulta/Diagnóstico/Odontograma deben decir que el funcionario es la sesión, que el odontograma es uno por consulta con
  precarga del anterior y que los síntomas del diagnóstico son una selección múltiple.
- **Odontograma: igualarlo al estándar en la migración de Consultorio a Tabler.** Hoy NO tiene columna `activo`: su baja lógica es
  `estado = 'Inactivo'` (CHECK Activo/Finalizado/Inactivo) y el único parcial es `ux_odontograma_consulta_vigente ... WHERE
  estado <> 'Inactivo'`. Al migrarlo hay que agregar `activo BOOLEAN NOT NULL DEFAULT true` e índice único parcial
  `WHERE activo = true` (conservando `estado` para Activo/Finalizado), y actualizar los filtros `estado <> 'Inactivo'` de
  `OdontogramaDao` (listados, `existeOdontogramaConsulta`, `getOdontogramaVigentePaciente`, alta) y el test `smoke_migracion02`.
- **Pendientes de Consultorio para la migración a Tabler** (relevados contra la base, no tienen script en el repo):
  la base YA tiene `tratamientos.id_paciente` (sin espacio), `'cancelado'` en el CHECK de `tratamientos.estado`,
  `sesiones_tratamiento.activo`, `sesion_insumos` con FK a `sesiones_tratamiento` (`tratamiento_insumos` ya no existe) y las
  tablas `tipo_procedimiento_medico` y `medicamentos`. Lo que SIGUE sin hacer: **versionar el `CREATE TABLE`** de
  `tipo_procedimiento_medico` y `medicamentos` (no hay ningún `CREATE TABLE` de Consultorio en el repo: ni de esas ni de
  `sesiones_tratamiento`/`sesion_insumos`/`tratamientos`) y dejar un script idempotente que reproduzca esas correcciones en una
  base nueva. Se hace junto con la migración de Consultorio a Tabler.

## Migración de Consultorio a Tabler (en curso, rama `consultorio-tabler`)
Plan completo en `plan_consultorio.md` (sin versionar). Etapas 0 a 7, un commit por etapa. **Decisiones de negocio confirmadas:**
- **PDF** de Receta, Orden de Estudios y Orden de Análisis (estilo factura/Justificativo).
- **Auditoría de Consultorio sin contenido clínico:** solo quién, cuándo, paciente, N.º de documento y cambios de estado (nunca diagnósticos,
  síntomas, indicaciones, medicamentos, observaciones). Los referenciales sí auditan su descripción.
- **Anulación definitiva** en todos los movimientos de Consultorio; solo los referenciales se reactivan.
- **Odontograma: solo Activo y Anulado** (sin "Finalizado"); lo que impide modificarlo es que la consulta esté finalizada.
- **Movimientos clínicos** (Ficha, Diagnóstico, Odontograma, Tratamiento, Sesiones, Receta, Órdenes, Justificativo): rol Médico/Odontólogo, consulta
  `programada` o `en_proceso` (se revalida al guardar), no se anulan con la consulta `finalizada`, paciente y médico heredados de la consulta.
  Diagnóstico: tipo, al menos un síntoma y descripción obligatorios, pieza dental FDI válida, no se anula con tratamiento asociado. Odontograma: sin
  repetir pieza + superficie + estado. Órdenes: avanzan de estado y no se cancelan si están Completadas o Canceladas.
- Registrar Consulta: la registra un funcionario desde una cita `Confirmado` sin consulta; bloquea si paciente, médico o consultorio están inactivos; no se
  anula con Ficha, Diagnóstico o Tratamiento.

### Etapa 0 (hecha): esquema versionado y andamiaje
- ⚠️ **Cambio del DER: se eliminó la tabla `consultas_detalle`** (vacía, sin FK entrantes ni objetos que dependieran; superada por Diagnóstico, Tratamiento y
  Sesiones; no figura en la Lista de Archivos de ningún CUS vigente). Se quitaron su DAO, su API (`/consultas-detalle`), las pestañas de detalle clínico de
  `consulta-index.html` y sus referencias en `estaEnUso()` de Síntomas, Tipo Diagnóstico y Tipo Procedimiento. Además `odontograma` suma `activo`
  (⚠️ DER) con único parcial `ux_odontograma_consulta_activo WHERE activo`; `estado` se retira en la etapa 4.
- Scripts en `app/dao/referenciales_consultorio/`: `schema_consultorio_base.sql` (las 23 tablas de Consultorio, generado de la base real, idempotente; es la
  fuente para reconstruir la base: depende de las tablas de Agendamiento/Seguridad, que todavía no están versionadas) y `schema_consultorio_etapa0.sql`
  (migración de una base existente, con verificación previa de `consultas_detalle`). Los 6 únicos parciales de los referenciales comparan con `UPPER()`.
- Auditoría: las 18 entidades de Consultorio están en `MODULO_POR_ENTIDAD`/`ETIQUETA_ENTIDAD` (módulos "Referenciales Consultorio" y "Módulo Consultorio";
  los 10 movimientos son `ENTIDADES_MOVIMIENTO`). `app/rutas/modulo_consultorio/utils.py` reexporta los helpers de Facturación.
- Test: `tests/consultorio/smoke_esquema_consultorio.py` (reconstruye las tablas en una base temporal y las compara con la real).
- **Corrección a la tabla de estado de referenciales de más arriba:** Tipo Diagnóstico y Síntomas YA tenían `activo` e índice único parcial en la base; solo
  sus DAO seguían con `DELETE` físico (resuelto en la etapa 2).
- ✅ **Resuelto en la etapa 3:** al anular una consulta la cita vuelve a `Confirmado` y `consultas_cab.id_cita` es UNIQUE parcial (`WHERE activo = true`); la anulación se audita.
- **Pendiente de la migración de Agendamiento (médicos):** al intentar eliminar un médico con historial, el mensaje dice *"No se encontró el médico con el ID 19 o
  no se pudo eliminar"*. Tiene que ser **baja lógica** (`medico.activo`) con un mensaje claro de que está en uso (consultas, agendas, citas, usuario vinculado), y
  `MedicoDao.deleteMedico` debe devolver `"EN_USO"` con el motivo y la API responder 409 (como Paciente→cliente y Consultorio→cajas).
- **Pendiente de la migración de Agendamiento:** generar el script base (`CREATE TABLE`) de Agendamiento y de Seguridad (paciente, medico, funcionario,
  consultorio, cita_*, agenda_*, usuarios, roles, permisos, menu, auditoría...) para que la base completa se pueda reconstruir desde el repo.
  `schema_consultorio_base.sql` depende de esas tablas.
- El DAO de Odontograma vive en `app/dao/referenciales_agendamiento/odontograma/` (ubicación equivocada; se mueve en la etapa 4).

### Etapa 3 (hecha): Registrar Consulta + Ficha Médica
Plan aprobado: `plan_etapa3.md` (sin versionar). **Decisiones de negocio confirmadas:**
- **Estados de la consulta:** `programada → en_proceso → finalizada` y `programada | en_proceso → cancelada`; `finalizada` y `cancelada` son finales. **Inicia y finaliza el
  médico de la consulta; cancela Recepción** (funcionario) **o el médico de la consulta**. `cancelada` ≠ `anulada`: cancelada = la atención no se realizó y queda en el
  historial, y **su cita pasa de `Realizado` a `Cancelado`** en la misma transacción (devolviendo el cupo; no vuelve a `Confirmado` y se audita); anulada = baja por error,
  definitiva, y la cita vuelve a `Confirmado`. Si la cita ya no estaba `Realizado` (la tocó Agendamiento) no se pisa y la auditoría lo dice.
- **Quién carga lo clínico:** el usuario debe estar vinculado a un médico (`id_medico_sesion()` en `permisos_contexto.py`) **y ser el médico de esa consulta** (se aplica a
  Ficha Médica ya y al resto de los movimientos en las etapas siguientes). El **Administrador queda con lectura clínica** (puede ver; no crea, edita ni cambia estados
  clínicos). Un médico solo ve SUS consultas en el listado y en el resumen.
- **Permisos** (`schema_permisos_consultorio_roles.sql`, idempotente y auditado): `Medico` = consulta `ver`/`estado`, y todo lo clínico (Ficha con `ver/nuevo/editar/anular`);
  `Recepcion` = consulta `ver/nuevo/estado/anular` y Ficha solo `ver`. Los usuarios vinculados a un médico pasan al rol `Medico` (los usuarios 9 y 10 están inactivos).
  `fichamedica` suma la acción `nuevo` en el catálogo.
- **Anular una consulta** también se bloquea con Odontograma, Receta, Órdenes (no canceladas) o Justificativo vigentes y con la consulta finalizada (el CUS: "no es posible
  anular una consulta con datos clínicos asociados").
- **Lecturas clínicas** (la ficha) restringidas a `fichamedica: ver`; **rangos clínicos de la ficha aprobados** (temperatura 30–45 °C, FC 20–250, FR 5–80, presión sistólica
  50–300 y diastólica 30–200 con sistólica > diastólica, peso 1–500 kg, talla 30–250 cm) y **no se permiten fichas sin ningún dato**; n.º de consulta `CON-0000017` derivado del id.
- **Mejora futura (fuera de esta etapa): reasignación del médico de una consulta** (p. ej. un suplente). Hoy el médico de la consulta es el de la cita y no se puede cambiar.
**Commit 1 (hecho):**
- `schema_consultorio_etapa3.sql` (id_cita único parcial, duración 1–480, CHECK de rangos y de la presión de la ficha, FK de la ficha a `RESTRICT`; `chk_ficha_con_datos` va
  `NOT VALID` a propósito para no tocar la ficha vacía 15 anterior) y su reflejo en `schema_consultorio_base.sql`.
- `ConsultaDao`/`consulta_api.py` reescritos: alta con bloqueo de la cita (`FOR UPDATE`, consulta simple: bloquearla con el JOIN a `estado_cita` daba "no encontrada" al
  perder una carrera), paciente/médico/consultorio/funcionario activos, estado inicial siempre `programada`; `PATCH /consultas/<id>/estado` (reemplaza al `PUT` libre);
  `DELETE` con reversión de la cita; `GET /consultas` con filtros y paginación en el servidor; `/indicadores`; `/citas-disponibles`; `/<id>/resumen` (solo contadores).
- Auditoría de `consultas_cab` (ALTA, MODIFICACION de estado y BAJA) con N.º de consulta, paciente con CI y médico; nunca contenido clínico.
- `CitaDao.getCitasConfirmadasSinConsulta` ya no cuenta las consultas anuladas.
- Tests: `smoke_consulta.py` (134 chequeos, incluida la carrera de dos altas) con `tests/consultorio/_fixtures.py` (datos `ZZ` por SQL, sin depender de usuarios reales).
- Datos de prueba para la prueba manual con el médico Oscar Gonzales (CI 2222222, usuario con rol `Medico`): `scripts/datos_prueba_oscar.py` (idempotente; sin `--ejecutar`
  solo simula). Los médicos Laura González y Andrea Cabrera (15 y 19) tienen sus usuarios INACTIVOS: no usarlos para probar.
**Commit 2 (hecho): Ficha Médica**
- **Validaciones** (servidor: `app/rutas/modulo_consultorio/validadores_clinicos.py`; espejo `app/static/js/consultorio-validadores.js`; base: `chk_ficha_rangos` y
  `chk_ficha_presion`): temperatura 30–45 °C, FC 20–250, FR 5–80, presión `SSS/DDD` (50–300 / 30–200, sistólica > diastólica), peso 1–500 kg, talla 30–250 cm (hasta 2 decimales,
  coma o punto), textos hasta 2.000 caracteres, **al menos un dato**. **El IMC lo calcula el servidor** (`peso / (talla/100)²`, 2 decimales); el del navegador se ignora.
  Si cambia un rango, cambiar los tres sitios; `tests/consultorio/comparar_ficha_js_py.py` verifica que JS y Python den lo mismo (74 casos, con JScript).
- **Quién y cuándo:** crear, editar y anular la ficha: solo el médico de esa consulta (`id_medico_sesion()`), con la consulta `programada` o `en_proceso`; se revalida DENTRO de la
  transacción con la consulta bloqueada (`FOR UPDATE`), así que si la cancelan mientras se carga, la ficha se rechaza (409). Una ficha activa por consulta (índice parcial + 409).
  Recepción y el Administrador solo leen.
- **Privacidad:** las lecturas (`/ficha-medica/consulta/<id>` y `/ficha-medica/<id>`) ya no son `@require_login`: piden `fichamedica ver`, y un médico solo lee las de SUS consultas.
  El listado (`GET /ficha-medica`, reemplaza a `/fichas-todas`) identifica la ficha (consulta, paciente con CI, médico, fecha, cuántos datos tiene) y **no devuelve ningún valor clínico**.
- **Auditoría** (`ficha_medica_consulta`): ALTA (consulta y paciente), MODIFICACION **sin valores** (ni anteriores ni nuevos; "sin cambios" no audita) y BAJA (Activo → Anulado).
- Tests: `smoke_ficha_medica.py` (115 chequeos: esquema, permisos por rol, 31 valores inválidos, IMC, una por consulta, estados de la consulta, auditoría sin valores, listado sin
  valores clínicos, dos altas simultáneas y la consulta que se cancela mientras se guarda) y `comparar_ficha_js_py.py`. `smoke_migracion02` ahora borra la auditoría que genera.
**Commit 3 (hecho): vistas Tabler**
- `consulta-index.html` (se reemplazaron las 2.142 líneas por ~330; se fueron el CSS "médico" de 700 líneas, jQuery, DataTables, Bootstrap 4 por CDN y el modal de funcionario):
  4 indicadores del servidor, filtros (estado, paciente o CI, fechas) y paginación en el servidor, badges de estado, `Abrir` y `Anular`, y el modal **Nueva Consulta** (elegir una cita
  `Confirmado` pendiente con buscador, duración opcional; no se elige médico, paciente ni funcionario).
- **Pantalla central** `consulta-detalle.html` en `/referenciales/consulta/consulta-detalle/<id>` (contextual, sin entrada de menú; permiso `consulta ver`; 404 si no existe o está
  anulada; 403 si es de otro médico): cabecera en tarjeta, acciones de estado según lo que devuelve `GET /consultas/<id>/resumen` (`acciones`: iniciar, finalizar, cancelar,
  cargar_clinico), la **tarjeta de la Ficha Médica** (formulario con IMC en vivo y las mismas validaciones del servidor; vista, editar y anular) y la grilla de los 7 registros clínicos
  con su contador de vigentes (se ofrecen según el `ver` de cada ventana destino; "Abrir" si puede cargar, "Ver" si no). Los destinos siguen en SB Admin 2 y se abren con `?consulta=<id>`
  (Diagnósticos también con `&paciente=&medico=`). **Pendiente de las etapas 4 a 7:** que cada destino lea `?consulta=` con la validación nueva y agregue "Volver a la consulta".
- `ficha-medica-index.html`: listado/auditoría transversal de fichas (consulta, paciente con CI, médico, estado de la consulta, cuántos datos tiene) **sin valores clínicos**; la ficha se
  abre, edita o anula desde la consulta.
- Las vistas declaran `const PK = 'id_consulta_cab'` / `PK_FICHA = 'id_ficha_medica'` (lección de la etapa 1: el JSON de Flask viene con las claves ordenadas).
- Tests: `smoke_consulta_vistas.py` (acceso por rol y por médico, Tabler sin jQuery, qué tarjetas ve cada rol, baja real por HTTP con el id de la vista) y `browser_consulta.py` (Edge headless con
  fetch simulado: listado, filtros, paginación, Nueva Consulta, atención de la consulta en 4 escenarios —médico programada, médico con ficha, Recepción, finalizada— y Fichas).

### Etapa 7 (en curso): Justificativo Médico y cierre del módulo
Plan: `plan_etapa7.md` (sin versionar). **Decisiones confirmadas (Justificativo):** estados **`pendiente` → `emitido` | `anulado`** (el CUS): se registra `pendiente`; la acción "Generar Justificativo" (permiso `estado`, solo el médico de la
consulta, también con la consulta finalizada, no con la cancelada ni anulada, auditada como MODIFICACION de estado) lo pasa a `emitido` y recién ahí es el documento oficial; "Anular" (definitivo) lo pasa a `anulado` desde `pendiente` o
`emitido`, **no con la consulta finalizada**. Solo el médico de la consulta crea y anula (consulta programada / en proceso revalidada en la transacción); Recepción sin acceso, Administrador solo lectura; un médico solo ve lo suyo. Días de reposo
1 a 365; recomendaciones opcionales; vínculo opcional solo con un diagnóstico vigente de la misma consulta; fecha fijada por el servidor; N.º `JUS-0000012` derivado del id.
- ⚠️ **Cambio del DER:** `justificativo_medico.estado` pasa de `activo` / `anulado` a **`pendiente` / `emitido` / `anulado`** (CHECK; por defecto `pendiente`; lo que estaba `activo` pasó a `emitido`) y `dias_reposo` tiene CHECK de 1 a 365.
  El CUS "Generar Justificativo Médico" debe describir los tres estados y la acción "Generar" como la que emite el documento.
**Commit 1 (hecho): base, backend y PDF**
- `schema_consultorio_etapa7.sql` (idempotente; `schema_consultorio_base.sql` actualizado). El rol Médico recibe `justificativomedico: estado` (`schema_permisos_consultorio_roles.sql`; el catálogo suma la acción `estado` a la ventana).
- `JustificativoMedicoDao` y `justificativo_medico_api.py` reescritos sobre `documento_clinico.py` (`/api/v1/justificativos`: GET lista con filtros y paginación, GET `/<id>`, POST, `PUT /<id>/emitir`, `DELETE /<id>`, `GET /<id>/pdf`; un médico solo lee lo
  suyo). Bloqueos: consulta `FOR UPDATE` → diagnóstico `FOR SHARE`; emitir: consulta `FOR SHARE` → justificativo `FOR UPDATE`.
- Auditoría (`justificativo_medico`): ALTA (Estado Pendiente), MODIFICACION (Pendiente → Emitido), BAJA (Pendiente o Emitido → Anulado; `estructura_auditoria` respeta el estado anterior que informa la API) y **EXPORTACION en cada descarga del PDF**, con
  N.º, consulta y paciente con CI; nunca los días de reposo ni las recomendaciones.
- **PDF** en el servicio común (`documento_clinico_pdf_service.py`, tipo `justificativo`): "se indica reposo por N día(s) a partir del dd/mm/aaaa" + recomendaciones; **pendiente = marca BORRADOR, emitido = sin marca, anulado = marca ANULADO**.
  `justificativo_pdf_service.py` se eliminó.
- `validar_justificativo` + espejo JS (324 casos JS ↔ Python en el comparador). Test: `smoke_justificativo.py` (esquema, permisos, validaciones, ciclo pendiente → emitido → anulado, consulta finalizada / cancelada / anulada, privacidad, PDF con sus tres marcas y
  la auditoría de cada descarga, auditoría sin contenido y carreras).

**Commit 2 (hecho): vista Tabler**
- `justificativo-medico-index.html` (reemplaza las 455 líneas SB Admin 2 + jQuery): listado con filtros (paciente o CI, estado, fechas) y paginación en el servidor, con `Ver`, **`PDF`**, **`Generar`** (pendiente → emitido, con confirmación; también con la
  consulta finalizada, no con la cancelada) y `Anular` (pendiente o emitido, solo con la consulta abierta); con `?consulta=<id>`: tarjeta de la consulta, "Volver a la consulta", los justificativos de esa consulta y el modal **Nuevo justificativo** (días de
  reposo 1–365, recomendaciones, diagnóstico opcional; mismas validaciones que el servidor). Las rutas pasan `es_medico`.
- Tests: `smoke_justificativo_vistas.py` (acceso por rol, Tabler sin jQuery, quién ve cada botón, generar / anular / PDF reales por HTTP con los ids de la vista, también con la consulta finalizada) y 4 escenarios más en `browser_documentos.py` (listado, de la
  consulta, rechazo del servidor, lectura).

### Etapa 6 (hecha): Recetas, Orden de Estudios y Orden de Análisis (con PDF)
Plan: `plan_etapa6.md` (sin versionar). **Decisiones confirmadas:** solo el médico de la consulta crea y anula (consulta programada / en proceso revalidada en la transacción; Recepción sin acceso, Administrador solo lectura;
no se anula con la consulta finalizada); **avanza el estado de una orden solo el médico de la orden, también con la consulta FINALIZADA** (el paciente trae el resultado días después) y no con la cancelada ni anulada;
vínculos opcionales con un diagnóstico vigente y con un tratamiento no cancelado **de la misma consulta** (así lo dice el CUS); la receta no tiene `estado` (el "estado inicial Pendiente" es de las órdenes); fecha del documento
fijada por el servidor; N.º de documento derivado del id (`RCT-0000012`, `OES-0000005`, `OAN-0000003`), sin columnas nuevas.
**Commit 1 (hecho): base, backend y PDF**
- `schema_consultorio_etapa6.sql` (idempotente; `schema_consultorio_base.sql` actualizado): único parcial `receta_medicamento (receta, medicamento) WHERE activo` (un medicamento no se repite en una receta; si había repetidos
  vigentes se dejó el primero), `activo` NOT NULL, CHECK de textos no vacíos y trigger diferido `trg_receta_con_medicamento` (toda receta vigente tiene al menos un medicamento).
- Código común: `documento_clinico.py` (consulta y vínculos bloqueados, N.º de documento, clínica y médico para el PDF) y `orden_base.py` (`OrdenBaseDao`: las dos órdenes son idénticas, solo cambia el catálogo; `OrdenEstudioDao` y
  `OrdenAnalisisDao` solo declaran tabla y columnas) con la fábrica de API `orden_api_base.crear_orden_api` (`/api/v1/orden-estudios` y `/orden-analisis`); `RecetaDao` + `receta_api.py` (`/api/v1/recetas`).
  Bloqueos: consulta `FOR UPDATE` → diagnóstico y tratamiento `FOR SHARE` → medicamentos / tipo `FOR SHARE` en orden de id (los inactivos se rechazan; lo ya cargado se sigue mostrando aunque el catálogo se anule).
  Avanzar el estado: consulta `FOR SHARE` → orden `FOR UPDATE`, un paso por vez que calcula el sistema (el cuerpo no elige el estado).
- Endpoints (todos con privacidad: un médico solo lee lo de SUS consultas): `GET` lista (filtros `q`, `estado`, `desde`, `hasta`, `consulta`, paginación), `GET /<id>`, `POST`, `PUT /<id>/estado` (órdenes), `DELETE /<id>`, `GET /<id>/pdf`.
- Auditoría (`recetas`, `orden_estudios`, `orden_analisis`): ALTA, BAJA, MODIFICACION (estado de la orden) y **EXPORTACION en cada descarga del PDF**, con N.º de documento, consulta y paciente con CI; **nunca** medicamentos, dosis,
  tipos, motivo ni indicaciones.
- **PDF** (`app/Services/documento_clinico_pdf_service.py`, patrón `calcular_datos_documento` / `dibujar_documento` / `generarDocumentoPdf`): encabezado con la clínica (`empresa`), título, N.º y fecha, paciente con CI, médico con
  especialidad (y N.º de registro solo si lo tiene), el contenido (receta: tabla de medicamentos + indicaciones; órdenes: tipo, motivo, indicaciones y estado), firma y sello, marca ANULADA / CANCELADA en rojo (se descarga igual) y
  continúa en otra página si es largo. **Lleva el contenido clínico; la auditoría no.** El Justificativo (etapa 7) pasará a este servicio.
- `validadores_clinicos.py` + `consultorio-validadores.js`: `validar_receta`, `validar_orden_estudio`, `validar_orden_analisis` y sus espejos (298 casos JS ↔ Python en `comparar_ficha_js_py.py`).
- Tests: `smoke_receta.py`, `smoke_orden_clinica.py` (las dos órdenes con el mismo código, incluido el avance con la consulta finalizada y las carreras) y `smoke_pdf_documentos.py` (contenido de los tres PDF, marca, varias páginas, privacidad y
  la auditoría de cada descarga). `_fixtures.py`: la receta de los fixtures se inserta con su medicamento (trigger diferido) y suma `medicamento()`, `tipo_estudio()` y `tipo_analisis()`.

**Commit 2 (hecho): vistas Tabler**
- `receta-index.html` (reemplaza las 537 líneas SB Admin 2 + jQuery): **sin `?consulta=`** = listado con filtros (paciente o CI, fechas) y paginación en el servidor, con `Ver` (modal con la tabla de medicamentos, dosis, frecuencia, duración
  e indicaciones), **`PDF`** (se abre en otra pestaña) y `Anular` (solo con la consulta abierta); **con `?consulta=<id>`** = tarjeta de la consulta, "Volver a la consulta", las recetas de esa consulta y el modal **Nueva receta** (filas de
  medicamento con su dosis, frecuencia y duración que se agregan y se quitan, indicaciones generales y diagnóstico / tratamiento opcionales; mismas validaciones que el servidor con `consultorio-validadores.js`).
- **Una sola plantilla para las dos órdenes**: `app/templates/orden-clinica-index.html` (reemplaza las dos de 547 líneas); la ruta de cada una le pasa `cfg` (título, API, clave primaria, columna del tipo, catálogo, ventana, validador).
  Listado con filtros (paciente, CI o tipo; estado; fechas), `Ver` (+ PDF), **avanzar estado** con confirmación y **cancelar**. La vista ofrece avanzar también con la consulta FINALIZADA y solo lo niega con la cancelada; cancelar solo con la
  consulta abierta y la orden no completada.
- Las rutas pasan `es_medico`: solo un usuario vinculado a un médico ve los botones de registrar, avanzar y anular (el Administrador, no).
- Tests: `smoke_docs_vistas.py` (acceso por rol, Tabler sin jQuery, quién ve cada botón, la plantilla común de las órdenes y el avance / la baja reales por HTTP con los ids de las vistas, incluso con la consulta finalizada) y
  `browser_documentos.py` (Edge headless, 9 escenarios: receta en listado / consulta / rechazo del servidor / lectura, orden de estudios en listado / consulta / rechazo / lectura y orden de análisis).
- Pendiente para la etapa 7: el Justificativo pasa al servicio común de PDF y a la misma auditoría de descargas.

### Etapa 5 (hecha): Tratamientos y Sesiones (Procedimientos e Insumos Utilizados)
Plan: `plan_etapa5.md` (sin versionar). **Decisiones confirmadas:** cada sesión se registra DENTRO de una consulta; varios procedimientos por sesión; insumos opcionales (0 o más, sin repetir, cantidad 1–999);
solo el médico crea, anula y finaliza (Recepción sin acceso, Administrador solo lectura); anulación de tratamiento definitiva; anular una sesión solo la última vigente, desde su consulta abierta, con cascada, y el
tratamiento vuelve a `pendiente` si queda sin sesiones; fecha del tratamiento propuesta hoy (editable, no futura), fecha de la sesión fijada por el servidor, próxima cita opcional no anterior a hoy.
- ⚠️ **Cambios del DER (hay que reflejarlos en el diagrama y el análisis):** `sesiones_tratamiento.id_consulta_cab` (INT NOT NULL, FK RESTRICT a `consultas_cab`: la consulta en la que se registró la sesión, del mismo paciente y
  médico que el tratamiento, puede ser posterior a la que lo creó); **tabla nueva `sesion_procedimientos`** (`id_sesion_procedimiento`, `id_sesion` FK, `id_tipo_procedimiento` FK, `activo`; único parcial por sesión + tipo
  entre los vigentes; al menos uno por sesión vigente, con trigger diferido); **columna retirada `sesiones_tratamiento.id_tipo_procedimiento`** (los datos se migraron a `sesion_procedimientos`); `sesion_insumos` con único parcial
  por sesión + insumo y cantidad 1–999; `activo` / `estado` NOT NULL. Triggers `trg_validar_sesion_consulta` (la consulta de la sesión es del mismo paciente y médico que el tratamiento) y `trg_sesion_con_procedimiento`.
- ⚠️ **El CUS de "Gestionar Procedimientos e Insumos Utilizados" debe reflejar que cada sesión se registra en una consulta** (mismo paciente y médico que el tratamiento; un tratamiento de varias visitas recibe sus sesiones
  en consultas posteriores), que una sesión tiene uno o más procedimientos y que los insumos son opcionales.
**Commit 1 (hecho): base y backend**
- `app/dao/referenciales_consultorio/schema_consultorio_etapa5.sql` (idempotente; `schema_consultorio_base.sql` actualizado). Al migrar, los renglones de insumo repetidos en una misma sesión se fusionaron en uno (suma de cantidades).
- `TratamientoDao` y `SesionTratamientoDao` reescritos. Bloqueos: consulta `FOR UPDATE` → tratamiento `FOR UPDATE` → tipos `FOR SHARE` en orden de id (tipo de tratamiento, diagnóstico, procedimientos, insumos; los inactivos se rechazan).
  Alta de tratamiento: médico de la consulta, consulta `programada` / `en_proceso` revalidada, diagnóstico opcional vigente y de la misma consulta. Sesión: consulta abierta y del mismo paciente y médico que el tratamiento, que debe estar
  `pendiente` o `en_seguimiento` (la 1.ª sesión lo pasa a `en_seguimiento`). Anular tratamiento: sin sesiones vigentes ni venta EMITIDA y con la consulta que lo creó abierta. **Finalizar** (permiso `estado`): solo el médico del
  tratamiento, desde `en_seguimiento`, sin exigir la consulta abierta. Un tratamiento finalizado no admite sesiones ni anular sus sesiones.
- APIs `/api/v1/tratamientos` (GET lista con filtros `q`, `estado`, `desde`, `hasta`, `consulta`, `paciente`, `en_curso=1` y paginación; GET `/<id>` con sus sesiones; GET `/consulta/<id>` lookup de Receta y Órdenes con
  `require_algun_permiso`; POST; DELETE; PUT `/<id>/finalizar`) y `/api/v1/sesiones-tratamiento` (GET `/tratamiento/<id>`, GET `/<id>`, POST, DELETE). Un médico solo lee lo suyo; Recepción sin acceso.
- Auditoría (`tratamientos` y `sesiones_tratamiento`): ALTA / BAJA con consulta, paciente (con CI) y tipo de tratamiento, y MODIFICACION del estado del tratamiento (finalizar, 1.ª sesión, última sesión anulada); **nunca**
  descripciones, observaciones, procedimientos ni insumos.
- `validadores_clinicos.py` + `consultorio-validadores.js`: `validar_tratamiento` / `validar_sesion` y sus espejos (215 casos JS ↔ Python en `comparar_ficha_js_py.py`).
- `TipoProcedimientoMedicoDao.esta_en_uso` consulta `sesion_procedimientos`; Insumo y Tipo Tratamiento siguen igual (ya hacían el `FOR SHARE` del hijo: el alta toma el bloqueo del referencial).
- **Facturación (Venta de Tratamiento) intacta:** lee `id_tratamiento`, `id_paciente`, `estado <> 'cancelado'`, `fecha_tratamiento`, `codigo` e `id_tipo_tratamiento`; `smoke_ventas.py` se adaptó para anular los tratamientos como el médico de una
  consulta abierta (datos ZZ) y pasa completo.
- Tests: `smoke_tratamiento.py` (79 chequeos, con carreras del tipo y de la consulta que se anulan mientras se guarda) y `smoke_sesion_tratamiento.py` (92, con varias visitas, cascada, base de datos y carreras). Las vistas de esta etapa
  (todavía las viejas SB Admin 2) se reescriben en el commit 2.
**Commit 2 (hecho): vistas Tabler**
- `tratamiento-index.html` (reemplaza las 521 líneas SB Admin 2 + jQuery): **sin `?consulta=`** = listado con filtros (paciente / CI / tipo, estado, fechas) y paginación en el servidor, con `Ver` (modal con el detalle y sus
  sesiones), `Sesiones`, `Finalizar` y `Anular`; **con `?consulta=<id>`** = tarjeta de la consulta, "Volver a la consulta", los tratamientos de esa consulta, los **tratamientos en curso del paciente creados en otras
  consultas** (con el botón "Registrar sesión en esta consulta": así se arma un tratamiento de varias visitas) y el modal **Nuevo tratamiento** (tipo, diagnóstico opcional de la consulta, fecha propuesta hoy y no futura,
  descripción; mismas validaciones que el servidor con `consultorio-validadores.js`). Anular solo se ofrece sin sesiones, sin factura y con la consulta de origen abierta; Finalizar, en seguimiento.
- `sesion-tratamiento-index.html` (reemplaza las 518 líneas viejas; pantalla contextual `?tratamiento=<id>[&consulta=<id>]`): tarjeta del tratamiento y de la consulta en la que se registra, tabla de sesiones (número, fecha,
  consulta, procedimientos, insumos × cantidad, próxima cita), `Ver`, `Anular` (solo la última, con la consulta de la sesión abierta y el tratamiento no finalizado), `Finalizar tratamiento` y el modal **Nueva sesión**
  (procedimientos con buscador y contador, descripción, observaciones, próxima cita no anterior a hoy y filas de insumos con cantidad que se agregan y se quitan). Sin `?consulta=` es solo lectura ("Volver a tratamientos");
  con una consulta de otro paciente o médico avisa y no ofrece registrar.
- Las rutas pasan `es_medico`: solo un usuario vinculado a un médico ve los botones de registrar, finalizar y anular (el Administrador, no).
- Tests: `smoke_trat_vistas.py` (acceso por rol, Tabler sin jQuery, quién ve cada botón, recorrido de un tratamiento de dos visitas y baja real por HTTP con los ids de las vistas) y `browser_tratamiento.py` (Edge headless,
  11 escenarios: listado, tratamientos de la consulta y en curso del paciente, alta y rechazo del servidor, lectura, sesiones con procedimientos / insumos / validaciones, consulta cerrada, otra consulta, tratamiento finalizado).

### Etapa 4 (hecha): Diagnóstico y Odontograma
Plan: `plan_etapa4.md`. **Decisiones confirmadas:** pieza dental del diagnóstico **opcional** (si se carga, FDI válida); la **fecha del diagnóstico la fija el servidor** (no editable);
quitar un hallazgo del odontograma = **baja lógica del renglón** (`activo = false`, no borrado físico); un odontograma sin hallazgos se permite; la acción `editar` de la ventana Odontograma se
agregó al catálogo y solo la tiene el rol Médico.
- ⚠️ **Cambios del DER (hay que reflejarlos en el diagrama y el análisis):** `estado_dental.aplica_a` (`PIEZA` | `SUPERFICIE`: Caries, Obturación, Incrustación, Sellador, Resina, Amalgama y
  Fractura son de superficie; los otros 15, de pieza completa); `odontograma` **sin la columna `estado`** (queda `activo`); `odontograma_detalle.activo` (baja lógica por renglón) con único parcial
  `(odontograma, pieza, superficie, estado) WHERE activo`; superficie `O V L M D` o `T` (pieza completa) con CHECK; pieza FDI con CHECK en `odontograma_detalle.numero_diente` y en
  `diagnosticos.pieza_dental`; FKs de `odontograma.id_paciente` y `odontograma_detalle.id_odontograma` a `RESTRICT`; **trigger diferido** `trg_diagnostico_con_sintoma` (todo diagnóstico vigente tiene
  al menos un síntoma). Script `schema_consultorio_etapa4.sql` (idempotente; `schema_consultorio_base.sql` actualizado).
- **Diagnóstico** (`DiagnosticoDao`, `diagnostico_api.py`): crea y anula solo el médico de la consulta, con la consulta `programada` / `en_proceso` revalidada con la consulta bloqueada (`FOR UPDATE`);
  tipo ACTIVO y **al menos un síntoma, todos ACTIVOS** (bloqueados `FOR SHARE`, en orden); descripción obligatoria; pieza FDI opcional (permanentes 11–18, 21–28, 31–38, 41–48; temporales 51–55, 61–65,
  71–75, 81–85); anular (definitiva) sin tratamiento **vigente** asociado. Los diagnósticos ya cargados se siguen mostrando aunque su tipo o sus síntomas se hayan anulado. Un médico solo lee lo de SUS
  consultas. El lookup `GET /diagnosticos-medicos/consulta/<id>` (lo usan Tratamiento, Receta, Órdenes y Justificativo) pasó de `@require_login` a `@require_algun_permiso` (nuevo decorador). Auditoría
  (`diagnosticos`): ALTA / BAJA con código DX, N.º de consulta y paciente; sin tipo, síntomas ni descripción.
- **Odontograma** (`OdontogramaDao`, ahora en `app/dao/referenciales_consultorio/odontograma/`; `odontograma_api.py`): uno por consulta; **la precarga la hace el servidor** en la misma transacción
  (copia los hallazgos ACTIVOS del último odontograma vigente del paciente de una consulta ANTERIOR no cancelada); hallazgos con pieza FDI + superficie + estado, un estado de pieza completa solo con `T` y uno de
  superficie solo con `O V L M D`, **un registro idéntico activo se rechaza** (409); agregar / quitar hallazgos con la acción `editar`, solo el médico de la consulta con la consulta abierta. Se eliminaron
  `PUT`, `PATCH …/estado`, `validar-consulta` y `precarga`. Auditoría (`odontograma`): ALTA (con "Precargado desde CON-…"), MODIFICACION ("odontograma modificado", sin piezas ni estados) y BAJA.
- `validadores_clinicos.py` + `consultorio-validadores.js`: `validar_pieza_fdi`, `validar_superficie`, `validar_diagnostico` y sus espejos (142 casos JS ↔ Python en `comparar_ficha_js_py.py`).
- `acceso_consulta()` en `modulo_consultorio/utils.py`: la consulta existe y, si el usuario es médico, es suya (lo usan Ficha, Diagnóstico y Odontograma).
- Tests: `smoke_diagnostico.py` (117 chequeos, con las carreras del tipo / síntoma / consulta que se anulan mientras se guarda) y `smoke_odontograma.py` (137, con la precarga y los duplicados).
  `smoke_migracion02.py` quedó solo con las secciones de esquema, permisos y consulta (lo demás lo cubren los tests nuevos).
**Commit 2 (hecho): vistas Tabler**
- `diagnostico-index.html` (reemplaza `diagnosticos-medicos-index.html`, 1.178 líneas SB Admin 2 + jQuery): **sin `?consulta=`** = listado con filtros (código, paciente o CI, fechas) y paginación en el servidor, `Ver` (modal con
  tipo, síntomas, descripción, pieza y observaciones) y `Anular`; **con `?consulta=<id>`** (desde la Atención de la consulta) = tarjeta de la consulta, "Volver a la consulta", los diagnósticos de esa consulta y el modal
  **Nuevo diagnóstico** (tipo, selector de síntomas con búsqueda y contador, pieza FDI en un selector de 8 cuadrantes, descripción, observaciones; mismas validaciones que el servidor con `consultorio-validadores.js`).
  Las rutas pasan `es_medico` al template: solo un usuario vinculado a un médico ve "Nuevo" y "Anular" (el Administrador, no).
- `odontograma-index.html` (reemplaza las 1.208 líneas viejas): **listado** (sin `?consulta=`) y **odontograma visual** (con `?consulta=<id>`): SVG generado en el navegador con las piezas FDI en dos arcadas y cuatro
  cuadrantes (+ interruptor de dentición temporal: 32 piezas permanentes, 52 con las temporales), cada pieza con sus 5 superficies (V hacia afuera, M hacia la línea media, O al centro) y un contorno para los hallazgos
  de pieza completa; **el color de cada superficie / contorno es `estado_dental.color`**, con el símbolo y una leyenda; clic en una superficie (o en el número = pieza completa) abre el panel de la pieza (estados filtrados por
  `aplica_a`, observación, Agregar y Quitar con confirmación); tabla con todos los hallazgos; "Crear odontograma" (precargado) y "Anular odontograma" (definitivo). **Para pulir el diseño** (Antigravity): el dibujo está en
  `dibujarPieza()` / `pintarOdontograma()` y las clases `.odo-*` del `<style>` de la plantilla (variables `--odo-*`); la lógica no depende de esas clases.
- Los destinos que faltan migrar (Tratamientos, Recetas, Órdenes, Justificativo) siguen con `?consulta=` y todavía no tienen "Volver a la consulta" (etapas 5 a 7).
- Tests: `smoke_diag_odo_vistas.py` (acceso por rol, Tabler sin jQuery, quién ve cada botón, baja real por HTTP con el id de la vista) y `browser_diag_odontograma.py` (Edge headless, 8 escenarios: listados, diagnóstico en la
  consulta con alta y rechazo del servidor, lectura, odontograma sin crear / editor / solo lectura; verifica las 32 y 52 piezas, la orientación M/D y V/L por cuadrante, el color por estado, el filtrado de estados por pieza o
  superficie, agregar / quitar y anular).

### Etapa 2 (hecha): Tipo Diagnóstico y Síntomas
- Mismo `CatalogoDao` y `crear_api_catalogo` que la etapa 1 (ahora con `FECHA = False`: estas dos tablas no tienen `fecha_registro`). **Tipo Diagnóstico** lleva
  descripción (`descripcion_diagnostico`, la clave única entre los activos) y tipo (`tipo_diagnostico`, obligatorio, en MAYÚSCULAS); su API sigue en `/api/v1/diagnosticos`
  (la consume también Gestión de Diagnósticos para su combo). **Síntomas** solo lleva la descripción (`/api/v1/sintomas`, que alimenta el selector de síntomas del
  diagnóstico). Ambos en modo ampliado; el `DELETE` físico y las validaciones propias (solo letras) desaparecieron.
- Baja bloqueada (409): Tipo Diagnóstico → diagnósticos vigentes o tratamientos no `cancelado`; Síntoma → `diagnostico_sintoma` de diagnósticos vigentes. Auditoría
  como en la etapa 1 (entidades `tipo_diagnostico` y `sintoma`).
- `schema_consultorio_etapa2.sql` (idempotente): pasa a MAYÚSCULAS lo cargado antes (`prueba` → `PRUEBA`, etc.).
- **Pendiente de la etapa 4 (Diagnóstico):** el alta de un diagnóstico debe tomar `FOR SHARE` sobre su tipo y sobre cada síntoma elegido (y rechazar los inactivos),
  y los listados que muestran diagnósticos ya cargados NO deben filtrar por `activo` del tipo (un diagnóstico viejo con un tipo anulado se sigue viendo).
- `SintomaDao.estaEnUso` / `TipoDiagnosticoDao.estaEnUso` pasaron a `esta_en_uso` (devuelve el motivo o `False`, como el resto).
- Tests: `smoke_referenciales_consultorio` y `browser_referenciales` ahora cubren los 8.

### Etapa 1 (hecha): los 6 referenciales con baja lógica en Tabler
Tipo Tratamiento, Tipo Insumo Utilizado, Tipo Procedimiento Médico, Medicamentos, Tipo Estudio y Tipo Análisis cumplen el Estándar de referenciales (los 6 puntos).
- **Código compartido:** `app/dao/referenciales_consultorio/CatalogoDao.py` (listar con/sin inactivos, obtener, duplicado, alta, modificación, `anular` con
  `FOR UPDATE` + `_motivo_en_uso` en la misma transacción, `reactivar` que valida duplicado) y la fábrica `app/rutas/modulo_consultorio/catalogo_api.py`
  (`crear_api_catalogo`: GET lista/uno, POST, PUT, DELETE, PATCH `/reactivar`, auditoría y permisos). Cada referencial declara solo lo suyo: su DAO hereda de
  `CatalogoDao` (tabla, clave de texto, extras y el motivo de uso) y su `*_api.py` llama a la fábrica. Nombres de blueprint y URL sin cambios; las claves JSON de
  los lookups de otras pantallas tampoco (`id_insumo`, `id_tipo_procedimiento`, `nombre_comercial`...), solo se suman `activo` y `fecha_registro`.
- **Vistas:** una plantilla por pantalla (`base_tabler.html`, modal, Estado, "Mostrar inactivos", Reactivar con SweetAlert2, `facturacion-listado.js` y
  `facturacion-validadores.js`). Tipo Tratamiento suma Precio (Gs.) e IVA (10% / 5% / Exenta); Insumo y Medicamento, Presentación (opcional).
- **Descripción en modo ampliado en TODOS los de Consultorio** (`normalizar_descripcion(..., 100, ampliada=True)`): MAYÚSCULAS, letras con tildes y Ñ, números,
  espacios y `. - / , % ( ) + &`, hasta 100, debe empezar con letra o número (ej. `AMOXICILINA/CLAVULÁNICO 875/125 MG`, `LIMPIEZA DENTAL (PROFILAXIS)`).
  `normalizar_descripcion` ganó `campo`/`etiqueta`/`articulo` (Medicamentos usa `nombre_comercial` / "nombre comercial" / "El") y `validar_presentacion`
  (opcional, hasta 100, mismos caracteres); espejo en `facturacion-validadores.js` (`V.presentacion`, y `V.descripcion` con `etiqueta`/`articulo`).
- **Bajas bloqueadas (409) si están en uso:** Tipo Tratamiento → tratamientos no `cancelado`; Insumo → `sesion_insumos` activos; Procedimiento → sesiones
  activas; Medicamento → `receta_medicamento` activos; Estudio / Análisis → órdenes no `cancelado`. **Etapa 5 (hecha):** el alta de tratamientos y sesiones toma `FOR SHARE` sobre tipo de tratamiento, procedimiento e insumo. **Etapa 6 (hecha):** lo mismo para Medicamento, Tipo Estudio y Tipo Análisis.
- **Id en las vistas:** cada plantilla declara `const PK = '<clave primaria>'` y arma las URL con `f[PK]`. **Nunca tomar "la primera clave" del JSON:** Flask
  devuelve las claves ordenadas alfabéticamente y la primera es `activo` (la vista pedía `/tipos-tratamiento/true` y todo daba 404: anular, reactivar y editar).
  `smoke_referenciales_consultorio` hace la baja y la reactivación reales por HTTP con el id que arma la vista y comprueba contra `url_map` que todas las filas
  reales resuelvan sus rutas; `browser_referenciales` usa un mock con las claves ordenadas como el servidor.
- ⚠️ **Presentación (Insumo y Medicamento) es un campo nuevo para el análisis: hay que agregarlo al DER y a los CUS de "Mantener Tipo Insumo Utilizado" y
  "Mantener Medicamentos"** (texto opcional, hasta 100 caracteres, en MAYÚSCULAS, p. ej. `CAJA X 20 COMPRIMIDOS`). La columna `presentacion VARCHAR(100)` ya
  existía en `insumos` y `medicamentos`, pero no figuraba en la documentación. Igual que `precio` e `iva` de Tipo Tratamiento (ver más arriba).
- **Auditoría** (`auditoria_cambios`, módulo "Referenciales Consultorio"): ALTA, MODIFICACION (solo lo que cambió; sin cambios no audita), BAJA y REACTIVACION.
- Tests: `tests/consultorio/smoke_referenciales_consultorio.py` (338 chequeos sobre los 6), `tests/consultorio/browser_referenciales.py` (Edge headless, ~230
  chequeos de DOM) y `smoke_tipo_tratamiento.py` actualizado (el test limpia ahora la auditoría que genera).

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
