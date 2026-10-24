"""Registrar Pedido Cliente: esquema, alta (precio/IVA/totales calculados por el servidor, aunque el cliente mande otros),
stock (insuficiente, ítems sin stock, descuento y reposición), anulación (también de un FACTURADO), listado compartido y
filtros, detalle, PDF, auditoría, permisos, bloqueos de baja de Ítems y Cliente, y concurrencia de stock.

Usa usuarios REALES (Administrador, Cajero y Recepción) con sesiones simuladas, y datos de prueba con prefijo ZZ
(tipos, depósito, ítems, cliente y pedidos) que crea y borra POR ID. No toca ítems ni clientes reales."""
import sys, pathlib, threading, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from datetime import date, timedelta
from app import app
from app.conexion.Conexion import Conexion
from app.dao.modulo_facturacion.pedido_cliente.PedidoClienteDao import (
    PedidoClienteDao, calcular_totales, STOCK_INSUFICIENTE, YA_ANULADO, CLIENTE_INVALIDO, ITEM_INVALIDO)
from app.dao.modulo_facturacion.items.ItemDao import ItemDao
from app.dao.modulo_facturacion.cliente.ClienteDao import ClienteDao

c = app.test_client()
fallos = []
PED = '/api/v1/pedidos-cliente'

def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)

def api(metodo, url, esperado, json=None, nombre=None, exacto=None, contiene=None, campo=None):
    f = getattr(c, metodo)
    r = f(url, json=json) if json is not None else f(url)
    d = r.get_json(silent=True) or {}
    ok = r.status_code == esperado
    texto = d.get('error') or d.get('mensaje') or ''
    if exacto is not None:
        ok = ok and texto == exacto
    if contiene is not None:
        ok = ok and contiene in texto
    if campo is not None:
        ok = ok and d.get('campo') == campo
    chk(f"{nombre or metodo + ' ' + url} -> {r.status_code}" + ('' if ok else f' {d}'), ok)
    return d

cx = Conexion().getConexion(); cu = cx.cursor()
cx.autocommit = True

# ---------- usuarios reales ----------
cu.execute("SELECT u.id_usuario, r.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.activo ORDER BY 1")
usuarios = cu.fetchall()
def primero(rol):
    return next((u for u in usuarios if u[2] == rol), None)
ADMIN, CAJERO, RECEP = primero('Administrador'), primero('Cajero'), primero('Recepcion')
if not (ADMIN and CAJERO and RECEP):
    print('ABORTADO: se necesitan un usuario Administrador, uno Cajero y uno de Recepción.'); sys.exit(1)

def como(u):
    with c.session_transaction() as s:
        s['id_usuario'] = u[0]; s['id_rol'] = u[1]; s['nombre_rol'] = u[2]

ids = {'tipo': [], 'dep': None, 'item': {}, 'cliente': []}
pedidos = set()

def stock(k):
    cu.execute("SELECT cantidad_disponible FROM items WHERE id_item=%s", (ids['item'][k],)); return cu.fetchone()[0]

def mkitem(clave, tipo, desc, precio, iva, cant):
    cu.execute("INSERT INTO items(id_tipo_item, descripcion, precio_unitario, iva, cantidad_disponible, id_deposito) "
               "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id_item", (tipo, desc, precio, iva, cant, ids['dep']))
    ids['item'][clave] = cu.fetchone()[0]

def lineas(*pares):
    return [{'id_item': ids['item'][k], 'cantidad': q} for k, q in pares]

def crear(cli, items, esperado=201, **kw):
    d = api('post', PED, esperado, {'id_cliente': cli, 'items': items}, **kw)
    if esperado == 201:
        pedidos.add(d['data']['id_pedido'])
    return d

try:
    # ---------- datos de prueba ----------
    cu.execute("INSERT INTO tipo_items(descripcion, controla_stock) VALUES ('ZZ TIPO PED CON', true) RETURNING id_tipo_item"); T_CON = cu.fetchone()[0]
    cu.execute("INSERT INTO tipo_items(descripcion, controla_stock) VALUES ('ZZ TIPO PED SIN', false) RETURNING id_tipo_item"); T_SIN = cu.fetchone()[0]
    cu.execute("INSERT INTO tipo_items(descripcion, controla_stock) VALUES ('ZZ TIPO PED CAMBIA', true) RETURNING id_tipo_item"); T_CAM = cu.fetchone()[0]
    ids['tipo'] = [T_CON, T_SIN, T_CAM]
    cu.execute("INSERT INTO deposito(descripcion, ubicacion) VALUES ('ZZ DEPOSITO PED', 'ZZ') RETURNING id_deposito"); ids['dep'] = cu.fetchone()[0]
    mkitem('A', T_CON, 'ZZ ITEM A', 10000, 10, 10)
    mkitem('C', T_CON, 'ZZ ITEM C', 21000, 5, 10)
    mkitem('S', T_SIN, 'ZZ ITEM S', 5000, 0, 0)
    mkitem('D', T_CAM, 'ZZ ITEM D', 7000, 10, 5)
    mkitem('E', T_CON, 'ZZ ITEM E', 3000, 10, 5)
    mkitem('F', T_CON, 'ZZ ITEM F', 1000, 10, 1)
    mkitem('G', T_CON, 'ZZ ITEM G', 1000, 10, 50)
    mkitem('H', T_CON, 'ZZ ITEM H', 1000, 10, 50)
    cu.execute("INSERT INTO cliente(nombre, apellido, ci_ruc) VALUES ('ZZ CLIENTE', 'PEDIDO', %s) RETURNING id_cliente", ('ZZP' + str(int(time.time()))[-8:],))
    CLI = cu.fetchone()[0]; ids['cliente'].append(CLI)
    cu.execute("INSERT INTO cliente(nombre, apellido, ci_ruc) VALUES ('ZZ CLIENTE', 'OTRO', %s) RETURNING id_cliente", ('ZZQ' + str(int(time.time()))[-8:],))
    CLI2 = cu.fetchone()[0]; ids['cliente'].append(CLI2)
    cu.execute("INSERT INTO cliente(nombre, apellido, ci_ruc, activo) VALUES ('ZZ CLIENTE', 'INACTIVO', %s, false) RETURNING id_cliente", ('ZZR' + str(int(time.time()))[-8:],))
    CLI_INACT = cu.fetchone()[0]; ids['cliente'].append(CLI_INACT)
    cu.execute("SELECT id_cliente FROM cliente WHERE ci_ruc='44444401-7' AND activo"); CONSUMIDOR = cu.fetchone()[0]

    # ---------- esquema ----------
    cu.execute("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name='pedido_venta_cab' ORDER BY ordinal_position")
    cab = {r[0]: r[1:] for r in cu.fetchall()}
    chk('pedido_venta_cab: columnas', list(cab) == ['id_pedido', 'id_cliente', 'id_usuario', 'fecha_pedido', 'observacion', 'total', 'estado'])
    chk('pedido_venta_cab: observacion NULL; resto NOT NULL', cab['observacion'][1] == 'YES' and all(cab[k][1] == 'NO' for k in cab if k != 'observacion'))
    cu.execute("SELECT column_name FROM information_schema.columns WHERE table_name='pedido_venta_det' ORDER BY ordinal_position")
    chk('pedido_venta_det: columnas', [r[0] for r in cu.fetchall()] == ['id_pedido_det', 'id_pedido', 'id_item', 'cantidad', 'precio_unitario', 'iva', 'subtotal'])
    cu.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='pedido_venta_cab'::regclass AND contype='c'")
    chk("estado CHECK PENDIENTE/FACTURADO/ANULADO", any("PENDIENTE" in r[0] and "FACTURADO" in r[0] and "ANULADO" in r[0] for r in cu.fetchall()))
    cu.execute("SELECT confdeltype FROM pg_constraint WHERE conrelid IN ('pedido_venta_cab'::regclass,'pedido_venta_det'::regclass) AND contype='f'")
    fk = [r[0] for r in cu.fetchall()]
    chk('todas las FK son RESTRICT', len(fk) == 4 and set(fk) == {'r'})
    cu.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='pedido_venta_det'::regclass AND contype='u'")
    chk('UNIQUE (id_pedido, id_item)', any('id_pedido' in r[0] and 'id_item' in r[0] for r in cu.fetchall()))

    # ---------- totales (función pura) ----------
    t = calcular_totales([{'iva': 10, 'subtotal': 30000}, {'iva': 5, 'subtotal': 42000}, {'iva': 0, 'subtotal': 5000}])
    chk('calcular_totales: exentas/gravadas/total', (t['exentas'], t['gravadas_5'], t['gravadas_10'], t['total']) == (5000, 42000, 30000, 77000))
    chk('calcular_totales: IVA liquidado total/21 y total/11', (t['iva_5'], t['iva_10'], t['total_iva']) == (2000, 2727, 4727))

    # ---------- permisos ----------
    como(RECEP)
    api('get', PED, 403, nombre='Recepción sin permiso: listado'); api('post', PED, 403, {}, nombre='Recepción sin permiso: alta')
    api('delete', f'{PED}/1', 403, nombre='Recepción sin permiso: anular'); api('get', f'{PED}/items', 403, nombre='Recepción: buscador de ítems')
    como(CAJERO)
    api('get', PED, 200, nombre='Cajero: listado'); api('get', f'{PED}/items?q=zz', 200, nombre='Cajero: buscador de ítems')
    api('get', f'{PED}/clientes?q=zz', 200, nombre='Cajero: buscador de clientes')
    d = c.get(f'{PED}/clientes?q=').get_json()['data']
    chk('buscador de clientes: SIN NOMBRE disponible y primero', bool(d) and d[0]['ci_ruc'] == '44444401-7')
    d = c.get(f'{PED}/items?q=zz item').get_json()['data']
    chk('buscador de ítems: trae precio, IVA, stock y si controla stock', bool(d) and all(k in d[0] for k in ('precio_unitario', 'iva', 'cantidad_disponible', 'controla_stock')))
    chk('buscador de ítems: no devuelve ítems de otros textos', all('ZZ' in i['descripcion'] for i in d))
    r = c.get('/referenciales/pedido-cliente/pedido-cliente-index'); chk('vista: Cajero 200', r.status_code == 200)
    como(RECEP); r = c.get('/referenciales/pedido-cliente/pedido-cliente-index'); chk('vista: Recepción 403', r.status_code == 403)

    # ---------- alta: el servidor calcula todo ----------
    como(CAJERO)
    cuerpo = {'id_cliente': CLI, 'observacion': '  Retira   mañana  ', 'total': 1, 'id_usuario': ADMIN[0], 'estado': 'FACTURADO',
              'items': [{'id_item': ids['item']['A'], 'cantidad': 3, 'precio_unitario': 1, 'iva': 0, 'subtotal': 1},
                        {'id_item': ids['item']['C'], 'cantidad': '2'},
                        {'id_item': ids['item']['S'], 'cantidad': 1}]}
    d = api('post', PED, 201, cuerpo, nombre='alta con datos falsificados por el navegador')
    P1 = d['data']['id_pedido']; pedidos.add(P1)
    p = d['data']
    chk('total calculado por el servidor (77.000)', p['total'] == 77000)
    chk('estado PENDIENTE y cajero = el de la sesión (no el enviado)', p['estado'] == 'PENDIENTE' and p['id_usuario'] == CAJERO[0])
    chk('observación normalizada', p['observacion'] == 'Retira mañana')
    det = {x['item']: x for x in p['detalle']}
    chk('precio, IVA y subtotal salen de items', (det['ZZ ITEM A']['precio_unitario'], det['ZZ ITEM A']['iva'], det['ZZ ITEM A']['subtotal']) == (10000, 10, 30000)
        and (det['ZZ ITEM C']['subtotal'], det['ZZ ITEM C']['iva']) == (42000, 5) and (det['ZZ ITEM S']['subtotal'], det['ZZ ITEM S']['iva']) == (5000, 0))
    tt = p['totales']
    chk('totales: exentas 5.000, gravadas 5% 42.000, gravadas 10% 30.000, IVA 2.000 + 2.727',
        (tt['exentas'], tt['gravadas_5'], tt['gravadas_10'], tt['iva_5'], tt['iva_10']) == (5000, 42000, 30000, 2000, 2727))
    chk('stock descontado solo en ítems que controlan stock (A 10->7, C 10->8, S sigue 0)', (stock('A'), stock('C'), stock('S')) == (7, 8, 0))
    cu.execute("SELECT count(*), sum(subtotal) FROM pedido_venta_det WHERE id_pedido=%s", (P1,))
    chk('detalle guardado: 3 renglones que suman el total', cu.fetchone() == (3, 77000))

    # ---------- auditoría del alta ----------
    cu.execute("SELECT id_usuario, accion, detalle FROM auditoria_cambios WHERE entidad='pedido_venta_cab' AND id_registro=%s", (P1,))
    aud = cu.fetchall()
    chk('auditoría: 1 ALTA del cajero con nombres (no IDs)', len(aud) == 1 and aud[0][0] == CAJERO[0] and aud[0][1] == 'ALTA'
        and 'ZZ CLIENTE PEDIDO' in aud[0][2] and 'ZZ ITEM A x3' in aud[0][2] and 'Gs. 77.000' in aud[0][2])

    # ---------- stock insuficiente ----------
    api('post', PED, 409, {'id_cliente': CLI, 'items': lineas(('S', 1), ('A', 8))}, nombre='stock insuficiente',
        exacto='Stock insuficiente para ZZ ITEM A: disponible 7, solicitado 8.', campo='items')
    chk('stock insuficiente: nada cambia (ni S ni A)', (stock('A'), stock('S')) == (7, 0))
    cu.execute("SELECT count(*) FROM pedido_venta_cab WHERE id_cliente=%s", (CLI,)); n0 = cu.fetchone()[0]
    chk('stock insuficiente: no se creó pedido', n0 == 1)
    crear(CLI, lineas(('A', 7)), nombre='pide exactamente el stock disponible (7)')
    chk('stock llega a 0', stock('A') == 0)
    api('post', PED, 409, {'id_cliente': CLI, 'items': lineas(('A', 1))}, nombre='stock en 0 -> insuficiente',
        exacto='Stock insuficiente para ZZ ITEM A: disponible 0, solicitado 1.')
    d = crear(CLI, lineas(('S', 1000)), nombre='ítem sin stock: cantidad grande, no valida ni descuenta')
    chk('ítem sin stock sigue en 0', stock('S') == 0)

    # ---------- validaciones ----------
    for nombre, cuerpo_, msg, camp in [
        ('sin cliente', {'items': lineas(('S', 1))}, 'Debe seleccionar un cliente.', 'id_cliente'),
        ('sin ítems', {'id_cliente': CLI, 'items': []}, 'Debe agregar al menos un ítem.', 'items'),
        ('ítems no es lista', {'id_cliente': CLI, 'items': 'x'}, 'Debe agregar al menos un ítem.', 'items'),
        ('cantidad 0', {'id_cliente': CLI, 'items': lineas(('S', 0))}, 'Fila 1: La cantidad debe ser un número entero mayor a 0.', 'items'),
        ('cantidad negativa', {'id_cliente': CLI, 'items': lineas(('S', -2))}, 'Fila 1: La cantidad debe ser un número entero mayor a 0.', 'items'),
        ('cantidad decimal', {'id_cliente': CLI, 'items': lineas(('S', '1.5'))}, 'Fila 1: La cantidad debe ser un número entero mayor a 0.', 'items'),
        ('cantidad texto', {'id_cliente': CLI, 'items': lineas(('S', 'abc'))}, 'Fila 1: La cantidad debe ser un número entero mayor a 0.', 'items'),
        ('ítem repetido', {'id_cliente': CLI, 'items': lineas(('S', 1), ('S', 2))}, 'Un ítem no puede repetirse en el mismo pedido.', 'items'),
        ('id_item inválido', {'id_cliente': CLI, 'items': [{'id_item': 'x', 'cantidad': 1}]}, 'El ítem de la fila 1 no es válido.', 'items'),
        ('ítem inexistente', {'id_cliente': CLI, 'items': [{'id_item': 2147483000, 'cantidad': 1}]}, 'Uno de los ítems seleccionados no existe o está inactivo.', 'items'),
        ('cliente inexistente', {'id_cliente': 2147483000, 'items': lineas(('S', 1))}, 'El cliente seleccionado no existe o está inactivo.', 'id_cliente'),
        ('cliente inactivo', {'id_cliente': CLI_INACT, 'items': lineas(('S', 1))}, 'El cliente seleccionado no existe o está inactivo.', 'id_cliente'),
        ('observación larga', {'id_cliente': CLI, 'observacion': 'a' * 201, 'items': lineas(('S', 1))}, 'La observación no puede superar los 200 caracteres.', 'observacion'),
    ]:
        code = 409 if False else 400
        api('post', PED, code, cuerpo_, nombre=f'validación: {nombre}', exacto=msg, campo=camp)
    api('post', PED, 400, None or {}, nombre='cuerpo vacío')
    crear(CONSUMIDOR, lineas(('S', 1)), nombre='SIN NOMBRE (consumidor final) puede pedir')

    # ---------- listado compartido, filtros, detalle, PDF ----------
    como(ADMIN); lst = api('get', PED, 200, nombre='Administrador: listado')['data']
    ids_adm = {x['id_pedido'] for x in lst}
    como(CAJERO); lst = api('get', PED, 200, nombre='Cajero: listado')['data']
    chk('el listado es compartido: el Cajero ve los pedidos de prueba', P1 in {x['id_pedido'] for x in lst})
    chk('Administrador y Cajero ven los mismos pedidos de prueba', {i for i in ids_adm if i in pedidos} == {x['id_pedido'] for x in lst if x['id_pedido'] in pedidos})
    r = api('get', f'{PED}?cliente=ZZ CLIENTE PEDIDO', 200, nombre='filtro por cliente (nombre)')['data']
    chk('filtro cliente por nombre', bool(r) and all('ZZ CLIENTE PEDIDO' in x['cliente'] for x in r))
    cu.execute("SELECT ci_ruc FROM cliente WHERE id_cliente=%s", (CLI,)); ci = cu.fetchone()[0]
    r = api('get', f'{PED}?cliente={ci}', 200, nombre='filtro por cliente (CI/RUC)')['data']
    chk('filtro cliente por CI/RUC', bool(r) and all(x['ci_ruc'] == ci for x in r))
    r = api('get', f'{PED}?estado=PENDIENTE&cliente={ci}', 200)['data']
    chk('filtro estado PENDIENTE', bool(r) and all(x['estado'] == 'PENDIENTE' for x in r))
    hoy = date.today().isoformat(); ayer = (date.today() - timedelta(days=1)).isoformat(); manana = (date.today() + timedelta(days=1)).isoformat()
    chk('filtro fechas: hoy..hoy incluye el pedido', P1 in {x['id_pedido'] for x in api('get', f'{PED}?desde={hoy}&hasta={hoy}', 200)['data']})
    chk('filtro fechas: hasta ayer no lo incluye', P1 not in {x['id_pedido'] for x in api('get', f'{PED}?hasta={ayer}', 200)['data']})
    chk('filtro fechas: desde mañana no lo incluye', P1 not in {x['id_pedido'] for x in api('get', f'{PED}?desde={manana}', 200)['data']})
    api('get', f'{PED}?estado=XX', 400, nombre='estado inválido'); api('get', f'{PED}?desde=hoy', 400, nombre='fecha inválida')
    api('get', f'{PED}?desde={manana}&hasta={ayer}', 400, nombre='desde > hasta')
    d = api('get', f'{PED}/{P1}', 200, nombre='detalle')['data']
    chk('detalle: cliente, cajero y 3 renglones', d['cliente'] == 'ZZ CLIENTE PEDIDO' and d['cajero'] and len(d['detalle']) == 3)
    api('get', f'{PED}/2147483000', 404, nombre='detalle inexistente')
    r = c.get(f'{PED}/{P1}/pdf'); chk('PDF: 200, application/pdf y empieza con %PDF', r.status_code == 200 and r.mimetype == 'application/pdf' and r.data[:4] == b'%PDF')
    api('get', f'{PED}/2147483000/pdf', 404, nombre='PDF inexistente')

    # ---------- anular: repone stock ----------
    como(CAJERO)
    api('delete', f'{PED}/{P1}', 200, nombre='anular P1', contiene='anulado correctamente')
    chk('stock repuesto (A 0->3, C 8->10, S 0)', (stock('A'), stock('C'), stock('S')) == (3, 10, 0))
    cu.execute("SELECT estado FROM pedido_venta_cab WHERE id_pedido=%s", (P1,)); chk('estado ANULADO', cu.fetchone()[0] == 'ANULADO')
    api('delete', f'{PED}/{P1}', 409, nombre='anular dos veces', exacto='El pedido ya está anulado.')
    chk('anular dos veces NO repone dos veces', (stock('A'), stock('C')) == (3, 10))
    api('delete', f'{PED}/2147483000', 404, nombre='anular inexistente')
    cu.execute("SELECT id_usuario, detalle FROM auditoria_cambios WHERE entidad='pedido_venta_cab' AND id_registro=%s AND accion='BAJA'", (P1,))
    aud = cu.fetchall()
    chk('auditoría BAJA (una sola) con quién anuló y el stock repuesto', len(aud) == 1 and aud[0][0] == CAJERO[0] and 'ZZ ITEM A +3' in aud[0][1] and 'ZZ ITEM C +2' in aud[0][1])
    r = c.get(f'{PED}/{P1}/pdf'); chk('PDF de un pedido anulado se puede descargar', r.status_code == 200 and r.data[:4] == b'%PDF')
    como(ADMIN)
    d = crear(CLI, lineas(('A', 3)), nombre='otro cajero (Administrador) crea'); PA = d['data']['id_pedido']
    como(CAJERO); api('delete', f'{PED}/{PA}', 200, nombre='cualquiera con permiso anular puede anular pedidos ajenos')
    chk('stock de A de vuelta a 3', stock('A') == 3)

    # ---------- FACTURADO no se anula ----------
    como(CAJERO)
    d = crear(CLI, lineas(('A', 2), ('S', 1)), nombre='pedido para facturar'); PF = d['data']['id_pedido']
    cu.execute("UPDATE pedido_venta_cab SET estado='FACTURADO' WHERE id_pedido=%s", (PF,))
    api('delete', f'{PED}/{PF}', 409, nombre='anular un FACTURADO', exacto='El pedido ya fue facturado; no se puede anular.')
    chk('FACTURADO: estado y stock intactos', stock('A') == 1)
    cu.execute("SELECT estado FROM pedido_venta_cab WHERE id_pedido=%s", (PF,)); chk('sigue FACTURADO', cu.fetchone()[0] == 'FACTURADO')
    chk('filtro estado FACTURADO', PF in {x['id_pedido'] for x in api('get', f'{PED}?estado=FACTURADO', 200)['data']})

    # ---------- reposición cuando el tipo ya no controla stock ----------
    d = crear(CLI, lineas(('D', 2)), nombre='pedido de D'); PD = d['data']['id_pedido']
    chk('D descontado (5->3)', stock('D') == 3)
    cu.execute("UPDATE tipo_items SET controla_stock=false WHERE id_tipo_item=%s", (T_CAM,))
    cu.execute("UPDATE items SET cantidad_disponible=0 WHERE id_item=%s", (ids['item']['D'],))
    api('delete', f'{PED}/{PD}', 200, nombre='anular con el tipo ya sin control de stock')
    chk('no se repone stock a un ítem que ya no lo controla', stock('D') == 0)
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='pedido_venta_cab' AND id_registro=%s AND accion='BAJA'", (PD,))
    chk('auditoría anota "Sin reposición"', 'Sin reposición' in cu.fetchone()[0])

    # ---------- bloqueos de baja (Ítems y Cliente) ----------
    with app.app_context():
        d = crear(CLI, lineas(('E', 1)), nombre='pedido PENDIENTE de E'); PE = d['data']['id_pedido']
        r = ItemDao().deleteItem(ids['item']['E'])
        chk('baja de ítem en pedido PENDIENTE bloqueada', r == ('EN_USO', 'No se puede dar de baja, el ítem está en un pedido pendiente.'))
        chk('esta_en_uso del ítem devuelve el motivo', ItemDao().esta_en_uso(ids['item']['E']) == 'No se puede dar de baja, el ítem está en un pedido pendiente.')
        como(ADMIN); api('delete', f'/api/v1/items/{ids["item"]["E"]}', 409, nombre='API: baja de ítem en pedido -> 409', contiene='pedido pendiente')
        cu.execute("UPDATE pedido_venta_cab SET estado='FACTURADO' WHERE id_pedido=%s", (PE,))
        chk('ítem en pedido FACTURADO (ya no PENDIENTE) se puede dar de baja', ItemDao().esta_en_uso(ids['item']['E']) is False)
        cu.execute("UPDATE pedido_venta_cab SET estado='PENDIENTE' WHERE id_pedido=%s", (PE,))
        como(CAJERO); api('delete', f'{PED}/{PE}', 200, nombre='anular pedido de E')
        chk('ítem en pedido ANULADO se puede dar de baja', ItemDao().deleteItem(ids['item']['E']) is True)
        api('post', PED, 400, {'id_cliente': CLI, 'items': lineas(('E', 1))}, nombre='no se puede pedir un ítem dado de baja',
            exacto='Uno de los ítems seleccionados no existe o está inactivo.')
        r = ClienteDao().deleteCliente(CLI)
        chk('baja de cliente con pedidos no anulados bloqueada', r == ('EN_USO', 'No se puede dar de baja, el cliente tiene pedidos registrados.'))
        d = crear(CLI2, lineas(('S', 1)), nombre='pedido de CLI2'); P2 = d['data']['id_pedido']
        chk('baja de cliente con pedido PENDIENTE bloqueada', ClienteDao().deleteCliente(CLI2)[0] == 'EN_USO')
        api('delete', f'{PED}/{P2}', 200, nombre='anular pedido de CLI2')
        chk('cliente con solo pedidos ANULADOS se puede dar de baja', ClienteDao().deleteCliente(CLI2) is True)
        api('post', PED, 400, {'id_cliente': CLI2, 'items': lineas(('S', 1))}, nombre='no se puede pedir para un cliente dado de baja',
            exacto='El cliente seleccionado no existe o está inactivo.')

    # ---------- concurrencia ----------
    def correr(hilos):
        res = [None] * len(hilos); barrera = threading.Barrier(len(hilos))
        def w(i, fn):
            with app.app_context():
                barrera.wait(); res[i] = fn()
        ts = [threading.Thread(target=w, args=(i, f)) for i, f in enumerate(hilos)]
        [t.start() for t in ts]; [t.join(60) for t in ts]
        return res

    dao = PedidoClienteDao()
    res = correr([lambda: dao.guardarPedido(CAJERO[0], CLI, None, [(ids['item']['F'], 1)]) for _ in range(2)])
    ok = [r for r in res if isinstance(r, int)]; mal = [r for r in res if isinstance(r, tuple) and r[0] == STOCK_INSUFICIENTE]
    pedidos.update(ok)
    chk('concurrencia: 2 pedidos por la última unidad -> exactamente 1 gana y 1 recibe stock insuficiente', len(ok) == 1 and len(mal) == 1)
    chk('concurrencia: el stock queda en 0 (nunca negativo)', stock('F') == 0)

    def pedido_cruzado(orden):
        return lambda: dao.guardarPedido(CAJERO[0], CLI, None, [(ids['item'][k], 1) for k in orden])
    g0, h0 = stock('G'), stock('H')
    hilos = [pedido_cruzado('GH') if i % 2 == 0 else pedido_cruzado('HG') for i in range(20)]
    res = correr(hilos)
    pedidos.update(r for r in res if isinstance(r, int))
    chk('concurrencia: 20 pedidos con ítems en orden cruzado, sin deadlock ni fallos', all(isinstance(r, int) for r in res))
    chk('concurrencia: el stock descontado es exacto (20 unidades de G y de H)', (g0 - stock('G'), h0 - stock('H')) == (20, 20))

    d = dao.guardarPedido(CAJERO[0], CLI, None, [(ids['item']['G'], 5)]); pedidos.add(d)
    sg = stock('G')
    res = correr([lambda: dao.anularPedido(d) for _ in range(3)])
    chk('concurrencia: 3 anulaciones simultáneas -> 1 sola repone, 2 reciben "ya anulado"',
        sum(isinstance(r, dict) for r in res) == 1 and sum(r == YA_ANULADO for r in res) == 2)
    chk('concurrencia: el stock se repuso UNA vez (+5)', stock('G') == sg + 5)

finally:
    ped = sorted(pedidos)
    try:
        cu.execute("SELECT id_pedido FROM pedido_venta_cab WHERE id_cliente = ANY(%s)", (ids['cliente'],))
        ped = sorted(set(ped) | {r[0] for r in cu.fetchall()})
        if ped:
            cu.execute("DELETE FROM auditoria_cambios WHERE entidad='pedido_venta_cab' AND id_registro = ANY(%s)", (ped,))
            cu.execute("DELETE FROM pedido_venta_det WHERE id_pedido = ANY(%s)", (ped,))
            cu.execute("DELETE FROM pedido_venta_cab WHERE id_pedido = ANY(%s)", (ped,))
        if ids['item']:
            cu.execute("DELETE FROM items WHERE id_item = ANY(%s)", (list(ids['item'].values()),))
        if ids['tipo']:
            cu.execute("DELETE FROM tipo_items WHERE id_tipo_item = ANY(%s)", (ids['tipo'],))
        if ids['dep']:
            cu.execute("DELETE FROM deposito WHERE id_deposito = %s", (ids['dep'],))
        if ids['cliente']:
            cu.execute("DELETE FROM cliente WHERE id_cliente = ANY(%s)", (ids['cliente'],))
    except Exception as e:
        print('ERROR EN LA LIMPIEZA:', e)
        fallos.append('limpieza')

print()
print('FALLOS:', 'ninguno' if not fallos else fallos)
sys.exit(1 if fallos else 0)
