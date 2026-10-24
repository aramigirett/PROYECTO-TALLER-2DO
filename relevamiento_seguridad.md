# Tanda de cierre, Etapa A: Seguridad de acceso — Relevamiento y plan

Solo lectura: no se modificó código ni base de datos.

## Estado actual

### 1. Contraseñas — ya cumple, no hace falta migración
- Los 5 usuarios de la base tienen hash `scrypt:32768:8:1` con salt propio, generado con `generate_password_hash` de Werkzeug en alta, edición, recuperación y `seed_admin_usuario.py`.
- No hay texto plano ni hash débil. La verificación usa `check_password_hash`.

### 2. Cierre de sesión por inactividad — no existe
- No hay `PERMANENT_SESSION_LIFETIME`, ni `before_request`, ni JS de timeout.
- La sesión es la cookie firmada de Flask, sin vencimiento de actividad.
- Solo existe `/logout`, que audita `LOGOUT`.
- Hay dos bases con scripts propios: `base.html` (SB Admin, jQuery) y `base_tabler.html` (Bootstrap 5). Login, 2FA y recuperación son páginas standalone.

### 3. Validación de IP por país — no existe
- El login usa `request.remote_addr` solo para auditar.
- No hay librería GeoIP ni archivo `.mmdb` en el proyecto.
- `auditoria_acceso` no tiene columna de país. `resultado` es `VARCHAR(30)` sin CHECK, así que `IP_NO_PERMITIDA` cabe sin cambios.
- El tablero tiene filtro de fechas, pero no de resultado.
- **Tabla `paises`:** 1 fila (`16, PARAGUAY, activo`), sin código ISO y sin FKs. Ningún código de `app/` la usa. **No sirve para esto**: un GeoIP devuelve códigos ISO ("PY") y la tabla no los tiene.

### 4. Recordar usuario — no existe
El login no tiene checkbox ni cookie.

### 5. HTTPS
Nada que implementar. Falta solo la nota en CLAUDE.md.

### Hallazgo extra: `SECRET_KEY`
El `.env` solo tiene `MAIL_*`. `app/__init__.py` cae al valor por defecto `'dev-secret-key-cambiar-en-produccion'`, que está en el repo. Cualquiera que lo lea puede falsificar cookies de sesión. Propuesta: agregar `SECRET_KEY` al `.env` con un valor aleatorio.

## Plan

1. **`.env`:** variables nuevas `SECRET_KEY`, `SESSION_INACTIVIDAD_MINUTOS=15`, `SESSION_AVISO_SEGUNDOS=60`, `PAIS_PERMITIDO=PY`, `GEOIP_DB_PATH`, `IP_SIMULADA` (solo se lee con `app.debug`) y `RECORDAR_USUARIO_DIAS=30`. Más un `.env.example` sin secretos.
2. **GeoIP:** librería `maxminddb` y la base **DB-IP Lite Country** (`.mmdb`, gratuita, sin registro, licencia CC-BY). Se guarda en una carpeta `geoip/` fuera de `static` y se agrega a `.gitignore`. Módulo `app/Services/geoip_service.py`; IP privadas, loopback y link-local se permiten sin consultar. El chequeo corre en un `before_request` sobre las rutas de acceso, antes de leer usuario o contraseña. Resultado cacheado por IP.
3. **Auditoría:** script SQL idempotente que agrega `auditoria_acceso.pais_detectado VARCHAR(2)` y un índice por `resultado`. `AuditoriaDao.registrar` recibe el país. El tablero suma la columna País y un filtro de resultado (Todos, Exitosos, Fallidos, `IP_NO_PERMITIDA`, `CIERRE_INACTIVIDAD`); `GET /auditoria/intentos?resultado=` lo acepta.
4. **Inactividad:**
   - El servidor guarda `ultima_actividad` en la sesión y la renueva en cada request, salvo en un endpoint de ping que no la renueva. Pasados 15 minutos cierra la sesión, audita `CIERRE_INACTIVIDAD` y redirige al login con "Sesión cerrada por inactividad". En `/api/` responde 401 JSON con un código que el JS reconoce.
   - Un único `inactividad.js` con modal propio (HTML/CSS, sin depender de Bootstrap 4 ni 5), incluido en `base.html` y `base_tabler.html`. Cuenta regresiva desde 60 s y botón "Seguir conectado", que llama a un endpoint para renovar la sesión. Al llegar a 0 va al login. Los minutos los toma de la configuración del servidor.
   - La actividad del usuario (clicks, teclas) renueva el contador y avisa al servidor, máximo una vez por minuto, para no expulsar a quien llena un formulario largo sin hacer requests.
5. **Recordar usuario:** checkbox en `login.html`. La cookie `oc_usuario` guarda solo el CI/RUC: 30 días, `HttpOnly`, `SameSite=Lax`, `Secure` según configuración. Precarga el campo y marca el checkbox; desmarcarlo la borra. También se fijan `SESSION_COOKIE_HTTPONLY` y `SESSION_COOKIE_SAMESITE=Lax`.
6. **CLAUDE.md:** sección de HTTPS (justificación de red local y cómo activarlo con certificado y proxy inverso como Nginx o Caddy, más `SESSION_COOKIE_SECURE`), la IP por país deja de estar descartada, y estado de las 5 rúbricas.
7. **Tests y cierre:** `tests/seguridad/smoke_inactividad.py` y `smoke_ip_pais.py`, más regresión completa de `tests/`. Luego `resumen_seguridad.md` sin commitear.

## Decisiones de negocio pendientes

1. **IP pública que no se puede geolocalizar** (no figura en la base o falta el `.mmdb`): ¿permitir o bloquear? Recomendación: **permitir y registrar una advertencia**, para que un archivo faltante no deje afuera a toda la clínica.
2. **Tabla `paises`:** no sirve para esto. ¿Eliminarla del DER y de la base, o dejarla sin usar? Recomendación: eliminarla (1 fila, sin referencias). El país permitido queda solo en `.env` como código ISO.
3. **Mensaje genérico de rechazo por IP:** propuesta "No es posible acceder al sistema desde esta ubicación." ¿Se deja así o se prefiere otro texto?

## Nota
Hay que descargar el `.mmdb` de DB-IP (unos pocos MB). Sin internet en el entorno, se copia a mano a la carpeta `geoip/`. Los tests de IP usan IPs simuladas y no dependen del archivo.
