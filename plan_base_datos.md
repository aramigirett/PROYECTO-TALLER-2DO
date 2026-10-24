# Tanda de cierre, Etapa B: Base de datos — Relevamiento y plan

Solo lectura: no se modificó código ni base de datos.

## Estado actual

- **Servidor:** PostgreSQL **14.12** en el puerto 5432. El `pg_dump` del PATH es el de la versión 16; en la máquina hay también servidores 13 y 16, y algo escucha en el 5433. Se usarán los binarios de la 14 (ruta configurable en `.env`).
- **Roles:** existe un solo rol, `postgres` (superusuario). La app se conecta con él.
- **Objetos:** todos son de `postgres`. 77 tablas, 76 secuencias, 5 vistas, 28 funciones y 2 procedimientos (`sp_registrar_arqueo`, `sp_siguiente_numero_factura`). Ninguna función es `SECURITY DEFINER`. No hay privilegios por defecto configurados.
- **Esquema `public`:** en la versión 14 cualquier rol puede crear tablas ahí (`CREATE` dado a `PUBLIC`). Se revocará.
- **Auditoría:** `auditoria_cambios` y `auditoria_acceso` ya tienen el trigger `trg_auditoria_inmutable`.
- **Acceso por red:** `listen_addresses = '*'`, pero `pg_hba.conf` solo admite `127.0.0.1` y `::1`: hoy no entra nadie por red.
- **Pruebas:** 22 tests abren su propia conexión con `Conexion()`. Varios necesitan superusuario (`session_replication_role` para borrar su auditoría; uno crea y borra una base temporal).
- **Carpetas:** `backups/` y `docs/` no existen. El proyecto está dentro de OneDrive.

## Plan

### 1. Usuario propio de la aplicación
- `app/dao/modulo_seguridad/schema_usuario_app.sql` (idempotente, **sin contraseña**):
  - Crea `odontoclinic_app`: `LOGIN`, sin superusuario, sin `CREATEDB`, sin `CREATEROLE`, sin `REPLICATION`.
  - `SELECT/INSERT/UPDATE/DELETE` en las tablas, `USAGE/SELECT` en las secuencias, `EXECUTE` en funciones y procedimientos.
  - En `auditoria_cambios` y `auditoria_acceso`: solo `SELECT/INSERT` (doble protección con el trigger).
  - `REVOKE CREATE ON SCHEMA public FROM PUBLIC`.
  - `ALTER DEFAULT PRIVILEGES FOR ROLE postgres` para tablas, secuencias y funciones futuras.
- `crear_usuario_app.py`: aplica el SQL y fija las contraseñas por la conexión (nunca en comandos). Las toma de una variable de entorno o las pide al ejecutarlo.
- Separación app / pruebas:
  - `tests/_conexion_pruebas.py` con una clase `Conexion` que usa `TEST_DB_USER` / `TEST_DB_PASSWORD`.
  - En cada test se cambia solo la línea del `import`.
  - La app y los DAO que importan los tests siguen con `odontoclinic_app`, así la regresión prueba los permisos de verdad.
- `.env`: `DB_USER` / `DB_PASSWORD` pasan a ser los del rol nuevo; se agregan `TEST_DB_*` y `BACKUP_DB_*`. `.env.example` actualizado sin valores.
- `tests/seguridad/smoke_permisos_app.py`:
  - Atributos del rol.
  - Rechazo de `UPDATE`, `DELETE`, `TRUNCATE`, `CREATE` y `DROP` donde corresponde.
  - Privilegios por defecto sobre una tabla de prueba creada y borrada.
  - Regresión completa de todas las pantallas y movimientos.

### 2. Copias de seguridad
- Rol `odontoclinic_backup`: solo lectura, miembro de `pg_read_all_data` (existe desde la versión 14).
- `app/Services/backup_service.py`:
  - `pg_dump -Fc` a la carpeta de backups, archivo `odontosisbd_AAAAMMDD_HHMMSS.dump`.
  - Contraseña por `PGPASSWORD` en el proceso hijo, nunca en argumentos ni logs.
  - Retención de los últimos 7.
  - `backup.log` con OK/ERROR, archivo y tamaño.
- `scripts/backup_db.py` y `scripts/backup_diario.bat` (para las 23:00).
- `docs/backups.md`: pasos del Programador de tareas de Windows y procedimiento de restauración. La tarea programada no se crea desde acá: queda documentada.
- Pantalla "Copias de Seguridad" (Tabler, solo Administrador):
  - Lista de archivos con fecha y tamaño.
  - Botón "Generar backup ahora", auditado en `auditoria_cambios`.
  - Entrada en `menu_catalog.py`, fila en `menu` y permisos solo para Administrador.
  - La restauración **no** se hace desde la web.
- Prueba de restauración real en `odontosisbd_restore_test`: comparar filas de las tablas principales con la original y borrar la base temporal.
- `tests/seguridad/smoke_backup.py`.

### 3. Acceso por red
- Solo la guía `docs/acceso_red.md`, con las rutas reales de la 14:
  - `listen_addresses` en `postgresql.conf`.
  - `pg_hba.conf`: `host odontosisbd odontoclinic_app <subred> scram-sha-256`.
  - Regla del firewall de Windows para el puerto 5432.
  - Cómo apuntar `DB_HOST` desde otra PC.
- No se edita ningún archivo de PostgreSQL. Subred de ejemplo: `192.168.1.0/24`.

### 4. Cierre
- CLAUDE.md: usuario de la app, backups, acceso por red y estado de las rúbricas 3 y 8.
- Regresión completa.
- `resumen_base_datos.md`, sin commitear.

## Decisiones pendientes

1. **Carpeta de los backups.** El proyecto está en OneDrive, así que `backups/` se sincronizaría a la nube con datos de pacientes. Recomendación: carpeta configurable (`BACKUP_DIR` en `.env`) apuntando fuera de OneDrive, por ejemplo `C:\OdontoClinic\backups`. Alternativa: `backups/` dentro del proyecto, como se pidió.
2. **Rúbricas 3 y 8.** CLAUDE.md no dice a qué corresponde cada número. Si no se aclara, se anotan por nombre ("usuario de BD con mínimo privilegio" y "copias de seguridad").
