# Copias de seguridad de OdontoClinic

Las copias se hacen con `pg_dump` en **formato custom** (`-Fc`: comprimido y restaurable con `pg_restore`, incluso una sola
tabla). Se guardan con fecha y hora en el nombre (`odontosisbd_AAAAMMDD_HHMMSS.dump`), se conservan las **últimas 7** y cada
ejecución queda en `backup.log` (OK o ERROR, archivo y tamaño).

## Cómo funciona

| Pieza | Qué es |
|---|---|
| `app/Services/backup_service.py` | La lógica (la usan el script y la pantalla). |
| `scripts/backup_db.py` | Genera una copia; sale con código 0 (OK) o 1 (ERROR). |
| `scripts/backup_diario.bat` | Lo que ejecuta el Programador de tareas. |
| Pantalla **Copias de Seguridad** (Módulo Seguridad) | Solo el Administrador: lista de copias con fecha y tamaño y el botón *Generar backup ahora* (queda auditado en `auditoria_cambios`). **No restaura**: la restauración es solo manual, con esta guía. |

### Credenciales (archivo `.env`)

El backup usa su **propio rol de solo lectura**, `odontoclinic_backup` (miembro de `pg_read_all_data`; no puede modificar nada).
La contraseña se pasa a `pg_dump` por la variable de entorno `PGPASSWORD` del proceso hijo: **no aparece en la línea de
comandos, ni en `backup.log`, ni en los mensajes de error**.

```
BACKUP_DB_USER=odontoclinic_backup
BACKUP_DB_PASSWORD=<la contraseña del rol>
BACKUP_DIR=C:\OdontoClinic\backups
PG_BIN_DIR=C:\Program Files\PostgreSQL\14\bin
```

`PG_BIN_DIR` debe ser la carpeta `bin` de **la misma versión que el servidor** (esta base corre en PostgreSQL 14; en la
máquina hay también 13 y 16, y el `pg_dump` que aparece primero en el PATH es el 16). El rol se crea con
`python -m app.dao.modulo_seguridad.crear_usuario_app` (ver `docs/acceso_red.md` y CLAUDE.md).

### Por qué `BACKUP_DIR` va FUERA de la carpeta del proyecto

El proyecto está dentro de **OneDrive**, que sincroniza todo lo que haya en esa carpeta con la nube de Microsoft. Una copia de
la base contiene **datos personales y clínicos de los pacientes** y los hashes de las contraseñas: no debe subirse a un servicio
de terceros sin control. Por eso las copias van a `C:\OdontoClinic\backups`, que no se sincroniza (tampoco entra en git: la
carpeta `backups/` está en `.gitignore` por si alguien la usa dentro del proyecto). Si querés una copia fuera de la máquina,
llevala a un disco externo o a un almacenamiento de la clínica, con control de acceso.

## Programar la copia diaria a las 23:00 (Programador de tareas de Windows)

1. Abrí **Programador de tareas** (`taskschd.msc`) → **Crear tarea…** (no “tarea básica”).
2. **General:** nombre `OdontoClinic - Backup diario`. Marcá **Ejecutar tanto si el usuario inició sesión como si no** y
   **Ejecutar con los privilegios más altos** si el usuario no es administrador de la PC.
3. **Desencadenadores → Nuevo:** *Diariamente*, inicio **23:00:00**, repetir cada 1 día.
4. **Acciones → Nueva:** *Iniciar un programa*.
   - Programa o script: `C:\Users\Usuario\OneDrive\Documentos\Proyectos\PROYECTO_TALLER\scripts\backup_diario.bat`
     (ajustá la ruta a donde esté el proyecto).
   - Iniciar en: la carpeta del proyecto (`...\PROYECTO_TALLER`).
5. **Condiciones:** si es una notebook, desmarcá *Iniciar la tarea solo si el equipo está con corriente alterna*.
   **Configuración:** marcá *Ejecutar la tarea lo antes posible si se omitió un inicio programado* (así, si la PC estaba apagada a
   las 23:00, hace la copia al encenderse).
6. Aceptá (pide la contraseña de Windows si elegiste “ejecutar tanto si inició sesión como si no”).
7. **Probala:** clic derecho sobre la tarea → *Ejecutar*. Mirá la columna *Último resultado* (`0x0` = OK) y el archivo
   `BACKUP_DIR\backup.log`.

Por línea de comandos (equivalente, en una consola de administrador):

```
schtasks /Create /TN "OdontoClinic - Backup diario" /TR "C:\ruta\al\proyecto\scripts\backup_diario.bat" /SC DAILY /ST 23:00
```

### Controlar que se hacen

- `BACKUP_DIR\backup.log` — una línea por ejecución: `2026-10-24 23:00:02 OK archivo=odontosisbd_20261024_230001.dump tamano=445055 bytes`
  o `... ERROR <motivo>`.
- La pantalla *Copias de Seguridad* muestra las últimas 7.

## Restaurar una copia

> La restauración **no se hace desde la web** a propósito: reemplaza datos y debe hacerla una persona, sabiendo qué hace.
> Usá siempre el `pg_restore` de la **misma versión del servidor** (`PG_BIN_DIR`). Todo se ejecuta con el usuario `postgres`.

### A) Probar una copia en una base temporal (no toca la real) — recomendado antes de cualquier restauración

```
set PGPASSWORD=<contraseña de postgres>
"C:\Program Files\PostgreSQL\14\bin\createdb.exe" -h 127.0.0.1 -p 5432 -U postgres odontosisbd_restore_test
"C:\Program Files\PostgreSQL\14\bin\pg_restore.exe" -h 127.0.0.1 -p 5432 -U postgres -d odontosisbd_restore_test --exit-on-error C:\OdontoClinic\backups\odontosisbd_AAAAMMDD_HHMMSS.dump
```

Compará la cantidad de filas con la original (en `psql`, conectado a cada base):

```sql
SELECT 'usuarios' t, count(*) FROM usuarios UNION ALL SELECT 'paciente', count(*) FROM paciente
UNION ALL SELECT 'venta_cab', count(*) FROM venta_cab UNION ALL SELECT 'cobro_cab', count(*) FROM cobro_cab;
```

Cuando termines, **borrá la base temporal**:

```
"C:\Program Files\PostgreSQL\14\bin\dropdb.exe" -h 127.0.0.1 -p 5432 -U postgres odontosisbd_restore_test
```

### B) Restaurar sobre la base real (después de una pérdida de datos)

1. **Frená la aplicación** (cerrá `run.py`) y avisá a los usuarios: nadie debe estar conectado.
2. Hacé una copia de lo que haya ahora, por si acaso (`scripts\backup_db.py`).
3. Recreá la base vacía y restaurá:

```
set PGPASSWORD=<contraseña de postgres>
"C:\Program Files\PostgreSQL\14\bin\dropdb.exe"   -h 127.0.0.1 -p 5432 -U postgres odontosisbd
"C:\Program Files\PostgreSQL\14\bin\createdb.exe" -h 127.0.0.1 -p 5432 -U postgres odontosisbd
"C:\Program Files\PostgreSQL\14\bin\pg_restore.exe" -h 127.0.0.1 -p 5432 -U postgres -d odontosisbd --exit-on-error C:\OdontoClinic\backups\odontosisbd_AAAAMMDD_HHMMSS.dump
```

4. Los roles `odontoclinic_app` y `odontoclinic_backup` **son del servidor, no de la base**: sobreviven a `dropdb`. Sus permisos
   sobre las tablas se restauran con la copia. Si restaurás en **otro servidor**, creá antes los roles y reaplicá los permisos:
   `python -m app.dao.modulo_seguridad.crear_usuario_app`.
5. Arrancá la aplicación y entrá con un usuario para verificar.

Para restaurar **una sola tabla** (por ejemplo, `paciente`) sin tocar el resto:
`pg_restore ... -d odontosisbd --data-only -t paciente archivo.dump` (con la tabla vacía; revisá las claves foráneas antes).

## Prueba de restauración realizada

Se restauró una copia real en `odontosisbd_restore_test` y se comparó con la base original: las **77 tablas** tienen la misma
cantidad de filas, y coinciden las vistas, funciones/procedimientos y triggers; los permisos del rol de la aplicación (sin
`UPDATE` sobre las auditorías) también volvieron. La base temporal se borró. `tests/seguridad/smoke_backup.py` repite esta
prueba cada vez que se corre.
