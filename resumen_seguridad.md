# Resumen — Tanda de cierre, Etapa A: Seguridad de acceso

Rama `finalizando`. **Sin commitear.** Regresión completa: 23 scripts `smoke_*.py`, todos con `FALLOS: ninguno`
(los 3 nuevos: `smoke_inactividad` 49 chequeos, `smoke_ip_pais` 53, `smoke_acceso_basico` 28).

## 1. Contraseñas — ya cumplía
Los 5 usuarios tienen hash `scrypt:32768:8:1` con salt propio (`generate_password_hash`). Sin texto plano ni hash débil: no hizo
falta migración. Verificado por `smoke_acceso_basico`.

## 2. Cierre por inactividad
- Servidor (`sesion_seguridad.py`, `before_request`): pasados `SESSION_INACTIVIDAD_MINUTOS` (**30**) sin actividad limpia la sesión,
  audita `CIERRE_INACTIVIDAD` y redirige a `/login` con "Sesión cerrada por inactividad" (401 JSON en `/api/`).
- Cliente (`static/js/inactividad.js` + `templates/_inactividad.html`, incluido en `base.html` y `base_tabler.html`): a
  `SESSION_AVISO_SEGUNDOS` (**120**) del vencimiento, modal propio con cuenta regresiva y "Seguir conectado". Funciona en
  Bootstrap 4 y 5 (no depende de ninguno). Endpoints: `/sesion/estado` (no renueva), `/sesion/extender`, `/sesion/expirar`.
- Probado: lógica del servidor, config por `.env`, presencia en ambas bases y el modal en Edge headless con reloj/red simulados.

## 3. Validación de IP por país
- `app/Services/geoip_service.py` + base local DB-IP Lite Country (`geoip/dbip-country-lite.mmdb`, `maxminddb`). Sin APIs externas.
- País permitido: `PAIS_PERMITIDO=PY`. Red privada/loopback/link-local: siempre permitida.
- Es lo primero de `/login`, `/verificar-2fa` y `/recuperar*`. Rechazo: 403 con "No es posible acceder al sistema desde esta ubicación."
  y fila `IP_NO_PERMITIDA` (usuario si lo ingresó, IP, país, fecha/hora). IP pública no resuelta: se permite y queda
  `IP_SIN_GEOLOCALIZAR`.
- Tablero: columna País y filtro por resultado (`?resultado=`). `auditoria_acceso.pais_detectado VARCHAR(2)` (script
  `schema_ip_inactividad.sql`).
- Prueba: `IP_SIMULADA` en `.env`, solo con la app en modo debug.
- **Tabla `paises` eliminada** (`schema_eliminar_paises.sql`, verifica referencias; no tenía ninguna).
- Atribución CC-BY de DB-IP: pie del login y CLAUDE.md.

## 4. Recordar usuario
Checkbox en el login; al completar el 2FA se guarda la cookie `oc_usuario` con solo el CI/RUC (30 días, HttpOnly, SameSite=Lax).
Sin marcar se borra. Nunca contraseña ni código 2FA.

## 5. HTTPS
No se implementa (red local). Justificación y pasos de producción (WSGI + proxy inverso con TLS + `ProxyFix` + `COOKIE_SECURE=true`)
en CLAUDE.md.

## Ajustes pedidos
- `Conexion.py` lee `DB_HOST/PORT/NAME/USER/PASSWORD` de `.env` (error claro si falta); `.env.example` sin valores; `.env` y
  `geoip/` en `.gitignore` y fuera de git.
- `SECRET_KEY`: valor fijo quitado del código; sin ella la app no arranca (salvo modo debug, `run.py` fija `FLASK_DEBUG=1`).
  Se generó una clave aleatoria en `.env`.

## Archivos
Nuevos: `app/Services/geoip_service.py`, `app/rutas/modulo_seguridad/sesion_seguridad.py`, `app/static/js/inactividad.js`,
`app/templates/_inactividad.html`, `schema_ip_inactividad.sql`, `schema_eliminar_paises.sql`, `.env.example`, `tests/seguridad/*`.
Modificados: `.gitignore`, `CLAUDE.md`, `app/__init__.py`, `Conexion.py`, `AuditoriaDao.py`, `auditoria_api.py`, `seguridad_routes.py`,
`auditoria-index.html`, `login.html`, `base.html`, `base_tabler.html`, `paquetes.txt`, `run.py`, `tests/README.md`.

## Pendiente / a tener en cuenta
- **DER:** quitar `paises` y agregar `auditoria_acceso.pais_detectado`.
- El pie del login dice "Conexión segura" aunque no hay HTTPS: conviene cambiar el texto.
- Refrescar la base GeoIP de vez en cuando (DB-IP publica una nueva por mes).
- Sigue pendiente de la tanda de cierre: usuario de base de datos propio de la app, sin superusuario.
- El `.env` actual sigue usando el usuario `postgres`; ahora la contraseña vive ahí y no en el código.
