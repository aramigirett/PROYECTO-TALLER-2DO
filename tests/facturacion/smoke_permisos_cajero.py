"""Permisos del rol Cajero: la matriz de la base contra la regla y contra el catálogo del menú, y el comportamiento
real con una sesión simulada del Cajero. Solo lectura: no crea ni borra nada (los pedidos de escritura apuntan a ids
inexistentes o llevan cuerpo vacío, así que prueban el permiso sin llegar a escribir).

Regla (CLAUDE.md, "Permisos del rol Cajero"): todas las acciones de cada ventana de "Módulo Facturación"; Cliente
con ver/nuevo/editar; los demás referenciales de Facturación solo ver; nada de Agendamiento, Consultorio ni Seguridad."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from flask import url_for
from app import app
from tests._conexion_pruebas import Conexion
from app.rutas.modulo_seguridad.menu_catalog import CATALOGO_MENU

c = app.test_client()
fallos = []

def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)

SOLO_VER = {'formacobro', 'marcatarjeta', 'entidademisora', 'entidadadherida', 'caja', 'deposito', 'tipoitem', 'item', 'cuentabancaria'}
MODULOS_SIN_ACCESO = {'Agendamiento', 'Referenciales Agendamiento', 'Referenciales Consultorio',
                      'Módulo Consultorio', 'Módulo Seguridad'}

def esperado(e):
    if e['modulo'] == 'Módulo Facturación':
        return set(e['acciones'])
    if e['ventana'] == 'cliente':
        return {'ver', 'nuevo', 'editar'}
    if e['ventana'] in SOLO_VER:
        return {'ver'}
    return set()

cx = Conexion().getConexion(); cu = cx.cursor()
cu.execute("SELECT id_rol FROM roles WHERE nombre_rol = 'Cajero'"); ROL = cu.fetchone()[0]
cu.execute("SELECT m.clave, p.accion FROM permisos p JOIN menu m ON m.id_menu = p.id_menu WHERE p.id_rol = %s", (ROL,))
actual = {}
for v, a in cu.fetchall():
    actual.setdefault(v, set()).add(a)
catalogo = {e['ventana']: e for e in CATALOGO_MENU}

# ---------- la matriz de la base ----------
chk('el Cajero no tiene permisos sobre ventanas que no están en el catálogo', set(actual) <= set(catalogo))
for e in CATALOGO_MENU:
    esp, hoy = esperado(e), actual.get(e['ventana'], set())
    chk(f"{e['ventana']}: {sorted(hoy)} == {sorted(esp)}", hoy == esp)
chk('toda acción esperada existe en el catálogo de su ventana',
    all(esperado(e) <= set(e['acciones']) for e in CATALOGO_MENU))
chk('cada ventana de Módulo Facturación tiene TODAS sus acciones (agregarla a schema_permisos_cajero.sql)',
    all(actual.get(e['ventana'], set()) == set(e['acciones']) for e in CATALOGO_MENU if e['modulo'] == 'Módulo Facturación'))
chk('ninguna ventana de Agendamiento, Consultorio ni Seguridad tiene permisos',
    all(not actual.get(e['ventana']) for e in CATALOGO_MENU if e['modulo'] in MODULOS_SIN_ACCESO))
chk('ningún referencial de Facturación (salvo Cliente) tiene nuevo/editar/anular',
    all(actual.get(v, set()) <= {'ver'} for v in SOLO_VER))
chk('Cliente no tiene anular', 'anular' not in actual.get('cliente', set()))

# ---------- comportamiento con la sesión del Cajero ----------
cu.execute("SELECT id_usuario FROM usuarios WHERE id_rol = %s AND activo ORDER BY id_usuario LIMIT 1", (ROL,))
fila = cu.fetchone()
if not fila:
    print('ABORTADO: no hay un usuario Cajero activo para simular la sesión.'); sys.exit(1)
with c.session_transaction() as s:
    s['id_usuario'] = fila[0]; s['id_rol'] = ROL; s['nombre_rol'] = 'Cajero'

NO_EXISTE = 2147483000
API = {'formacobro': '/api/v1/formas-cobro', 'caja': '/api/v1/cajas', 'deposito': '/api/v1/depositos',
       'cliente': '/api/v1/clientes'}

def codigo(metodo, url, json=None):
    f = getattr(c, metodo)
    return (f(url, json=json) if json is not None else f(url)).status_code

for v, base in API.items():
    chk(f'{v}: GET lista permitido (200)', codigo('get', base) == 200)
    chk(f'{v}: POST sin permiso nuevo/ o con cuerpo vacío -> ' + ('400' if v == 'cliente' else '403'),
        codigo('post', base, {}) == (400 if v == 'cliente' else 403))
    chk(f'{v}: PUT -> ' + ('no es 403' if v == 'cliente' else '403'),
        (codigo('put', f'{base}/{NO_EXISTE}', {}) != 403) if v == 'cliente' else (codigo('put', f'{base}/{NO_EXISTE}', {}) == 403))
    chk(f'{v}: DELETE (anular) -> 403', codigo('delete', f'{base}/{NO_EXISTE}') == 403)
    chk(f'{v}: PATCH reactivar -> ' + ('no es 403' if v == 'cliente' else '403'),
        (codigo('patch', f'{base}/{NO_EXISTE}/reactivar') != 403) if v == 'cliente' else (codigo('patch', f'{base}/{NO_EXISTE}/reactivar') == 403))
    chk(f'{v}: ver inactivos (?inactivos=1) permitido (200)', codigo('get', base + '?inactivos=1') == 200)

chk('apertura de caja: lista permitida (200)', codigo('get', '/api/v1/aperturas-caja') == 200)
chk('apertura de caja: abrir con monto inválido llega a validar (400, no 403)',
    codigo('post', '/api/v1/aperturas-caja', {}) == 400)
chk('apertura de caja: anular inexistente no es 403', codigo('delete', f'/api/v1/aperturas-caja/{NO_EXISTE}') != 403)
chk('apertura de caja: cerrar inexistente no es 403', codigo('patch', f'/api/v1/aperturas-caja/{NO_EXISTE}/cerrar') != 403)

with app.test_request_context():
    vistas = {e['ventana']: url_for(e['endpoint']) for e in CATALOGO_MENU if e.get('endpoint')}
for e in CATALOGO_MENU:
    if e['ventana'] not in vistas:
        continue
    r = c.get(vistas[e['ventana']])
    if 'ver' in esperado(e):
        chk(f"vista {e['ventana']}: permitida (200)", r.status_code == 200)
    else:
        chk(f"vista {e['ventana']}: prohibida (403)", r.status_code == 403)

# el menú lateral de la vista permitida solo muestra Facturación
html = c.get(vistas['aperturacaja']).get_data(as_text=True)
for e in CATALOGO_MENU:
    if e['ventana'] not in vistas:
        continue
    visible = vistas[e['ventana']] in html
    if 'ver' in esperado(e):
        chk(f"menú: {e['ventana']} visible", visible)
    else:
        chk(f"menú: {e['ventana']} oculto", not visible)

# ---------- los demás roles no se tocan por este seed ----------
cu.execute("""SELECT r.nombre_rol, count(*) FROM permisos p JOIN roles r USING(id_rol) GROUP BY 1""")
conteos = dict(cu.fetchall())
chk('Medico y Recepcion siguen con permisos (el seed solo toca al Cajero)',
    conteos.get('Medico', 0) > 100 and conteos.get('Recepcion', 0) > 50)   # Recepción quedó con 91 tras quitarle los referenciales clínicos

print()
print('FALLOS:', 'ninguno' if not fallos else fallos)
sys.exit(1 if fallos else 0)
