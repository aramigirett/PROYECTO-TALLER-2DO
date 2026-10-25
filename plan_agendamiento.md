# Plan — Punto 4: Migración de Agendamiento (y Seguridad en SB Admin) a Tabler

Rama: `agendamiento-tabler` (creada desde `main`; `main` estaba limpio y a 0/0 commits de `origin/main`).
Estado: **solo relevamiento. No se modificó ningún archivo del proyecto.** Este archivo no está commiteado.

Fuentes del relevamiento: código (DAO, API, rutas, plantillas, catálogo del menú), la base real `odontosisbd`
(consultada solo en lectura: columnas, índices, FK, triggers, permisos por rol) y `tests/`. Lo que está marcado
con *(a verificar)* lo deduje por tamaño/estructura y hay que mirarlo al empezar la etapa.

---------------------------------------------------------------------------------------------------

## 0. Hallazgos que cambian el plan (leer primero)

1. **La base ya está por delante del código y del repo.** Las tablas `ciudades`, `cargo`, `consultorio`,
   `especialidades`, `dias`, `turnos`, `estado_cita`, `paciente`, `medico` y `funcionario` **ya tienen la columna
   `activo`**, y las 7 primeras (más `estado_cita`) ya tienen su **índice único parcial** `... WHERE activo = true`
   (con `UPPER`). Pero: ningún `.sql` del repo lo crea, y **ningún DAO de Agendamiento usa `activo`** (todos hacen
   `DELETE` físico y listan todo). Es decir, CLAUDE.md dice "borrado físico" y es cierto en el código, pero la base
   se adelantó por algún cambio manual no versionado. No investigué quién lo hizo. Consecuencia: el script de la
   Etapa 1 tiene que ser idempotente (`ADD COLUMN IF NOT EXISTS`, `CREATE UNIQUE INDEX IF NOT EXISTS`) para
   funcionar igual en la base actual y en una reconstruida desde cero.
2. **Faltan los `CREATE TABLE` de 17 tablas** (no hay ninguno en el repo): `ciudades, cargo, consultorio, dias, turnos,
   especialidades, estado_cita, paciente, medico, funcionario, disponibilidad_horaria, agenda_cabecera,
   agenda_detalle, cita_cabecera, cita_detalle, avisos_recordatorios, historial_medico_paciente` y también
   **`menu`**. Seguridad sí versiona `roles, usuarios, token_2fa, auditoria_acceso, permisos`, pero `permisos` y `usuarios`
   quedaron modificados por migraciones posteriores (id_menu, bloqueo, etc.), así que hay que verificar que el script
   reconstruya el estado actual (el test de esquema lo comprueba).
3. **Riesgo de datos hoy**: `cita_cabecera.id_paciente` y `historial_medico_paciente.id_paciente` son `ON DELETE
   CASCADE`. `deletePaciente` solo se protege contra `cliente` (FK RESTRICT) y contra consultas (FK RESTRICT de
   `consultas_cab`); un paciente con citas sin consulta o con historial **se borra llevándose todo**.
   `medico.id_ciudad` y `avisos.id_medico` son `SET NULL` (pérdida silenciosa del vínculo).
4. **El mensaje de baja de médico** ("No se encontró el médico con el ID 19") sale porque `deleteMedico` devuelve
   `False` ante cualquier error (incluida la violación de FK RESTRICT de agenda, disponibilidad, consultas,
   tratamientos, odontogramas, diagnósticos y usuarios) y la API lo traduce a 404. No hay `estaEnUso()` en Médico
   ni en Funcionario.
5. **`ConsultaDao` compara textos fijos de `estado_cita`** (`'Realizado'`, `'Cancelado'`) y el cupo se repone con
   SQL directo sobre `agenda_detalle`. Por eso `estado_cita` **no puede volverse un referencial editable** y el
   cupo (`cupos_disponibles`, `estado_detalle`) no se toca en la migración más que para auditar.

---------------------------------------------------------------------------------------------------

## 1. Relevamiento por pantalla

Convenciones de las tablas: **Prog.** = programada completa (alta/edición/baja/listado/validaciones) o a medias;
**Base** = SB Admin 2 (`base.html`, jQuery) o Tabler; **Estándar** = cumple/incumple los 6 puntos de referenciales o
las reglas de movimientos.

### 1.1 Referenciales de Agendamiento (7)

| Pantalla | Prog. | Base | Borrado hoy | Auditoría (formato nuevo) | Estado / Mostrar inactivos / Reactivar | Tests | Permisos (Médico / Recepción) |
|---|---|---|---|---|---|---|---|
| Ciudad (`ciudades`) | Completa. Sin `estaEnUso` (físico; lo frena la FK RESTRICT → falla genérica) | SB Admin (jQuery) | **Físico**; base ya tiene `activo` + único parcial sin usar | No | No | No | M: ver/nuevo/editar/anular · R: **solo ver** |
| Cargo | Completa; sin `estaEnUso` | SB Admin | Físico (`activo` sin usar) | No | No | No | M: ver/nuevo/editar/anular · R: ver/nuevo/editar |
| Consultorio (`consultorio`, PK `codigo`) | Completa, con `estaEnUso()` | SB Admin | Físico (`activo` existe, sin usar). `correo` con `UNIQUE` **no parcial** | No | No | `tests/agendamiento/smoke_consultorio.py` (regresión) | M y R: todo |
| Disponibilidad Horaria | Completa; hay `estaEnUso` | SB Admin (568 líneas) | Físico. **No tiene `activo`**; único `(medico, fecha, inicio, fin)` no parcial | No | No | No | M y R: todo |
| Especialidad | Completa | SB Admin | Físico (`activo` sin usar) | No | No | No | M y R: todo |
| Día | Completa, con `estaEnUso` | SB Admin | Físico (`activo` sin usar). `CHECK` solo 7 días | No | No | No | M y R: todo |
| Turno | Completa, con `estaEnUso` | SB Admin | Físico (`activo` sin usar). `CHECK` solo MAÑANA/TARDE/NOCHE | No | No | No | M y R: todo |

Comunes: sin los validadores espejo (`utils.py` / `*-validadores.js`); la descripción se pasa a mayúsculas inline en
la API; mensajes con ID crudo ("Ciudad con ID 7 eliminada correctamente"); sin 409 con motivo de uso (salvo los que
tienen `estaEnUso`); GET de lista con `@require_login` (correcto por los combos) pero **sin `?inactivos=1`**.
Ubicación inconsistente: Ciudad/Cargo/Día/Especialidad/Turno viven en `app/rutas/referenciales/` y Consultorio/
Disponibilidad en `modulo_agendamiento/`; DAO de Funcionario está en `dao/referenciales/` y el de Médico en
`dao/referenciales_agendamiento/`.

### 1.2 Personas

| Pantalla | Prog. | Base | Borrado hoy | Auditoría | Estado/Reactivar | Tests | Permisos (M / R) |
|---|---|---|---|---|---|---|---|
| Paciente | Completa (CRUD, duplicado cédula/correo, búsqueda para otras pantallas) | SB Admin (347 líneas) | **Físico**; protegido solo contra `cliente` (`"EN_USO"`, ya con `FOR UPDATE`). CASCADE a citas e historial (ver 0.3). `activo` existe, sin usar. `cedula_entidad` `UNIQUE` no parcial | No | No | `smoke_paciente.py` (cubre bloqueo por cliente) | M y R: todo (incluye anular y editar) |
| Médico | Completa; validación cédula cruzada con funcionario (CI/RUC de login) y confirmación al cambiar cédula (audita `auditoria_acceso`) | SB Admin (451) | Físico, **sin motivo de uso** (0.4). `activo` sin usar | Solo el cambio de cédula, en `auditoria_acceso` | No | No | M y R: todo |
| Funcionario | Completa; mismas reglas de cédula | SB Admin (470) | Físico sin `estaEnUso`. `activo` sin usar | Solo cambio de cédula | No | No | M y R: todo |

Notas: no hay tabla Persona (se respeta). Hay `getUsuarioVinculado()` en Médico/Funcionario (para la regla del
login). `usuarios` apunta a `funcionario`/`medico` con FK sin acción (RESTRICT implícito) y `chk_usuario_persona_xor`.

### 1.3 Movimientos

| Pantalla | Prog. | Base | "Borrado" hoy | Auditoría | Estado/Reactivar | Tests | Permisos (M / R) |
|---|---|---|---|---|---|---|---|
| Registrar Agenda (`agenda_cabecera` + `agenda_detalle`) | Completa (cabecera, detalles, cupos, estado) | SB Admin (`app/templates/agenda/index.html`, 999 líneas; fuera de la carpeta de su blueprint) | Lógico por `estado` `'Activo'/'Inactivo'` en cabecera y `'Cancelado'` en detalle; único parcial por `estado`. Anular cancela detalles | No | `PATCH .../estado` existe pero exige **`anular`** (la ventana no expone `estado`) | No | M y R: ver/nuevo/anular |
| Gestionar Cita (`cita_cabecera` + `cita_detalle`) | Completa (cabecera, detalle por horario, estados, cupo atómico `restar/sumarCupo`, confirmadas sin consulta) | SB Admin (1.310 líneas, 124 usos de jQuery) | Lógico: cabecera `'Inactivo'`, detalle → estado `Cancelado` (devuelve cupo). `cita_cabecera`: **sin índice único** | No | `estado` por horario con permiso `estado` ✔; cabecera por `anular` | No (solo se ejercita por `smoke_consultorio`) | M y R: ver/nuevo/anular/estado |
| Gestionar Avisos y Recordatorios | Completa (CRUD, envío WhatsApp con Selenium, estadísticas, preview) | SB Admin (1.337 líneas). **Existe una copia muerta** en `rutas/referenciales/avisosRecordatorios/` | Lógico por `estado` `'Activo'/'Inactivo'`; sin único | No | `estado` ✔ | No | M y R: ver/nuevo/anular/estado |
| Registrar Historial Médico del Paciente (`historial_medico_paciente`; menú "Módulo Consultorio", código en Agendamiento) | Completa (documentos por tipo, alergias, medicamentos habituales, **archivos adjuntos**) | SB Admin (1.408 líneas) | Lógico por `estado` `'activo'/'inactivo'` (minúsculas; los otros usan mayúscula inicial) | No | No | No | M y R: ver/nuevo/anular. **Recepción lee historial clínico y adjuntos** (contradice la regla de privacidad de Consultorio) |

Comunes: el `PUT` de Agenda, Cita, Avisos e Historial exige `editar` y esas ventanas no lo exponen → solo
Administrador (documentado, pero la UI de edición hoy está visible para quien tenga la acción en la pantalla; a
verificar caso por caso). Varios GET usados como lookup tienen `@require_login` y devuelven datos sensibles:
`/agenda/cabeceras`, `/agenda/cabeceras/<id>/detalles`, `/citas/paciente/<id>`, `/citas-detalle/confirmadas-sin-consulta`
(cualquier rol logueado, incluido el Cajero, puede listar citas de un paciente).

### 1.4 Pantallas de Seguridad

| Pantalla | Base | Estado | Pendiente |
|---|---|---|---|
| Login, 2FA, Recuperar | Tabler (ya) | OK | — |
| Tablero de Accesos, Auditoría de Cambios, Copias de Seguridad | Tabler (ya) | OK | — |
| **Gestión de Usuarios** (`usuario-index.html`, 485 líneas) | **SB Admin (jQuery, 59 usos)** | Completa: alta, edición, baja/reactivar lógica, desbloqueo, CI/RUC y correo desde la persona | Migrar a Tabler; auditar con el formato nuevo (hoy solo audita el cambio de cédula y algo de permisos: 2 filas `usuarios`, 5 `permisos`); Estado/Mostrar inactivos |
| **Roles y Permisos** (matriz, `permiso-index.html`, 193 líneas) | **SB Admin** | Completa, `@require_admin` fijo | Migrar a Tabler; auditar con módulo+JSON (hay 5 filas viejas sin formato) |
| Roles (ABM) | — | **No existe**: los 4 roles son fijos (`CHECK` en `roles.nombre_rol`) | Decisión: queda fijo (ver preguntas) |
| Mantener Menú | — | Solo el buscador (`/menu/buscar`); la tabla `menu` existe pero no alimenta el sidebar | Pendiente ya anotado; **no entra** salvo que lo decidas |
| Ventanas `usuario` y `auditoria` | — | Están en el catálogo pero **no tienen fila en `menu`** (no se les pueden otorgar permisos) | Anotar; no cambia nada mientras sean solo-Administrador |
| Páginas de error 403/404/500 | SB Admin (standalone) y `base.html` | OK | Se mueven a Tabler cuando se retire `base.html` (fuera de alcance) |

### 1.5 Contradicciones entre el código y el estándar (lista consolidada)

1. 7 referenciales + Paciente/Médico/Funcionario con `DELETE` físico mientras la base ya tiene `activo`.
2. Índices únicos **no parciales**: `consultorio.correo`, `paciente.cedula_entidad`, `medico.cedula`,
   `funcionario.cedula`, `disponibilidad_horaria(uk_disponibilidad)`. Con baja lógica bloquearían el alta de un
   registro igual para siempre (regla 3).
3. Mensajes con ID crudo en todas las bajas y altas de referenciales (regla 6).
4. Botón "Eliminar" (`.btn-eliminar`) en vez de "Anular".
5. Sin validadores espejo ni normalización en `utils.py`.
6. Sin ninguna auditoría en `auditoria_cambios` en todo Agendamiento (y 48 filas históricas sin módulo → "Otro").
   Las entidades nuevas hay que sumarlas a `MODULO_POR_ENTIDAD`, `ETIQUETA_ENTIDAD` y `ENTIDADES_MOVIMIENTO`
   (`app/Services/auditoria_detalle.py`).
7. `PATCH .../estado` de Agenda exige `anular` en vez de `estado` (la ventana no lo expone).
8. Permisos demasiado amplios: **Médico** puede anular/editar Paciente, Funcionario, Médico y los 7 referenciales;
   **Recepción** puede anular/editar Médico y Funcionario; Recepción lee el historial clínico (privacidad).
9. Lookups con `@require_login` que exponen citas/agenda a cualquier rol.
10. Estados con tres convenciones (`Activo/Inactivo`, `activo/inactivo`, boolean `activo`) y `cita_cabecera`/
    `avisos` sin índice único ni borrado consistente.
11. Carpetas muertas (`rutas/referenciales/consultorio/`, `rutas/referenciales/avisosRecordatorios/`),
    `ciudad-agregar.html` sin uso aparente, `___init__.py` con tres guiones bajos en agenda, historial y cargo
    (el paquete funciona por ser namespace, pero es un error de tipeo), plantilla de Agenda fuera de su carpeta.
12. Hoy no hay ningún test de navegador (`browser_*`) ni smoke para los 7 referenciales, Médico, Funcionario,
    Agenda, Cita, Avisos ni Historial. Existen solo `smoke_consultorio.py` y `smoke_paciente.py`.
13. La ruta suelta `/vista` de `app/__init__.py` (ya anotada) y el pie "Conexión segura" del login no entran en esta migración.

---------------------------------------------------------------------------------------------------

## 2. Cómo se aplica el estándar (decisiones técnicas, ya resueltas)

- **Referenciales y personas**: columna `activo` + únicos parciales con `UPPER` (los de cédula/correo, sin `UPPER`);
  FK `RESTRICT`; `esta_en_uso()` devuelve `False` o el motivo, `deleteX()` devuelve `("EN_USO", motivo)` con la
  fila `FOR UPDATE`, y el alta/edición de los hijos toma `FOR SHARE` del padre; API compara `== "EN_USO"`;
  `?inactivos=1` exige `ver`; Reactivar valida duplicado y padres activos en una transacción (409);
  vista con `FacturacionListado` (se reutiliza el helper tal cual, sin copia nueva).
- **Qué cuenta como "en uso"** (cada uno con mensaje con datos descriptivos): Ciudad ← paciente, médico;
  Cargo ← funcionario; Especialidad ← médico, agenda; Consultorio ← agenda, avisos, caja, consultas, tratamientos;
  Día/Turno ← disponibilidad, agenda_detalle; Disponibilidad ← agenda_detalle; Paciente ← cliente, citas (no
  canceladas), consultas, tratamientos, diagnósticos, odontograma, avisos, historial; Médico ← usuario activo,
  agenda activa, disponibilidad, consultas, tratamientos, odontogramas, diagnósticos; Funcionario ← usuario activo,
  citas, consultas, tratamientos, avisos, agenda.
  Para que anular una Ciudad/Especialidad/etc. **no deje huérfano** a quien ya la usa, el listado de otras pantallas
  filtra `activo` (los combos) y los datos ya guardados siguen mostrando el nombre (JOIN sin filtrar `activo` en
  el detalle, con filtro solo en los combos).
- **Consultorio**: `CajaDao` documenta "consultorio activo = existe". Al pasar a lógico hay que actualizar ese
  comentario/consulta (JOIN de Caja y combos) — es una dependencia cruzada (regla 4).
- **Movimientos (Agenda, Cita, Avisos, Historial)**: **no se cambia el esquema de estado** (`estado` varchar ya
  tiene su CHECK y sus únicos parciales y `Cancelado`/cupo dependen de él). Se agrega Estado/badge,
  "Mostrar inactivos" y Reactivar donde el CUS lo permita (Agenda y Aviso se pueden reactivar; una cita Cancelada
  **no** se reactiva porque el cupo ya se devolvió, igual que "anulación definitiva"), y se corrigen permisos
  (`estado` en Agenda) con seed idempotente. Se unifica la capitalización del historial solo en la API/visual,
  no en la base.
- **Auditoría**: `utils.detalle_cambios()` + `utils.auditar` en alta/modificación/baja/reactivación de todo lo
  anterior. Nombres, no IDs. Entidades nuevas en las tres tablas de `auditoria_detalle.py`; módulo "Agendamiento"
  y "Referenciales Agendamiento". **Datos personales**: se audita quién, cuándo, nombre y N.º de documento; no
  teléfono, dirección ni correo. **Historial médico**: sin contenido clínico (solo tipo de documento y paciente),
  como Consultorio.
- **Permisos**: ventanas ya existen en `menu` y en el catálogo; se corrige el seed (nuevo
  `schema_permisos_agendamiento_tabler.sql`, idempotente, define el conjunto completo de Médico y Recepción para
  estas ventanas) según tu respuesta a las preguntas. El Cajero sigue sin nada de Agendamiento.
- **Concurrencia**: Cita ↔ cupo ya usa decremento atómico; se agrega revalidación del estado de la agenda/cita
  dentro de la transacción donde falte (a verificar en la Etapa 3) y orden de bloqueo por id.
- **Conexiones que no se rompen** (cada una con prueba explícita en su etapa):
  - cita → consulta: `getCitasConfirmadasSinConsulta`, `consultas_cab.id_cita` RESTRICT, y la cancelación de cita
    al finalizar/cancelar consulta (`'Realizado'`/`'Cancelado'`, reposición de cupo con `LEAST`).
  - paciente → cliente: `deletePaciente`/anular sigue bloqueado por `cliente`; el buscador `/clientes/pacientes`
    solo trae pacientes activos.
  - médico y funcionario → usuarios: CI/RUC y correo siguen saliendo de la persona; anular una persona
    con usuario activo se bloquea (ver pregunta 2); `crear usuario` solo ofrece personas activas.
  - cupo: `restarCupoAgendaDetalle`/`sumarCupoAgendaDetalle`/`actualizarCuposDisponibles` no se modifican.
- **Regresiones obligatorias al final de cada etapa**: todos los `smoke_*` de `tests/consultorio`,
  `tests/facturacion` y `tests/seguridad` + `smoke_consultorio` y `smoke_paciente`. Nada de lo que hoy pasa puede dejar de pasar.

---------------------------------------------------------------------------------------------------

## 3. Etapas (3, cada una con commit 1 backend/BD y commit 2 vistas; corro de corrido y freno al final de la etapa)

### Etapa 1 — Base de datos + 7 referenciales
**Commit 1 (base y backend)**
- `app/dao/modulo_agendamiento/schema_agendamiento_base.sql`: `CREATE TABLE IF NOT EXISTS` de las 17 tablas de
  Agendamiento (columnas, PK, FK, CHECK, secuencias, índices reales de hoy) y datos fijos (`estado_cita` 6 filas,
  días, turnos) con `ON CONFLICT DO NOTHING`.
- `app/dao/modulo_seguridad/schema_seguridad_base.sql`: `menu` y verificación/completado de `roles`, `usuarios`,
  `token_2fa`, `permisos` con el estado actual (`id_menu`, bloqueo, `chk_usuario_persona_xor`, `ux_menu_*`).
- `schema_agendamiento_etapa1.sql` (idempotente): `activo` donde falte (Disponibilidad), índices únicos **parciales**
  (consultorio.correo, y los de cédula en la Etapa 2), CHECK de días/turnos conservados.
- 7 DAOs reescritos al patrón (lógico, `?inactivos`, `esta_en_uso`, `FOR UPDATE/SHARE`, `reactivar`), APIs con
  `@require_permiso`, 409 con motivo, auditoría estructurada; entidades nuevas en `auditoria_detalle.py`;
  validadores en `utils.py`. Actualizar `CajaDao`/combos de Facturación por la dependencia de Consultorio.
- `tests/agendamiento/smoke_esquema_agendamiento.py` (reconstruye una base temporal desde los `schema_*.sql` en orden
  y compara columnas, índices, FK, CHECK y triggers contra `odontosisbd`; patrón de `smoke_esquema_consultorio.py`),
  `smoke_referenciales_agendamiento.py`, `smoke_permisos_agendamiento.py`.
**Commit 2 (vistas)**: 7 vistas Tabler con `facturacion-listado.js`, validadores JS espejo + comparador JS↔Py,
`browser_referenciales_agendamiento.py`; se retiran las plantillas SB Admin reemplazadas; se limpian las carpetas muertas
(`rutas/referenciales/consultorio`, `.../avisosRecordatorios`, `ciudad-agregar.html`, `___init__.py`).
**Frena con**: lista de pruebas a mano (alta/anular/reactivar/uso de cada referencial, combos de otras pantallas,
Caja con consultorio anulado, esquema en una base vacía).

### Etapa 2 — Paciente, Médico y Funcionario
**Commit 1**: `schema_agendamiento_etapa2.sql` (únicos parciales de cédula/correo con `WHERE activo`),
`esta_en_uso` completo de las tres personas con los mensajes con nombre/CI (arregla "No se encontró el médico con
el ID 19": 409 "El médico X no se puede anular: tiene N agendas…"), bloqueo por usuario activo, cédula cruzada
contra personas **activas**, auditoría estructurada con campos personales mínimos, quitar el `CASCADE` real
(las FK a paciente pasan a `RESTRICT`, previa verificación de que no haya huérfanos), tests
(`smoke_paciente_ext`, `smoke_medico`, `smoke_funcionario`, `smoke_personas_usuarios`).
**Commit 2**: 3 vistas Tabler (modal, validaciones, Estado, Mostrar inactivos, Reactivar), buscador de pacientes
para Cita/Consulta/Cliente/Historial verificado, `browser_personas.py`.

### Etapa 3 — 4 movimientos + Usuarios y Roles/Permisos
**Commit 1**: Estado/Reactivar y permisos (`estado` en Agenda, seed nuevo), auditoría estructurada de Agenda, Cita,
Avisos, Historial y de Usuarios/Permisos (que hoy solo audita 2+5 filas), lookups sensibles protegidos por permiso,
privacidad del historial según tu respuesta, `ENTIDADES_MOVIMIENTO` para que la BAJA diga "Anulado",
tests de cada movimiento (cupo, doble reserva concurrente, cita→consulta, cancelar cita al cancelar consulta,
anulación de agenda con citas, permisos por rol).
**Commit 2**: 6 vistas Tabler (Agenda 999, Cita 1.310, Avisos 1.337, Historial 1.408, Usuarios 485, Roles y Permisos 193
líneas) + `browser_*`. **Es la etapa más grande** (≈5.700 líneas de plantilla); si al llegar a ese punto la vista
de Cita o Historial resulta inmanejable la parto en dos commits 2 sin frenar, manteniendo "una etapa, un freno".

**Fuera de alcance** (para que no se asuma): Mantener Menú completo, HTTPS, rediseñar Selenium/WhatsApp, convertir
`estado_cita` en referencial editable, retirar `base.html`/SB Admin (las pantallas de error y cualquier pantalla no listada
siguen ahí hasta el cierre del proyecto).

---------------------------------------------------------------------------------------------------

## 4. Preguntas de negocio (lista corta; en cada una va mi recomendación)

1. **Día y Turno**: la base los limita por `CHECK` a 7 días y a MAÑANA/TARDE/NOCHE. ¿Los dejo como **catálogo fijo
   (solo ver y Estado, sin alta ni edición)** o con ABM completo? *Recomiendo catálogo fijo: un día o turno nuevo no
   tiene sentido de negocio y el ABM completo exigiría soltar el `CHECK`.*
2. **Anular un Médico o Funcionario que tiene usuario de acceso activo**: ¿se **bloquea** ("anule primero el
   usuario") o se **anula también el usuario** automáticamente? *Recomiendo bloquear, para que no se pierda un
   acceso sin que el Administrador lo decida.*
3. **Permisos**: hoy Médico y Recepción tienen casi todo (editar/anular) sobre referenciales y personas. ¿Qué
   queda? *Recomiendo: referenciales de Agendamiento y Médico/Funcionario → Administrador (editar/anular) y los
   demás roles solo `ver`; Paciente → Recepción `ver/nuevo/editar` y Médico `ver`; Agenda/Cita/Avisos → Recepción
   todo y Médico `ver` (+`estado` en Cita para marcar Realizado). Anular Paciente → solo Administrador.*
4. **Historial Médico del Paciente** (datos de salud + adjuntos): ¿**Recepción sin acceso** y Médico solo lee/crea/
   anula lo suyo, igual que Consultorio (Administrador solo lee)? *Recomiendo sí; hoy Recepción lo lee entero.*
5. **Cita Cancelada / Agenda Inactiva**: ¿pueden **reactivarse**? *Recomiendo: Agenda e Aviso sí (si no hay
   conflicto de médico y fecha); Cita cancelada no (el cupo ya se liberó; se crea una nueva).*
6. **Auditoría de datos personales**: ¿alcanza con quién, cuándo, nombre y cédula, **sin** teléfono, dirección ni
   correo en el detalle? *Recomiendo sí (misma lógica que el contenido clínico).*

Con esas 6 respuestas, más tu aprobación del plan, arranco la Etapa 1. Si alguna no te cierra, usá mi recomendación como default
y corregime solo lo que no.
