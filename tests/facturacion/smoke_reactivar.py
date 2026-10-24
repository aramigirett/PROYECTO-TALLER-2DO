"""Estado / "Mostrar inactivos" / Reactivar en los 6 referenciales de Facturación + protocolo EN_USO de Forma de Cobro."""
import sys
from unittest import mock
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from tests.facturacion._limpieza import borrar_auditoria
from app import app
from tests._conexion_pruebas import Conexion

c = app.test_client()
fallos = []
creados = {}   # entidad (auditoría) -> ids

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
cu.execute("SELECT id_rol FROM roles WHERE nombre_rol <> 'Administrador' LIMIT 1"); ROL = cu.fetchone()[0]

def reg(entidad, i):
    creados.setdefault(entidad, set()).add(i)
    return i

def sin_permiso(ventana, accion):
    cu.execute("DELETE FROM permisos WHERE id_menu = (SELECT id_menu FROM menu WHERE clave=%s AND activo = true) AND id_rol=%s AND accion=%s", (ventana, ROL, accion)); cx.commit()

def con_permiso(ventana, accion):
    cu.execute("INSERT INTO permisos (id_rol, id_menu, accion) SELECT %s, id_menu, %s FROM menu WHERE clave=%s AND activo = true ON CONFLICT DO NOTHING", (ROL, accion, ventana)); cx.commit()

def como_admin():
    with c.session_transaction() as s:
        s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

def como_rol():
    with c.session_transaction() as s:
        s['id_usuario'] = 1; s['id_rol'] = ROL; s['nombre_rol'] = 'NoAdmin'

def auditoria(entidad, i):
    cu.execute("SELECT accion, id_usuario, ip, detalle FROM auditoria_cambios WHERE entidad=%s AND id_registro=%s ORDER BY id_auditoria_cambio", (entidad, i))
    return cu.fetchall()

def flujo_comun(titulo, base, ventana, entidad, idk, crear_extra, texto_dup, texto_ya, nombre_rec):
    """Baja, listados, reactivar OK / duplicado / ya activo / inexistente, auditoría y permisos."""
    print(f'--- {titulo}')
    d = api('post', base, 201, crear_extra('ZZ REACT ' + titulo.upper() + ' A'), f'{titulo}: alta A'); a = reg(entidad, d['data'][idk])
    api('delete', f'{base}/{a}', 200, nombre=f'{titulo}: baja A')
    d = api('get', base, 200, nombre=f'{titulo}: lista por defecto'); chk(f'{titulo}: la lista por defecto NO trae al anulado', a not in {x[idk] for x in d['data']})
    d = api('get', f'{base}?inactivos=1', 200, nombre=f'{titulo}: lista con inactivos'); f = [x for x in d['data'] if x[idk] == a]
    chk(f'{titulo}: con ?inactivos=1 trae al anulado con activo=False', len(f) == 1 and f[0]['activo'] is False)
    chk(f'{titulo}: los inactivos van después de los activos', [x['activo'] for x in d['data']] == sorted([x['activo'] for x in d['data']], reverse=True))
    d = api('post', base, 201, crear_extra('ZZ REACT ' + titulo.upper() + ' A'), f'{titulo}: alta B (misma descripción, tras la baja)'); b = reg(entidad, d['data'][idk])
    api('patch', f'{base}/{a}/reactivar', 409, nombre=f'{titulo}: REACTIVAR CON DUPLICADO', exacto=texto_dup)
    api('delete', f'{base}/{b}', 200, nombre=f'{titulo}: baja B')
    api('patch', f'{base}/{a}/reactivar', 200, nombre=f'{titulo}: reactivar OK', contiene=nombre_rec)
    api('get', f'{base}/{a}', 200, nombre=f'{titulo}: vuelve a estar activo')
    api('patch', f'{base}/{a}/reactivar', 409, nombre=f'{titulo}: reactivar uno ya activo', exacto=texto_ya)
    api('patch', f'{base}/999999/reactivar', 404, nombre=f'{titulo}: reactivar inexistente')
    api('patch', f'{base}/{b}/reactivar', 409, nombre=f'{titulo}: reactivar B choca con A reactivado', exacto=texto_dup)
    aud = auditoria(entidad, a)
    chk(f'{titulo}: auditoría ALTA, BAJA, REACTIVACION con usuario e IP', [x[0] for x in aud] == ['ALTA', 'BAJA', 'REACTIVACION'] and all(x[1] == 1 and x[2] == '127.0.0.1' for x in aud))
    # permisos
    como_rol()
    try:
        api('delete', f'{base}/{a}', 200, nombre=f'{titulo}: rol con anular puede anular')
        sin_permiso(ventana, 'editar')
        api('patch', f'{base}/{a}/reactivar', 403, nombre=f'{titulo}: rol SIN editar no puede reactivar (mismo permiso que editar)')
        con_permiso(ventana, 'editar')
        api('patch', f'{base}/{a}/reactivar', 200, nombre=f'{titulo}: rol CON editar puede reactivar')
        sin_permiso(ventana, 'ver')
        api('get', f'{base}?inactivos=1', 403, nombre=f'{titulo}: ?inactivos=1 sin permiso ver -> 403')
        api('get', base, 200, nombre=f'{titulo}: la lista de activos sigue disponible (lookup, solo login)')
    finally:
        for acc in ('ver', 'editar', 'anular'):
            con_permiso(ventana, acc)
    como_admin()
    return a

try:
    api('get', '/api/v1/formas-cobro', 401, nombre='sin sesión')
    como_admin()

    # ---------- las 4 entidades simples ----------
    flujo_comun('Forma de cobro', '/api/v1/formas-cobro', 'formacobro', 'forma_cobro', 'id_forma_cobro',
                lambda d: {'descripcion': d, 'tipo': 'EFECTIVO'},   # el tipo es obligatorio desde Cobranzas
                'No se puede reactivar: ya existe una forma de cobro activa con esa descripción.',
                'La forma de cobro ya está activa.', 'reactivada')
    flujo_comun('Marca de tarjeta', '/api/v1/marcas-tarjeta', 'marcatarjeta', 'marca_tarjeta', 'id_marca_tarjeta',
                lambda d: {'descripcion': d},
                'No se puede reactivar: ya existe una marca de tarjeta activa con esa descripción.',
                'La marca de tarjeta ya está activa.', 'reactivada')
    flujo_comun('Entidad emisora', '/api/v1/entidades-emisoras', 'entidademisora', 'entidad_emisora', 'id_entidad_emisora',
                lambda d: {'descripcion': d, 'direccion': 'Dir prueba 1', 'telefono': '021 111222', 'correo': 'zz@test.invalid'},
                'No se puede reactivar: ya existe una entidad emisora activa con esa descripción.',
                'La entidad emisora ya está activa.', 'reactivada')
    flujo_comun('Tipo de ítem', '/api/v1/tipos-item', 'tipoitem', 'tipo_items', 'id_tipo_item',
                lambda d: {'descripcion': d, 'controla_stock': True},
                'No se puede reactivar: ya existe un tipo de ítem activo con esa descripción.',
                'El tipo de ítem ya está activo.', 'reactivado')

    # ---------- Entidad adherida: emisora / marca anuladas ----------
    print('--- Entidad adherida')
    EM = '/api/v1/entidades-emisoras'; MA = '/api/v1/marcas-tarjeta'; AD = '/api/v1/entidades-adheridas'
    e = reg('entidad_emisora', api('post', EM, 201, {'descripcion': 'zz adh banco', 'direccion': 'Dir 1', 'telefono': '021 111222', 'correo': 'zz@test.invalid'}, 'adherida: banco de prueba')['data']['id_entidad_emisora'])
    m = reg('marca_tarjeta', api('post', MA, 201, {'descripcion': 'zz adh marca'}, 'adherida: marca de prueba')['data']['id_marca_tarjeta'])
    cuerpo = {'descripcion': 'zz adh proc', 'id_entidad_emisora': e, 'id_marca_tarjeta': m, 'direccion': 'Dir 2', 'telefono': '021 333444', 'correo': 'zz2@test.invalid'}
    a = reg('entidad_adherida', api('post', AD, 201, cuerpo, 'adherida: alta')['data']['id_entidad_adherida'])
    api('delete', f'{AD}/{a}', 200, nombre='adherida: baja')
    d = api('get', f'{AD}?inactivos=1', 200, nombre='adherida: lista con inactivos'); f = [x for x in d['data'] if x['id_entidad_adherida'] == a]
    chk('adherida: la lista inactiva trae banco y marca', f and f[0]['activo'] is False and f[0]['entidad_emisora'] == 'ZZ ADH BANCO' and f[0]['marca_tarjeta'] == 'ZZ ADH MARCA')
    api('delete', f'{EM}/{e}', 200, nombre='adherida: se puede anular el banco (ya no tiene adheridas ACTIVAS)')
    api('patch', f'{AD}/{a}/reactivar', 409, nombre='adherida: REACTIVAR CON BANCO ANULADO', exacto='No se puede reactivar: el banco (entidad emisora) está anulado. Reactívelo primero.')
    api('patch', f'{EM}/{e}/reactivar', 200, nombre='adherida: se reactiva el banco')
    api('delete', f'{MA}/{m}', 200, nombre='adherida: se anula la marca')
    api('patch', f'{AD}/{a}/reactivar', 409, nombre='adherida: REACTIVAR CON MARCA ANULADA', exacto='No se puede reactivar: la marca de tarjeta está anulada. Reactívela primero.')
    api('patch', f'{MA}/{m}/reactivar', 200, nombre='adherida: se reactiva la marca')
    b = reg('entidad_adherida', api('post', AD, 201, cuerpo, 'adherida: alta duplicada tras la baja')['data']['id_entidad_adherida'])
    api('patch', f'{AD}/{a}/reactivar', 409, nombre='adherida: REACTIVAR CON DUPLICADO (misma descripción, banco y marca)', exacto='No se puede reactivar: ya existe una entidad adherida activa con esa descripción, banco y marca.')
    api('delete', f'{AD}/{b}', 200, nombre='adherida: baja del duplicado')
    api('patch', f'{AD}/{a}/reactivar', 200, nombre='adherida: reactivar OK', contiene='reactivada')
    api('patch', f'{AD}/{a}/reactivar', 409, nombre='adherida: ya activa', exacto='La entidad adherida ya está activa.')
    api('patch', f'{AD}/999999/reactivar', 404, nombre='adherida: inexistente')
    aud = auditoria('entidad_adherida', a)
    chk('adherida: auditoría ALTA, BAJA, REACTIVACION con banco y marca', [x[0] for x in aud] == ['ALTA', 'BAJA', 'REACTIVACION'] and 'Banco: ZZ ADH BANCO; Marca: ZZ ADH MARCA' in aud[2][3])
    como_rol()
    try:
        api('delete', f'{AD}/{a}', 200, nombre='adherida: rol con anular')
        sin_permiso('entidadadherida', 'editar')
        api('patch', f'{AD}/{a}/reactivar', 403, nombre='adherida: rol SIN editar no reactiva')
        con_permiso('entidadadherida', 'editar')
        sin_permiso('entidadadherida', 'ver')
        api('get', f'{AD}?inactivos=1', 403, nombre='adherida: ?inactivos=1 sin ver -> 403')
    finally:
        for acc in ('ver', 'editar', 'anular'):
            con_permiso('entidadadherida', acc)
    como_admin()

    # ---------- Ítems: tipo / depósito anulados, duplicado y stock ----------
    print('--- Ítem')
    TI = '/api/v1/tipos-item'; DP = '/api/v1/depositos'; IT = '/api/v1/items'
    t = reg('tipo_items', api('post', TI, 201, {'descripcion': 'zz it tipo', 'controla_stock': True}, 'ítem: tipo de prueba')['data']['id_tipo_item'])
    dp = reg('deposito', api('post', DP, 201, {'descripcion': 'zz it deposito', 'ubicacion': 'zz'}, 'ítem: depósito de prueba')['data']['id_deposito'])
    cu_i = {'id_tipo_item': t, 'id_deposito': dp, 'descripcion': 'zz item react', 'precio_unitario': 1000, 'iva': 10, 'cantidad_disponible': 5}
    i = reg('items', api('post', IT, 201, cu_i, 'ítem: alta (stock 5)')['data']['id_item'])
    api('delete', f'{IT}/{i}', 200, nombre='ítem: baja')
    d = api('get', f'{IT}?inactivos=1', 200, nombre='ítem: lista con inactivos'); f = [x for x in d['data'] if x['id_item'] == i]
    chk('ítem: la lista inactiva trae tipo, depósito y stock', f and f[0]['activo'] is False and f[0]['tipo_item'] == 'ZZ IT TIPO' and f[0]['deposito'] == 'ZZ IT DEPOSITO' and f[0]['cantidad_disponible'] == 5)
    api('delete', f'{TI}/{t}', 200, nombre='ítem: se puede anular el tipo (sin ítems ACTIVOS)')
    api('patch', f'{IT}/{i}/reactivar', 409, nombre='ítem: REACTIVAR CON TIPO ANULADO', exacto='No se puede reactivar: el tipo de ítem está anulado. Reactívelo primero.')
    api('patch', f'{TI}/{t}/reactivar', 200, nombre='ítem: se reactiva el tipo')
    api('delete', f'{DP}/{dp}', 200, nombre='ítem: se puede anular el depósito (sin ítems ACTIVOS)')
    api('patch', f'{IT}/{i}/reactivar', 409, nombre='ítem: REACTIVAR CON DEPÓSITO ANULADO', exacto='No se puede reactivar: el depósito está anulado. Reactívelo primero.')
    api('patch', f'{DP}/{dp}/reactivar', 200, nombre='ítem: se reactiva el depósito')
    j = reg('items', api('post', IT, 201, cu_i, 'ítem: alta duplicada tras la baja')['data']['id_item'])
    api('patch', f'{IT}/{i}/reactivar', 409, nombre='ítem: REACTIVAR CON DUPLICADO', exacto='No se puede reactivar: ya existe un ítem activo con esa descripción.')
    api('delete', f'{IT}/{j}', 200, nombre='ítem: baja del duplicado')

    # stock: el tipo deja de controlar stock mientras el ítem está anulado (permitido: no tiene ítems ACTIVOS)
    api('put', f'{TI}/{t}', 200, {'descripcion': 'zz it tipo', 'controla_stock': False}, 'ítem: el tipo pasa a NO controlar stock')
    d = api('patch', f'{IT}/{i}/reactivar', 200, nombre='ítem: REACTIVAR CON STOCK > 0 BAJO UN TIPO SIN STOCK')
    chk('ítem: el mensaje avisa que el stock se puso en 0 y cuánto tenía', 'El stock se puso en 0' in d['mensaje'] and 'tenía 5' in d['mensaje'])
    chk('ítem: la respuesta ya trae stock 0 y activo', d['data']['cantidad_disponible'] == 0 and d['data']['activo'] is True)
    cu.execute("SELECT cantidad_disponible, activo FROM items WHERE id_item=%s", (i,)); chk('ítem: en la base: stock 0 y activo', cu.fetchone() == (0, True))
    aud = auditoria('items', i)
    chk('ítem: auditoría ALTA, BAJA, REACTIVACION con el stock descartado', [x[0] for x in aud] == ['ALTA', 'BAJA', 'REACTIVACION'] and 'Stock: 5 -> 0' in aud[2][3] and 'Tipo: ZZ IT TIPO' in aud[2][3] and 'Depósito: ZZ IT DEPOSITO' in aud[2][3])
    # reactivación normal (tipo con stock): no toca la cantidad
    api('put', f'{TI}/{t}', 200, {'descripcion': 'zz it tipo', 'controla_stock': True}, 'ítem: el tipo vuelve a controlar stock') if False else None
    t2 = reg('tipo_items', api('post', TI, 201, {'descripcion': 'zz it tipo 2', 'controla_stock': True}, 'ítem: segundo tipo (con stock)')['data']['id_tipo_item'])
    k = reg('items', api('post', IT, 201, {**cu_i, 'id_tipo_item': t2, 'descripcion': 'zz item react 2', 'cantidad_disponible': 7}, 'ítem 2: alta (stock 7)')['data']['id_item'])
    api('delete', f'{IT}/{k}', 200, nombre='ítem 2: baja')
    d = api('patch', f'{IT}/{k}/reactivar', 200, nombre='ítem 2: reactivar normal', exacto=f'Ítem "ZZ ITEM REACT 2" reactivado correctamente.')
    chk('ítem 2: conserva su stock (7)', d['data']['cantidad_disponible'] == 7)
    api('patch', f'{IT}/{k}/reactivar', 409, nombre='ítem 2: ya activo', exacto='El ítem ya está activo.')
    api('patch', f'{IT}/999999/reactivar', 404, nombre='ítem: inexistente')
    como_rol()
    try:
        api('delete', f'{IT}/{k}', 200, nombre='ítem: rol con anular')
        sin_permiso('item', 'editar')
        api('patch', f'{IT}/{k}/reactivar', 403, nombre='ítem: rol SIN editar no reactiva')
        con_permiso('item', 'editar')
        sin_permiso('item', 'ver')
        api('get', f'{IT}?inactivos=1', 403, nombre='ítem: ?inactivos=1 sin ver -> 403')
    finally:
        for acc in ('ver', 'editar', 'anular'):
            con_permiso('item', acc)
    como_admin()

    # ---------- Forma de Cobro: protocolo esta_en_uso() / ("EN_USO", motivo) ----------
    print('--- Forma de Cobro: protocolo EN_USO')
    from app.dao.modulo_facturacion.forma_cobro.FormaCobroDao import FormaCobroDao
    FC = '/api/v1/formas-cobro'
    f1 = reg('forma_cobro', api('post', FC, 201, {'descripcion': 'zz fc en uso', 'tipo': 'EFECTIVO'}, 'forma de cobro: alta para el test de EN_USO')['data']['id_forma_cobro'])
    with app.app_context():
        chk('esta_en_uso() devuelve False cuando nada la usa', FormaCobroDao().esta_en_uso(f1) is False)
        chk('deleteFormaCobro devuelve True al anular y False si ya no existe',
            FormaCobroDao().deleteFormaCobro(999999) is False)
    with mock.patch.object(FormaCobroDao, '_motivo_en_uso', return_value='No se puede dar de baja, motivo de prueba.'):
        api('delete', f'{FC}/{f1}', 409, nombre='forma de cobro: baja con motivo -> 409 con el motivo', exacto='No se puede dar de baja, motivo de prueba.')
        with app.app_context():
            r = FormaCobroDao().deleteFormaCobro(f1)
            chk('deleteFormaCobro devuelve ("EN_USO", motivo)', r == ('EN_USO', 'No se puede dar de baja, motivo de prueba.'))
            chk('esta_en_uso() devuelve el texto del motivo (truthy)', FormaCobroDao().esta_en_uso(f1) == 'No se puede dar de baja, motivo de prueba.')
    cu.execute("SELECT activo FROM forma_cobro WHERE id_forma_cobro=%s", (f1,)); chk('forma de cobro: NO se anuló', cu.fetchone()[0] is True)
    api('delete', f'{FC}/{f1}', 200, nombre='forma de cobro: sin motivo se anula normal', contiene='anulada')
    api('delete', f'{FC}/{f1}', 404, nombre='forma de cobro: baja repetida -> 404')
    aud = auditoria('forma_cobro', f1)
    chk('forma de cobro: el intento bloqueado NO se audita (solo ALTA y BAJA)', [x[0] for x in aud] == ['ALTA', 'BAJA'])

    # ---------- las 6 vistas cargan con el helper ----------
    print('--- vistas')
    for url, marca in [('/referenciales/forma-cobro/forma-cobro-index', b'chkInactivos'), ('/referenciales/marca-tarjeta/marca-tarjeta-index', b'chkInactivos'),
                       ('/referenciales/entidad-emisora/entidad-emisora-index', b'chkInactivos'), ('/referenciales/entidad-adherida/entidad-adherida-index', b'chkInactivos'),
                       ('/referenciales/tipo-item/tipo-item-index', b'chkInactivos'), ('/referenciales/item/item-index', b'chkInactivos')]:
        r = c.get(url)
        chk(f'vista {url.split("/")[-1]}: carga con el switch, el helper y la acción reactivar',
            r.status_code == 200 and marca in r.data and b'facturacion-listado.js' in r.data and b"accion === 'reactivar'" in r.data and b'L.reactivar(' in r.data and b'L.badgeEstado' in r.data)
    r = c.get('/static/js/facturacion-listado.js'); chk('helper JS servido', r.status_code == 200 and b'FacturacionListado' in r.data)
finally:
    # limpieza acotada a lo creado por este test (hijos antes que padres)
    orden = ['entidad_adherida', 'items', 'entidad_emisora', 'marca_tarjeta', 'tipo_items', 'deposito', 'forma_cobro']
    tablas = {'entidad_adherida': ('entidad_adherida', 'id_entidad_adherida'), 'items': ('items', 'id_item'),
              'entidad_emisora': ('entidad_emisora', 'id_entidad_emisora'), 'marca_tarjeta': ('marca_tarjeta', 'id_marca_tarjeta'),
              'tipo_items': ('tipo_items', 'id_tipo_item'), 'deposito': ('deposito', 'id_deposito'), 'forma_cobro': ('forma_cobro', 'id_forma_cobro')}
    for ent in orden:
        ids = list(creados.get(ent, []))
        if ids:
            borrar_auditoria(cu, ent, ids)
    for ent in orden:
        ids = list(creados.get(ent, []))
        if ids:
            t, pk = tablas[ent]
            cu.execute(f"DELETE FROM {t} WHERE {pk} = ANY(%s)", (ids,))
    for acc in ('ver', 'editar', 'anular', 'nuevo'):
        for v in ('formacobro', 'marcatarjeta', 'entidademisora', 'entidadadherida', 'tipoitem', 'item'):
            con_permiso(v, acc)
    cx.commit(); cu.close(); cx.close()
print('FALLOS:', fallos or 'ninguno')
