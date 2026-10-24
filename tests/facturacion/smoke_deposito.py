import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from tests.facturacion._limpieza import borrar_auditoria
from app import app
from app.conexion.Conexion import Conexion
from app.rutas.modulo_facturacion import utils

c = app.test_client()
fallos = []
deps = set(); items = set(); tipos = set()

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
    texto = d.get('error') or d.get('mensaje') or ''
    if contiene is not None:
        ok = ok and contiene in texto
    if exacto is not None:
        ok = ok and texto == exacto
    chk(f"{nombre or metodo + ' ' + url} -> {r.status_code}" + ('' if ok else f' {d}'), ok)
    return d

DP = '/api/v1/depositos'; IT = '/api/v1/items'; TI = '/api/v1/tipos-item'
cx = Conexion().getConexion(); cu = cx.cursor()
MSG_DUP = 'Ya existe un depósito con esa descripción.'
MSG_BAJA = 'No se puede dar de baja, el depósito tiene ítems asignados.'

try:
    # ---------- validador compartido (mayúsculas) ----------
    chk('validar_texto mayusculas=True', utils.validar_texto('  planta  baja - detrás ', 'ubicación', 100, mayusculas=True) == ('PLANTA BAJA - DETRÁS', None))
    chk('validar_texto sin mayusculas conserva el texto', utils.validar_texto('Av. x', 'dirección', 150) == ('Av. x', None))

    api('get', DP, 401, nombre='sin sesion')
    with c.session_transaction() as s:
        s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

    r = c.get('/referenciales/deposito/deposito-index')
    chk('vista depósito', r.status_code == 200 and b'Mostrar inactivos' in r.data and b'txtUbicacion' in r.data)
    r = c.get('/static/js/facturacion-validadores.js'); chk('js tiene ubicacion()', b'ubicacion:' in r.data and b'MAX_UBICACION' in r.data)

    # ---------- seeds ----------
    d = api('get', DP, 200, nombre='lista (solo activos)')
    filas = {x['descripcion']: x for x in d['data']}
    chk('seed DEPÓSITO PRINCIPAL', filas.get('DEPÓSITO PRINCIPAL', {}).get('ubicacion') == 'PLANTA BAJA - DETRÁS DE RECEPCIÓN')
    chk('seed DEPÓSITO ORTODONCIA', filas.get('DEPÓSITO ORTODONCIA', {}).get('ubicacion') == 'PRIMER PISO - SALA DE ORTODONCIA')
    chk('lista por defecto: solo activos', all(x['activo'] for x in d['data']))

    # ---------- validaciones ----------
    ok = {'descripcion': ' zz  deposito   uno ', 'ubicacion': ' planta  alta - atrás '}
    api('post', DP, 400, {**ok, 'descripcion': ' '}, 'desc vacía', campo='descripcion')
    api('post', DP, 400, {**ok, 'descripcion': 'X' * 61}, 'desc 61', campo='descripcion')
    api('post', DP, 400, {**ok, 'descripcion': 'a<b>'}, 'desc símbolos', campo='descripcion')
    api('post', DP, 400, {**ok, 'ubicacion': ''}, 'ubicación vacía', campo='ubicacion')
    api('post', DP, 400, {**ok, 'ubicacion': None}, 'ubicación null', campo='ubicacion')
    api('post', DP, 400, {**ok, 'ubicacion': 'U' * 101}, 'ubicación 101', campo='ubicacion')
    api('post', DP, 400, {**ok, 'ubicacion': 'abc\x07def'}, 'ubicación con caracteres de control', campo='ubicacion')
    api('post', DP, 400, {'descripcion': 'depósito principal', 'ubicacion': 'x'}, 'duplicado contra seed (otra capitalización)', campo='descripcion', exacto=MSG_DUP)
    d = api('post', DP, 201, {**ok, 'ubicacion': 'U' * 100}, 'ubicación de 100 exactos')
    deps.add(d['data']['id_deposito']); api('delete', f"{DP}/{d['data']['id_deposito']}", 200, nombre='baja de la de 100')

    # ---------- alta / modificación ----------
    d = api('post', DP, 201, ok, 'alta')
    z1 = d['data']['id_deposito']; deps.add(z1)
    chk('normalizada y en mayúsculas', d['data']['descripcion'] == 'ZZ DEPOSITO UNO' and d['data']['ubicacion'] == 'PLANTA ALTA - ATRÁS' and d['data']['activo'] is True)
    api('post', DP, 400, ok, 'duplicado', exacto=MSG_DUP)
    api('get', f'{DP}/{z1}', 200, nombre='get')
    api('put', f'{DP}/{z1}', 200, ok, 'mod sin cambios', contiene='sin cambios')
    d = api('put', f'{DP}/{z1}', 200, {'descripcion': 'zz deposito dos', 'ubicacion': 'sótano'}, 'mod descripción y ubicación')
    chk('mod aplicada en mayúsculas', d['data']['descripcion'] == 'ZZ DEPOSITO DOS' and d['data']['ubicacion'] == 'SÓTANO')
    api('put', f'{DP}/{z1}', 400, {'descripcion': 'depósito ortodoncia', 'ubicacion': 'x'}, 'mod duplicada', campo='descripcion', exacto=MSG_DUP)
    api('put', f'{DP}/{z1}', 400, {'descripcion': 'zz deposito dos', 'ubicacion': ' '}, 'mod ubicación vacía', campo='ubicacion')
    api('put', f'{DP}/999999', 404, ok, 'mod inexistente')

    # ---------- baja / inactivos ----------
    api('delete', f'{DP}/{z1}', 200, nombre='baja', contiene='anulado')
    api('delete', f'{DP}/{z1}', 404, nombre='baja repetida')
    api('get', f'{DP}/{z1}', 404, nombre='get de inactivo (solo activos)')
    d = api('get', DP, 200, nombre='lista default'); chk('default no incluye el anulado', z1 not in {x['id_deposito'] for x in d['data']})
    d = api('get', f'{DP}?inactivos=1', 200, nombre='lista con inactivos')
    fila = [x for x in d['data'] if x['id_deposito'] == z1]
    chk('con inactivos incluye el anulado con activo=False', len(fila) == 1 and fila[0]['activo'] is False)
    d = api('post', DP, 201, {'descripcion': 'zz deposito dos', 'ubicacion': 'otra'}, 'reuso de descripción tras la baja')
    z2 = d['data']['id_deposito']; deps.add(z2)

    # ---------- reactivación ----------
    api('patch', f'{DP}/{z1}/reactivar', 409, nombre='reactivar CON DUPLICADO (hay otro activo igual)',
        exacto='No se puede reactivar: ya existe un depósito activo con esa descripción.')
    api('delete', f'{DP}/{z2}', 200, nombre='baja del que bloqueaba')
    api('patch', f'{DP}/{z1}/reactivar', 200, nombre='reactivar OK', contiene='reactivado')
    d = api('get', f'{DP}/{z1}', 200, nombre='vuelve a estar activo'); chk('activo=True', d['data']['activo'] is True)
    api('patch', f'{DP}/{z1}/reactivar', 409, nombre='reactivar uno ya activo', exacto='El depósito ya está activo.')
    api('patch', f'{DP}/999999/reactivar', 404, nombre='reactivar inexistente')
    api('patch', f'{DP}/{z2}/reactivar', 409, nombre='reactivar choca con el reactivado', contiene='ya existe un depósito activo')

    # ---------- baja bloqueada por ítems activos ----------
    d = api('post', TI, 201, {'descripcion': 'zz tipo dep', 'controla_stock': True}, 'tipo de prueba'); t1 = d['data']['id_tipo_item']; tipos.add(t1)
    item = {'id_tipo_item': t1, 'id_deposito': z1, 'descripcion': 'zz item en deposito', 'precio_unitario': 1000, 'iva': 10, 'cantidad_disponible': 3}
    d = api('post', IT, 201, item, 'ítem en el depósito de prueba'); i1 = d['data']['id_item']; items.add(i1)
    chk('el ítem trae el depósito', d['data']['deposito'] == 'ZZ DEPOSITO DOS')
    api('delete', f'{DP}/{z1}', 409, nombre='baja BLOQUEADA (ítem activo asignado)', exacto=MSG_BAJA)
    cu.execute("SELECT activo FROM deposito WHERE id_deposito=%s", (z1,)); chk('el depósito sigue activo', cu.fetchone()[0] is True)
    api('put', f'{IT}/{i1}', 200, {**item, 'id_deposito': z1, 'precio_unitario': 1500}, 'editar ítem (mismo depósito)')
    api('delete', f'{DP}/{z1}', 409, nombre='sigue bloqueada tras editar el ítem', exacto=MSG_BAJA)
    # mover el ítem a otro depósito libera al primero
    d = api('post', DP, 201, {'descripcion': 'zz deposito tres', 'ubicacion': 'x'}, 'depósito destino'); z3 = d['data']['id_deposito']; deps.add(z3)
    api('put', f'{IT}/{i1}', 200, {**item, 'id_deposito': z3}, 'mover el ítem al otro depósito')
    api('delete', f'{DP}/{z3}', 409, nombre='el destino ahora está bloqueado', exacto=MSG_BAJA)
    api('delete', f'{IT}/{i1}', 200, nombre='ítem anulado')
    api('delete', f'{DP}/{z3}', 200, nombre='baja OK (el ítem anulado no bloquea)')
    api('delete', f'{DP}/{z1}', 200, nombre='baja OK del primero (ya sin ítems)')
    api('post', IT, 400, item, 'ítem nuevo en depósito anulado', campo='id_deposito')

    # ---------- auditoría ----------
    cu.execute("SELECT id_registro, accion, id_usuario, ip, detalle FROM auditoria_cambios WHERE entidad='deposito' AND id_registro = ANY(%s) ORDER BY id_auditoria_cambio", (list(deps),))
    aud = cu.fetchall()
    de_z1 = [x for x in aud if x[0] == z1]
    print('AUD z1', [(x[1], x[4][:60]) for x in de_z1])
    chk('auditoría z1: ALTA, MOD, BAJA, REACTIVACION, BAJA (sin fila para "sin cambios")', [x[1] for x in de_z1] == ['ALTA', 'MODIFICACION', 'BAJA', 'REACTIVACION', 'BAJA'])
    chk('ALTA con descripción y ubicación en mayúsculas', 'Ubicación: PLANTA ALTA - ATRÁS' in de_z1[0][4])
    chk('MOD solo lista lo que cambió', 'Descripción: ZZ DEPOSITO UNO -> ZZ DEPOSITO DOS' in de_z1[1][4] and 'Ubicación: PLANTA ALTA - ATRÁS -> SÓTANO' in de_z1[1][4])
    chk('REACTIVACION con descripción y ubicación', 'ZZ DEPOSITO DOS' in de_z1[3][4] and 'SÓTANO' in de_z1[3][4])
    chk('auditoría: usuario e IP de la sesión', all(x[2] == 1 and x[3] == '127.0.0.1' for x in aud))

    # ---------- permisos ----------
    cu.execute("SELECT id_rol FROM roles WHERE nombre_rol <> 'Administrador' LIMIT 1"); rol = cu.fetchone()[0]
    def sin_permiso(a):
        cu.execute("DELETE FROM permisos WHERE ventana='deposito' AND id_rol=%s AND accion=%s", (rol, a)); cx.commit()
    def con_permiso(a):
        cu.execute("INSERT INTO permisos (id_rol, ventana, accion) VALUES (%s,'deposito',%s) ON CONFLICT DO NOTHING", (rol, a)); cx.commit()
    with c.session_transaction() as s:
        s['id_rol'] = rol; s['nombre_rol'] = 'NoAdmin'
    try:
        chk('rol sin cambios entra a la vista', c.get('/referenciales/deposito/deposito-index').status_code == 200)
        sin_permiso('editar')
        api('patch', f'{DP}/{z1}/reactivar', 403, nombre='rol SIN editar no puede reactivar')
        api('put', f'{DP}/{z1}', 403, ok, 'rol SIN editar no puede editar')
        con_permiso('editar')
        api('patch', f'{DP}/{z1}/reactivar', 200, nombre='rol CON editar puede reactivar')
        sin_permiso('ver')
        api('get', f'{DP}?inactivos=1', 403, nombre='?inactivos=1 sin permiso ver -> 403')
        api('get', DP, 200, nombre='lista de activos sigue disponible (lookup, solo login)')
    finally:
        for a in ('ver', 'editar'):
            con_permiso(a)
    with c.session_transaction() as s:
        s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'
finally:
    # limpieza acotada a lo creado por este test
    borrar_auditoria(cu, 'items', list(items))
    borrar_auditoria(cu, 'tipo_items', list(tipos))
    borrar_auditoria(cu, 'deposito', list(deps))
    cu.execute("DELETE FROM items WHERE id_item = ANY(%s)", (list(items),))
    cu.execute("DELETE FROM tipo_items WHERE id_tipo_item = ANY(%s)", (list(tipos),))
    cu.execute("DELETE FROM deposito WHERE id_deposito = ANY(%s)", (list(deps),))
    cx.commit(); cu.close(); cx.close()
print('FALLOS:', fallos or 'ninguno')
