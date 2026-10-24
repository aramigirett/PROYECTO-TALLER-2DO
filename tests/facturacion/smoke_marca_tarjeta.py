import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from app import app
from app.conexion.Conexion import Conexion

c = app.test_client()
creados = set()
fallos = []

def chk(nombre, r, esperado, extra=None):
    ok = r.status_code == esperado and (extra is None or extra(r.get_json()))
    print(('OK  ' if ok else 'FAIL'), nombre, r.status_code)
    if not ok:
        fallos.append(nombre)
    return r.get_json() if r.is_json else None

chk('sin sesion', c.get('/api/v1/marcas-tarjeta'), 401)
with c.session_transaction() as s:
    s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

r = c.get('/referenciales/marca-tarjeta/marca-tarjeta-index')
print('OK  ' if r.status_code == 200 and b'Marcas de Tarjeta' in r.data and b'/api/v1/marcas-tarjeta' in r.data else 'FAIL', 'vista', r.status_code)
chk('lista seed', c.get('/api/v1/marcas-tarjeta'), 200, lambda d: {'VISA', 'MASTERCARD', 'AMERICAN EXPRESS', 'CABAL', 'PANAL'} <= {x['descripcion'] for x in d['data']})

d = chk('alta', c.post('/api/v1/marcas-tarjeta', json={'descripcion': '  zz   prueba '}), 201, lambda d: d['data']['descripcion'] == 'ZZ PRUEBA')
i = d['data']['id_marca_tarjeta']; creados.add(i)
chk('dup (otra capitalizacion)', c.post('/api/v1/marcas-tarjeta', json={'descripcion': 'visa'}), 400, lambda d: 'ya existe' in d['error'])
chk('vacia', c.post('/api/v1/marcas-tarjeta', json={'descripcion': '  '}), 400)
chk('larga', c.post('/api/v1/marcas-tarjeta', json={'descripcion': 'A' * 61}), 400)
chk('simbolos', c.post('/api/v1/marcas-tarjeta', json={'descripcion': 'a<b>'}), 400)
chk('sin body', c.post('/api/v1/marcas-tarjeta'), 400)
chk('get', c.get(f'/api/v1/marcas-tarjeta/{i}'), 200)
chk('mod', c.put(f'/api/v1/marcas-tarjeta/{i}', json={'descripcion': 'zz prueba 2'}), 200)
chk('mod sin cambios', c.put(f'/api/v1/marcas-tarjeta/{i}', json={'descripcion': 'ZZ PRUEBA 2'}), 200, lambda d: 'sin cambios' in d['mensaje'])
chk('mod dup', c.put(f'/api/v1/marcas-tarjeta/{i}', json={'descripcion': 'cabal'}), 400, lambda d: 'ya existe' in d['error'])
chk('mod inexistente', c.put('/api/v1/marcas-tarjeta/999999', json={'descripcion': 'x'}), 404)
chk('baja', c.delete(f'/api/v1/marcas-tarjeta/{i}'), 200, lambda d: 'anulada' in d['mensaje'])
chk('baja 2', c.delete(f'/api/v1/marcas-tarjeta/{i}'), 404)
chk('get anulada', c.get(f'/api/v1/marcas-tarjeta/{i}'), 404)
d = chk('realta tras baja', c.post('/api/v1/marcas-tarjeta', json={'descripcion': 'zz prueba 2'}), 201)
creados.add(d['data']['id_marca_tarjeta'])

con = Conexion().getConexion(); cur = con.cursor()
cur.execute("SELECT accion, id_usuario, ip FROM auditoria_cambios WHERE entidad='marca_tarjeta' AND id_registro = ANY(%s) ORDER BY id_auditoria_cambio", (list(creados),))
acc = cur.fetchall(); print('AUD', acc)
esperado = ['ALTA', 'MODIFICACION', 'BAJA', 'ALTA']
print('OK  ' if [a[0] for a in acc] == esperado and all(a[1] == 1 and a[2] == '127.0.0.1' for a in acc) else 'FAIL', 'auditoria (sin fila para "sin cambios")')

cur.execute("SELECT id_rol FROM roles WHERE nombre_rol <> 'Administrador' LIMIT 1"); rr = cur.fetchone()
with c.session_transaction() as s:
    s['id_rol'] = rr[0]; s['nombre_rol'] = 'NoAdmin'
chk('rol no-admin (seed)', c.get('/referenciales/marca-tarjeta/marca-tarjeta-index'), 200)

# limpieza acotada: solo lo creado por este test
cur.execute("DELETE FROM auditoria_cambios WHERE entidad='marca_tarjeta' AND id_registro = ANY(%s)", (list(creados),))
cur.execute("DELETE FROM marca_tarjeta WHERE id_marca_tarjeta = ANY(%s)", (list(creados),))
con.commit(); cur.close(); con.close()
print('FALLOS:', fallos or 'ninguno')
