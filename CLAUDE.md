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
- ✅ Mantener Menú (buscador general del header, filtrado por rol/permisos):
  terminado y probado (catálogo fijo `CATALOGO_MENU` en código, sin tabla
  nueva; Administrador ve todo, el resto ve las pantallas abiertas más las
  de Seguridad solo si tiene el permiso correspondiente en `permisos`).

Con esto el Módulo Seguridad queda completo. Los próximos módulos a programar
son los funcionales grandes: Agendamiento, Consultorio, Facturación — ya
documentados en el análisis de la tesis.

## Pendiente de decidir a futuro: control de acceso en módulos grandes
Hoy Agendamiento, Referenciales y Consultorio NO tienen ninguna restricción
de rol en el código — cualquier usuario logueado (sin importar su rol) puede
entrar. Esto salió a la luz al programar Mantener Menú (buscar-only), que
respeta esta realidad en vez de inventar restricciones nuevas. Cuando se
encaren estos módulos a fondo, hay que definir con el análisis qué rol puede
acceder a qué pantalla, y aplicar el mismo patrón de decorator que ya existe
(`require_admin` en `app/rutas/modulo_seguridad/decorators.py`, más un
`require_login` más liviano agregado para Mantener Menú).
Ese `require_login` ya existe y está disponible para cuando se definan esas
restricciones: solo exige que haya sesión iniciada (cualquier rol), sin
restringir por rol — a diferencia de `require_admin`, que exige rol
Administrador.

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