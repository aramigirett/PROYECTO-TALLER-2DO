import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from tests.facturacion._limpieza import borrar_auditoria
from app import app
from tests._conexion_pruebas import Conexion
from app.rutas.modulo_facturacion import utils

c = app.test_client()
creados = {'entidad_emisora': set(), 'entidad_adherida': set(), 'marca_tarjeta': set()}
fallos = []

def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)

def api(metodo, url, esperado, json=None, nombre=None, campo=None, contiene=None):
    r = getattr(c, metodo)(url, json=json) if json is not None else getattr(c, metodo)(url)
    d = r.get_json(silent=True) or {}
    ok = r.status_code == esperado
    if campo is not None:
        ok = ok and d.get('campo') == campo
    if contiene is not None:
        ok = ok and contiene in (d.get('error') or d.get('mensaje') or '')
    chk(f"{nombre or metodo + ' ' + url} -> {r.status_code}" + ('' if ok else f' {d}'), ok)
    return d

# ---------- validadores unitarios ----------
tel = utils.validar_telefono
chk('tel ok +595 21 123456', tel('+595 21 123456')[1] is None)
chk('tel ok 021-123-456', tel('021-123-456')[1] is None)
chk('tel < 6 digitos reales (+5-95 1  = 4 digitos, largo 11)', tel('+5-95 1 -- 1')[1] is not None and 'dígitos' in tel('+5-95 1 -- 1')[1])
chk('tel 5 digitos con separadores (largo>=6)', tel('12 34 5')[1] is not None)
chk('tel 6 digitos exactos', tel('123456')[1] is None)
chk('tel letras', tel('12345a678')[1] is not None)
chk('tel + no inicial', tel('12+3456789')[1] is not None)
chk('tel largo 21', tel('1' * 21)[1] is not None)
chk('tel vacio', tel('   ')[1] is not None)
chk('correo minusculas', utils.validar_correo('  Info@Banco.COM.py ')[0] == 'info@banco.com.py')
for malo in ['sin-arroba', 'a@b', 'a b@c.com', '@x.com', 'a@.com', 'a@x..com']:
    chk(f'correo invalido {malo!r}', utils.validar_correo(malo)[1] is not None)
chk('direccion larga 151', utils.validar_texto('a' * 151, 'dirección', 150)[1] is not None)
chk('direccion colapsa espacios', utils.validar_texto('  Av.   X,  #12 ', 'dirección', 150)[0] == 'Av. X, #12')

with c.session_transaction() as s:
    s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

EM = '/api/v1/entidades-emisoras'; AD = '/api/v1/entidades-adheridas'; MA = '/api/v1/marcas-tarjeta'
ok_emi = {'descripcion': '  zz banco   prueba ', 'direccion': ' Av. Test 1,  Asunción ', 'telefono': '+595 21 123456', 'correo': 'Test@Banco.COM.py'}

# ---------- vistas ----------
for url, txt in [('/referenciales/entidad-emisora/entidad-emisora-index', b'Entidades Emisoras'),
                 ('/referenciales/entidad-adherida/entidad-adherida-index', b'Entidades Adheridas')]:
    r = c.get(url); chk(f'vista {url}', r.status_code == 200 and txt in r.data and b'facturacion-validadores.js' in r.data)
r = c.get('/static/js/facturacion-validadores.js'); chk('js validadores servido', r.status_code == 200 and b'FacturacionValidadores' in r.data)

# ---------- ENTIDAD EMISORA ----------
sin = c.get(EM);
d = api('get', EM, 200, nombre='emisoras lista')
nombres = {x['descripcion'] for x in d['data']}
chk('seed emisoras', {'BANCO ITAÚ', 'BANCO CONTINENTAL', 'SUDAMERIS BANK', 'BANCO NACIONAL DE FOMENTO', 'UENO BANK'} <= nombres)

api('post', EM, 400, {**ok_emi, 'descripcion': ' '}, 'emisora desc vacia', campo='descripcion')
api('post', EM, 400, {**ok_emi, 'direccion': ''}, 'emisora dir vacia', campo='direccion')
api('post', EM, 400, {**ok_emi, 'direccion': 'x' * 151}, 'emisora dir larga', campo='direccion')
api('post', EM, 400, {**ok_emi, 'telefono': '12345'}, 'emisora tel corto', campo='telefono')
api('post', EM, 400, {**ok_emi, 'telefono': '+5-95-1 1'}, 'emisora tel <6 digitos', campo='telefono')
api('post', EM, 400, {**ok_emi, 'correo': 'malo'}, 'emisora correo malo', campo='correo')
api('post', EM, 400, {**ok_emi, 'descripcion': 'BANCO ITAÚ'}, 'emisora dup', campo='descripcion', contiene='ya existe')
api('post', EM, 400, {**ok_emi, 'descripcion': 'banco itaú'}, 'emisora dup otra capitalizacion', campo='descripcion')
d = api('post', EM, 201, ok_emi, 'emisora alta')
e1 = d['data']['id_entidad_emisora']; creados['entidad_emisora'].add(e1)
chk('emisora normalizada', d['data']['descripcion'] == 'ZZ BANCO PRUEBA' and d['data']['correo'] == 'test@banco.com.py' and d['data']['direccion'] == 'Av. Test 1, Asunción')
d = api('get', f'{EM}/{e1}', 200, nombre='emisora get')
chk('emisora correo guardado en minusculas', d['data']['correo'] == 'test@banco.com.py')
api('put', f'{EM}/{e1}', 200, {**ok_emi, 'telefono': '021 999 888'}, 'emisora mod tel')
api('put', f'{EM}/{e1}', 200, {**ok_emi, 'telefono': '021 999 888'}, 'emisora mod sin cambios', contiene=None)
api('put', f'{EM}/{e1}', 400, {**ok_emi, 'descripcion': 'ueno bank'}, 'emisora mod dup', campo='descripcion')
api('put', f'{EM}/{e1}', 400, {**ok_emi, 'correo': 'x'}, 'emisora mod correo malo', campo='correo')
api('put', f'{EM}/99999', 404, ok_emi, 'emisora mod inexistente')

# ---------- MARCA (de prueba, propia) ----------
d = api('post', MA, 201, {'descripcion': 'zz marca prueba'}, 'marca alta')
m1 = d['data']['id_marca_tarjeta']; creados['marca_tarjeta'].add(m1)

# ---------- ENTIDAD ADHERIDA ----------
base = {'descripcion': ' zz  adherida ', 'id_entidad_emisora': e1, 'id_marca_tarjeta': m1,
        'direccion': 'Calle Ad 2', 'telefono': '021 555 000', 'correo': 'Ad@Proc.com.py'}
d = api('get', AD, 200, nombre='adheridas lista')
filas = {(x['descripcion'], x['entidad_emisora'], x['marca_tarjeta']) for x in d['data']}
chk('seed adheridas', {('BANCARD', 'BANCO ITAÚ', 'VISA'), ('CABAL', 'BANCO CONTINENTAL', 'CABAL')} <= filas)

api('post', AD, 400, {**base, 'id_entidad_emisora': None}, 'adherida sin emisora', campo='id_entidad_emisora')
api('post', AD, 400, {**base, 'id_marca_tarjeta': ''}, 'adherida sin marca', campo='id_marca_tarjeta')
api('post', AD, 400, {**base, 'id_entidad_emisora': 999999}, 'adherida emisora inexistente', campo='id_entidad_emisora')
api('post', AD, 400, {**base, 'id_marca_tarjeta': 999999}, 'adherida marca inexistente', campo='id_marca_tarjeta')
api('post', AD, 400, {**base, 'telefono': '123'}, 'adherida tel malo', campo='telefono')
api('post', AD, 400, {**base, 'correo': 'x@'}, 'adherida correo malo', campo='correo')
api('post', AD, 400, {**base, 'direccion': ' '}, 'adherida dir vacia', campo='direccion')
d = api('post', AD, 201, base, 'adherida alta')
a1 = d['data']['id_entidad_adherida']; creados['entidad_adherida'].add(a1)
api('post', AD, 400, base, 'adherida dup (misma terna)', campo='descripcion', contiene='Ya existe')
# misma descripcion con OTRA marca es valida
d = api('post', MA, 201, {'descripcion': 'zz marca prueba b'}, 'marca alta b'); m2 = d['data']['id_marca_tarjeta']; creados['marca_tarjeta'].add(m2)
d = api('post', AD, 201, {**base, 'id_marca_tarjeta': m2}, 'adherida misma desc otra marca (valida)')
a2 = d['data']['id_entidad_adherida']; creados['entidad_adherida'].add(a2)
d = api('get', f'{AD}/{a1}', 200, nombre='adherida get')
chk('adherida con nombres de banco y marca', d['data']['entidad_emisora'] == 'ZZ BANCO PRUEBA' and d['data']['marca_tarjeta'] == 'ZZ MARCA PRUEBA' and d['data']['correo'] == 'ad@proc.com.py')
api('put', f'{AD}/{a2}', 400, {**base, 'id_marca_tarjeta': m1}, 'adherida mod -> choca con otra', campo='descripcion')
api('put', f'{AD}/{a1}', 200, {**base, 'direccion': 'Otra 3'}, 'adherida mod direccion')
api('put', f'{AD}/{a1}', 200, {**base, 'direccion': 'Otra 3'}, 'adherida mod sin cambios')

# ---------- BLOQUEOS DE BAJA ----------
api('delete', f'{EM}/{e1}', 409, nombre='emisora baja BLOQUEADA (adherida activa)', contiene='No se puede dar de baja, el banco está asociado a una entidad adherida')
api('delete', f'{MA}/{m1}', 409, nombre='marca baja BLOQUEADA (adherida activa)', contiene='No se puede dar de baja, la marca está asociada a una entidad adherida')
api('delete', f'{MA}/{m2}', 409, nombre='marca b baja BLOQUEADA (adherida activa)')
api('delete', f'{AD}/{a1}', 200, nombre='adherida a1 baja')
api('delete', f'{EM}/{e1}', 409, nombre='emisora sigue bloqueada (queda a2)')
api('delete', f'{MA}/{m1}', 200, nombre='marca m1 baja OK (a1 ya anulada)')
api('delete', f'{AD}/{a2}', 200, nombre='adherida a2 baja')
api('delete', f'{AD}/{a2}', 404, nombre='adherida a2 baja repetida')
api('delete', f'{EM}/{e1}', 200, nombre='emisora baja OK (sin adheridas activas)')
api('delete', f'{MA}/{m2}', 200, nombre='marca m2 baja OK')
api('post', AD, 400, base, 'adherida con emisora/marca anuladas', campo='id_entidad_emisora')
api('get', f'{EM}/{e1}', 404, nombre='emisora anulada no se ve')
d = api('get', EM, 200, nombre='combo emisoras sin anuladas'); chk('combo emisoras no incluye anulada', e1 not in {x['id_entidad_emisora'] for x in d['data']})
d = api('get', MA, 200, nombre='combo marcas sin anuladas'); chk('combo marcas no incluye anuladas', not ({m1, m2} & {x['id_marca_tarjeta'] for x in d['data']}))
# reuso de descripcion tras la baja
d = api('post', EM, 201, ok_emi, 'emisora realta tras baja'); e2 = d['data']['id_entidad_emisora']; creados['entidad_emisora'].add(e2)

# ---------- AUDITORIA ----------
con = Conexion().getConexion(); cur = con.cursor()
def aud(ent):
    cur.execute("SELECT accion, id_usuario, ip, detalle FROM auditoria_cambios WHERE entidad=%s AND id_registro = ANY(%s) ORDER BY id_auditoria_cambio", (ent, list(creados[ent])))
    return cur.fetchall()
a = aud('entidad_emisora'); print('AUD emisora', [(x[0], x[3][:60]) for x in a])
chk('auditoria emisora: ALTA, MOD, BAJA, ALTA (sin fila para "sin cambios")', [x[0] for x in a] == ['ALTA', 'MODIFICACION', 'BAJA', 'ALTA'] and all(x[1] == 1 and x[2] == '127.0.0.1' for x in a))
chk('auditoria emisora MOD solo lista lo que cambió', 'Teléfono' in a[1][3] and 'Dirección' not in a[1][3])
a = aud('entidad_adherida'); print('AUD adherida', [(x[0], x[3][:60]) for x in a])
chk('auditoria adherida: 2 ALTA, MOD, BAJA, BAJA', sorted(x[0] for x in a) == sorted(['ALTA', 'ALTA', 'MODIFICACION', 'BAJA', 'BAJA']))

# ---------- PERMISOS ----------
cur.execute("SELECT id_rol FROM roles WHERE nombre_rol <> 'Administrador' LIMIT 1"); rr = cur.fetchone()
with c.session_transaction() as s:
    s['id_rol'] = rr[0]; s['nombre_rol'] = 'NoAdmin'
for u in ['/referenciales/entidad-emisora/entidad-emisora-index', '/referenciales/entidad-adherida/entidad-adherida-index']:
    chk(f'rol no-admin entra {u}', c.get(u).status_code == 200)
cur.execute("DELETE FROM permisos WHERE id_menu = (SELECT id_menu FROM menu WHERE clave='entidademisora' AND activo = true) AND id_rol=%s AND accion='anular'", (rr[0],))  # simular rol sin 'anular'
con.commit()
api('delete', f'{EM}/{e2}', 403, nombre='rol sin anular -> 403')
cur.execute("INSERT INTO permisos (id_rol, id_menu, accion) SELECT %s, id_menu, 'anular' FROM menu WHERE clave='entidademisora' AND activo = true ON CONFLICT DO NOTHING", (rr[0],))
con.commit()

# ---------- LIMPIEZA acotada a lo creado por este test ----------
for ent in ['entidad_adherida', 'entidad_emisora', 'marca_tarjeta']:
    borrar_auditoria(cur, ent, list(creados[ent]))
cur.execute("DELETE FROM entidad_adherida WHERE id_entidad_adherida = ANY(%s)", (list(creados['entidad_adherida']),))
cur.execute("DELETE FROM entidad_emisora WHERE id_entidad_emisora = ANY(%s)", (list(creados['entidad_emisora']),))
cur.execute("DELETE FROM marca_tarjeta WHERE id_marca_tarjeta = ANY(%s)", (list(creados['marca_tarjeta']),))
con.commit(); cur.close(); con.close()
print('FALLOS:', fallos or 'ninguno')
