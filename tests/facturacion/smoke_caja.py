import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from tests.facturacion._limpieza import borrar_auditoria
from app import app
from tests._conexion_pruebas import Conexion

c = app.test_client()
fallos = []
cajas_creadas = set()

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

CA = '/api/v1/cajas'
cx = Conexion().getConexion(); cu = cx.cursor()

# consultorios de prueba (la tabla real no tiene baja lógica: se crean y se borran por SQL)
def nuevo_consultorio(nombre, correo):
    cu.execute("INSERT INTO consultorio(nombre_consultorio, direccion, correo) VALUES (%s,'Dir de prueba 123',%s) RETURNING codigo", (nombre, correo))
    cx.commit(); return cu.fetchone()[0]
cA = nuevo_consultorio('ZZ CONSULTORIO A', 'zz.a@test.invalid')
cB = nuevo_consultorio('ZZ CONSULTORIO B', 'zz.b@test.invalid')

cu.execute("SELECT codigo FROM consultorio ORDER BY codigo LIMIT 2"); reales = [r[0] for r in cu.fetchall()]

try:
    api('get', CA, 401, nombre='sin sesion')
    with c.session_transaction() as s:
        s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

    r = c.get('/referenciales/caja/caja-index')
    chk('vista caja', r.status_code == 200 and b'Mostrar inactivas' in r.data and b'facturacion-validadores.js' in r.data)

    # ---------- seeds ----------
    d = api('get', CA, 200, nombre='lista (solo activas)')
    filas = {(x['descripcion'], x['id_consultorio']) for x in d['data']}
    cu.execute("SELECT codigo, UPPER(TRIM(nombre_consultorio)) FROM consultorio ORDER BY codigo LIMIT 2"); (c1, n1), (c2, n2) = cu.fetchall()
    # (los seeds pueden haberse editado/anulado a mano desde la pantalla: se exige solo CAJA RECEPCIÓN, que no se toca)
    chk('seed: CAJA RECEPCIÓN en el 1.º consultorio', ('CAJA RECEPCIÓN', c1) in filas)
    chk(f'seed: CAJA {n2} en el 2.º consultorio', (f'CAJA {n2}', c2) in filas)
    chk('lista trae el nombre del consultorio y activo', all('consultorio' in x and x['activo'] is True for x in d['data']))
    chk('lista por defecto no trae inactivas', all(x['activo'] for x in d['data']))

    # ---------- validaciones ----------
    ok = {'id_consultorio': cA, 'descripcion': ' zz  caja   uno '}
    api('post', CA, 400, {**ok, 'descripcion': ' '}, 'desc vacia', campo='descripcion')
    api('post', CA, 400, {**ok, 'descripcion': 'X' * 61}, 'desc 61', campo='descripcion')
    api('post', CA, 400, {**ok, 'descripcion': 'a<b>'}, 'desc simbolos', campo='descripcion')
    api('post', CA, 400, {'descripcion': 'ZZ X'}, 'sin consultorio', campo='id_consultorio')
    api('post', CA, 400, {**ok, 'id_consultorio': 'abc'}, 'consultorio no numerico', campo='id_consultorio')
    api('post', CA, 400, {**ok, 'id_consultorio': 999999}, 'consultorio inexistente', campo='id_consultorio', exacto='El consultorio seleccionado no existe o está anulado.')
    api('post', CA, 400, {'id_consultorio': c1, 'descripcion': 'caja recepción'}, 'duplicado contra seed (otra capitalizacion)', campo='descripcion', exacto='Ya existe una caja con esa descripción en el consultorio.')

    # ---------- alta / duplicados ----------
    d = api('post', CA, 201, ok, 'alta en A')
    a1 = d['data']['id_caja']; cajas_creadas.add(a1)
    chk('normalizada y con consultorio', d['data']['descripcion'] == 'ZZ CAJA UNO' and d['data']['consultorio'] == 'ZZ CONSULTORIO A' and d['data']['activo'] is True)
    api('post', CA, 400, ok, 'duplicado en el mismo consultorio', exacto='Ya existe una caja con esa descripción en el consultorio.')
    d = api('post', CA, 201, {**ok, 'id_consultorio': cB}, 'misma descripcion en OTRO consultorio (valida)')
    b1 = d['data']['id_caja']; cajas_creadas.add(b1)

    # ---------- modificación ----------
    api('put', f'{CA}/{a1}', 200, ok, 'mod sin cambios', contiene='sin cambios')
    d = api('put', f'{CA}/{a1}', 200, {**ok, 'descripcion': 'zz caja dos'}, 'mod descripcion')
    api('put', f'{CA}/{a1}', 400, {'id_consultorio': cB, 'descripcion': 'zz caja uno'}, 'mod -> choca en destino', campo='descripcion')
    api('put', f'{CA}/{a1}', 400, {'id_consultorio': 999999, 'descripcion': 'zz caja dos'}, 'mod consultorio inexistente', campo='id_consultorio')
    d = api('put', f'{CA}/{a1}', 200, {'id_consultorio': cB, 'descripcion': 'zz caja dos'}, 'mod cambia de consultorio')
    chk('cambió de consultorio', d['data']['consultorio'] == 'ZZ CONSULTORIO B')
    api('put', f'{CA}/{a1}', 200, {'id_consultorio': cA, 'descripcion': 'zz caja dos'}, 'vuelve a A')
    api('put', f'{CA}/999999', 404, ok, 'mod inexistente')

    # ---------- baja, listado de inactivas ----------
    api('delete', f'{CA}/{a1}', 200, nombre='baja', contiene='anulada')
    api('delete', f'{CA}/{a1}', 404, nombre='baja repetida')
    api('get', f'{CA}/{a1}', 404, nombre='get de inactiva (activas solamente)')
    d = api('get', CA, 200, nombre='lista default'); chk('default no incluye la anulada', a1 not in {x['id_caja'] for x in d['data']})
    d = api('get', f'{CA}?inactivas=1', 200, nombre='lista con inactivas')
    fila = [x for x in d['data'] if x['id_caja'] == a1]
    chk('con inactivas incluye la anulada con activo=False', len(fila) == 1 and fila[0]['activo'] is False)
    chk('con inactivas incluye también las activas', b1 in {x['id_caja'] for x in d['data']})
    d = api('post', CA, 201, {'id_consultorio': cA, 'descripcion': 'zz caja dos'}, 'reuso de descripcion tras la baja')
    a2 = d['data']['id_caja']; cajas_creadas.add(a2)

    # ---------- reactivación ----------
    api('patch', f'{CA}/{a1}/reactivar', 409, nombre='reactivar CON DUPLICADO (hay otra activa igual)',
        exacto='No se puede reactivar: ya existe una caja activa con esa descripción en el consultorio.')
    api('delete', f'{CA}/{a2}', 200, nombre='baja de la que bloqueaba')
    api('patch', f'{CA}/{a1}/reactivar', 200, nombre='reactivar OK', contiene='reactivada')
    d = api('get', f'{CA}/{a1}', 200, nombre='vuelve a estar activa'); chk('activo=True', d['data']['activo'] is True)
    api('patch', f'{CA}/{a1}/reactivar', 409, nombre='reactivar una ya activa', exacto='La caja ya está activa.')
    api('patch', f'{CA}/999999/reactivar', 404, nombre='reactivar inexistente')
    # a2 sigue anulada; reactivarla ahora choca con a1 (que la reemplazó)
    api('patch', f'{CA}/{a2}/reactivar', 409, nombre='reactivar choca con la reactivada', contiene='ya existe una caja activa')

    # ---------- consultorio: sin baja lógica ----------
    # (reactivar con consultorio inexistente no es construible: la FK impide borrar un consultorio con cajas)
    cu.execute("SELECT confdeltype FROM pg_constraint WHERE conrelid='caja'::regclass AND contype='f'")
    chk('FK caja->consultorio es RESTRICT', cu.fetchone()[0] == 'r')

    # ---------- auditoría ----------
    cu.execute("SELECT accion, id_usuario, ip, detalle FROM auditoria_cambios WHERE entidad='caja' AND id_registro = ANY(%s) ORDER BY id_auditoria_cambio", (list(cajas_creadas),))
    aud = cu.fetchall(); print('AUD', [(x[0], x[3][:70]) for x in aud])
    por_caja = {}
    cu.execute("SELECT id_registro, accion, detalle FROM auditoria_cambios WHERE entidad='caja' AND id_registro = ANY(%s) ORDER BY id_auditoria_cambio", (list(cajas_creadas),))
    for idr, acc, det in cu.fetchall():
        por_caja.setdefault(idr, []).append((acc, det))
    chk('auditoría de a1: ALTA, MOD, MOD, MOD, BAJA, REACTIVACION (sin fila para "sin cambios")',
        [x[0] for x in por_caja[a1]] == ['ALTA', 'MODIFICACION', 'MODIFICACION', 'MODIFICACION', 'BAJA', 'REACTIVACION'])
    chk('ALTA muestra el NOMBRE del consultorio', 'Consultorio: ZZ CONSULTORIO A' in por_caja[a1][0][1])
    chk('MOD de consultorio muestra nombres', any('Consultorio: ZZ CONSULTORIO A -> ZZ CONSULTORIO B' in x[1] for x in por_caja[a1]))
    chk('REACTIVACION con descripción y consultorio', 'ZZ CAJA DOS' in por_caja[a1][-1][1] and 'ZZ CONSULTORIO A' in por_caja[a1][-1][1])
    chk('auditoría: usuario e IP de la sesión', all(x[1] == 1 and x[2] == '127.0.0.1' for x in aud))

    # ---------- permisos ----------
    cu.execute("SELECT id_rol FROM roles WHERE nombre_rol <> 'Administrador' LIMIT 1"); rol = cu.fetchone()[0]
    def sin_permiso(accion):
        cu.execute("DELETE FROM permisos WHERE id_menu = (SELECT id_menu FROM menu WHERE clave='caja' AND activo = true) AND id_rol=%s AND accion=%s", (rol, accion)); cx.commit()
    def con_permiso(accion):
        cu.execute("INSERT INTO permisos (id_rol, id_menu, accion) SELECT %s, id_menu, %s FROM menu WHERE clave='caja' AND activo = true ON CONFLICT DO NOTHING", (rol, accion)); cx.commit()
    with c.session_transaction() as s:
        s['id_rol'] = rol; s['nombre_rol'] = 'NoAdmin'
    try:
        chk('rol sin cambios entra a la vista', c.get('/referenciales/caja/caja-index').status_code == 200)
        api('delete', f'{CA}/{a1}', 200, nombre='rol con anular puede anular')
        sin_permiso('editar')
        api('patch', f'{CA}/{a1}/reactivar', 403, nombre='rol SIN editar no puede reactivar (mismo permiso que editar)')
        api('put', f'{CA}/{a1}', 403, {'id_consultorio': cA, 'descripcion': 'x'}, 'rol SIN editar no puede editar')
        con_permiso('editar')
        api('patch', f'{CA}/{a1}/reactivar', 200, nombre='rol CON editar puede reactivar')
        sin_permiso('ver')
        api('get', f'{CA}?inactivas=1', 403, nombre='?inactivas=1 sin permiso ver -> 403')
        api('get', CA, 200, nombre='lista de activas sigue disponible (lookup, solo login)')
        con_permiso('ver')
    finally:
        for a in ('ver', 'editar'):
            con_permiso(a)
    with c.session_transaction() as s:
        s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

    # ---------- consultorio con cajas no se puede eliminar ----------
    api('delete', f'/api/v1/consultorios/{cA}', 409, nombre='anular consultorio con cajas ACTIVAS', contiene='No se puede anular, el consultorio tiene')
    cu.execute("UPDATE caja SET activo=false WHERE id_consultorio=%s", (cA,)); cx.commit()
    api('delete', f'/api/v1/consultorios/{cA}', 200, nombre='anular consultorio con cajas solo INACTIVAS (baja lógica)')
    cu.execute("SELECT activo FROM consultorio WHERE codigo = %s", (cA,)); chk('el consultorio sigue existiendo, inactivo', cu.fetchone() == (False,))
    for real in reales:
        api('delete', f'/api/v1/consultorios/{real}', 409, nombre=f'consultorio real {real} protegido', contiene='No se puede anular, el consultorio tiene')
    cu.execute("SELECT count(*) FROM consultorio WHERE codigo = ANY(%s) AND activo", (reales,)); chk('consultorios reales intactos', cu.fetchone()[0] == len(reales))
finally:
    # limpieza acotada a lo creado por este test
    borrar_auditoria(cu, 'caja', list(cajas_creadas))
    cu.execute("DELETE FROM caja WHERE id_consultorio = ANY(%s)", ([cA, cB],))
    cu.execute("DELETE FROM consultorio WHERE codigo = ANY(%s)", ([cA, cB],))
    borrar_auditoria(cu, 'consultorio', [cA, cB])
    cx.commit(); cu.close(); cx.close()
print('FALLOS:', fallos or 'ninguno')
