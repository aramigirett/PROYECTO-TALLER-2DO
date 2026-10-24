"""Registrar Nota de Remisión: esquema y objetos de base (fn_siguiente_numero_remision, trg_validar_remision_cab/det, trg_remision_estado,
trg_bloquear_anular_venta_remitida, v_pendientes_entrega), validaciones de la API, entregas parciales y por depósito, servicios que no
se entregan, ventas anuladas o de tratamiento, anulación que libera cantidades, conexiones (Venta, Depósito), concurrencia, PDF y permisos.

Usa como usuario al Administrador real (y al Cajero y a Recepción para probar permisos: la remisión no exige caja) y datos ZZ
(caja, apertura, cliente, timbrado inactivo, tipos, depósitos, ítems y ventas insertadas por SQL) que borra POR ID. NO depende de que
alguien tenga una caja abierta ni la toca."""
import sys, pathlib, re, threading, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from datetime import date, timedelta
import psycopg2
from app import app
from tests._conexion_pruebas import Conexion
from app.dao.modulo_facturacion.remision.RemisionDao import RemisionDao, ERROR_BD, YA_ANULADA
from app.dao.modulo_facturacion.deposito.DepositoDao import DepositoDao, MSG_BAJA_CON_ITEMS, MSG_BAJA_CON_REMISIONES
from app.Services.remision_pdf_service import generarRemisionPdf
from tests.facturacion._limpieza import borrar_auditoria
from tests.facturacion._pdf import paginas_pdf, texto_pdf

c = app.test_client()
fallos = []
REM, VEN = '/api/v1/remisiones', '/api/v1/ventas'
HOY = date.today()
MANANA = HOY + timedelta(days=1)


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


cx = Conexion().getConexion(); cx.autocommit = True; cu = cx.cursor()

# ---------- usuarios reales ----------
cu.execute("SELECT u.id_usuario, r.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.activo ORDER BY 1")
usuarios = cu.fetchall()
def primero(rol):
    return next((u for u in usuarios if u[2] == rol), None)
ADMIN, CAJERO, RECEP = primero('Administrador'), primero('Cajero'), primero('Recepcion')
if not (ADMIN and CAJERO and RECEP):
    print('ABORTADO: se necesitan un usuario Administrador, uno Cajero y uno de Recepción.'); sys.exit(1)
# La apertura ABIERTA que necesita la sección de Venta se crea por SQL a nombre de un usuario SIN caja abierta (así el test no depende de
# que el Administrador o el Cajero tengan una caja abierta de verdad, ni la toca).
cu.execute("SELECT id_usuario FROM usuarios WHERE activo AND id_usuario NOT IN (SELECT id_usuario FROM apertura_cierre_caja WHERE estado='ABIERTA') ORDER BY id_usuario")
LIBRES = [r_[0] for r_ in cu.fetchall()]
if not LIBRES:
    print('ABORTADO: no hay un usuario sin caja abierta para la apertura de prueba.'); sys.exit(1)


def como(u):
    with c.session_transaction() as s:
        s['id_usuario'] = u[0]; s['id_rol'] = u[1]; s['nombre_rol'] = u[2]


ids = {'caja': None, 'tim': None, 'cliente': None, 'ap': [], 'tipos': [], 'depositos': [], 'items': [], 'ventas': []}
remisiones = set()
numeros = []
stamp = str(int(time.time()))[-8:]
seq = [0]
I, D = {}, {}


def sql_en_txn(sql, params=(), despues=None):
    """Corre SQL en una transacción propia que SIEMPRE se deshace. Devuelve el mensaje de error de la base o None
    (o la fila de `despues` = (sql, params) si se pide)."""
    k = Conexion().getConexion(); kc = k.cursor()
    try:
        if isinstance(sql, str):
            sql = [(sql, params)]
        for s, p in sql:
            kc.execute(s, p)
        if despues:
            kc.execute(despues[0], despues[1]); return kc.fetchone()
        return None
    except psycopg2.Error as e:
        return getattr(getattr(e, 'diag', None), 'message_primary', None) or str(e).splitlines()[0]
    finally:
        k.rollback(); kc.close(); k.close()


def nueva_venta(lineas, apertura=None, tipo='ITEMS', estado='EMITIDA'):
    """Venta ZZ por SQL (timbrado ZZ inactivo). `lineas` = [(clave_item, cantidad)]."""
    seq[0] += 1
    total = sum(1000 * n for _, n in lineas)
    cu.execute("""INSERT INTO venta_cab(id_apertura, id_cliente, id_usuario, id_timbrado, numero_factura, tipo_venta, condicion,
                    total_exenta, total_gravada_5, total_gravada_10, iva_5, iva_10, total, estado)
                  VALUES (%s, %s, %s, %s, %s, %s, 'CONTADO', 0, 0, %s, 0, %s, %s, %s) RETURNING id_venta""",
               (apertura or ids['ap'][0], ids['cliente'], ADMIN[0], ids['tim'], f'ZZR{stamp}{seq[0]:03d}', tipo, total, round(total / 11), total, estado))
    v = cu.fetchone()[0]; ids['ventas'].append(v)
    for clave, n in lineas:
        cu.execute("INSERT INTO venta_det(id_venta, id_item, descripcion, cantidad, precio_unitario, iva, subtotal) VALUES (%s, %s, %s, %s, 1000, 10, %s)",
                   (v, I[clave], 'ZZ ' + clave, n, 1000 * n))
    return v


def pendiente(v, clave):
    cu.execute("SELECT cantidad_facturada, cantidad_remitida, cantidad_pendiente FROM v_pendientes_entrega WHERE id_venta=%s AND id_item=%s", (v, I[clave]))
    f = cu.fetchone()
    return f if f is None else tuple(int(x) for x in f)


def stock(clave):
    cu.execute("SELECT cantidad_disponible FROM items WHERE id_item=%s", (I[clave],)); return cu.fetchone()[0]


def cuerpo(v, dep, items, **extra):
    d = {'id_venta': v, 'id_deposito': dep, 'fecha_traslado': HOY.isoformat(), 'direccion_llegada': 'Av. Mariscal López 123',
         'responsable_traslado': 'pedro gómez', 'items': [{'id_item': I[k], 'cantidad': n} for k, n in items]}
    d.update(extra)
    return d


def emitir(v, dep, items, esperado=201, usuario=None, **kw):
    como(usuario or ADMIN)
    extra = kw.pop('extra', {})
    d = api('post', REM, esperado, cuerpo(v, dep, items, **extra), **kw)
    if esperado == 201:
        remisiones.add(d['data']['id_remision']); numeros.append(d['data']['numero_remision'])
    return d


def anular(idr, esperado=200, **kw):
    como(ADMIN)
    return api('delete', f'{REM}/{idr}', esperado, **kw)


def cuantas():
    cu.execute("SELECT count(*) FROM nota_remision_cab WHERE id_venta = ANY(%s)", (ids['ventas'] or [0],)); return cu.fetchone()[0]


try:
    # =====================================================================================================================
    # DATOS DE PRUEBA
    # =====================================================================================================================
    cu.execute("SELECT codigo FROM consultorio ORDER BY codigo LIMIT 1"); COD = cu.fetchone()[0]
    cu.execute("INSERT INTO caja(id_consultorio, descripcion) VALUES (%s, 'ZZ CAJA REMISION') RETURNING id_caja", (COD,)); ids['caja'] = cu.fetchone()[0]
    cu.execute("INSERT INTO timbrado(numero_timbrado, fecha_inicio, fecha_fin, establecimiento, punto_expedicion, numero_desde, numero_hasta, activo) "
               "VALUES ('ZZ000008', %s, %s, '996', '996', 1, 10, false) RETURNING id_timbrado", (HOY - timedelta(days=30), HOY + timedelta(days=30))); ids['tim'] = cu.fetchone()[0]
    cu.execute("INSERT INTO cliente(nombre, apellido, ci_ruc) VALUES ('ZZ CLIENTE', 'REMISION', %s) RETURNING id_cliente", ('ZZK' + stamp,)); ids['cliente'] = cu.fetchone()[0]
    cu.execute("INSERT INTO apertura_cierre_caja(id_caja, id_usuario, monto_apertura, estado, fecha_cierre) VALUES (%s, %s, 0, 'CERRADA', now()) RETURNING id_apertura", (ids['caja'], ADMIN[0]))
    ids['ap'].append(cu.fetchone()[0])
    T = {}
    for clave, desc, stock_ in (('ST', 'ZZ TIPO CON STOCK', True), ('SV', 'ZZ TIPO SERVICIO', False)):
        cu.execute("INSERT INTO tipo_items(descripcion, controla_stock) VALUES (%s, %s) RETURNING id_tipo_item", (desc, stock_)); T[clave] = cu.fetchone()[0]; ids['tipos'].append(T[clave])
    for clave, desc, act in (('A', 'ZZ DEPOSITO A', True), ('B', 'ZZ DEPOSITO B', True), ('X', 'ZZ DEPOSITO INACTIVO', False)):
        cu.execute("INSERT INTO deposito(descripcion, ubicacion, activo) VALUES (%s, %s, %s) RETURNING id_deposito", (desc, 'ZZ UBICACION ' + clave, act)); D[clave] = cu.fetchone()[0]; ids['depositos'].append(D[clave])
    for clave, tipo, dep, stk in (('A1', 'ST', 'A', 100), ('A2', 'ST', 'A', 50), ('B1', 'ST', 'B', 30), ('S1', 'SV', 'A', 0), ('OTRO', 'ST', 'A', 10)):
        cu.execute("INSERT INTO items(id_tipo_item, descripcion, precio_unitario, iva, cantidad_disponible, id_deposito) VALUES (%s, %s, 1000, 10, %s, %s) RETURNING id_item",
                   (T[tipo], 'ZZ ' + clave, stk, D[dep])); I[clave] = cu.fetchone()[0]; ids['items'].append(I[clave])
    V1 = nueva_venta([('A1', 10), ('A2', 5), ('B1', 3), ('S1', 1)])
    V2 = nueva_venta([('A1', 2)], estado='ANULADA')
    V3 = nueva_venta([], tipo='TRATAMIENTO')
    cu.execute("SELECT count(*) FROM nota_remision_cab WHERE id_venta = ANY(%s)", (ids['ventas'],)); assert cu.fetchone()[0] == 0

    # =====================================================================================================================
    # 1. ESQUEMA Y OBJETOS DE BASE DE DATOS
    # =====================================================================================================================
    cu.execute("SELECT array_agg(column_name::text ORDER BY ordinal_position) FROM information_schema.columns WHERE table_name='nota_remision_cab'")
    chk('nota_remision_cab: columnas tal cual las creó el DER (sin cambios)', cu.fetchone()[0] == [
        'id_remision', 'id_venta', 'id_deposito', 'id_usuario', 'numero_remision', 'fecha_emision', 'fecha_traslado', 'motivo_traslado',
        'direccion_llegada', 'responsable_traslado', 'observacion', 'estado'])
    cu.execute("SELECT array_agg(column_name::text ORDER BY ordinal_position) FROM information_schema.columns WHERE table_name='nota_remision_det'")
    chk('nota_remision_det: columnas tal cual las creó el DER (sin cambios)', cu.fetchone()[0] == ['id_remision_det', 'id_remision', 'id_item', 'cantidad'])
    cu.execute("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal AND tgname IN ('trg_validar_remision_cab','trg_validar_remision_det','trg_remision_estado','trg_bloquear_anular_venta_remitida')")
    chk('los 4 triggers de remisión existen', len(cu.fetchall()) == 4)
    cu.execute("SELECT count(*) FROM pg_trigger t JOIN pg_description d ON d.objoid = t.oid WHERE t.tgname IN ('trg_validar_remision_cab','trg_validar_remision_det','trg_remision_estado','trg_bloquear_anular_venta_remitida')")
    chk('los 4 triggers tienen COMMENT ON', cu.fetchone()[0] == 4)
    cu.execute("SELECT count(*) FROM pg_proc WHERE proname IN ('fn_siguiente_numero_remision','fn_validar_remision_cab','fn_validar_remision_det','fn_remision_estado','fn_bloquear_anular_venta_remitida') AND obj_description(oid,'pg_proc') IS NOT NULL")
    chk('las 5 funciones tienen COMMENT ON', cu.fetchone()[0] == 5)
    cu.execute("SELECT count(*) FROM pg_description WHERE objoid = 'v_pendientes_entrega'::regclass AND objsubid = 0")
    chk('v_pendientes_entrega tiene COMMENT ON', cu.fetchone()[0] == 1)
    cu.execute("SELECT string_agg(column_name, ',' ORDER BY ordinal_position) FROM information_schema.columns WHERE table_name='v_pendientes_entrega'")
    chk('v_pendientes_entrega: columnas', cu.fetchone()[0] == 'id_venta,numero_factura,estado_venta,id_cliente,cliente,ci_ruc,id_item,item,id_deposito,deposito,cantidad_facturada,cantidad_remitida,cantidad_pendiente')
    cu.execute("SELECT fn_siguiente_numero_remision()")
    chk('fn_siguiente_numero_remision: formato REM-0000000 (7 dígitos)', re.fullmatch(r'REM-\d{7}', cu.fetchone()[0]) is not None)
    cu.execute("SELECT id_menu FROM menu WHERE clave='remision' AND activo"); MENU = cu.fetchone()
    chk('menu: existe la entrada "remision"', MENU is not None)
    cu.execute("SELECT array_agg(accion ORDER BY accion) FROM permisos p JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND ventana='remision'")
    chk('el Cajero tiene ver, nuevo y anular sobre remision', cu.fetchone()[0] == ['anular', 'nuevo', 'ver'])
    cu.execute("SELECT count(*) FROM permisos p JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero'")
    chk('el Cajero conserva sus permisos (al menos las 27 filas con remision; smoke_permisos_cajero verifica el total)', cu.fetchone()[0] >= 27)
    cu.execute("SELECT count(*) FROM permisos WHERE ventana='remision' AND id_menu = %s", (MENU[0],))
    chk('permisos.id_menu de remision se completó solo (trigger)', cu.fetchone()[0] == 3)

    # v_pendientes_entrega antes de remitir
    chk('vista: A1 facturado 10, remitido 0, pendiente 10', pendiente(V1, 'A1') == (10, 0, 10))
    chk('vista: los servicios (tipo sin stock) NO aparecen', pendiente(V1, 'S1') is None)
    cu.execute("SELECT count(*) FROM v_pendientes_entrega WHERE id_venta = %s", (V3,)); chk('vista: una venta de tratamiento no aparece', cu.fetchone()[0] == 0)

    # =====================================================================================================================
    # 2. PERMISOS
    # =====================================================================================================================
    como(RECEP)
    for url, nombre in ((REM, 'listado'), (f'{REM}/1', 'detalle'), (f'{REM}/1/pdf', 'PDF'), (f'{REM}/ventas?q=zz', 'buscador de ventas'),
                        (f'{REM}/ventas/{V1}/pendientes', 'pendientes'), (f'{REM}/depositos', 'depósitos')):
        api('get', url, 403, nombre=f'Recepción sin permiso: {nombre}')
    api('post', REM, 403, {}, nombre='Recepción sin permiso: alta'); api('delete', f'{REM}/1', 403, nombre='Recepción sin permiso: anular')
    chk('vista: Recepción 403', c.get('/referenciales/remision/remision-index').status_code == 403)
    como(CAJERO)
    api('get', REM, 200, nombre='Cajero: listado'); chk('vista: Cajero 200', c.get('/referenciales/remision/remision-index').status_code == 200)
    como(ADMIN); chk('vista: Administrador 200', c.get('/referenciales/remision/remision-index').status_code == 200)

    # =====================================================================================================================
    # 3. VALIDACIONES DE LA API
    # =====================================================================================================================
    como(ADMIN)
    def val(c_, msg, camp, nombre, code=400):
        api('post', REM, code, c_, nombre=f'validación: {nombre}', exacto=msg, campo=camp)
    base = cuerpo(V1, D['A'], [('A1', 1)])
    def sin(k): d = dict(base); d.pop(k); return d
    def con(**k): return {**base, **k}
    val(sin('id_venta'), 'Debe seleccionar una venta.', 'id_venta', 'sin venta')
    val(sin('id_deposito'), 'Debe seleccionar el depósito de origen.', 'id_deposito', 'sin depósito')
    val(sin('fecha_traslado'), 'La fecha de traslado no es válida (use AAAA-MM-DD).', 'fecha_traslado', 'sin fecha de traslado')
    val(con(fecha_traslado='mañana'), 'La fecha de traslado no es válida (use AAAA-MM-DD).', 'fecha_traslado', 'fecha de traslado inválida')
    val(con(fecha_traslado=(HOY - timedelta(days=1)).isoformat()), 'La fecha de traslado no puede ser anterior a hoy.', 'fecha_traslado', 'fecha de traslado pasada')
    val(sin('direccion_llegada'), 'El campo dirección de llegada es obligatorio y no puede estar vacío.', 'direccion_llegada', 'sin dirección')
    val(con(direccion_llegada='x' * 151), 'El campo dirección de llegada no puede superar los 150 caracteres.', 'direccion_llegada', 'dirección larga')
    val(sin('responsable_traslado'), 'El campo responsable del traslado es obligatorio y no puede estar vacío.', 'responsable_traslado', 'sin responsable')
    val(con(responsable_traslado='juan@perez'), "El campo responsable del traslado solo puede contener letras, números, espacios y los símbolos . , - & ' / ( )", 'responsable_traslado', 'responsable con símbolos raros')
    val(con(observacion='a' * 201), 'La observación no puede superar los 200 caracteres.', 'observacion', 'observación larga')
    val(sin('items'), 'Debe indicar al menos un ítem a remitir.', 'items', 'sin ítems')
    val(con(items=[]), 'Debe indicar al menos un ítem a remitir.', 'items', 'ítems vacío')
    val(con(items='x'), 'Debe indicar al menos un ítem a remitir.', 'items', 'ítems no es lista')
    val(con(items=[{'cantidad': 1}]), 'Ítem 1: debe seleccionar el ítem.', 'items', 'ítem sin id')
    for malo in (0, -3, 'abc', '1.5', None):
        val(con(items=[{'id_item': I['A1'], 'cantidad': malo}]), 'Ítem 1: La cantidad debe ser un número entero mayor a 0.', 'items', f'cantidad {malo!r}')
    val(con(items=[{'id_item': I['A1'], 'cantidad': 1}, {'id_item': I['A1'], 'cantidad': 2}]), 'Ítem 2: el ítem está repetido en la remisión.', 'items', 'ítem repetido')
    val(con(items=[{'id_item': I['A1'], 'cantidad': 1}] * 101), 'Una remisión no puede tener más de 100 ítems.', 'items', 'demasiados ítems')
    val(con(items=[{'id_item': 2147483000, 'cantidad': 1}]), 'Ítem 1: el ítem no existe.', 'items', 'ítem inexistente', 409)
    val(con(id_venta=2147483000), 'No se encontró la venta.', 'id_venta', 'venta inexistente', 404)
    val(con(id_deposito=2147483000), 'El depósito no existe o está inactivo.', 'id_deposito', 'depósito inexistente', 409)
    val(con(id_deposito=D['X']), 'El depósito no existe o está inactivo.', 'id_deposito', 'depósito INACTIVO', 409)
    val(con(id_venta=V2), 'No se puede emitir una remisión de una venta anulada.', 'id_venta', 'venta ANULADA', 409)
    val(con(id_venta=V3), 'Solo se pueden remitir ventas de ítems.', 'id_venta', 'venta de TRATAMIENTO', 409)
    val(con(items=[{'id_item': I['A1'], 'cantidad': 11}]), 'Cantidad a remitir de ZZ A1 supera lo pendiente de entrega: 10.', 'items', 'cantidad mayor a lo facturado', 409)
    val(con(items=[{'id_item': I['B1'], 'cantidad': 1}]), 'El ítem ZZ B1 no está en el depósito seleccionado.', 'items', 'ítem de otro depósito', 409)
    val(con(id_deposito=D['B']), 'El ítem ZZ A1 no está en el depósito seleccionado.', 'items', 'depósito B con un ítem del depósito A', 409)
    val(con(items=[{'id_item': I['S1'], 'cantidad': 1}]), 'El ítem ZZ S1 no se entrega: su tipo no controla stock.', 'items', 'servicio (tipo sin stock)', 409)
    val(con(items=[{'id_item': I['OTRO'], 'cantidad': 1}]), 'El ítem ZZ OTRO no pertenece a la venta.', 'items', 'ítem que no es de la venta', 409)
    chk('validaciones: no se creó ninguna remisión ni cambió lo pendiente', cuantas() == 0 and pendiente(V1, 'A1') == (10, 0, 10))

    # =====================================================================================================================
    # 4. ENTREGAS PARCIALES, POR DEPÓSITO Y SIN MOVER STOCK
    # =====================================================================================================================
    stock_antes = {k: stock(k) for k in ('A1', 'A2', 'B1')}
    d = emitir(V1, D['A'], [('A1', 4)], nombre='remisión PARCIAL (A1 x4 de 10)', extra={'motivo_traslado': 'DEVOLUCION', 'id_usuario': CAJERO[0], 'numero_remision': 'REM-9999999', 'estado': 'ANULADA'})
    R1 = d['data']; ID1 = R1['id_remision']
    chk('cabecera: EMITIDA, motivo fijo VENTA y usuario de la SESIÓN (se ignora lo que mande el navegador)', (R1['estado'], R1['motivo_traslado'], R1['id_usuario']) == ('EMITIDA', 'VENTA', ADMIN[0]) and R1['numero_remision'] != 'REM-9999999')
    chk('cabecera: responsable en MAYÚSCULAS, depósito, factura, cliente y fechas', (R1['responsable_traslado'], R1['deposito'], R1['ubicacion_deposito'], R1['cliente'], R1['fecha_traslado'], R1['direccion_llegada']) ==
        ('PEDRO GÓMEZ', 'ZZ DEPOSITO A', 'ZZ UBICACION A', 'ZZ CLIENTE REMISION', HOY.isoformat(), 'Av. Mariscal López 123') and R1['numero_factura'].startswith('ZZR'))
    chk('el número tiene formato REM-0000001', re.fullmatch(r'REM-\d{7}', R1['numero_remision']) is not None)
    chk('detalle: A1 x4 y total de unidades 4', [(x['item'], x['cantidad']) for x in R1['detalle']] == [('ZZ A1', 4)] and R1['total_unidades'] == 4 and R1['cantidad_items'] == 1)
    chk('vista: A1 facturado 10, remitido 4, pendiente 6', pendiente(V1, 'A1') == (10, 4, 6))
    chk('la remisión NO mueve el stock', {k: stock(k) for k in ('A1', 'A2', 'B1')} == stock_antes)
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='nota_remision_cab' AND id_registro=%s AND accion='ALTA'", (ID1,))
    f = cu.fetchone(); chk('auditoría ALTA: remisión, cliente, factura, depósito, responsable e ítems', f is not None and all(x in f[0] for x in (R1['numero_remision'], 'ZZ CLIENTE REMISION', 'ZZ DEPOSITO A', 'PEDRO GÓMEZ', 'ZZ A1 x4')))

    d = emitir(V1, D['A'], [('A1', 6), ('A2', 5)], nombre='segunda remisión (completa A1 y A2)'); ID2 = d['data']['id_remision']
    chk('numeración correlativa sin huecos', int(numeros[1][4:]) == int(numeros[0][4:]) + 1)
    chk('vista: A1 y A2 sin pendiente', pendiente(V1, 'A1') == (10, 10, 0) and pendiente(V1, 'A2') == (5, 5, 0))
    emitir(V1, D['A'], [('A1', 1)], 409, nombre='remitir más de lo facturado', exacto='Cantidad a remitir de ZZ A1 supera lo pendiente de entrega: 0.', campo='items')
    d = emitir(V1, D['B'], [('B1', 3)], nombre='remisión desde el OTRO depósito (B1 x3)', usuario=CAJERO); ID3 = d['data']['id_remision']
    chk('el Cajero puede emitir (usuario = Cajero, sin exigir caja)', d['data']['id_usuario'] == CAJERO[0] and d['data']['deposito'] == 'ZZ DEPOSITO B')
    chk('vista: toda la mercadería de la venta entregada', pendiente(V1, 'B1') == (3, 3, 0))
    cu.execute("SELECT count(*) FROM v_pendientes_entrega WHERE id_venta=%s AND cantidad_pendiente > 0", (V1,)); chk('vista: nada pendiente en V1', cu.fetchone()[0] == 0)
    como(ADMIN)

    # =====================================================================================================================
    # 5. ANULAR LIBERA LAS CANTIDADES
    # =====================================================================================================================
    anular(ID2, nombre='anular la segunda remisión', contiene='anulada correctamente')
    chk('anular: A1 vuelve a tener 6 pendientes y A2 5 (la anulada no cuenta)', pendiente(V1, 'A1') == (10, 4, 6) and pendiente(V1, 'A2') == (5, 0, 5))
    cu.execute("SELECT estado FROM nota_remision_cab WHERE id_remision=%s", (ID2,)); chk('la remisión queda ANULADA', cu.fetchone()[0] == 'ANULADA')
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='nota_remision_cab' AND id_registro=%s AND accion='BAJA'", (ID2,))
    f = cu.fetchone(); chk('auditoría BAJA con el número y la factura', f is not None and numeros[1] in f[0] and 'pendientes de entrega' in f[0])
    chk('anular no mueve el stock', {k: stock(k) for k in ('A1', 'A2', 'B1')} == stock_antes)
    anular(ID2, 409, nombre='anular dos veces', exacto='La remisión ya está anulada.')
    anular(2147483000, 404, nombre='anular inexistente')
    d = emitir(V1, D['A'], [('A1', 6), ('A2', 5)], nombre='re-emitir lo liberado'); ID4 = d['data']['id_remision']
    chk('el número de la anulada NO se reutiliza (el nuevo es mayor)', int(numeros[-1][4:]) > int(numeros[1][4:]) and numeros[-1] != numeros[1])
    chk('vista: otra vez todo entregado', pendiente(V1, 'A1') == (10, 10, 0))

    # =====================================================================================================================
    # 6. TRIGGERS EN LA BASE (directos, siempre en transacciones que se deshacen)
    # =====================================================================================================================
    cab = "INSERT INTO nota_remision_cab(id_venta, id_deposito, id_usuario, numero_remision, fecha_traslado, direccion_llegada, responsable_traslado) VALUES (%s, %s, %s, %s, %s, 'ZZ', 'ZZ') RETURNING id_remision"
    det = "INSERT INTO nota_remision_det(id_remision, id_item, cantidad) VALUES ((SELECT id_remision FROM nota_remision_cab WHERE numero_remision=%s), %s, %s)"
    chk('trg_validar_remision_cab: una venta anulada no admite remisión', sql_en_txn(cab, (V2, D['A'], ADMIN[0], 'ZZT-1', HOY)) == 'No se puede emitir una remisión de una venta anulada.')
    chk('trg_validar_remision_cab: solo ventas de ítems', sql_en_txn(cab, (V3, D['A'], ADMIN[0], 'ZZT-2', HOY)) == 'Solo se pueden remitir ventas de ítems.')
    chk('trg_validar_remision_cab: la venta debe existir', sql_en_txn(cab, (2147483000, D['A'], ADMIN[0], 'ZZT-3', HOY)) is not None)
    chk('trg_validar_remision_cab: fecha de traslado no anterior a la emisión', sql_en_txn(cab, (V1, D['A'], ADMIN[0], 'ZZT-4', HOY - timedelta(days=1))) == 'La fecha de traslado no puede ser anterior a la fecha de emisión.')
    chk('trg_validar_remision_det: cantidad mayor a lo pendiente (0)', sql_en_txn([(cab, (V1, D['A'], ADMIN[0], 'ZZT-5', HOY)), (det, ('ZZT-5', I['A1'], 1))]) == 'Cantidad a remitir de ZZ A1 supera lo pendiente de entrega: 0.')
    chk('trg_validar_remision_det: ítem de otro depósito', sql_en_txn([(cab, (V1, D['A'], ADMIN[0], 'ZZT-6', HOY)), (det, ('ZZT-6', I['B1'], 1))]) == 'El ítem ZZ B1 no está en el depósito seleccionado.')
    chk('trg_validar_remision_det: servicio sin stock', sql_en_txn([(cab, (V1, D['A'], ADMIN[0], 'ZZT-7', HOY)), (det, ('ZZT-7', I['S1'], 1))]) == 'El ítem ZZ S1 no se entrega: su tipo no controla stock.')
    chk('trg_validar_remision_det: ítem que no es de la venta', sql_en_txn([(cab, (V1, D['A'], ADMIN[0], 'ZZT-8', HOY)), (det, ('ZZT-8', I['OTRO'], 1))]) == 'El ítem ZZ OTRO no pertenece a la venta.')
    chk('trg_validar_remision_det: ítem inexistente', sql_en_txn([(cab, (V1, D['A'], ADMIN[0], 'ZZT-9', HOY)), (det, ('ZZT-9', 2147483000, 1))]) == 'El ítem no existe.')
    chk('trg_validar_remision_det: no se agregan ítems a una remisión anulada',
        sql_en_txn([(cab, (V1, D['B'], ADMIN[0], 'ZZT-10', HOY)), ("UPDATE nota_remision_cab SET estado='ANULADA' WHERE numero_remision='ZZT-10'", ()),
                    (det, ('ZZT-10', I['B1'], 1))]) == 'No se pueden agregar ítems a una remisión anulada.')
    chk('trg_validar_remision_det: un cantidad <= 0 la rechaza el CHECK de la tabla',
        'ck_remision_det_cantidad' in (sql_en_txn([(cab, (V1, D['A'], ADMIN[0], 'ZZT-11', HOY)), (det, ('ZZT-11', I['A1'], 0))]) or '') or
        'cantidad' in (sql_en_txn([(cab, (V1, D['A'], ADMIN[0], 'ZZT-11', HOY)), (det, ('ZZT-11', I['A1'], 0))]) or ''))
    chk('trg_validar_remision_det: modificar la cantidad de una línea existente tampoco puede superar lo pendiente',
        sql_en_txn("UPDATE nota_remision_det SET cantidad = 11 WHERE id_remision = %s AND id_item = %s", (ID4, I['A1'])) == 'Cantidad a remitir de ZZ A1 supera lo pendiente de entrega: 6.')
    chk('trg_remision_estado: una remisión anulada no se puede reactivar', sql_en_txn("UPDATE nota_remision_cab SET estado='EMITIDA' WHERE id_remision=%s", (ID2,)) == 'Una remisión anulada no se puede reactivar.')
    chk('trg_bloquear_anular_venta_remitida: la base rechaza anular una venta con remisiones EMITIDAS',
        sql_en_txn("UPDATE venta_cab SET estado='ANULADA' WHERE id_venta=%s", (V1,)) == 'No es posible anular, existen remisiones emitidas. Anule primero las remisiones.')
    VU = nueva_venta([('A2', 4)])
    dos = sql_en_txn([(cab, (VU, D['A'], ADMIN[0], 'ZZT-13', HOY)), (det, ('ZZT-13', I['A2'], 1)), (det, ('ZZT-13', I['A2'], 1))]) or ''
    chk('uq_remision_det_item: un ítem no se repite dentro de la misma remisión', 'uq_remision_det_item' in dos or 'duplicad' in dos)
    chk('uq_remision_numero: el número es único',
        sql_en_txn([(cab, (V1, D['A'], ADMIN[0], 'ZZT-12', HOY)), (cab, (V1, D['A'], ADMIN[0], 'ZZT-12', HOY))]) is not None)
    cu.execute("SELECT count(*) FROM nota_remision_cab WHERE numero_remision LIKE 'ZZT-%'")
    chk('las pruebas directas no dejaron nada', cu.fetchone()[0] == 0 and pendiente(V1, 'A1') == (10, 10, 0))

    # =====================================================================================================================
    # 7. LISTADO, DETALLE Y BUSCADORES
    # =====================================================================================================================
    r = api('get', f'{REM}?cliente=ZZ CLIENTE REMISION', 200, nombre='filtro por cliente')['data']
    chk('el listado trae las remisiones del cliente (con unidades y depósito)', {x['id_remision'] for x in r} >= {ID1, ID2, ID3, ID4} and all('deposito' in x and 'total_unidades' in x for x in r))
    r = api('get', f'{REM}?cliente={numeros[0]}', 200, nombre='filtro por N.º de remisión')['data']; chk('filtro por N.º de remisión', [x['id_remision'] for x in r] == [ID1])
    r = api('get', f'{REM}?cliente={R1["numero_factura"]}', 200, nombre='filtro por N.º de factura')['data']; chk('filtro por factura', {x['id_remision'] for x in r} >= {ID1, ID2, ID3, ID4})
    r = api('get', f'{REM}?estado=ANULADA&cliente=ZZ CLIENTE', 200)['data']; chk('filtro por estado ANULADA', ID2 in {x['id_remision'] for x in r} and ID1 not in {x['id_remision'] for x in r})
    chk('filtro por fechas (hoy sí, ayer no)', ID1 in {x['id_remision'] for x in api('get', f'{REM}?desde={HOY}&hasta={HOY}', 200)['data']} and ID1 not in {x['id_remision'] for x in api('get', f'{REM}?hasta={HOY - timedelta(days=1)}', 200)['data']})
    api('get', f'{REM}?estado=XX', 400, nombre='estado inválido'); api('get', f'{REM}?desde=hoy', 400, nombre='fecha inválida')
    api('get', f'{REM}?desde={HOY}&hasta={HOY - timedelta(days=1)}', 400, nombre='desde > hasta')
    det_ = api('get', f'{REM}/{ID4}', 200, nombre='detalle de la remisión')['data']
    chk('detalle: ítems, cantidades y empresa', [(x['item'], x['cantidad']) for x in det_['detalle']] == [('ZZ A1', 6), ('ZZ A2', 5)] and det_['empresa']['ruc'] == '80099999-1')
    api('get', f'{REM}/2147483000', 404, nombre='detalle inexistente')
    V4 = nueva_venta([('A1', 3), ('B1', 2)])
    q = {x['id_venta']: x for x in api('get', f'{REM}/ventas?q=ZZ CLIENTE REMISION', 200, nombre='buscador de ventas por cliente')['data']}
    chk('buscador: solo ventas de ítems EMITIDAS con algo pendiente (V4 sí; V1 entregada, V2 anulada y V3 tratamiento no)', V4 in q and not ({V1, V2, V3} & set(q)))
    chk('buscador: unidades pendientes y depósitos', q[V4]['unidades_pendientes'] == 5 and q[V4]['depositos'] == ['ZZ DEPOSITO A', 'ZZ DEPOSITO B'])
    chk('buscador por N.º de factura', [x['id_venta'] for x in api('get', f'{REM}/ventas?q={q[V4]["numero_factura"]}', 200)['data']] == [V4])
    p = api('get', f'{REM}/ventas/{V4}/pendientes', 200, nombre='pendientes de la venta')['data']
    chk('pendientes: ítems con facturado / remitido / pendiente y su depósito (sin servicios)', [(x['item'], x['id_deposito'], x['facturado'], x['remitido'], x['pendiente']) for x in p['items']] == [('ZZ A1', D['A'], 3, 0, 3), ('ZZ B1', D['B'], 2, 0, 2)])
    api('get', f'{REM}/ventas/2147483000/pendientes', 404, nombre='pendientes de una venta inexistente')
    ds = {x['id_deposito'] for x in api('get', f'{REM}/depositos', 200, nombre='depósitos disponibles')['data']}
    chk('depósitos disponibles: solo ACTIVOS', {D['A'], D['B']} <= ds and D['X'] not in ds)

    # =====================================================================================================================
    # 8. CONEXIÓN CON VENTA: anular una venta con remisiones
    # =====================================================================================================================
    cu.execute("INSERT INTO apertura_cierre_caja(id_caja, id_usuario, monto_apertura) VALUES (%s, %s, 0) RETURNING id_apertura", (ids['caja'], LIBRES[0]))
    AP1 = cu.fetchone()[0]; ids['ap'].append(AP1); chk('apertura de caja ZZ ABIERTA (a nombre de un usuario libre)', isinstance(AP1, int))
    V5 = nueva_venta([('A1', 5)], apertura=AP1)
    d = emitir(V5, D['A'], [('A1', 2)], nombre='remisión de la venta V5'); ID5 = d['data']['id_remision']
    como(ADMIN)
    api('delete', f'{VEN}/{V5}', 409, nombre='anular una venta CON remisiones emitidas', exacto='No es posible anular, existen remisiones emitidas. Anule primero las remisiones.')
    cu.execute("SELECT estado FROM venta_cab WHERE id_venta=%s", (V5,)); chk('la venta con remisiones sigue EMITIDA', cu.fetchone()[0] == 'EMITIDA')
    anular(ID5, nombre='anular la remisión de V5')
    api('delete', f'{VEN}/{V5}', 200, nombre='sin remisiones EMITIDAS la venta se anula (las anuladas no bloquean)')
    emitir(V5, D['A'], [('A1', 1)], 409, nombre='tras anular la venta ya no se puede remitir', exacto='No se puede emitir una remisión de una venta anulada.')

    # =====================================================================================================================
    # 9. CONEXIÓN CON DEPÓSITO: baja bloqueada con remisiones EMITIDAS
    # =====================================================================================================================
    cu.execute("UPDATE items SET activo = false WHERE id_item = ANY(%s)", (ids['items'],))   # para llegar a la verificación de remisiones
    with app.app_context():
        chk('Depósito con remisiones EMITIDAS: baja bloqueada', DepositoDao().esta_en_uso(D['A']) == MSG_BAJA_CON_REMISIONES)
        chk('Depósito sin remisiones EMITIDAS (X): baja permitida', DepositoDao().esta_en_uso(D['X']) is False)
    cu.execute("UPDATE items SET activo = true WHERE id_item = ANY(%s)", (ids['items'],))
    with app.app_context():
        chk('con ítems activos el motivo sigue siendo el de los ítems', DepositoDao().esta_en_uso(D['A']) == MSG_BAJA_CON_ITEMS)

    # =====================================================================================================================
    # 10. CONCURRENCIA
    # =====================================================================================================================
    V6 = nueva_venta([('A1', 10)])
    res = [None] * 3; barrera = threading.Barrier(3)
    def hilo(i, n):
        with app.app_context():
            barrera.wait()
            res[i] = RemisionDao().guardarRemision(ADMIN[0], V6, D['A'], HOY, 'ZZ', 'ZZ', None, [{'id_item': I['A1'], 'cantidad': n}])
    ts = [threading.Thread(target=hilo, args=(i, 6)) for i in range(3)]; [t.start() for t in ts]; [t.join(60) for t in ts]
    oks = [r_ for r_ in res if isinstance(r_, int)]; remisiones.update(oks)
    chk('concurrencia: 3 remisiones de 6 sobre 10 a la vez -> exactamente 1 gana', len(oks) == 1 and sum(isinstance(r_, tuple) and r_[0] == ERROR_BD for r_ in res) == 2)
    chk('concurrencia: lo pendiente queda en 4 (nunca negativo)', pendiente(V6, 'A1') == (10, 6, 4))
    res = [None] * 3; barrera = threading.Barrier(3)
    ts = [threading.Thread(target=lambda i=i: (barrera.wait(), res.__setitem__(i, (lambda: None)()))) for i in range(0)]
    def hilo_anular(i):
        with app.app_context():
            barrera.wait(); res[i] = RemisionDao().anularRemision(oks[0])
    ts = [threading.Thread(target=hilo_anular, args=(i,)) for i in range(3)]; [t.start() for t in ts]; [t.join(60) for t in ts]
    chk('concurrencia: 3 anulaciones de la misma remisión -> 1 anula y 2 reciben "ya anulada"', sum(isinstance(r_, dict) for r_ in res) == 1 and sum(r_ == YA_ANULADA for r_ in res) == 2)
    chk('concurrencia: lo pendiente volvió a 10 UNA sola vez', pendiente(V6, 'A1') == (10, 0, 10))
    res = [None] * 4; barrera = threading.Barrier(4)
    ts = [threading.Thread(target=hilo, args=(i, 3)) for i in range(4)]; [t.start() for t in ts]; [t.join(60) for t in ts]
    oks2 = [r_ for r_ in res if isinstance(r_, int)]; remisiones.update(oks2)
    cu.execute("SELECT array_agg(numero_remision ORDER BY id_remision) FROM nota_remision_cab WHERE id_remision = ANY(%s)", (oks2,)); nums = cu.fetchone()[0]
    chk('concurrencia: 4 remisiones de 3 sobre 10 -> ganan 3 (9) y la 4.ª excede', len(oks2) == 3 and pendiente(V6, 'A1') == (10, 9, 1))
    chk('concurrencia: los 3 números son distintos y consecutivos', len(set(nums)) == 3 and [int(n[4:]) for n in nums] == list(range(int(nums[0][4:]), int(nums[0][4:]) + 3)))

    # =====================================================================================================================
    # 11. PDF
    # =====================================================================================================================
    como(CAJERO)
    r = c.get(f'{REM}/{ID4}/pdf')
    chk('PDF: 200, application/pdf y empieza con %PDF', r.status_code == 200 and r.mimetype == 'application/pdf' and r.data[:4] == b'%PDF')
    chk('PDF: exactamente 2 páginas (ORIGINAL y DUPLICADO)', paginas_pdf(r.data) == 2)
    txt = texto_pdf(r.data)
    chk('PDF: título, N.º de remisión (en las 2 copias) y RUC de la empresa', 'NOTA DE REMISI' in txt and txt.count(numeros[3]) >= 2 and '80099999-1' in txt)
    chk('PDF: cliente, factura, depósito, dirección y responsable', all(x in txt for x in ('ZZ CLIENTE REMISION', R1['numero_factura'], 'ZZ DEPOSITO A', 'Mariscal', 'PEDRO')))
    chk('PDF: ítems con su cantidad y total de unidades (11)', 'ZZ A1' in txt and 'ZZ A2' in txt and 'TOTAL DE UNIDADES' in txt and '11' in txt)
    chk('PDF de una remisión vigente: sin marca ANULADA, con ORIGINAL y DUPLICADO', 'ANULADA' not in txt and 'ORIGINAL' in txt and 'DUPLICADO' in txt)
    r = c.get(f'{REM}/{ID2}/pdf'); chk('PDF de una remisión ANULADA: se descarga con la marca ANULADA', r.status_code == 200 and 'ANULADA' in texto_pdf(r.data) and paginas_pdf(r.data) == 2)
    como(RECEP); api('get', f'{REM}/{ID4}/pdf', 403, nombre='PDF sin permiso ver')
    como(ADMIN); api('get', f'{REM}/2147483000/pdf', 404, nombre='PDF de una remisión inexistente')
    larga = {**det_, 'detalle': [{'item': f'ITEM LARGO NUMERO {n} CON UNA DESCRIPCION BASTANTE EXTENSA PARA OCUPAR VARIAS LINEAS EN LA GRILLA DEL PDF', 'cantidad': n} for n in range(1, 81)],
             'total_unidades': sum(range(1, 81))}
    pdf = generarRemisionPdf(larga); tx = texto_pdf(pdf)
    chk('PDF con 80 ítems: sigue en páginas de continuación (más de 2 páginas)', paginas_pdf(pdf) > 2)
    chk('PDF con 80 ítems: el total aparece una vez por copia y no se pierde ningún ítem', tx.count('TOTAL DE UNIDADES') == 2 and 'ITEM LARGO NUMERO 80' in tx and 'ITEM LARGO NUMERO 1 ' in tx)

    chk('las tablas del DER siguen siendo las mismas (no se recrearon)', (cu.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('nota_remision_cab','nota_remision_det')") or cu.fetchone()[0]) == 2)

finally:
    try:
        cu.execute("SELECT id_remision FROM nota_remision_cab WHERE id_venta = ANY(%s)", (ids['ventas'] or [0],))
        todas = sorted(set(remisiones) | {r_[0] for r_ in cu.fetchall()})
        if todas:
            cu.execute("DELETE FROM nota_remision_cab WHERE id_remision = ANY(%s)", (todas,))   # cascada: detalle
            borrar_auditoria(cu, 'nota_remision_cab', todas)
        if ids['ventas']:
            borrar_auditoria(cu, 'venta_cab', ids['ventas'])
            cu.execute("DELETE FROM venta_det WHERE id_venta = ANY(%s)", (ids['ventas'],))
            cu.execute("DELETE FROM cuenta_cobrar WHERE id_venta = ANY(%s)", (ids['ventas'],))
            cu.execute("DELETE FROM venta_cab WHERE id_venta = ANY(%s)", (ids['ventas'],))
        if ids['ap']:
            borrar_auditoria(cu, 'apertura_cierre_caja', ids['ap'])
            cu.execute("DELETE FROM apertura_cierre_caja WHERE id_apertura = ANY(%s)", (ids['ap'],))
        if ids['caja']:
            cu.execute("DELETE FROM caja WHERE id_caja=%s", (ids['caja'],))
        if ids['items']:
            cu.execute("DELETE FROM items WHERE id_item = ANY(%s)", (ids['items'],))
        if ids['depositos']:
            cu.execute("DELETE FROM deposito WHERE id_deposito = ANY(%s)", (ids['depositos'],))
        if ids['tipos']:
            cu.execute("DELETE FROM tipo_items WHERE id_tipo_item = ANY(%s)", (ids['tipos'],))
        if ids['cliente']:
            cu.execute("DELETE FROM cliente WHERE id_cliente=%s", (ids['cliente'],))
        if ids['tim']:
            cu.execute("DELETE FROM timbrado WHERE id_timbrado=%s", (ids['tim'],))
    except Exception as e:
        print('ERROR EN LA LIMPIEZA:', e); fallos.append('limpieza')

print()
print('FALLOS:', 'ninguno' if not fallos else fallos)
sys.exit(1 if fallos else 0)
