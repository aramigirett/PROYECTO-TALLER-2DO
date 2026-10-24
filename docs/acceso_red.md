# Acceso a la base de datos por red local

Guía para que **otra PC de la clínica** (por ejemplo, la de Recepción con la aplicación instalada) use la base de datos que corre
en la PC servidor. **Nada de esto está aplicado**: el proyecto no modifica archivos de PostgreSQL; los cambios los hace a mano
quien administra el servidor, con esta guía.

## Cómo está hoy (verificado)

- Servidor: **PostgreSQL 14** (servicio `postgresql-x64-14`), puerto **5432**, datos en `C:\Program Files\PostgreSQL\14\data`.
  Ojo: en la misma PC hay también un servidor 16 (`postgresql-x64-16`, otro puerto) y una 13 instalada. **Editá siempre los
  archivos de la carpeta de la 14**; en `psql`: `SHOW config_file;` y `SHOW hba_file;` confirman cuáles son.
- `listen_addresses = '*'` (escucha en todas las interfaces), pero `pg_hba.conf` solo admite `127.0.0.1` y `::1`, así que **desde
  la red hoy no entra nadie**. Para abrir el acceso hay que tocar `pg_hba.conf` (paso 2) y el firewall (paso 3).
- La aplicación usa el usuario `odontoclinic_app` (sin superusuario, sin DDL). `postgres` **no** debe poder entrar por red.
- Red de la PC servidor al momento de escribir esta guía: `192.168.100.80/24` (Wi-Fi). Usá la tuya en todos los ejemplos.

## 0. Antes de empezar

1. **IP fija para el servidor.** Si la IP del servidor cambia, las demás PC dejan de conectarse. Reservala en el router (reserva
   DHCP por MAC) o asignala manualmente en Windows.
2. Que existan los roles de la aplicación: `python -m app.dao.modulo_seguridad.crear_usuario_app` (ver CLAUDE.md).
3. Hacé una copia de los dos archivos que vas a editar (`postgresql.conf.bak`, `pg_hba.conf.bak`).

## 1. `postgresql.conf` — en qué interfaces escucha

Archivo: `C:\Program Files\PostgreSQL\14\data\postgresql.conf`

```
listen_addresses = 'localhost,192.168.100.80'   # la IP del servidor en la red local (en vez de '*')
port = 5432
password_encryption = scram-sha-256             # ya está así
```

`'localhost,<IP del servidor>'` escucha solo en el propio equipo y en la tarjeta de la red local. Es más estricto que `'*'`, que
también escucharía en cualquier otra interfaz (VPN, otra red, etc.).

## 2. `pg_hba.conf` — quién puede entrar, desde dónde y cómo

Archivo: `C:\Program Files\PostgreSQL\14\data\pg_hba.conf`. PostgreSQL lee las reglas **de arriba hacia abajo**: dejá las que ya
están (acceso local con `scram-sha-256`) y **agregá una sola línea** debajo de las de `127.0.0.1`:

```
# TIPO   BASE          USUARIO           ORIGEN               MÉTODO
host     odontosisbd   odontoclinic_app  192.168.100.0/24     scram-sha-256
```

- **Solo la red local** (`192.168.100.0/24`; ajustala a tu subred). Nunca uses `0.0.0.0/0`.
- **Solo la base `odontosisbd` y solo el usuario `odontoclinic_app`**: ni `postgres` ni `odontoclinic_backup` entran por red (el
  backup corre en el propio servidor).
- **`scram-sha-256`**: autenticación con contraseña cifrada. No uses `trust` ni `md5`.
- Si la subred de la clínica no es `/24`, calculá el prefijo correcto (por ejemplo `192.168.0.0/16`); si querés permitir una
  sola PC, usá su IP con `/32` (`192.168.100.25/32`).

## 3. Firewall de Windows — puerto 5432

En el servidor, **PowerShell como administrador**. La regla abre el 5432 **solo para la red local**:

```powershell
New-NetFirewallRule -DisplayName "PostgreSQL 14 - OdontoClinic (5432)" `
    -Direction Inbound -Protocol TCP -LocalPort 5432 `
    -RemoteAddress 192.168.100.0/24 -Profile Private -Action Allow
```

- `-Profile Private`: aplica solo cuando Windows clasifica la red como *Privada*. Si el Wi-Fi figura como *Pública*, cambialo en
  Configuración → Red e Internet → Propiedades de la red → *Privada*.
- Para quitarla: `Remove-NetFirewallRule -DisplayName "PostgreSQL 14 - OdontoClinic (5432)"`.
- Por el entorno gráfico: *Firewall de Windows Defender con seguridad avanzada* → Reglas de entrada → Nueva regla → Puerto → TCP
  5432 → Permitir → perfil Privado → en *Ámbito*, “Direcciones IP remotas” = tu subred.

## 4. Reiniciar PostgreSQL

`listen_addresses` exige **reiniciar** el servicio (`pg_hba.conf` solo necesitaría recargar):

```powershell
Restart-Service postgresql-x64-14
```

Si el servicio no arranca, el motivo está en `C:\Program Files\PostgreSQL\14\data\log\`. Lo más común: un error de tipeo en una
de las dos líneas. Volvé a poner los `.bak` y reiniciá.

## 5. Apuntar la aplicación de otra PC al servidor

En la **otra PC** (con el proyecto instalado), en su archivo `.env` cambiá solo el host; el resto (`DB_PORT`, `DB_NAME`,
`DB_USER=odontoclinic_app`, `DB_PASSWORD`) es el mismo:

```
DB_HOST=192.168.100.80
```

Reiniciá la aplicación en esa PC. El `.env` de cada equipo es local (no se versiona): copiá la contraseña de
`odontoclinic_app` por un medio seguro, no por mensajes ni correo.

### Probar la conexión antes de usar la app

Desde la otra PC (si tiene `psql`):

```
psql -h 192.168.100.80 -p 5432 -U odontoclinic_app -d odontosisbd -c "SELECT current_user, inet_server_addr();"
```

Sin `psql`, con el Python del proyecto:

```
python -c "from app.conexion.Conexion import Conexion; c=Conexion().getConexion(); k=c.cursor(); k.execute('select current_user'); print(k.fetchone())"
```

Qué significa cada error:

| Mensaje | Causa probable |
|---|---|
| `timeout` / `Connection timed out` | Firewall (paso 3) o IP/subred equivocada. |
| `Connection refused` | PostgreSQL no escucha en esa IP (paso 1) o no se reinició (paso 4). |
| `no pg_hba.conf entry for host ...` | Falta la línea del paso 2 o la subred no incluye esa PC. |
| `password authentication failed` | Contraseña incorrecta de `odontoclinic_app`. |

## Seguridad: qué tener presente

- **Esta conexión no va cifrada** (PostgreSQL sin SSL): sirve para una red local de confianza. Si la red incluye Wi-Fi de
  visitas, activá SSL en PostgreSQL (`ssl = on` con certificado) y usá `hostssl` en lugar de `host` en `pg_hba.conf`.
- Con la base abierta a la red, la **contraseña de `odontoclinic_app` debe ser larga y única**, y las demás PC no deben guardar
  la de `postgres`.
- La validación de IP por país de la aplicación (login) es independiente de este acceso a la base: protege la interfaz web.
- Revisá de vez en cuando los accesos: `SELECT usename, client_addr, application_name FROM pg_stat_activity;`.
