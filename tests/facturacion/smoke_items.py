import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from tests.facturacion._limpieza import borrar_auditoria
from app import app
from tests._conexion_pruebas import Conexion
from app.rutas.modulo_facturacion import utils

c = app.test_client()
creados = {'tipo_items': set(), 'items': set()}
fallos = []

def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)

def api(metodo, url, esperado, json=None, nombre=None, campo=None, contiene=None, exacto=None):
    f = getattr(c, metodo)
    r = f(url, json=json) if json is not None else f(url)
    d = r.get_json(silent=True) or {}
    ok = r.status_code == esperado
    if campo is not None:
        ok = ok and d.get('campo') == campo
    if contiene is not None:
        ok = ok and contiene in (d.get('error') or d.get('mensaje') or '')
    if exacto is not None:
        ok = ok and (d.get('error') or d.get('mensaje') or '') == exacto
    chk(f"{nombre or metodo + ' ' + url} -> {r.status_code}" + ('' if ok else f' {d}'), ok)
    return d

TI = '/api/v1/tipos-item'; IT = '/api/v1/items'; DP = '/api/v1/depositos'
_cx0 = Conexion().getConexion(); _cu0 = _cx0.cursor()
def _dep(nombre):
    _cu0.execute("SELECT id_deposito FROM deposito WHERE activo AND UPPER(descripcion)=%s", (nombre,)); return _cu0.fetchone()[0]
DEP_P = _dep('DEPÓSITO PRINCIPAL'); DEP_O = _dep('DEPÓSITO ORTODONCIA')
deps_creados = set()

# ---------- validadores unitarios ----------
vp = utils.validar_precio
chk('precio ok', vp('15000') == (15000, None) and vp(15000) == (15000, None))
for malo in [0, -5, '0', 15000.5, '15000.5', '15.000', True, 'abc', '', None, 10 ** 12]:
    chk(f'precio invalido {malo!r}', vp(malo)[1] is not None)
chk('precio maximo ok', vp(999_999_999_999)[1] is None)
chk('iva ok', [utils.validar_iva(x)[1] for x in (0, 5, 10, '5')] == [None] * 4)
chk('iva invalido', all(utils.validar_iva(x)[1] for x in (7, 'x', None, True, 15)))
vc = utils.validar_cantidad
chk('cantidad ok', vc(0)[1] is None and vc('12') == (12, None))
chk('cantidad invalida', all(vc(x)[1] for x in (-1, 'x', None, '', 1.5, True, 2 ** 31)))

with c.session_transaction() as s:
    s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

# ---------- vistas ----------
for url, txt in [('/referenciales/tipo-item/tipo-item-index', b'Tipo de &Iacute;tems'), ('/referenciales/item/item-index', b'')]:
    r = c.get(url); chk(f'vista {url}', r.status_code == 200 and b'facturacion-validadores.js' in r.data)
r = c.get('/static/js/facturacion-validadores.js'); chk('js tiene precio/iva/cantidad/formatoGs', all(x in r.data for x in (b'precio:', b'iva:', b'cantidad:', b'formatoGs')))

# ---------- TIPO ÍTEMS ----------
d = api('get', TI, 200, nombre='tipos lista')
activos = {(x['descripcion'], x['controla_stock']) for x in d['data']}
chk('seed tipos (5 de odontología, con su controla_stock)', {
    ('HIGIENE BUCAL', True), ('ORTODONCIA', True), ('APARATOLOGÍA Y PROTECCIÓN', True),
    ('ESTUDIOS RADIOGRÁFICOS', False), ('DOCUMENTOS Y CERTIFICADOS', False)} <= activos)
chk('PRODUCTO y SERVICIO ya no están activos', not ({'PRODUCTO', 'SERVICIO'} & {x[0] for x in activos}))
api('post', TI, 400, {'descripcion': ' ', 'controla_stock': True}, 'tipo desc vacia', campo='descripcion')
api('post', TI, 400, {'descripcion': 'a%b', 'controla_stock': True}, 'tipo desc % (regla estricta)', campo='descripcion')
api('post', TI, 400, {'descripcion': 'X' * 61, 'controla_stock': True}, 'tipo desc larga', campo='descripcion')
api('post', TI, 400, {'descripcion': 'ZZ T'}, 'tipo sin controla_stock', campo='controla_stock')
api('post', TI, 400, {'descripcion': 'ZZ T', 'controla_stock': 'si'}, 'tipo controla_stock no bool', campo='controla_stock')
api('post', TI, 400, {'descripcion': 'higiene bucal', 'controla_stock': True}, 'tipo dup', campo='descripcion', contiene='ya existe')
d = api('post', TI, 201, {'descripcion': '  zz tipo   stock ', 'controla_stock': True}, 'tipo alta stock')
t_stock = d['data']['id_tipo_item']; creados['tipo_items'].add(t_stock)
chk('tipo normalizado', d['data']['descripcion'] == 'ZZ TIPO STOCK')
d = api('post', TI, 201, {'descripcion': 'zz tipo serv', 'controla_stock': False}, 'tipo alta servicio')
t_serv = d['data']['id_tipo_item']; creados['tipo_items'].add(t_serv)
d = api('post', TI, 201, {'descripcion': 'zz tipo tog', 'controla_stock': True}, 'tipo alta toggle')
t_tog = d['data']['id_tipo_item']; creados['tipo_items'].add(t_tog)
api('get', f'{TI}/{t_serv}', 200, nombre='tipo get')
api('put', f'{TI}/{t_stock}', 200, {'descripcion': 'zz tipo stock', 'controla_stock': True}, 'tipo mod sin cambios', contiene='sin cambios')
api('put', f'{TI}/{t_tog}', 200, {'descripcion': 'zz tipo toggle', 'controla_stock': False}, 'tipo mod desc + controla (sin items): permitido')
api('put', f'{TI}/{t_tog}', 200, {'descripcion': 'zz tipo toggle', 'controla_stock': True}, 'tipo vuelve a controlar')
api('put', f'{TI}/{t_tog}', 400, {'descripcion': 'documentos y certificados', 'controla_stock': True}, 'tipo mod dup', campo='descripcion')
api('put', f'{TI}/99999', 404, {'descripcion': 'x', 'controla_stock': True}, 'tipo mod inexistente')

# ---------- ÍTEMS: validaciones ----------
ok_item = {'id_tipo_item': t_stock, 'id_deposito': DEP_P, 'descripcion': ' zz  cepillo  prueba ', 'precio_unitario': '15000', 'iva': '10', 'cantidad_disponible': '5'}
api('post', IT, 400, {**ok_item, 'descripcion': ''}, 'item desc vacia', campo='descripcion')
api('post', IT, 400, {**ok_item, 'descripcion': 'A' * 101}, 'item desc 101', campo='descripcion')
api('post', IT, 400, {**ok_item, 'descripcion': 'zz <x>'}, 'item desc simbolo invalido', campo='descripcion')
api('post', IT, 400, {**ok_item, 'id_tipo_item': None}, 'item sin tipo', campo='id_tipo_item')
api('post', IT, 400, {**ok_item, 'id_tipo_item': 999999}, 'item tipo inexistente', campo='id_tipo_item')
for malo in [None, '', 'abc', 0]:
    api('post', IT, 400, {**ok_item, 'id_deposito': malo}, f'item sin depósito válido {malo!r}', campo='id_deposito', exacto='Debe seleccionar un depósito.')
api('post', IT, 400, {**ok_item, 'id_deposito': 999999}, 'item depósito inexistente', campo='id_deposito', exacto='El depósito seleccionado no existe o está anulado.')
d = api('post', DP, 201, {'descripcion': 'zz deposito anulado', 'ubicacion': 'zz ubic'}, 'depósito de prueba')
dep_x = d['data']['id_deposito']; deps_creados.add(dep_x)
api('delete', f'{DP}/{dep_x}', 200, nombre='depósito de prueba anulado (sin ítems)')
api('post', IT, 400, {**ok_item, 'id_deposito': dep_x}, 'item con depósito ANULADO', campo='id_deposito', exacto='El depósito seleccionado no existe o está anulado.')
for malo in [0, -1, '15000.5', 15000.5, 'abc', '', True, 10 ** 12]:
    api('post', IT, 400, {**ok_item, 'precio_unitario': malo}, f'item precio {malo!r}', campo='precio_unitario')
for malo in [7, 'x', '', None, 15]:
    api('post', IT, 400, {**ok_item, 'iva': malo}, f'item iva {malo!r}', campo='iva')
for malo in [-1, 'x', '', None, 1.5]:
    api('post', IT, 400, {**ok_item, 'cantidad_disponible': malo}, f'item cantidad {malo!r} (tipo con stock)', campo='cantidad_disponible')

# ---------- ÍTEMS: altas y stock ----------
d = api('post', IT, 201, ok_item, 'item alta (tipo con stock)')
i1 = d['data']['id_item']; creados['items'].add(i1)
chk('item trae el depósito', d['data']['id_deposito'] == DEP_P and d['data']['deposito'] == 'DEPÓSITO PRINCIPAL')
chk('item normalizado', d['data']['descripcion'] == 'ZZ CEPILLO PRUEBA' and d['data']['precio_unitario'] == 15000 and d['data']['iva'] == 10 and d['data']['cantidad_disponible'] == 5 and d['data']['tipo_item'] == 'ZZ TIPO STOCK' and d['data']['controla_stock'] is True)
d = api('post', IT, 201, {**ok_item, 'id_tipo_item': t_serv, 'descripcion': 'zz servicio a', 'cantidad_disponible': 99, 'iva': 0}, 'item alta servicio con cantidad 99')
i2 = d['data']['id_item']; creados['items'].add(i2)
chk('servicio: cantidad forzada a 0 (y IVA exenta)', d['data']['cantidad_disponible'] == 0 and d['data']['iva'] == 0)
d = api('post', IT, 201, {**ok_item, 'id_tipo_item': t_serv, 'descripcion': 'zz servicio b', 'cantidad_disponible': 'basura'}, 'item servicio ignora cantidad invalida')
i3 = d['data']['id_item']; creados['items'].add(i3)
chk('servicio b cantidad 0', d['data']['cantidad_disponible'] == 0)
d = api('post', IT, 201, {**ok_item, 'descripcion': 'zz anestesia 2% (ampolla) + aguja, x&y', 'cantidad_disponible': 0}, 'item desc ampliada valida')
i4 = d['data']['id_item']; creados['items'].add(i4)
d = api('post', IT, 201, {**ok_item, 'descripcion': 'Z' * 98 + 'ZZ'.lower()[:2], 'cantidad_disponible': 1}, 'item desc de 100 exactos')
i5 = d['data']['id_item']; creados['items'].add(i5)
api('post', IT, 400, ok_item, 'item dup', campo='descripcion', contiene='ya existe')
api('post', IT, 400, {**ok_item, 'descripcion': 'ZZ cepillo PRUEBA'}, 'item dup otra capitalizacion', campo='descripcion')

# DAO: el stock se fuerza también bajo bloqueo, aunque la API no lo haga
with app.app_context():
    from app.dao.modulo_facturacion.items.ItemDao import ItemDao
    nuevo = ItemDao().guardarItem(t_serv, 'ZZ DAO DIRECTO', 1000, 10, 77, DEP_P)
    creados['items'].add(nuevo)
    chk('DAO fuerza cantidad 0 para tipo sin stock', ItemDao().getItemById(nuevo)['cantidad_disponible'] == 0)
    chk('DAO tipo inexistente', ItemDao().guardarItem(999999, 'ZZ X', 1000, 10, 1, DEP_P) == 'TIPO_INVALIDO')
    chk('DAO depósito inexistente', ItemDao().guardarItem(t_serv, 'ZZ X', 1000, 10, 1, 999999) == 'DEPOSITO_INVALIDO')

# listado
d = api('get', IT, 200, nombre='items lista')
filas = {x['descripcion']: x for x in d['data']}
esperado = {   # descripción: (tipo, precio, stock)
    'CEPILLO DENTAL ADULTO': ('HIGIENE BUCAL', 15000, 50),
    'PASTA DENTAL CON FLÚOR 90G': ('HIGIENE BUCAL', 18000, 40),
    'HILO DENTAL 50M': ('HIGIENE BUCAL', 25000, 30),
    'ENJUAGUE BUCAL 500ML': ('HIGIENE BUCAL', 45000, 20),
    'KIT DE HIGIENE PARA ORTODONCIA': ('ORTODONCIA', 60000, 15),
    'CERA ORTODÓNTICA': ('ORTODONCIA', 20000, 25),
    'PROTECTOR BUCAL DEPORTIVO': ('APARATOLOGÍA Y PROTECCIÓN', 80000, 10),
    'RADIOGRAFÍA PANORÁMICA': ('ESTUDIOS RADIOGRÁFICOS', 120000, 0),
    'RADIOGRAFÍA PERIAPICAL': ('ESTUDIOS RADIOGRÁFICOS', 40000, 0),
    'CERTIFICADO ODONTOLÓGICO': ('DOCUMENTOS Y CERTIFICADOS', 50000, 0),
}
for nombre, (tipo, precio, stock) in esperado.items():
    f = filas.get(nombre)
    # El stock de los ítems con control cambia con el uso normal (los pedidos lo descuentan): se exige solo que no
    # sea negativo. Los ítems sin control de stock siguen exigiendo 0.
    chk(f'seed item {nombre}: {tipo}, Gs. {precio}, IVA 10, stock ' + (str(stock) if stock == 0 else '>= 0 (varía con los pedidos)'),
        f is not None and f['tipo_item'] == tipo and f['precio_unitario'] == precio and f['iva'] == 10
        and (f['cantidad_disponible'] == 0 if stock == 0 else f['cantidad_disponible'] >= 0))
chk('seed: ORTODONCIA -> DEPÓSITO ORTODONCIA, el resto -> DEPÓSITO PRINCIPAL',
    all(filas[n]['deposito'] == ('DEPÓSITO ORTODONCIA' if v[0] == 'ORTODONCIA' else 'DEPÓSITO PRINCIPAL') for n, v in esperado.items()))
_cu0.execute("SELECT is_nullable FROM information_schema.columns WHERE table_name='items' AND column_name='id_deposito'")
chk('migración: items.id_deposito es NOT NULL', _cu0.fetchone()[0] == 'NO')
_cu0.execute("SELECT confdeltype FROM pg_constraint WHERE conname='fk_items_deposito'")
chk('migración: FK fk_items_deposito (RESTRICT)', (_cu0.fetchone() or [None])[0] == 'r')
_cu0.execute("SELECT count(*) FROM items WHERE id_deposito IS NULL")
chk('migración: ningún ítem sin depósito', _cu0.fetchone()[0] == 0)
chk('seed: ítems de tipo sin stock => controla_stock False y stock 0',
    all(filas[n]['controla_stock'] is False and filas[n]['cantidad_disponible'] == 0 for n, v in esperado.items() if v[2] == 0))

# ---------- ÍTEMS: modificación ----------
api('put', f'{IT}/{i1}', 200, ok_item, 'item mod sin cambios', contiene='sin cambios')
d = api('put', f'{IT}/{i1}', 200, {**ok_item, 'precio_unitario': 16500, 'iva': 5, 'cantidad_disponible': 9}, 'item mod precio/iva/stock')
chk('mod aplicada', d['data']['precio_unitario'] == 16500 and d['data']['iva'] == 5 and d['data']['cantidad_disponible'] == 9)
d = api('put', f'{IT}/{i1}', 200, {**ok_item, 'id_tipo_item': t_serv, 'precio_unitario': 16500, 'iva': 5, 'cantidad_disponible': 9}, 'item cambia a tipo SIN stock')
chk('cantidad pasa a 0 al cambiar a tipo sin stock', d['data']['cantidad_disponible'] == 0 and d['data']['controla_stock'] is False)
d = api('put', f'{IT}/{i1}', 200, {**ok_item, 'id_tipo_item': t_stock, 'cantidad_disponible': 7}, 'item vuelve a tipo con stock')
chk('cantidad 7 al volver', d['data']['cantidad_disponible'] == 7)
api('put', f'{IT}/{i1}', 400, {**ok_item, 'descripcion': 'zz servicio a'}, 'item mod dup', campo='descripcion')
api('put', f'{IT}/{i1}', 400, {**ok_item, 'precio_unitario': 0}, 'item mod precio 0', campo='precio_unitario')
api('put', f'{IT}/{i1}', 400, {**ok_item, 'id_tipo_item': 999999}, 'item mod tipo inexistente', campo='id_tipo_item')
api('put', f'{IT}/99999', 404, ok_item, 'item mod inexistente')
d = api('put', f'{IT}/{i4}', 200, {**ok_item, 'descripcion': 'zz anestesia 2% (ampolla) + aguja, x&y', 'cantidad_disponible': 0, 'id_deposito': DEP_O}, 'item cambia de depósito')
chk('depósito cambiado', d['data']['id_deposito'] == DEP_O and d['data']['deposito'] == 'DEPÓSITO ORTODONCIA')
api('put', f'{IT}/{i4}', 400, {**ok_item, 'descripcion': 'zz anestesia 2% (ampolla) + aguja, x&y', 'cantidad_disponible': 0, 'id_deposito': dep_x}, 'mod con depósito anulado', campo='id_deposito')

# ---------- BLOQUEOS ----------
api('put', f'{TI}/{t_stock}', 409, {'descripcion': 'zz tipo stock', 'controla_stock': False}, 'tipo: cambiar controla_stock con items activos -> BLOQUEADO', campo='controla_stock', contiene='Controla stock')
api('put', f'{TI}/{t_stock}', 200, {'descripcion': 'zz tipo stock renombrado', 'controla_stock': True}, 'tipo: renombrar con items activos es valido')
api('delete', f'{TI}/{t_stock}', 409, nombre='tipo baja BLOQUEADA (items activos)', contiene='No se puede dar de baja, el tipo está asignado a uno o más ítems.')
api('delete', f'{TI}/{t_serv}', 409, nombre='tipo servicio baja BLOQUEADA')
# anular todos los items del tipo de stock
for i in (i1, i4, i5):
    api('delete', f'{IT}/{i}', 200, nombre=f'item {i} baja')
api('delete', f'{IT}/{i1}', 404, nombre='item baja repetida')
api('get', f'{IT}/{i1}', 404, nombre='item anulado no se ve')
api('post', IT, 201, {**ok_item, 'cantidad_disponible': 1}, 'item reuso de descripcion tras baja')  # i6
r6 = c.get(IT).get_json()['data']; i6 = [x['id_item'] for x in r6 if x['descripcion'] == 'ZZ CEPILLO PRUEBA'][0]; creados['items'].add(i6)
api('delete', f'{TI}/{t_stock}', 409, nombre='tipo sigue bloqueado (i6 activo)')
api('delete', f'{IT}/{i6}', 200, nombre='item i6 baja')
api('delete', f'{TI}/{t_stock}', 200, nombre='tipo baja OK sin items activos')
api('post', IT, 400, ok_item, 'item con tipo anulado', campo='id_tipo_item')
d = api('get', TI, 200, nombre='combo tipos'); chk('combo no incluye anulado', t_stock not in {x['id_tipo_item'] for x in d['data']})
# tipo sin items: puede cambiar controla_stock libremente
for i in (i2, i3, i4):
    c.delete(f'{IT}/{i}')
cx = Conexion().getConexion(); cu = cx.cursor()
cu.execute("UPDATE items SET activo=false WHERE id_item = ANY(%s)", (list(creados['items']),)); cx.commit()
api('put', f'{TI}/{t_serv}', 200, {'descripcion': 'zz tipo serv', 'controla_stock': True}, 'tipo sin items activos: cambia controla_stock')
api('delete', f'{TI}/{t_serv}', 200, nombre='tipo serv baja OK')
d = api('post', TI, 201, {'descripcion': 'zz tipo stock', 'controla_stock': True}, 'tipo reuso de descripcion tras baja')
creados['tipo_items'].add(d['data']['id_tipo_item'])

# ---------- AUDITORÍA ----------
cu.execute("SELECT accion, id_usuario, ip, detalle FROM auditoria_cambios WHERE entidad='tipo_items' AND id_registro = ANY(%s) ORDER BY id_auditoria_cambio", (list(creados['tipo_items']),))
at = cu.fetchall()
chk('auditoria tipo: ALTA con "Controla stock: Sí/No"', any(x[0] == 'ALTA' and 'Controla stock: Sí' in x[3] for x in at) and any(x[0] == 'ALTA' and 'Controla stock: No' in x[3] for x in at))
chk('auditoria tipo: usuario/ip', all(x[1] == 1 and x[2] == '127.0.0.1' for x in at))
chk('auditoria tipo: toggle registrado, sin fila para "sin cambios"', any('Controla stock: Sí -> No' in x[3] for x in at) and sum(1 for x in at if x[0] == 'MODIFICACION' and x[3] == '') == 0)
cu.execute("SELECT accion, detalle FROM auditoria_cambios WHERE entidad='items' AND id_registro = %s ORDER BY id_auditoria_cambio", (i1,))
ai = cu.fetchall(); print('AUD item', [(x[0], x[1][:90]) for x in ai])
chk('auditoria item: ALTA, MOD, MOD, MOD, BAJA (sin fila para "sin cambios")', [x[0] for x in ai] == ['ALTA', 'MODIFICACION', 'MODIFICACION', 'MODIFICACION', 'BAJA'])
chk('auditoria item muestra NOMBRE de tipo, no ID', 'Tipo: ZZ TIPO STOCK' in ai[0][1] and 'ID' not in ai[0][1] and 'Tipo: ZZ TIPO STOCK -> ZZ TIPO SERV' in ai[2][1])
chk('auditoria item: stock a 0 al cambiar a tipo sin stock', 'Stock: 9 -> 0' in ai[2][1])

cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='items' AND id_registro=%s AND accion='MODIFICACION'", (i4,))
chk('auditoría: cambio de depósito con NOMBRES', any('Depósito: DEPÓSITO PRINCIPAL -> DEPÓSITO ORTODONCIA' in x[0] for x in cu.fetchall()))
cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='items' AND id_registro=%s AND accion='ALTA'", (i1,))
chk('auditoría ALTA incluye Depósito', 'Depósito: DEPÓSITO PRINCIPAL' in cu.fetchone()[0])

# ---------- PERMISOS ----------
cu.execute("SELECT id_rol FROM roles WHERE nombre_rol <> 'Administrador' LIMIT 1"); rr = cu.fetchone()
with c.session_transaction() as s:
    s['id_rol'] = rr[0]; s['nombre_rol'] = 'NoAdmin'
for u in ['/referenciales/tipo-item/tipo-item-index', '/referenciales/item/item-index']:
    chk(f'rol no-admin entra {u}', c.get(u).status_code == 200)
cu.execute("DELETE FROM permisos WHERE id_menu = (SELECT id_menu FROM menu WHERE clave='item' AND activo = true) AND id_rol=%s AND accion='nuevo'", (rr[0],)); cx.commit()
api('post', IT, 403, ok_item, 'rol sin "nuevo" -> 403')
cu.execute("INSERT INTO permisos (id_rol, id_menu, accion) SELECT %s, id_menu, 'nuevo' FROM menu WHERE clave='item' AND activo = true ON CONFLICT DO NOTHING", (rr[0],)); cx.commit()

# ---------- LIMPIEZA acotada a lo creado por este test ----------
for ent in ['items', 'tipo_items']:
    borrar_auditoria(cu, ent, list(creados[ent]))
cu.execute("DELETE FROM items WHERE id_item = ANY(%s)", (list(creados['items']),))
cu.execute("DELETE FROM tipo_items WHERE id_tipo_item = ANY(%s)", (list(creados['tipo_items']),))
borrar_auditoria(cu, 'deposito', list(deps_creados))
cu.execute("DELETE FROM deposito WHERE id_deposito = ANY(%s)", (list(deps_creados),))
cx.commit(); cu.close(); cx.close(); _cu0.close(); _cx0.close()
print('FALLOS:', fallos or 'ninguno')
