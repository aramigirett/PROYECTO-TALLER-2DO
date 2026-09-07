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
- Primer factor: CI/RUC + contraseña.
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

## Estado real del Módulo Consultorio (en desarrollo)

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

### El resto del módulo: 12 de 13 CUS restantes están SIN PROGRAMAR
Auditado y confirmado — de los movimientos/referenciales que faltaban
revisar, solo Odontograma tenía código. El resto:
- **Ya tienen tabla en la base, pero CERO código de aplicación (sin
  DAO/API/routes/pantalla):** `tratamientos` (bien foreada, ya usada para
  bloquear el ANULAR de Consulta), `insumos` (catálogo simple, huérfana, sin
  FK que la referencie todavía), `tipos_tratamiento` (Tipo Tratamiento).
- **No existen ni como tabla, hay que diseñarlas de cero:** Gestionar
  Procedimientos e Insumos Utilizados (incluye `consultas_detalle.id_tipo_procedimiento`,
  columna fantasma sin tabla ni FK detrás — mismo patrón que tenía
  `id_sintoma` antes de corregirlo), Generar Recetas e Indicaciones, Generar
  Orden de Estudios, Generar Orden de Análisis, Generar Justificativo
  Médico, Tipo Insumo Utilizado, Tipo Procedimiento Médico, Medicamentos
  (hoy solo existe como texto libre `nombre_medicamento` dentro de
  `historial_medico_paciente` de Agendamiento, no es un catálogo
  reutilizable), Tipo Análisis, Tipo Estudio.
- Decisión de orden: programar primero las **referenciales/catálogos**
  (Tipo Tratamiento, Tipo Insumo Utilizado, Tipo Procedimiento Médico,
  Medicamentos, Tipo Análisis, Tipo Estudio), porque los movimientos
  grandes (Gestionar Tratamientos, Generar Recetas, etc.) dependen de que
  esos catálogos ya existan y tengan datos cargados.

## Pendiente de decidir a futuro: control de acceso en módulos grandes
Hoy Agendamiento, Referenciales y Consultorio NO tienen ninguna restricción
de rol en el código — cualquier usuario logueado (sin importar su rol) puede
entrar. Esto salió a la luz al programar Mantener Menú (buscar-only), que
respeta esta realidad en vez de inventar restricciones nuevas. Cuando se
encaren estos módulos a fondo, hay que definir con el análisis qué rol puede
acceder a qué pantalla, y aplicar el mismo patrón de decorator que ya existe
(`require_admin` en `app/rutas/modulo_seguridad/decorators.py`, más un
`require_login` más liviano agregado para Mantener Menú).

## Control de acceso por rol
- Existe `app/rutas/modulo_seguridad/decorators.py` con `@require_admin`: primer
  decorator de control de acceso del proyecto. Bloquea vistas (redirige a
  dashboard con flash) y endpoints de API (403) si `session['nombre_rol']` no
  es `'Administrador'`.
- Toda pantalla/endpoint nuevo que sea exclusivo de Administrador (Mantener
  Usuario, Tablero de Administrador, y a futuro Mantener Roles y Permisos)
  debe usar este mismo decorator — no inventar uno nuevo.
- Los links del sidebar para esas pantallas deben estar envueltos en
  `{% if session.get('nombre_rol') == 'Administrador' %}` en base.html.
- Regla general: cualquier pantalla nueva de acá en más, definir de entrada
  quién puede verla (todos los roles logueados, o solo Administrador) y
  aplicar el control correspondiente desde el principio, no como parche
  después.

## Convenciones de código
- SQL crudo con psycopg2, sin ORM.
- Conexión vía `app/conexion/Conexion.py` — reusar esa clase, no crear una nueva.
- Cada DAO abre su propia conexión y la cierra en un `finally`.
- Los blueprints de rutas se registran en `app/__init__.py` bajo `/referenciales/<modulo>`
  o bajo `/api/v1`.
- Seguir el mismo estilo/nombres que los módulos ya existentes (ej. `CiudadDao.py`,
  `ciudad_api.py`, `ciudad_routes.py`) para cualquier módulo nuevo.

## Cómo trabajar conmigo en este proyecto
- Antes de tocar código existente, mostrame el plan de archivos que vas a crear/modificar.
- Si una decisión de diseño no está clara en este documento, preguntame antes de asumir.
- Priorizá consistencia con el patrón de capas por sobre "mejores prácticas" genéricas
  que rompan la estructura ya usada en el resto del proyecto.