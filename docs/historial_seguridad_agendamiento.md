# Historial de Seguridad y Agendamiento

> Leer al tocar acceso, usuarios, roles, agenda, citas, avisos o referenciales de Agendamiento.
> Movido tal cual desde `CLAUDE.md` (sin cambios de contenido) al reorganizarlo. La guía compacta es `CLAUDE.md`.

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

