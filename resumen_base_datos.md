# Resumen — Tanda de cierre, Etapa B: Base de datos

Rama `finalizando`. Código y guías commiteados en `6ff1aa1`; **este resumen y `plan_base_datos.md` quedan sin commitear**.
Regresión completa: **25 scripts `smoke_*.py`, todos con `FALLOS: ninguno`** (incluye `smoke_permisos_app` y `smoke_backup`, nuevos).

## 1. Usuario propio de la aplicación
- Roles `odontoclinic_app` (la app) y `odontoclinic_backup` (solo lectura, `pg_read_all_data`). Ambos `LOGIN`, sin superusuario,
  `CREATEDB`, `CREATEROLE`, `REPLICATION` ni `BYPASSRLS`.
- `schema_usuario_app.sql` (idempotente, **sin contraseñas**): `SELECT/INSERT/UPDATE/DELETE` en tablas, solo `SELECT` en vistas,
  `USAGE/SELECT` en secuencias, `EXECUTE` en funciones y procedimientos, **solo `SELECT/INSERT` en `auditoria_cambios` y
  `auditoria_acceso`**, `CREATE` revocado a `PUBLIC` en `public` y `ALTER DEFAULT PRIVILEGES` para objetos futuros de postgres.
- `crear_usuario_app.py` aplica el script y fija las contraseñas por la conexión (variable de entorno o por teclado).
- La app conecta como `odontoclinic_app` (verificado con `current_user`). Migraciones y tests usan postgres vía `TEST_DB_*`
  (`ConexionAdmin`, `tests/_conexion_pruebas.py`; 22 tests cambiaron solo su `import`).
- **DDL en el código:** se buscó `CREATE/ALTER/DROP/TRUNCATE` en `app/` y **no hay ninguno** (ni al arrancar ni en DAOs): no hubo
  nada que mover a migraciones.
- **Contraseñas:** las generé yo (aleatorias, 32 caracteres) sin pedírtelas, y quedaron solo en `.env`. Detalle y cómo rotarlas
  en la respuesta del chat.
- Regresión de permisos: todas las pantallas del menú y las APIs de lectura recorridas con el rol de la app sin ningún 500, y los
  25 scripts de escritura pasan con ese rol.

## 2. Copias de seguridad
- `backup_service.py`: `pg_dump -Fc` → `odontosisbd_AAAAMMDD_HHMMSS.dump`, retención de 7, `backup.log` (OK/ERROR, archivo,
  tamaño). Contraseña solo por `PGPASSWORD` del proceso hijo (no sale en comandos, logs ni errores).
- `scripts/backup_db.py` (código 0/1) y `scripts/backup_diario.bat` para las 23:00. **La tarea programada no está creada**: pasos en
  `docs/backups.md`.
- `BACKUP_DIR=C:\OdontoClinic\backups` (fuera de OneDrive; motivo en la guía). `PG_BIN_DIR` apunta a PostgreSQL 14.
- Pantalla **Copias de Seguridad** (Tabler, solo Administrador, auditada en `auditoria_cambios`); no restaura.
- **Restauración probada** en `odontosisbd_restore_test`: mismas filas en las 77 tablas, mismas vistas/funciones/triggers y
  permisos; base temporal borrada. Procedimiento en la guía.
- Se corrigió durante las pruebas: `pg_dump` en Windows habla en cp1252 (los mensajes de error salían con caracteres rotos).

## 3. Acceso por red
- Solo `docs/acceso_red.md` (no se tocó ningún archivo de PostgreSQL). Hoy: PostgreSQL 14, `listen_addresses='*'` pero
  `pg_hba.conf` solo admite localhost → sin acceso por red. Guía: `listen_addresses`, una línea
  `host odontosisbd odontoclinic_app <subred> scram-sha-256`, regla de firewall al 5432 solo desde la subred y `DB_HOST` en la otra PC.

## Archivos
Nuevos: `schema_usuario_app.sql`, `crear_usuario_app.py`, `schema_permisos_backup.sql`, `ConexionAdmin.py`, `backup_service.py`,
`backup_routes.py`, `backup_api.py`, `backup-index.html`, `scripts/backup_db.py`, `scripts/backup_diario.bat`, `docs/backups.md`,
`docs/acceso_red.md`, `tests/_conexion_pruebas.py`, `tests/seguridad/smoke_permisos_app.py`, `smoke_backup.py`.
Modificados: `.env.example`, `.gitignore`, `CLAUDE.md`, `menu_catalog.py` (ventana `solo_admin`), `permisos_contexto.py`,
`permiso_api.py`, `app/__init__.py`, `tests/README.md` y los 22 tests (`import`).

## Rotación de la contraseña de `postgres` y auditoría del historial de git
- **Rotada** (por el usuario). Verificado sin mostrar valores: `ConexionAdmin` (`TEST_DB_*`) conecta como `postgres` con la clave
  nueva, la anterior es **rechazada por el servidor**, y la app sigue conectando como `odontoclinic_app`.
- **Historial (74 commits, todas las ramas).** Valores del `.env` buscados en todo el historial:

  | Secreto | Commits que lo contienen |
  |---|---|
  | `MAIL_PASSWORD`, `MAIL_USERNAME` | 0 |
  | `SECRET_KEY` actual, `DB_PASSWORD`, `BACKUP_DB_PASSWORD`, `TEST_DB_PASSWORD` (nueva) | 0 |
  | Clave anterior de `postgres` | 3 (`Conexion.py` desde el primer commit y 2 líneas de `smoke_acceso_basico.py`) → ya **inútil**, rotada |
  | Clave de Flask de desarrollo escrita en `login_routes.py` (otro valor, no el actual) | 2 (`8f30c49` la agrega, `9f054d4` la quita) → ya no firma nada |
  | Clave por defecto pública `dev-secret-key-cambiar-en-produccion` en `app/__init__.py` | 3 → ya no se usa (hay `SECRET_KEY` aleatoria en `.env`) |

  También se buscó por patrón (`password/secret/token/api_key/credential = "literal"`): fuera de lo anterior solo salieron
  falsos positivos de librerías (`bootstrap` y `fontawesome`). **Ningún archivo sensible** (`.env`, claves, bases, sesiones de
  WhatsApp, cookies) se versionó nunca. Con la rotación hecha no hace falta reescribir el historial.

## Pendiente / a tener en cuenta
- **Crear la tarea programada** de las 23:00 y probarla (guía paso a paso).
- **Reiniciar `run.py`** en los servidores ya abiertos: conservan las credenciales viejas.
- Una tabla de auditoría nueva hay que agregarla a la lista del script `schema_usuario_app.sql`.
- Ruta suelta `/vista` de `app/__init__.py`: falla con cualquier usuario (falta `stats`); no es de permisos y no se tocó.
- Rúbricas 3 (Base de datos) y 8 (Seguridad) anotadas como completas en CLAUDE.md.
