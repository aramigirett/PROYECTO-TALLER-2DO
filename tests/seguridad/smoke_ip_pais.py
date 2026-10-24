"""Validación de IP por país (base GeoIP local DB-IP Lite): clasificación de IP (interna / permitida / no permitida / sin
geolocalizar), IP simulada solo en modo debug, rechazo ANTES de mirar usuario y contraseña con mensaje genérico, auditoría
(IP_NO_PERMITIDA / IP_SIN_GEOLOCALIZAR con IP, país y usuario si lo ingresó), tablero con filtro por resultado y baja de la
tabla `paises`. Usa IP de prueba y borra SOLO las filas de auditoría que él mismo generó (por ID)."""
import os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from app import app
from tests._conexion_pruebas import Conexion
from app.Services import geoip_service as geo
from app.dao.modulo_seguridad.UsuarioDao import UsuarioDao

fallos = []
MENSAJE = 'No es posible acceder al sistema desde esta ubicación.'
IP_PY, IP_US, IP_SIN_DATO, IP_LAN = '186.16.0.1', '8.8.8.8', '100.64.0.1', '192.168.1.10'
IP_PRUEBA = [IP_PY, IP_US, IP_SIN_DATO, IP_LAN, '127.0.0.1']
CI_INEXISTENTE = '0000001'


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


cx = Conexion().getConexion(); cx.autocommit = True; cu = cx.cursor()
cu.execute("SELECT COALESCE(MAX(id_auditoria), 0) FROM auditoria_acceso")
ID_BASE = cu.fetchone()[0]
cu.execute("SELECT u.id_usuario, r.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.activo AND NOT u.bloqueado ORDER BY 1")
ADMIN = next((u for u in cu.fetchall() if u[2] == 'Administrador'), None)
if not ADMIN:
    print('ABORTADO: se necesita un Administrador activo.'); sys.exit(1)
CI_ADMIN = UsuarioDao().get_by_id(ADMIN[0])['ci_ruc']


def filas(ip=None):
    """Filas de auditoría generadas por este test (id > base), opcionalmente de una IP."""
    cu.execute("SELECT resultado, accion, ip, pais_detectado, id_usuario, ci_ruc_ingresado FROM auditoria_acceso "
               "WHERE id_auditoria > %s AND (%s::text IS NULL OR ip = %s) ORDER BY id_auditoria", (ID_BASE, ip, ip))
    return cu.fetchall()


def intentar(ip, ci_ruc, ruta='/login', **extra):
    """POST desde un cliente nuevo (sin cookies) con la IP simulada; devuelve la respuesta."""
    os.environ['IP_SIMULADA'] = ip
    cliente = app.test_client()
    datos = {'ci_ruc': ci_ruc, 'password': 'No-Es-La-Clave-1!'}
    datos.update(extra)
    return cliente.post(ruta, data=datos)


debug_original = app.debug
simulada_original = os.environ.get('IP_SIMULADA')
ruta_original = os.environ.get('GEOIP_DB_PATH')
try:
    with app.app_context():
        # =====================================================================================================================
        # 1. CLASIFICACIÓN DE IP
        # =====================================================================================================================
        chk('base GeoIP local presente (geoip/dbip-country-lite.mmdb)', geo._ruta_base().exists())
        for ip in ('127.0.0.1', '192.168.1.5', '10.1.2.3', '172.16.0.9', '::1', '169.254.1.1', '::ffff:192.168.0.7'):
            chk(f'{ip} es red interna', geo.es_ip_interna(ip) is True)
        for ip in (IP_US, IP_PY, IP_SIN_DATO):
            chk(f'{ip} NO es red interna', geo.es_ip_interna(ip) is False)
        chk('IP inválida no es interna', geo.es_ip_interna('no-es-ip') is False)

        chk('186.16.0.1 -> PY', geo.pais_de_ip(IP_PY) == 'PY')
        chk('8.8.8.8 -> US', geo.pais_de_ip(IP_US) == 'US')
        chk('IP pública sin registro -> None', geo.pais_de_ip(IP_SIN_DATO) is None)

        os.environ.pop('GEOIP_DB_PATH', None)
        casos = [('127.0.0.1', 'INTERNA', True), (IP_LAN, 'INTERNA', True), (IP_PY, 'PERMITIDA', True),
                 (IP_US, 'NO_PERMITIDA', False), (IP_SIN_DATO, 'SIN_GEOLOCALIZAR', True), ('basura', 'SIN_GEOLOCALIZAR', True)]
        for ip, estado, permitido in casos:
            e = geo.evaluar_ip(ip)
            chk(f'evaluar_ip({ip}) -> {estado}, permitido={permitido}', e['estado'] == estado and e['permitido'] is permitido)

        os.environ['PAIS_PERMITIDO'] = 'us'
        chk('el país permitido se configura en .env (US permite 8.8.8.8 y rechaza PY)',
            geo.evaluar_ip(IP_US)['permitido'] and not geo.evaluar_ip(IP_PY)['permitido'])
        os.environ.pop('PAIS_PERMITIDO')

        os.environ['GEOIP_DB_PATH'] = 'geoip/no_existe.mmdb'
        chk('base ausente: IP pública -> SIN_GEOLOCALIZAR (se permite)', geo.evaluar_ip(IP_US)['estado'] == 'SIN_GEOLOCALIZAR')
        chk('base ausente: la red interna sigue permitida', geo.evaluar_ip(IP_LAN)['estado'] == 'INTERNA')
        os.environ.pop('GEOIP_DB_PATH')

        # =====================================================================================================================
        # 2. IP SIMULADA: SOLO EN MODO DEBUG
        # =====================================================================================================================
        os.environ['IP_SIMULADA'] = IP_US
        with app.test_request_context('/login'):
            app.debug = False
            chk('IP_SIMULADA se IGNORA fuera de modo debug', geo.ip_efectiva('127.0.0.1') == '127.0.0.1')
            app.debug = True
            chk('IP_SIMULADA se usa en modo debug', geo.ip_efectiva('127.0.0.1') == IP_US)

    # =========================================================================================================================
    # 3. LOGIN DESDE UN PAÍS NO PERMITIDO (modo debug + IP simulada)
    # =========================================================================================================================
    app.debug = True
    cu.execute("SELECT intentos_fallidos, bloqueado FROM usuarios WHERE id_usuario = %s", (ADMIN[0],))
    estado_admin = cu.fetchone()

    r = app.test_client().get('/login') if not os.environ.update({'IP_SIMULADA': IP_US}) else None
    texto = r.get_data(as_text=True)
    chk('GET /login desde IP no permitida -> 403 con el mensaje genérico', r.status_code == 403 and MENSAJE in texto)
    chk('GET /login desde IP no permitida: no se muestra el formulario', 'name="password"' not in texto)
    chk('GET /login desde IP no permitida: no deja auditoría (no es un intento)', filas(IP_US) == [])

    r = intentar(IP_US, CI_ADMIN)
    texto = r.get_data(as_text=True)
    chk('POST /login desde IP no permitida -> 403 con el mensaje genérico', r.status_code == 403 and MENSAJE in texto)
    chk('el mensaje no revela país, regla ni si el usuario existe',
        all(p not in texto.lower() for p in ('paraguay', 'estados unidos', 'pais_permitido', 'incorrectos', 'bloquead')))
    f = filas(IP_US)
    chk('auditoría: una sola fila IP_NO_PERMITIDA / LOGIN con IP, país y usuario',
        len(f) == 1 and f[0][:4] == ('IP_NO_PERMITIDA', 'LOGIN', IP_US, 'US') and f[0][4] == ADMIN[0] and f[0][5] == CI_ADMIN)
    cu.execute("SELECT intentos_fallidos, bloqueado FROM usuarios WHERE id_usuario = %s", (ADMIN[0],))
    chk('se rechaza ANTES de evaluar usuario y contraseña (no suma intento fallido ni audita CREDENCIALES_INVALIDAS)',
        cu.fetchone() == estado_admin and all(x[0] != 'CREDENCIALES_INVALIDAS' for x in f))

    n = len(filas())
    r = intentar(IP_US, CI_INEXISTENTE)
    f = filas(IP_US)[-1]
    chk('usuario inexistente: mismo 403 y mismo mensaje; se guarda lo ingresado sin usuario',
        r.status_code == 403 and MENSAJE in r.get_data(as_text=True) and f[0] == 'IP_NO_PERMITIDA' and f[4] is None and f[5] == CI_INEXISTENTE)
    r = intentar(IP_US, 'mi-clave-secreta')
    f = filas(IP_US)[-1]
    chk('si lo tipeado no parece CI/RUC no se guarda (podría ser una contraseña)', f[5] == '[formato inválido]')

    r = intentar(IP_US, CI_ADMIN, ruta='/recuperar')
    chk('/recuperar desde IP no permitida -> vuelve al login y audita', r.status_code == 302 and r.headers['Location'].endswith('/login')
        and filas(IP_US)[-1][0] == 'IP_NO_PERMITIDA')

    # =========================================================================================================================
    # 4. PAÍS PERMITIDO, RED INTERNA Y SIN GEOLOCALIZAR
    # =========================================================================================================================
    r = intentar(IP_PY, CI_INEXISTENTE)
    f = filas(IP_PY)
    chk('desde Paraguay sigue el login normal (credenciales inválidas, 200)', r.status_code == 200 and 'incorrectos' in r.get_data(as_text=True))
    chk('auditoría desde PY: CREDENCIALES_INVALIDAS con país PY y la IP', len(f) == 1 and f[0][0] == 'CREDENCIALES_INVALIDAS' and f[0][2:4] == (IP_PY, 'PY'))

    r = intentar(IP_LAN, CI_INEXISTENTE)
    f = filas(IP_LAN)
    chk('red interna (192.168.x.x): login normal, país NULL, sin filas IP_*',
        r.status_code == 200 and len(f) == 1 and f[0][0] == 'CREDENCIALES_INVALIDAS' and f[0][3] is None)

    r = intentar(IP_SIN_DATO, CI_INEXISTENTE)
    f = filas(IP_SIN_DATO)
    chk('IP pública sin geolocalizar: se PERMITE (login normal)', r.status_code == 200 and 'incorrectos' in r.get_data(as_text=True))
    chk('...y queda IP_SIN_GEOLOCALIZAR en accesos antes de CREDENCIALES_INVALIDAS',
        [x[0] for x in f] == ['IP_SIN_GEOLOCALIZAR', 'CREDENCIALES_INVALIDAS'] and f[0][3] is None and f[0][2] == IP_SIN_DATO)

    os.environ['GEOIP_DB_PATH'] = 'geoip/no_existe.mmdb'
    r = intentar(IP_US, CI_INEXISTENTE)
    chk('base GeoIP ausente: se permite y se audita IP_SIN_GEOLOCALIZAR',
        r.status_code == 200 and filas(IP_US)[-1][0] == 'CREDENCIALES_INVALIDAS' and filas(IP_US)[-2][0] == 'IP_SIN_GEOLOCALIZAR')
    os.environ.pop('GEOIP_DB_PATH')

    # Fuera de modo debug la IP real manda: el cliente de prueba es 127.0.0.1 (interna)
    app.debug = False
    n = len(filas())
    r = intentar(IP_US, CI_INEXISTENTE)
    chk('fuera de modo debug IP_SIMULADA no tiene efecto (127.0.0.1 es interna: login normal)',
        r.status_code == 200 and filas('127.0.0.1')[-1][0] == 'CREDENCIALES_INVALIDAS' and len(filas()) == n + 1)
    app.debug = True

    # =========================================================================================================================
    # 5. TABLERO DEL ADMINISTRADOR
    # =========================================================================================================================
    c = app.test_client()
    with c.session_transaction() as s:
        s['id_usuario'] = ADMIN[0]; s['id_rol'] = ADMIN[1]; s['nombre_rol'] = ADMIN[2]; s['ci_ruc'] = CI_ADMIN
    os.environ.pop('IP_SIMULADA', None)
    d = c.get('/api/v1/auditoria/intentos?resultado=IP_NO_PERMITIDA&limite=1000').get_json()
    datos = d['data']
    chk('tablero: filtro resultado=IP_NO_PERMITIDA devuelve solo ese resultado', d['success'] and datos and all(x['resultado'] == 'IP_NO_PERMITIDA' for x in datos))
    chk('tablero: cada fila trae pais_detectado (US) e IP', any(x['pais_detectado'] == 'US' and x['ip'] == IP_US for x in datos))
    d = c.get('/api/v1/auditoria/intentos?resultado=IP_SIN_GEOLOCALIZAR&limite=1000').get_json()
    chk('tablero: filtro resultado=IP_SIN_GEOLOCALIZAR', d['success'] and d['data'] and all(x['resultado'] == 'IP_SIN_GEOLOCALIZAR' for x in d['data']))
    chk('tablero: sin filtro devuelve más de un resultado', len({x['resultado'] for x in c.get('/api/v1/auditoria/intentos?limite=1000').get_json()['data']}) > 2)
    chk('tablero: resultado con formato inválido -> 400', c.get("/api/v1/auditoria/intentos?resultado=x'%3B--").status_code == 400)
    html = c.get('/referenciales/auditoria/auditoria-index').get_data(as_text=True)
    chk('tablero: la pantalla tiene el filtro de resultado con IP_NO_PERMITIDA, IP_SIN_GEOLOCALIZAR y CIERRE_INACTIVIDAD y la columna País',
        all(t in html for t in ('id="fResultado"', 'value="IP_NO_PERMITIDA"', 'value="IP_SIN_GEOLOCALIZAR"', 'value="CIERRE_INACTIVIDAD"', '<th>País</th>')))

    # =========================================================================================================================
    # 6. TABLA paises Y ATRIBUCIÓN
    # =========================================================================================================================
    cu.execute("SELECT to_regclass('public.paises')")
    chk('la tabla paises fue eliminada', cu.fetchone()[0] is None)
    cu.execute("SELECT data_type, character_maximum_length FROM information_schema.columns WHERE table_name='auditoria_acceso' AND column_name='pais_detectado'")
    chk('auditoria_acceso.pais_detectado VARCHAR(2)', cu.fetchone() == ('character varying', 2))
    login = app.test_client().get('/login').get_data(as_text=True)
    chk('el pie del login atribuye a DB-IP', 'db-ip.com' in login.lower() and 'DB-IP' in login)
    chk('.gitignore excluye .env y geoip/', all(any(l.strip() == t for l in open('.gitignore', encoding='utf-8')) for t in ('.env', 'geoip/')))
finally:
    app.debug = debug_original
    for k, v in (('IP_SIMULADA', simulada_original), ('GEOIP_DB_PATH', ruta_original)):
        if v is None: os.environ.pop(k, None)
        else: os.environ[k] = v
    os.environ.pop('PAIS_PERMITIDO', None)
    # Limpieza: solo las filas de auditoría de ESTE test (id posterior a la base y con IP de prueba), por ID
    cu.execute("SELECT id_auditoria FROM auditoria_acceso WHERE id_auditoria > %s AND ip = ANY(%s)", (ID_BASE, IP_PRUEBA))
    propios = [x[0] for x in cu.fetchall()]
    if propios:
        cu.execute("SET session_replication_role = replica")
        cu.execute("DELETE FROM auditoria_acceso WHERE id_auditoria = ANY(%s)", (propios,))
        cu.execute("RESET session_replication_role")
    cu.close(); cx.close()

print('FALLOS:', 'ninguno' if not fallos else fallos)
