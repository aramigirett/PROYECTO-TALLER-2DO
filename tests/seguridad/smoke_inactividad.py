"""Cierre de sesión por inactividad: el SERVIDOR vence la sesión pasados SESSION_INACTIVIDAD_MINUTOS (vistas y /api/), la deja
en auditoria_acceso como CIERRE_INACTIVIDAD y redirige al login con "Sesión cerrada por inactividad"; /sesion/estado no renueva,
/sesion/extender sí; el tiempo y el aviso salen del .env; el aviso con cuenta regresiva (inactividad.js) está en base.html y en
base_tabler.html, y su lógica se prueba en Edge headless con reloj y red simulados (inactividad_test.html).
Borra SOLO las filas de auditoría que generó (por ID)."""
import os, re, subprocess, sys, time, pathlib, tempfile
RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from app import app
from tests._conexion_pruebas import Conexion
from app.dao.modulo_seguridad.UsuarioDao import UsuarioDao

EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
fallos = []
VISTA_SBADMIN = '/referenciales/auditoria/auditoria-index'          # extiende base.html
VISTA_TABLER = '/referenciales/formacobro/forma-cobro-index'        # extiende base_tabler.html


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


cx = Conexion().getConexion(); cx.autocommit = True; cu = cx.cursor()
cu.execute("SELECT COALESCE(MAX(id_auditoria), 0) FROM auditoria_acceso")
ID_BASE = cu.fetchone()[0]
cu.execute("SELECT u.id_usuario, r.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.activo ORDER BY 1")
ADMIN = next((u for u in cu.fetchall() if u[2] == 'Administrador'), None)
if not ADMIN:
    print('ABORTADO: se necesita un Administrador activo.'); sys.exit(1)
CI_ADMIN = UsuarioDao().get_by_id(ADMIN[0])['ci_ruc']
minutos_original = os.environ.get('SESSION_INACTIVIDAD_MINUTOS')


def cliente(hace_segundos=None):
    """Cliente con sesión de Administrador cuya última actividad fue hace N segundos (None = sin marca)."""
    c = app.test_client()
    with c.session_transaction() as s:
        s['id_usuario'] = ADMIN[0]; s['id_rol'] = ADMIN[1]; s['nombre_rol'] = ADMIN[2]; s['ci_ruc'] = CI_ADMIN
        s['nombre_completo'] = 'ADMIN PRUEBA'
        if hace_segundos is not None:
            s['ultima_actividad'] = time.time() - hace_segundos
    return c


def ultima(c):
    with c.session_transaction() as s:
        return s.get('ultima_actividad'), s.get('id_usuario')


def cierres():
    cu.execute("SELECT resultado, accion, id_usuario, ci_ruc_ingresado FROM auditoria_acceso "
               "WHERE id_auditoria > %s AND resultado = 'CIERRE_INACTIVIDAD' ORDER BY id_auditoria", (ID_BASE,))
    return cu.fetchall()


try:
    os.environ.pop('SESSION_INACTIVIDAD_MINUTOS', None)
    os.environ['SESSION_INACTIVIDAD_MINUTOS'] = '30'

    # =========================================================================================================================
    # 1. CONFIGURACIÓN (.env)
    # =========================================================================================================================
    texto_env = (RAIZ / '.env').read_text(encoding='utf-8')
    chk('.env: SESSION_INACTIVIDAD_MINUTOS=30 y SESSION_AVISO_SEGUNDOS=120',
        re.search(r'^SESSION_INACTIVIDAD_MINUTOS=30\s*$', texto_env, re.M) is not None and
        re.search(r'^SESSION_AVISO_SEGUNDOS=120\s*$', texto_env, re.M) is not None)
    chk('.env.example documenta las dos variables sin valores secretos',
        'SESSION_INACTIVIDAD_MINUTOS' in (RAIZ / '.env.example').read_text(encoding='utf-8'))

    # =========================================================================================================================
    # 2. EL SERVIDOR VENCE LA SESIÓN
    # =========================================================================================================================
    c = cliente(hace_segundos=31 * 60)
    r = c.get(VISTA_SBADMIN)
    chk('vista con 31 min sin actividad -> 302 al login', r.status_code == 302 and r.headers['Location'].endswith('/login'))
    r = c.get('/login')
    chk('el login muestra "Sesión cerrada por inactividad"', 'Sesión cerrada por inactividad' in r.get_data(as_text=True) and 'alert-warning' in r.get_data(as_text=True))
    chk('la sesión quedó limpia (sin id_usuario)', ultima(c)[1] is None)
    chk('y ya no se puede entrar a otra vista', c.get(VISTA_SBADMIN).status_code == 302)
    f = cierres()
    chk('auditoría: una fila CIERRE_INACTIVIDAD / LOGOUT con el usuario y su CI/RUC',
        len(f) == 1 and f[0] == ('CIERRE_INACTIVIDAD', 'LOGOUT', ADMIN[0], CI_ADMIN))

    c = cliente(hace_segundos=31 * 60)
    r = c.get('/api/v1/auditoria/intentos?limite=1')
    d = r.get_json()
    chk('API con la sesión vencida -> 401 JSON con codigo INACTIVIDAD', r.status_code == 401 and d['codigo'] == 'INACTIVIDAD' and 'inactividad' in d['error'])
    chk('...y también audita el cierre', len(cierres()) == 2)

    # =========================================================================================================================
    # 3. DENTRO DEL LÍMITE SE RENUEVA
    # =========================================================================================================================
    c = cliente(hace_segundos=29 * 60)
    r = c.get(VISTA_SBADMIN)
    marca, _ = ultima(c)
    chk('a los 29 min la sesión sigue viva (200)', r.status_code == 200)
    chk('...y cada request la renueva (última actividad = ahora)', abs(time.time() - marca) < 5)

    c = cliente()   # sesión iniciada antes de existir el control: arranca el contador
    c.get(VISTA_SBADMIN)
    chk('una sesión sin marca de actividad la recibe en su primer request', ultima(c)[0] is not None)

    # =========================================================================================================================
    # 4. /sesion/estado NO renueva, /sesion/extender SÍ
    # =========================================================================================================================
    c = cliente(hace_segundos=10 * 60)
    antes, _ = ultima(c)
    d = c.get('/sesion/estado').get_json()
    despues, _ = ultima(c)
    chk('/sesion/estado informa el tiempo restante (~20 min)', d['success'] and abs(d['restante'] - 20 * 60) <= 3)
    chk('/sesion/estado no renueva la sesión', despues == antes)
    c.get(VISTA_SBADMIN, headers={'X-Sin-Actividad': '1'})
    chk('X-Sin-Actividad: 1 (consultas automáticas) no renueva', ultima(c)[0] == antes)
    d = c.post('/sesion/extender').get_json()
    chk('/sesion/extender (Seguir conectado) renueva: restante ~30 min', d['success'] and abs(d['restante'] - 30 * 60) <= 3 and ultima(c)[0] > antes)
    r = app.test_client().get('/sesion/estado')
    chk('/sesion/estado sin sesión -> 401', r.status_code == 401 and r.get_json()['codigo'] == 'INACTIVIDAD')
    r = app.test_client().post('/sesion/extender')
    chk('/sesion/extender sin sesión -> 401', r.status_code == 401)

    c = cliente(hace_segundos=31 * 60)
    d = c.get('/sesion/estado')
    chk('/sesion/estado con la sesión vencida -> 401 y audita', d.status_code == 401 and len(cierres()) == 3)

    c = cliente(hace_segundos=60)
    r = c.get('/sesion/expirar')
    chk('/sesion/expirar con la sesión viva (otra pestaña activa) NO cierra: vuelve al inicio', r.status_code == 302 and ultima(c)[1] == ADMIN[0])
    c = cliente(hace_segundos=31 * 60)
    r = c.get('/sesion/expirar')
    chk('/sesion/expirar con la sesión vencida -> login', r.status_code == 302 and r.headers['Location'].endswith('/login') and ultima(c)[1] is None)

    # =========================================================================================================================
    # 5. EL TIEMPO SE CONFIGURA EN .env
    # =========================================================================================================================
    os.environ['SESSION_INACTIVIDAD_MINUTOS'] = '1'
    chk('con 1 minuto: 30 s sin actividad -> sigue', cliente(30).get(VISTA_SBADMIN).status_code == 200)
    chk('con 1 minuto: 61 s sin actividad -> cierra', cliente(61).get(VISTA_SBADMIN).status_code == 302)
    os.environ['SESSION_INACTIVIDAD_MINUTOS'] = '30'
    chk('con 30 minutos: 61 s sin actividad -> sigue', cliente(61).get(VISTA_SBADMIN).status_code == 200)

    # =========================================================================================================================
    # 6. EL AVISO (JS) ESTÁ EN LAS DOS PLANTILLAS BASE
    # =========================================================================================================================
    for nombre, url in (('base.html (SB Admin)', VISTA_SBADMIN), ('base_tabler.html (Tabler)', VISTA_TABLER)):
        html = cliente(60).get(url).get_data(as_text=True)
        chk(f'{nombre}: incluye inactividad.js con límite 1800 s y aviso 120 s',
            'js/inactividad.js' in html and 'data-limite="1800"' in html and 'data-aviso="120"' in html)
        chk(f'{nombre}: pasa las URL de estado, extender, expirar y logout',
            all(t in html for t in ('data-url-estado="/sesion/estado"', 'data-url-extender="/sesion/extender"',
                                    'data-url-expirar="/sesion/expirar"', 'data-url-logout="/logout"')))
    chk('el login (sin sesión) no carga inactividad.js', 'inactividad.js' not in app.test_client().get('/login').get_data(as_text=True))
    os.environ['SESSION_INACTIVIDAD_MINUTOS'] = '10'
    chk('el límite que recibe el JS sale del .env (10 min -> 600 s)', 'data-limite="600"' in cliente(60).get(VISTA_SBADMIN).get_data(as_text=True))
    os.environ['SESSION_INACTIVIDAD_MINUTOS'] = '30'

    # =========================================================================================================================
    # 7. LÓGICA DEL AVISO CON CUENTA REGRESIVA (Edge headless, reloj y red simulados)
    # =========================================================================================================================
    if not pathlib.Path(EDGE).exists():
        chk('Edge disponible para la prueba del JS (saltada)', False)
    else:
        pagina = RAIZ / 'tests' / 'seguridad' / 'inactividad_test.html'
        with tempfile.TemporaryDirectory() as perfil:
            proc = subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--allow-file-access-from-files', '--no-first-run',
                                   f'--user-data-dir={perfil}', '--virtual-time-budget=15000', '--dump-dom', pagina.as_uri()],
                                  capture_output=True, text=True, encoding='utf-8', timeout=120)
        m = re.search(r'<pre id="resultado">(.*?)</pre>', proc.stdout, re.S)
        lineas = (m.group(1) if m else '').replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&').splitlines()
        chk('inactividad.js: la página de prueba terminó', 'FIN' in lineas)
        for l in lineas:
            if l.startswith(('OK|', 'FAIL|')):
                chk('JS: ' + l.split('|', 1)[1], l.startswith('OK|'))
finally:
    if minutos_original is None: os.environ.pop('SESSION_INACTIVIDAD_MINUTOS', None)
    else: os.environ['SESSION_INACTIVIDAD_MINUTOS'] = minutos_original
    cu.execute("SELECT id_auditoria FROM auditoria_acceso WHERE id_auditoria > %s AND resultado = 'CIERRE_INACTIVIDAD' AND id_usuario = %s",
               (ID_BASE, ADMIN[0]))
    propios = [x[0] for x in cu.fetchall()]
    if propios:
        cu.execute("SET session_replication_role = replica")
        cu.execute("DELETE FROM auditoria_acceso WHERE id_auditoria = ANY(%s)", (propios,))
        cu.execute("RESET session_replication_role")
    cu.close(); cx.close()

print('FALLOS:', 'ninguno' if not fallos else fallos)
