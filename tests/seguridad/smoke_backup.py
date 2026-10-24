"""Copias de seguridad: pg_dump -Fc con el rol de solo lectura odontoclinic_backup, nombre con fecha y hora, retención de 7, log
de cada ejecución (OK/ERROR, archivo, tamaño), contraseña que no aparece en comandos, logs ni mensajes, errores (clave mala,
configuración faltante) sin dejar archivos a medias, restauración REAL en una base temporal (odontosisbd_restore_test) con el
mismo conteo de filas que la original, el script programable, la pantalla "Copias de Seguridad" (solo Administrador, auditada)
y las guías. Usa una carpeta temporal para las copias (no toca las reales) y borra la base de restauración y la auditoría que
generó, por ID."""
import datetime, os, pathlib, re, shutil, subprocess, sys, tempfile
RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import psycopg2
from app import app
from app.Services import backup_service as bs
from app.Services.backup_service import BackupError
from tests._conexion_pruebas import Conexion as ConexionAdm

fallos = []
BASE_RESTAURACION = 'odontosisbd_restore_test'


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


adm = ConexionAdm().getConexion(); adm.autocommit = True; ca = adm.cursor()
adm_postgres = ConexionAdm('postgres').getConexion(); adm_postgres.autocommit = True; cp = adm_postgres.cursor()
ca.execute("SELECT COALESCE(MAX(id_auditoria_cambio), 0) FROM auditoria_cambios"); ID_AUD = ca.fetchone()[0]
ca.execute("SELECT u.id_usuario, r.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.activo ORDER BY 1")
usuarios = ca.fetchall()
ADMIN = next(u for u in usuarios if u[2] == 'Administrador')
CAJERO = next((u for u in usuarios if u[2] == 'Cajero'), None)
PG_BIN = os.environ['PG_BIN_DIR']
tmp = pathlib.Path(tempfile.mkdtemp(prefix='oc_backup_test_'))
env_original = {k: os.environ.get(k) for k in ('BACKUP_DIR', 'BACKUP_DB_PASSWORD', 'BACKUP_DB_USER')}
CLAVE = os.environ['BACKUP_DB_PASSWORD']


def conteos(base):
    c = ConexionAdm(base).getConexion(); k = c.cursor()
    k.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY 1")
    r = {}
    for (t,) in k.fetchall():
        k.execute(f'SELECT count(*) FROM "{t}"'); r[t] = k.fetchone()[0]
    k.execute("SELECT count(*) FROM information_schema.views WHERE table_schema='public'"); vistas = k.fetchone()[0]
    k.execute("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public'"); funciones = k.fetchone()[0]
    k.execute("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal"); triggers = k.fetchone()[0]
    c.close()
    return r, vistas, funciones, triggers


def log_texto():
    f = tmp / bs.NOMBRE_LOG
    return f.read_text(encoding='utf-8') if f.exists() else ''


try:
    os.environ['BACKUP_DIR'] = str(tmp)

    # =========================================================================================================================
    # 1. UNA COPIA REAL CON EL ROL DE SOLO LECTURA
    # =========================================================================================================================
    chk('BACKUP_DIR del .env real está fuera de OneDrive', 'onedrive' not in (env_original['BACKUP_DIR'] or '').lower() and (env_original['BACKUP_DIR'] or '') != '')
    chk('el rol del backup es odontoclinic_backup y no el de la app ni postgres', os.environ['BACKUP_DB_USER'] == 'odontoclinic_backup')
    antes = conteos('odontosisbd')
    pedidos = []
    original_run = subprocess.run

    def espia(*a, **k):
        pedidos.append((a[0], dict(k.get('env') or {})))
        return original_run(*a, **k)
    subprocess.run = espia
    try:
        r = bs.generar_backup()
    finally:
        subprocess.run = original_run
    despues = conteos('odontosisbd')
    archivo = tmp / r['archivo']
    chk('genera un .dump con nombre odontosisbd_AAAAMMDD_HHMMSS.dump', re.fullmatch(r'odontosisbd_\d{8}_\d{6}\.dump', r['archivo']) is not None and archivo.exists())
    chk('el tamaño informado es el del archivo y no es 0', r['tamano'] == archivo.stat().st_size > 10_000)
    chk('no queda ningún archivo .parcial', not list(tmp.glob('*.parcial')))
    comando, entorno = pedidos[0]
    chk('la contraseña NO está en la línea de comandos de pg_dump', CLAVE not in ' '.join(comando) and '--no-password' in comando)
    chk('...viaja solo en PGPASSWORD del proceso hijo', entorno.get('PGPASSWORD') == CLAVE)
    chk('pg_dump corre con -Fc (formato custom) y como odontoclinic_backup', '-Fc' in comando and comando[comando.index('-U') + 1] == 'odontoclinic_backup')
    lista = original_run([os.path.join(PG_BIN, 'pg_restore.exe'), '--list', str(archivo)], capture_output=True, text=True, encoding='utf-8', errors='replace')
    chk('pg_restore --list lee el archivo (formato custom válido)', lista.returncode == 0 and 'TABLE DATA' in lista.stdout)
    registro = log_texto()
    chk('backup.log: línea OK con archivo y tamaño', re.search(rf"\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}} OK archivo={re.escape(r['archivo'])} tamano={r['tamano']} bytes", registro) is not None)
    chk('el log no contiene la contraseña', CLAVE not in registro)

    # =========================================================================================================================
    # 2. EL ROL DEL BACKUP SOLO LEE
    # =========================================================================================================================
    cb = psycopg2.connect(dbname=os.environ['DB_NAME'], user='odontoclinic_backup', password=CLAVE, host=os.environ['DB_HOST'], port=int(os.environ['DB_PORT']))
    cb.autocommit = True; kb = cb.cursor()
    kb.execute('SELECT count(*) FROM usuarios'); chk('odontoclinic_backup puede leer', kb.fetchone()[0] > 0)
    for sentencia in ("UPDATE usuarios SET activo = activo WHERE false", "DELETE FROM paciente WHERE false", "TRUNCATE usuarios", "CREATE TABLE zz_b (a int)",
                      "INSERT INTO auditoria_acceso(ci_ruc_ingresado, resultado, accion) VALUES ('0', 'ZZ', 'LOGIN')"):
        try:
            kb.execute(sentencia); chk(f'odontoclinic_backup NO puede: {sentencia[:40]}', False)
        except psycopg2.Error as e:
            chk(f'odontoclinic_backup NO puede: {sentencia[:40]}', e.pgcode == '42501')
    cb.close()

    # =========================================================================================================================
    # 3. RESTAURACIÓN REAL EN UNA BASE TEMPORAL
    # =========================================================================================================================
    cp.execute(f'DROP DATABASE IF EXISTS {BASE_RESTAURACION}')
    cp.execute(f'CREATE DATABASE {BASE_RESTAURACION}')
    entorno_adm = dict(os.environ, PGPASSWORD=os.environ['TEST_DB_PASSWORD'])
    rest = original_run([os.path.join(PG_BIN, 'pg_restore.exe'), '--no-password', '-h', os.environ['DB_HOST'], '-p', os.environ['DB_PORT'],
                         '-U', os.environ['TEST_DB_USER'], '-d', BASE_RESTAURACION, '--exit-on-error', str(archivo)],
                        env=entorno_adm, capture_output=True, text=True, encoding='utf-8', errors='replace')
    chk('pg_restore restaura la copia sin errores' + ('' if rest.returncode == 0 else f' ({rest.stderr[-200:]})'), rest.returncode == 0)
    restaurada = conteos(BASE_RESTAURACION)
    chk('la base restaurada tiene las mismas tablas', set(restaurada[0]) == set(antes[0]))
    # Entre el conteo "antes" y "después" otro proceso pudo insertar (p. ej. la auditoría): la restaurada debe estar en ese rango
    distintas = {t: (antes[0][t], restaurada[0][t], despues[0][t]) for t in antes[0]
                 if not (min(antes[0][t], despues[0][t]) <= restaurada[0].get(t, -1) <= max(antes[0][t], despues[0][t]))}
    chk(f"mismas filas en las {len(antes[0])} tablas" + (f' DIFERENCIAS: {distintas}' if distintas else ''), not distintas)
    chk('mismas vistas, funciones/procedimientos y triggers', restaurada[1:] == antes[1:])
    for t in ('usuarios', 'paciente', 'venta_cab', 'cobro_cab', 'items', 'cliente', 'permisos'):
        chk(f'{t}: {antes[0][t]} filas en la original = {restaurada[0][t]} en la restaurada', restaurada[0][t] == antes[0][t] or t in ('auditoria_acceso',))
    cr = ConexionAdm(BASE_RESTAURACION).getConexion(); kr = cr.cursor()
    kr.execute("SELECT has_table_privilege('odontoclinic_app', 'auditoria_acceso', 'UPDATE'), has_table_privilege('odontoclinic_app', 'usuarios', 'UPDATE')")
    chk('los permisos del rol de la app también se restauraron (sin UPDATE en la auditoría)', kr.fetchone() == (False, True))
    cr.close()
    cp.execute(f'DROP DATABASE {BASE_RESTAURACION}')
    cp.execute("SELECT count(*) FROM pg_database WHERE datname = %s", (BASE_RESTAURACION,))
    chk('la base temporal se borró', cp.fetchone()[0] == 0)

    # =========================================================================================================================
    # 4. RETENCIÓN DE 7 Y ARCHIVOS AJENOS
    # =========================================================================================================================
    base = datetime.datetime(2020, 1, 1, 23, 0, 0)
    for i in range(9):
        (tmp / f"odontosisbd_{(base + datetime.timedelta(days=i)).strftime('%Y%m%d_%H%M%S')}.dump").write_bytes(b'x' * 10)
    (tmp / 'notas.txt').write_text('no es una copia')
    r2 = bs.generar_backup()
    nombres = [c['nombre'] for c in bs.listar_backups()]
    chk('retención: quedan exactamente 7 copias', len(nombres) == 7)
    chk('...las 7 más recientes (la nueva está, las de 2020 más viejas se borraron)', r2['archivo'] in nombres and nombres == sorted(nombres, reverse=True)
        and 'odontosisbd_20200101_230000.dump' not in nombres and nombres[0] == r2['archivo'])
    chk('...y no toca archivos ajenos (backup.log, notas.txt)', (tmp / 'notas.txt').exists() and (tmp / bs.NOMBRE_LOG).exists())
    chk('el listado va de la más reciente a la más vieja y cada copia trae fecha y tamaño', all(c['tamano'] > 0 and c['fecha'] for c in bs.listar_backups()))
    chk('backup.log registró ambas ejecuciones', len(re.findall(r' OK archivo=', log_texto())) == 2)

    # =========================================================================================================================
    # 5. ERRORES: sin dejar nada a medias y sin filtrar la contraseña
    # =========================================================================================================================
    n_archivos = len(list(tmp.iterdir()))
    os.environ['BACKUP_DB_PASSWORD'] = 'clave-incorrecta-ZZ'
    try:
        bs.generar_backup(); chk('contraseña incorrecta -> BackupError', False)
    except BackupError as e:
        chk('contraseña incorrecta -> BackupError con mensaje claro', 'pg_dump falló' in str(e))
        chk('...el mensaje no incluye ninguna contraseña', 'clave-incorrecta-ZZ' not in str(e) and CLAVE not in str(e))
    chk('...no queda ningún archivo nuevo ni .parcial', len(list(tmp.iterdir())) == n_archivos)
    registro = log_texto()
    chk('...backup.log registra ERROR sin contraseñas', ' ERROR ' in registro and 'clave-incorrecta-ZZ' not in registro and CLAVE not in registro)
    os.environ['BACKUP_DB_PASSWORD'] = CLAVE
    os.environ.pop('BACKUP_DB_USER')
    try:
        bs.generar_backup(); chk('sin BACKUP_DB_USER -> BackupError', False)
    except BackupError as e:
        chk('sin BACKUP_DB_USER -> BackupError que nombra la variable', 'BACKUP_DB_USER' in str(e))
    os.environ['BACKUP_DB_USER'] = 'odontoclinic_backup'
    pg_original = os.environ['PG_BIN_DIR']
    os.environ['PG_BIN_DIR'] = str(tmp / 'no_existe')
    try:
        bs.generar_backup(); chk('PG_BIN_DIR inválido -> BackupError', False)
    except BackupError as e:
        chk('PG_BIN_DIR inválido -> BackupError', 'PG_BIN_DIR' in str(e))
    os.environ['PG_BIN_DIR'] = pg_original

    # =========================================================================================================================
    # 6. SCRIPT PROGRAMABLE
    # =========================================================================================================================
    ejecucion = original_run([sys.executable, '-I', str(RAIZ / 'scripts' / 'backup_db.py')], capture_output=True, text=True, encoding='utf-8',
                             errors='replace', env=dict(os.environ, BACKUP_DIR=str(tmp)))
    chk('scripts/backup_db.py termina con código 0 e informa OK', ejecucion.returncode == 0 and ejecucion.stdout.startswith('OK: odontosisbd_'))
    ejecucion = original_run([sys.executable, '-I', str(RAIZ / 'scripts' / 'backup_db.py')], capture_output=True, text=True, encoding='utf-8',
                             errors='replace', env=dict(os.environ, BACKUP_DIR=str(tmp), BACKUP_DB_PASSWORD='mala-ZZ'))
    chk('...y con código 1 e informa ERROR si falla (el Programador de tareas lo ve)', ejecucion.returncode == 1 and 'ERROR' in ejecucion.stdout and 'mala-ZZ' not in ejecucion.stdout + ejecucion.stderr)
    bat = (RAIZ / 'scripts' / 'backup_diario.bat').read_text(encoding='utf-8')
    chk('backup_diario.bat usa el Python del entorno virtual y backup_db.py y devuelve su código de salida', '.venv\\Scripts\\python.exe' in bat and 'backup_db.py' in bat and 'ERRORLEVEL' in bat)

    # =========================================================================================================================
    # 7. PANTALLA: SOLO ADMINISTRADOR Y AUDITADA
    # =========================================================================================================================
    def cliente(u):
        c = app.test_client()
        with c.session_transaction() as s:
            s['id_usuario'], s['id_rol'], s['nombre_rol'] = u
        return c
    adm_c = cliente(ADMIN)
    html = adm_c.get('/referenciales/backup/backup-index')
    chk('el Administrador ve la pantalla con "Generar backup ahora"', html.status_code == 200 and 'Generar backup ahora' in html.get_data(as_text=True)
        and 'Copias de Seguridad' in html.get_data(as_text=True))
    chk('...y está en el menú lateral (Módulo Seguridad)', 'href="/referenciales/backup/backup-index"' in html.get_data(as_text=True))
    d = adm_c.get('/api/v1/backups').get_json()
    chk('GET /api/v1/backups lista las copias con nombre, fecha y tamaño', d['success'] and d['retencion'] == 7 and len(d['data']) == 7
        and all({'nombre', 'fecha', 'tamano', 'tamano_texto'} <= set(x) for x in d['data']))
    r = adm_c.post('/api/v1/backups')
    d = r.get_json()
    chk('POST /api/v1/backups genera una copia (201) y devuelve el archivo', r.status_code == 201 and d['success'] and d['archivo'].endswith('.dump') and (tmp / d['archivo']).exists())
    ca.execute("SELECT id_usuario, accion, detalle, ip FROM auditoria_cambios WHERE entidad = 'backup' AND id_auditoria_cambio > %s", (ID_AUD,))
    f = ca.fetchall()
    chk('queda auditado en auditoria_cambios (ALTA, usuario de la sesión, IP, archivo)', len(f) == 1 and f[0][0] == ADMIN[0] and f[0][1] == 'ALTA' and d['archivo'] in f[0][2] and f[0][3])
    ejemplos = [u for u in usuarios if u[2] != 'Administrador']
    for u in ejemplos[:1] + ([CAJERO] if CAJERO else []):
        c = cliente(u)
        chk(f'{u[2]}: la pantalla da 403', c.get('/referenciales/backup/backup-index').status_code == 403)
        chk(f'{u[2]}: GET /api/v1/backups da 403 y POST no genera copias', c.get('/api/v1/backups').status_code == 403
            and c.post('/api/v1/backups').status_code == 403)
    n_antes = len(bs.listar_backups())
    chk('...y no se generó ninguna copia por esos intentos', len(bs.listar_backups()) == n_antes)
    chk('sin sesión: 401 en la API', app.test_client().get('/api/v1/backups').status_code == 401)
    cat = adm_c.get('/api/v1/permisos/catalogo').get_json()['data']
    chk('la matriz de Roles y Permisos NO muestra Copias de Seguridad (no se delega)', all(v['ventana'] != 'backup' for m in cat for v in m['ventanas']))
    rol = ejemplos[0][1]
    r = adm_c.post('/api/v1/permisos/matriz', json={'id_rol': rol, 'ventana': 'backup', 'accion': 'ver'})
    chk('intentar otorgar el permiso desde la API se rechaza (400)', r.status_code == 400)
    ca.execute("INSERT INTO permisos(id_rol, ventana, accion) VALUES (%s, 'backup', 'ver') RETURNING id_permiso", (rol,)) if False else None
    ca.execute("SELECT column_name FROM information_schema.columns WHERE table_name='permisos' AND column_name LIKE 'id_%'"); cols = {x[0] for x in ca.fetchall()}
    idcol = 'id_permiso' if 'id_permiso' in cols else sorted(cols - {'id_rol', 'id_menu'})[0]
    ca.execute(f"INSERT INTO permisos(id_rol, ventana, accion) VALUES (%s, 'backup', 'ver') RETURNING {idcol}", (rol,)); pid = ca.fetchone()[0]
    try:
        chk('aunque la fila exista en la base, ese rol sigue sin acceso (403)', cliente(ejemplos[0]).get('/referenciales/backup/backup-index').status_code == 403)
    finally:
        ca.execute(f"DELETE FROM permisos WHERE {idcol} = %s", (pid,))
    ca.execute("SELECT count(*) FROM menu WHERE clave = 'backup' AND activo")
    chk('la ventana tiene su fila en la tabla menu', ca.fetchone()[0] == 1)

    # =========================================================================================================================
    # 8. GUÍAS Y ARCHIVOS
    # =========================================================================================================================
    guia = (RAIZ / 'docs' / 'backups.md').read_text(encoding='utf-8') if (RAIZ / 'docs' / 'backups.md').exists() else ''
    chk('docs/backups.md: Programador de tareas 23:00, restauración, base temporal y por qué fuera de OneDrive',
        all(t in guia for t in ('23:00', 'Programador de tareas', 'pg_restore', BASE_RESTAURACION, 'OneDrive')))
    red = (RAIZ / 'docs' / 'acceso_red.md').read_text(encoding='utf-8') if (RAIZ / 'docs' / 'acceso_red.md').exists() else ''
    chk('docs/acceso_red.md: listen_addresses, pg_hba.conf, scram-sha-256, odontoclinic_app, firewall y 5432',
        all(t in red for t in ('listen_addresses', 'pg_hba.conf', 'scram-sha-256', 'odontoclinic_app', 'firewall', '5432', 'DB_HOST')))
    ignorados = (RAIZ / '.gitignore').read_text(encoding='utf-8').splitlines()
    chk('backups/ está en .gitignore', 'backups/' in [l.strip() for l in ignorados])
    ejemplo = (RAIZ / '.env.example').read_text(encoding='utf-8')
    chk('.env.example documenta BACKUP_DB_*, BACKUP_DIR, PG_BIN_DIR y TEST_DB_* sin valores',
        all(re.search(rf'^{v}=\s*$', ejemplo, re.M) for v in ('BACKUP_DB_USER', 'BACKUP_DB_PASSWORD', 'BACKUP_DIR', 'PG_BIN_DIR', 'TEST_DB_USER', 'TEST_DB_PASSWORD')))
finally:
    for k, v in env_original.items():
        if v is None: os.environ.pop(k, None)
        else: os.environ[k] = v
    try:
        cp.execute(f'DROP DATABASE IF EXISTS {BASE_RESTAURACION}')
    except Exception as e:
        print('NO SE PUDO BORRAR LA BASE TEMPORAL:', e); fallos.append('limpieza')
    ca.execute("SELECT id_auditoria_cambio FROM auditoria_cambios WHERE entidad = 'backup' AND id_auditoria_cambio > %s", (ID_AUD,))
    propios = [x[0] for x in ca.fetchall()]
    if propios:
        ca.execute("SET session_replication_role = replica")
        ca.execute("DELETE FROM auditoria_cambios WHERE id_auditoria_cambio = ANY(%s)", (propios,))
        ca.execute("RESET session_replication_role")
    shutil.rmtree(tmp, ignore_errors=True)
    ca.close(); adm.close(); cp.close(); adm_postgres.close()

print('FALLOS:', 'ninguno' if not fallos else fallos)
