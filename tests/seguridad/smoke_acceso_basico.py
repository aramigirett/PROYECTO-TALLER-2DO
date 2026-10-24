"""Seguridad de acceso, resto de la Etapa A: contraseñas con hash scrypt y salt, "Recordar usuario" (cookie con SOLO el CI/RUC:
30 días, HttpOnly, SameSite=Lax), SECRET_KEY obligatoria fuera de modo debug, credenciales de la base fuera del código y archivos
sensibles en .gitignore. Borra SOLO la auditoría y los códigos 2FA que generó (por ID)."""
import os, re, subprocess, sys, pathlib
RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from werkzeug.security import check_password_hash, generate_password_hash
from app import app
from app.conexion.Conexion import Conexion
from app.dao.modulo_seguridad.UsuarioDao import UsuarioDao
from app.dao.modulo_seguridad.TokenDao import TokenDao
import app.rutas.modulo_seguridad.seguridad_routes as rutas

fallos = []


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


cx = Conexion().getConexion(); cx.autocommit = True; cu = cx.cursor()
cu.execute("SELECT COALESCE(MAX(id_auditoria), 0) FROM auditoria_acceso"); ID_AUD = cu.fetchone()[0]
cu.execute("SELECT COALESCE(MAX(id_token), 0) FROM token_2fa"); ID_TOK = cu.fetchone()[0]
cu.execute("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE u.activo AND NOT u.bloqueado AND r.nombre_rol = 'Administrador' ORDER BY 1")
ADMIN = cu.fetchone()
if not ADMIN:
    print('ABORTADO: se necesita un Administrador activo.'); sys.exit(1)
ADMIN = ADMIN[0]
CI = UsuarioDao().get_by_id(ADMIN)['ci_ruc']

validar_original = UsuarioDao.validar_password
correo_original = rutas.enviar_codigo_2fa


def cookies_de(resp, nombre='oc_usuario'):
    return [h for h in resp.headers.getlist('Set-Cookie') if h.startswith(nombre + '=')]


try:
    # =========================================================================================================================
    # 1. CONTRASEÑAS
    # =========================================================================================================================
    cu.execute("SELECT id_usuario, password_hash FROM usuarios")
    todos = cu.fetchall()
    chk('todas las contraseñas guardadas son hash scrypt con salt (ninguna en texto plano)',
        todos and all(re.match(r'^scrypt:\d+:\d+:\d+\$[A-Za-z0-9]{8,}\$[0-9a-f]{64,}$', h or '') for _, h in todos))
    chk('dos hashes de la misma contraseña difieren (salt aleatorio)', generate_password_hash('Abc123!x') != generate_password_hash('Abc123!x'))
    chk('UsuarioDao.validar_password verifica contra el hash',
        UsuarioDao().validar_password(generate_password_hash('Abc123!x'), 'Abc123!x') and
        not UsuarioDao().validar_password(generate_password_hash('Abc123!x'), 'otra'))

    # =========================================================================================================================
    # 2. SECRET_KEY Y CREDENCIALES DE LA BASE
    # =========================================================================================================================
    chk('SECRET_KEY del .env en uso y larga', len(app.secret_key) >= 32 and app.secret_key != 'dev-secret-key-cambiar-en-produccion')
    codigo_app = (RAIZ / 'app' / '__init__.py').read_text(encoding='utf-8')
    chk('el código ya no contiene la clave por defecto', 'dev-secret-key' not in codigo_app)
    conexion_py = (RAIZ / 'app' / 'conexion' / 'Conexion.py').read_text(encoding='utf-8')
    chk('Conexion.py no contiene credenciales y lee DB_HOST/PORT/NAME/USER/PASSWORD del entorno',
        '15dediciembre' not in conexion_py and all(f"'{v}'" in conexion_py for v in ('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD')))
    ejemplo = (RAIZ / '.env.example').read_text(encoding='utf-8')
    chk('.env.example lista las variables DB_* sin valores',
        all(re.search(rf'^{v}=\s*$', ejemplo, re.M) for v in ('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'SECRET_KEY')))
    chk('.env.example no contiene la contraseña real ni la SECRET_KEY real', '15dediciembre' not in ejemplo and app.secret_key not in ejemplo)
    ignorados = [l.strip() for l in (RAIZ / '.gitignore').read_text(encoding='utf-8').splitlines()]
    chk('.gitignore excluye .env y geoip/', '.env' in ignorados and 'geoip/' in ignorados)
    rastreados = subprocess.run(['git', 'ls-files', '.env', 'geoip'], capture_output=True, text=True, cwd=RAIZ).stdout.strip()
    chk('.env y geoip/ no están versionados en git', rastreados == '')

    # Sin SECRET_KEY y fuera de modo debug la app no arranca, con error claro; en debug sí (clave efímera)
    base = [sys.executable, '-I', '-c']
    codigo = ("import sys,os; sys.path.insert(0, %r); import dotenv; dotenv.load_dotenv=lambda *a, **k: None; "
              "os.environ.pop('SECRET_KEY', None); os.environ.pop('FLASK_DEBUG', None); %%s; from app import app; print('ARRANCO')" % str(RAIZ))
    # DB_* siguen en el entorno del proceso hijo (no hace falta .env para importar la app)
    entorno = dict(os.environ, DB_HOST='x', DB_PORT='1', DB_NAME='x', DB_USER='x', DB_PASSWORD='x')
    r = subprocess.run(base + [codigo % 'pass'], capture_output=True, text=True, env=entorno, timeout=60)
    chk('sin SECRET_KEY y sin debug la app NO arranca, con un error que nombra la variable',
        'ARRANCO' not in r.stdout and 'Falta SECRET_KEY' in r.stderr)
    r = subprocess.run(base + [codigo % "os.environ.__setitem__('FLASK_DEBUG', '1')"], capture_output=True, text=True, env=entorno, timeout=60)
    chk('sin SECRET_KEY pero en modo debug arranca (clave efímera, con aviso)', 'ARRANCO' in r.stdout and 'AVISO' in r.stdout)
    r = subprocess.run(base + ["import sys,os; sys.path.insert(0, %r); os.environ.pop('DB_PASSWORD', None); import dotenv; dotenv.load_dotenv=lambda *a, **k: None; "
                               "from app.conexion.Conexion import Conexion; Conexion()" % str(RAIZ)],
                       capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != 'DB_PASSWORD'}, timeout=60)
    chk('sin DB_PASSWORD la conexión falla con un error claro', 'Falta la variable DB_PASSWORD' in r.stderr)

    # =========================================================================================================================
    # 3. RECORDAR USUARIO
    # =========================================================================================================================
    html = app.test_client().get('/login').get_data(as_text=True)
    chk('el login tiene el checkbox "Recordar mi usuario" (desmarcado y con el campo vacío)',
        'name="recordar"' in html and 'type="checkbox"' in html and 'Recordar mi usuario' in html
        and 'checked' not in html.split('name="recordar"')[1].split('>')[0] and 'value=""' in html)

    c = app.test_client()
    c.set_cookie('oc_usuario', CI)
    html = c.get('/login').get_data(as_text=True)
    chk('con la cookie, el campo CI/RUC viene precargado y el checkbox marcado', f'value="{CI}"' in html and re.search(r'name="recordar"[^>]*checked', html, re.S) is not None)
    c.set_cookie('oc_usuario', '"><script>alert(1)</script>')
    html = c.get('/login').get_data(as_text=True)
    chk('una cookie manipulada (no parece CI/RUC) se ignora y no se inyecta', '<script>alert(1)' not in html and 'alert(1)' not in html)

    # Flujo real: contraseña correcta (simulada) -> 2FA con el código vigente -> cookie
    UsuarioDao.validar_password = lambda self, h, p: True
    rutas.enviar_codigo_2fa = lambda *a, **k: True
    for recordar in (True, False):
        c = app.test_client()
        r = c.post('/login', data={'ci_ruc': CI, 'password': 'una-clave-que-NO-debe-guardarse', **({'recordar': '1'} if recordar else {})})
        chk(f'login con recordar={recordar}: pasa al 2FA', r.status_code == 302 and r.headers['Location'].endswith('/verificar-2fa'))
        chk('...y todavía NO se guarda la cookie (falta el segundo factor)', cookies_de(r) == [])
        codigo2fa = TokenDao().generar_codigo(ADMIN)
        r = c.post('/verificar-2fa', data={'codigo': codigo2fa})
        sc = cookies_de(r)
        chk('2FA correcto: login completo', r.status_code == 302 and not r.headers['Location'].endswith('/verificar-2fa'))
        if recordar:
            chk('cookie oc_usuario: contiene SOLO el CI/RUC', len(sc) == 1 and sc[0].split(';')[0] == f'oc_usuario={CI}')
            chk('cookie: 30 días (Max-Age=2592000), HttpOnly y SameSite=Lax',
                'Max-Age=2592000' in sc[0] and 'HttpOnly' in sc[0] and 'SameSite=Lax' in sc[0])
            chk('la cookie no contiene ni la contraseña ni el código 2FA', 'clave' not in sc[0] and codigo2fa not in sc[0])
            chk('la cookie de sesión también es HttpOnly + SameSite=Lax',
                any('HttpOnly' in h and 'SameSite=Lax' in h for h in r.headers.getlist('Set-Cookie') if h.startswith('session=')))
        else:
            chk('sin marcar: se borra la cookie existente (Expires en el pasado)', len(sc) == 1 and 'oc_usuario=;' in sc[0] and '1970' in sc[0])

    os.environ['RECORDAR_USUARIO_DIAS'] = '7'
    c = app.test_client()
    c.post('/login', data={'ci_ruc': CI, 'password': 'x', 'recordar': '1'})
    r = c.post('/verificar-2fa', data={'codigo': TokenDao().generar_codigo(ADMIN)})
    chk('RECORDAR_USUARIO_DIAS del .env se respeta (7 días = 604800 s)', 'Max-Age=604800' in cookies_de(r)[0])
    os.environ.pop('RECORDAR_USUARIO_DIAS')
finally:
    UsuarioDao.validar_password = validar_original
    rutas.enviar_codigo_2fa = correo_original
    os.environ.pop('RECORDAR_USUARIO_DIAS', None)
    cu.execute("DELETE FROM token_2fa WHERE id_token > %s AND id_usuario = %s", (ID_TOK, ADMIN))
    cu.execute("SELECT id_auditoria FROM auditoria_acceso WHERE id_auditoria > %s AND id_usuario = %s AND resultado = 'EXITOSO' AND accion = 'LOGIN' AND ip = '127.0.0.1'",
               (ID_AUD, ADMIN))
    propios = [x[0] for x in cu.fetchall()]
    if propios:
        cu.execute("SET session_replication_role = replica")
        cu.execute("DELETE FROM auditoria_acceso WHERE id_auditoria = ANY(%s)", (propios,))
        cu.execute("RESET session_replication_role")
    cu.close(); cx.close()

print('FALLOS:', 'ninguno' if not fallos else fallos)
