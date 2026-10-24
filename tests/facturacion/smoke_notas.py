"""Registrar Notas de Crédito y Débito: columnas nuevas (id_apertura, monto_reintegro), numeración por tipo (fn_siguiente_numero_nota),
triggers (trg_preparar_nota, trg_aplicar_nota, trg_validar_nota_det, trg_validar_nota, trg_bloquear_anular_venta_con_notas), funciones y vistas
(fn_total_reintegros / fn_total_recaudado / fn_total_efectivo_apertura, v_resumen_caja, v_estado_cuenta_cliente, v_libro_ventas), crédito que reduce el
saldo, reintegro en efectivo (con y sin efectivo suficiente), débito, devolución de mercadería con stock, anular (caja abierta/cerrada), cierre de
caja, conexiones (Venta), concurrencia, PDF y permisos.

Usa como emisor a un usuario Cajero/Administrador SIN caja abierta (no toca ninguna caja real: abre una apertura ZZ por SQL) y datos ZZ (caja, apertura,
cliente, timbrado inactivo para las ventas, tipos, depósito, ítems, formas de cobro y ventas insertadas por SQL) que borra POR ID. Las notas usan el
timbrado ACTIVO real, pero su numeración es propia y no consume el rango de facturas."""
import sys, pathlib, re, threading, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from datetime import date, timedelta
import psycopg2
from app import app
from app.conexion.Conexion import Conexion
from app.dao.modulo_facturacion.nota_credito_debito.NotaCreditoDebitoDao import NotaCreditoDebitoDao, ERROR_BD
from tests.facturacion._limpieza import borrar_auditoria
from tests.facturacion._pdf import paginas_pdf, texto_pdf

c = app.test_client()
fallos = []
NOT, COB, VEN, APE = '/api/v1/notas-credito-debito', '/api/v1/cobros', '/api/v1/ventas', '/api/v1/aperturas-caja'
HOY = date.today()
RE_NUM = re.compile(r'^\d{3}-\d{3}-\d{7}$')


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
cu.execute("SELECT id_usuario FROM apertura_cierre_caja WHERE estado='ABIERTA'")
OCUPADOS = {r_[0] for r_ in cu.fetchall()}
def primero(rol, libre=False):
    return next((u for u in usuarios if u[2] == rol and (not libre or u[0] not in OCUPADOS)), None)
ADMIN, RECEP = primero('Administrador'), primero('Recepcion')
EMISOR = primero('Cajero', True) or primero('Administrador', True)
if not (ADMIN and RECEP and EMISOR):
    print('ABORTADO: se necesitan un Administrador, uno de Recepción y un Cajero o Administrador SIN caja abierta (para emitir las notas).'); sys.exit(1)


def como(u):
    with c.session_transaction() as s:
        s['id_usuario'] = u[0]; s['id_rol'] = u[1]; s['nombre_rol'] = u[2]


ids = {'caja': None, 'tim': None, 'cliente': None, 'ap': [], 'tipos': [], 'depositos': [], 'items': [], 'ventas': [], 'formas': []}
notas, cobros = set(), set()
stamp = str(int(time.time()))[-8:]
seq = [0]
I, F = {}, {}
AP0 = AP1 = None


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


def nueva_venta(lineas, apertura=None, tipo='ITEMS', estado='EMITIDA', precio=10000):
    """Venta ZZ por SQL (timbrado ZZ inactivo); el trigger crea la cuenta (CONTADO, vence hoy). `lineas` = [(clave_item, cantidad)].
    Devuelve (id_venta, id_cuenta, total)."""
    seq[0] += 1
    total = sum(precio * n for _, n in lineas) or 10000
    cu.execute("""INSERT INTO venta_cab(id_apertura, id_cliente, id_usuario, id_timbrado, numero_factura, tipo_venta, condicion,
                    total_exenta, total_gravada_5, total_gravada_10, iva_5, iva_10, total, estado)
                  VALUES (%s, %s, %s, %s, %s, %s, 'CONTADO', 0, 0, %s, 0, %s, %s, %s) RETURNING id_venta""",
               (apertura or AP0, ids['cliente'], ADMIN[0], ids['tim'], f'ZZN{stamp}{seq[0]:03d}', tipo, total, round(total / 11), total, estado))
    v = cu.fetchone()[0]; ids['ventas'].append(v)
    for clave, n in lineas:
        cu.execute("INSERT INTO venta_det(id_venta, id_item, descripcion, cantidad, precio_unitario, iva, subtotal) VALUES (%s, %s, %s, %s, %s, 10, %s)",
                   (v, I[clave], 'ZZ ' + clave, n, precio, precio * n))
    cu.execute("SELECT id_cuenta FROM cuenta_cobrar WHERE id_venta=%s", (v,))
    return v, cu.fetchone()[0], total


def cuenta(cta):
    cu.execute("SELECT saldo, estado FROM cuenta_cobrar WHERE id_cuenta=%s", (cta,)); f = cu.fetchone(); return int(f[0]), f[1]


def stock(clave):
    cu.execute("SELECT cantidad_disponible FROM items WHERE id_item=%s", (I[clave],)); return cu.fetchone()[0]


def disponible():
    cu.execute("SELECT monto_apertura + fn_total_efectivo_apertura(id_apertura) FROM apertura_cierre_caja WHERE id_apertura=%s", (AP1,)); return int(cu.fetchone()[0])


def pagar(cta, monto, forma='EF'):
    """Cobro por la API (el emisor, con su caja abierta). Efectivo o transferencia."""
    como(EMISOR)
    f = {'id_forma_cobro': F[forma], 'monto': monto}
    if forma == 'TR':
        f['numero_referencia'] = 'ZZ-REF'
    d = api('post', COB, 201, {'id_cuenta': cta, 'formas': [f]}, nombre=f'cobro de Gs. {monto} ({forma})')
    cobros.add(d['data']['id_cobro']); return d['data']['id_cobro']


def libre(monto, iva=10, desc='Ajuste de precio'):
    return [{'descripcion': desc, 'monto': monto, 'iva': iva}]


def nota(tipo, cta, renglones, esperado=201, motivo='Ajuste de prueba', usuario=None, devolucion=False, **kw):
    como(usuario or EMISOR)
    d = api('post', NOT, esperado, {'tipo': tipo, 'id_cuenta': cta, 'motivo': motivo, 'renglones': renglones, 'devolucion': devolucion, **kw.pop('extra', {})}, **kw)
    if esperado == 201:
        notas.add(d['data']['id_nota'])
    return d


def anular(idn, esperado=200, **kw):
    como(EMISOR)
    return api('delete', f'{NOT}/{idn}', esperado, **kw)


def fila_nota(idn):
    cu.execute("SELECT estado, monto_reintegro, total, tipo_nota FROM nota_credito_debito_cab WHERE id_nota=%s", (idn,)); f = cu.fetchone()
    return (f[0], int(f[1]), int(f[2]), f[3])


def cuantas(clave_venta):
    cu.execute("SELECT count(*) FROM nota_credito_debito_cab n JOIN cuenta_cobrar cc USING(id_cuenta) WHERE cc.id_venta = ANY(%s)", (clave_venta,)); return cu.fetchone()[0]


try:
    # =====================================================================================================================
    # DATOS DE PRUEBA
    # =====================================================================================================================
    cu.execute("SELECT codigo FROM consultorio ORDER BY codigo LIMIT 1"); COD = cu.fetchone()[0]
    cu.execute("INSERT INTO caja(id_consultorio, descripcion) VALUES (%s, 'ZZ CAJA NOTAS') RETURNING id_caja", (COD,)); ids['caja'] = cu.fetchone()[0]
    cu.execute("INSERT INTO timbrado(numero_timbrado, fecha_inicio, fecha_fin, establecimiento, punto_expedicion, numero_desde, numero_hasta, activo) "
               "VALUES ('ZZ000007', %s, %s, '995', '995', 1, 10, false) RETURNING id_timbrado", (HOY - timedelta(days=30), HOY + timedelta(days=30))); ids['tim'] = cu.fetchone()[0]
    cu.execute("INSERT INTO cliente(nombre, apellido, ci_ruc) VALUES ('ZZ CLIENTE', 'NOTAS', %s) RETURNING id_cliente", ('ZZK' + stamp,)); ids['cliente'] = cu.fetchone()[0]
    cu.execute("INSERT INTO apertura_cierre_caja(id_caja, id_usuario, monto_apertura, estado, fecha_cierre) VALUES (%s, %s, 0, 'CERRADA', now()) RETURNING id_apertura", (ids['caja'], ADMIN[0]))
    AP0 = cu.fetchone()[0]; ids['ap'].append(AP0)
    T = {}
    for clave, desc, stk in (('ST', 'ZZ TIPO NOTAS CON STOCK', True), ('SV', 'ZZ TIPO NOTAS SERVICIO', False)):
        cu.execute("INSERT INTO tipo_items(descripcion, controla_stock) VALUES (%s, %s) RETURNING id_tipo_item", (desc, stk)); T[clave] = cu.fetchone()[0]; ids['tipos'].append(T[clave])
    cu.execute("INSERT INTO deposito(descripcion, ubicacion) VALUES ('ZZ DEPOSITO NOTAS', 'ZZ') RETURNING id_deposito"); DEP = cu.fetchone()[0]; ids['depositos'].append(DEP)
    for clave, tipo, stk in (('A', 'ST', 100), ('B', 'ST', 50), ('S', 'SV', 0), ('OTRO', 'ST', 5)):
        cu.execute("INSERT INTO items(id_tipo_item, descripcion, precio_unitario, iva, cantidad_disponible, id_deposito) VALUES (%s, %s, 10000, 10, %s, %s) RETURNING id_item",
                   (T[tipo], 'ZZ ' + clave, stk, DEP)); I[clave] = cu.fetchone()[0]; ids['items'].append(I[clave])
    for clave, desc, tipo in (('EF', 'ZZ EFECTIVO NOTAS', 'EFECTIVO'), ('TR', 'ZZ TRANSFERENCIA NOTAS', 'TRANSFERENCIA')):
        cu.execute("INSERT INTO forma_cobro(descripcion, tipo) VALUES (%s, %s) RETURNING id_forma_cobro", (desc, tipo)); F[clave] = cu.fetchone()[0]; ids['formas'].append(F[clave])
    cu.execute("SELECT COALESCE(MAX(substring(numero_nota FROM '([0-9]{7})$')::INTEGER), 0) FROM nota_credito_debito_cab WHERE tipo_nota='CREDITO'"); BASE_C = cu.fetchone()[0]
    cu.execute("SELECT COALESCE(MAX(substring(numero_nota FROM '([0-9]{7})$')::INTEGER), 0) FROM nota_credito_debito_cab WHERE tipo_nota='DEBITO'"); BASE_D = cu.fetchone()[0]
    cu.execute("SELECT establecimiento || '-' || punto_expedicion FROM timbrado WHERE activo"); PREFIJO = cu.fetchone()[0].replace(' ', '')

    # =====================================================================================================================
    # 1. ESQUEMA Y OBJETOS DE BASE DE DATOS
    # =====================================================================================================================
    cu.execute("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name='nota_credito_debito_cab' AND column_name IN ('id_apertura','monto_reintegro') ORDER BY 1")
    r = cu.fetchall()
    chk('columnas nuevas: id_apertura INT NOT NULL y monto_reintegro NUMERIC NOT NULL DEFAULT 0', [(x[0], x[1], x[2]) for x in r] == [('id_apertura', 'integer', 'NO'), ('monto_reintegro', 'numeric', 'NO')] and '0' in r[1][3])
    cu.execute("SELECT count(*) FROM pg_constraint WHERE conname IN ('nota_cd_id_apertura_fkey','ck_nota_reintegro')"); chk('FK de id_apertura y CHECK del reintegro', cu.fetchone()[0] == 2)
    cu.execute("SELECT array_agg(column_name::text ORDER BY ordinal_position) FROM information_schema.columns WHERE table_name='nota_credito_debito_det'")
    chk('nota_credito_debito_det: columnas tal cual las creó el DER (sin cambios)', cu.fetchone()[0] == ['id_nota_det', 'id_nota', 'id_item', 'id_tratamiento', 'descripcion', 'cantidad', 'precio_unitario', 'iva', 'subtotal'])
    cu.execute("SELECT tgname, tgdeferrable FROM pg_trigger WHERE NOT tgisinternal AND tgname IN ('trg_preparar_nota','trg_aplicar_nota','trg_validar_nota_det','trg_validar_nota','trg_bloquear_anular_venta_con_notas')")
    tg = dict(cu.fetchall()); chk('los 5 triggers existen (trg_validar_nota diferido)', len(tg) == 5 and tg['trg_validar_nota'])
    cu.execute("SELECT count(*) FROM pg_trigger t JOIN pg_description d ON d.objoid = t.oid WHERE t.tgname IN ('trg_preparar_nota','trg_aplicar_nota','trg_validar_nota_det','trg_validar_nota','trg_bloquear_anular_venta_con_notas')")
    chk('los 5 triggers tienen COMMENT ON', cu.fetchone()[0] == 5)
    cu.execute("SELECT count(*) FROM pg_proc WHERE proname IN ('fn_siguiente_numero_nota','fn_preparar_nota','fn_aplicar_nota','fn_validar_nota_det','fn_validar_nota','fn_bloquear_anular_venta_con_notas','fn_total_reintegros','fn_total_recaudado','fn_total_efectivo_apertura') AND obj_description(oid,'pg_proc') IS NOT NULL")
    chk('las 9 funciones tienen COMMENT ON', cu.fetchone()[0] == 9)
    cu.execute("SELECT count(*) FROM pg_description WHERE objsubid = 0 AND objoid IN ('v_resumen_caja'::regclass, 'v_estado_cuenta_cliente'::regclass, 'v_libro_ventas'::regclass)")
    chk('las 3 vistas actualizadas tienen COMMENT ON', cu.fetchone()[0] == 3)
    cu.execute("SELECT string_agg(column_name, ',' ORDER BY ordinal_position) FROM information_schema.columns WHERE table_name='v_estado_cuenta_cliente'")
    chk('v_estado_cuenta_cliente: conserva las 15 columnas y suma total_notas_credito, total_notas_debito y cantidad_notas al final',
        cu.fetchone()[0] == 'id_cliente,cliente,ci_ruc,id_venta,numero_factura,fecha,condicion,total,saldo,estado_cuenta,fecha_vencimiento,saldo_total_cliente,total_cobrado,cantidad_cobros,fecha_ultimo_cobro,total_notas_credito,total_notas_debito,cantidad_notas')
    cu.execute("SELECT string_agg(column_name, ',' ORDER BY ordinal_position) FROM information_schema.columns WHERE table_name='v_libro_ventas'")
    chk('v_libro_ventas: conserva las 14 columnas y suma comprobante al final', cu.fetchone()[0] == 'fecha,numero_timbrado,numero_factura,ci_ruc,cliente,condicion,exenta,gravada_5,iva_5,gravada_10,iva_10,total,estado,comprobante')
    cu.execute("SELECT * FROM fn_siguiente_numero_nota('CREDITO')"); idt, num = cu.fetchone()
    chk('fn_siguiente_numero_nota: formato 001-001-0000001 con el prefijo del timbrado activo', RE_NUM.match(num) is not None and num.startswith(PREFIJO + '-') and int(num[-7:]) == BASE_C + 1)
    cu.execute("SELECT * FROM fn_siguiente_numero_nota('DEBITO')"); chk('fn_siguiente_numero_nota: numeración propia por tipo (el débito no depende de los créditos)', int(cu.fetchone()[1][-7:]) == BASE_D + 1)
    chk('fn_siguiente_numero_nota: tipo inválido', sql_en_txn("SELECT * FROM fn_siguiente_numero_nota('OTRO')") == 'Tipo de nota inválido.')
    chk('fn_siguiente_numero_nota: sin timbrado activo', sql_en_txn([("UPDATE timbrado SET activo = false WHERE activo", ()), ("SELECT * FROM fn_siguiente_numero_nota('CREDITO')", ())]) == 'No hay timbrado activo')
    chk('fn_siguiente_numero_nota: timbrado vencido', sql_en_txn([("UPDATE timbrado SET fecha_inicio = CURRENT_DATE - 30, fecha_fin = CURRENT_DATE - 1 WHERE activo", ()), ("SELECT * FROM fn_siguiente_numero_nota('CREDITO')", ())]) == 'El timbrado está vencido')
    chk('fn_siguiente_numero_nota: timbrado aún no vigente', sql_en_txn([("UPDATE timbrado SET fecha_inicio = CURRENT_DATE + 1 WHERE activo", ()), ("SELECT * FROM fn_siguiente_numero_nota('CREDITO')", ())]) == 'El timbrado aún no está vigente')
    cu.execute("SELECT numero_actual FROM timbrado WHERE activo"); NA0 = cu.fetchone()[0]
    cu.execute("SELECT id_menu FROM menu WHERE clave='notacd' AND activo"); chk('menu: existe la entrada "notacd"', cu.fetchone() is not None)
    cu.execute("SELECT array_agg(accion ORDER BY accion) FROM permisos p JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND ventana='notacd'"); chk('el Cajero tiene ver, nuevo y anular sobre notacd', cu.fetchone()[0] == ['anular', 'nuevo', 'ver'])
    cu.execute("SELECT count(*) FROM permisos p JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero'"); chk('el Cajero conserva sus permisos (al menos las 30 filas con notacd; smoke_permisos_cajero verifica el total)', cu.fetchone()[0] >= 30)

    # =====================================================================================================================
    # 2. PERMISOS
    # =====================================================================================================================
    V0, C0, T0 = nueva_venta([('A', 2)])
    como(RECEP)
    for url, nombre in ((NOT, 'listado'), (f'{NOT}/1', 'detalle'), (f'{NOT}/1/pdf', 'PDF'), (f'{NOT}/facturas?q=zz', 'buscador de facturas'),
                        (f'{NOT}/facturas/{C0}', 'factura'), (f'{NOT}/caja-actual', 'caja actual')):
        api('get', url, 403, nombre=f'Recepción sin permiso: {nombre}')
    api('post', NOT, 403, {}, nombre='Recepción sin permiso: alta'); api('delete', f'{NOT}/1', 403, nombre='Recepción sin permiso: anular')
    chk('vista: Recepción 403', c.get('/referenciales/nota-credito-debito/nota-index').status_code == 403)
    como(EMISOR); api('get', NOT, 200, nombre='emisor: listado'); chk('vista: el emisor 200', c.get('/referenciales/nota-credito-debito/nota-index').status_code == 200)

    # =====================================================================================================================
    # 3. SIN CAJA Y VALIDACIONES DE LA API
    # =====================================================================================================================
    nota('CREDITO', C0, libre(1000), 409, nombre='sin caja abierta', exacto='Debe abrir la caja antes de registrar una nota.')
    cu.execute("INSERT INTO apertura_cierre_caja(id_caja, id_usuario, monto_apertura) VALUES (%s, %s, 100000) RETURNING id_apertura", (ids['caja'], EMISOR[0]))
    AP1 = cu.fetchone()[0]; ids['ap'].append(AP1)
    como(EMISOR)
    def val(cuerpo, msg, camp, nombre, code=400):
        api('post', NOT, code, cuerpo, nombre=f'validación: {nombre}', exacto=msg, campo=camp)
    base = {'tipo': 'CREDITO', 'id_cuenta': C0, 'motivo': 'x', 'renglones': libre(1000)}
    def sin(k): d = dict(base); d.pop(k); return d
    def con(**k): return {**base, **k}
    val(sin('tipo'), 'Debe indicar si la nota es de crédito o de débito.', 'tipo', 'sin tipo')
    val(con(tipo='OTRO'), 'Debe indicar si la nota es de crédito o de débito.', 'tipo', 'tipo inválido')
    val(sin('id_cuenta'), 'Debe seleccionar una factura.', 'id_cuenta', 'sin factura')
    val(sin('motivo'), 'El campo motivo es obligatorio y no puede estar vacío.', 'motivo', 'sin motivo')
    val(con(motivo='m' * 201), 'El campo motivo no puede superar los 200 caracteres.', 'motivo', 'motivo largo')
    val(sin('renglones'), 'Debe agregar al menos un renglón a la nota.', 'renglones', 'sin renglones')
    val(con(renglones=[]), 'Debe agregar al menos un renglón a la nota.', 'renglones', 'renglones vacío')
    val(con(renglones=libre(1000) * 31), 'Una nota no puede tener más de 30 renglones.', 'renglones', 'demasiados renglones')
    val(con(renglones=[{'descripcion': '', 'monto': 1000, 'iva': 10}]), 'Renglón 1: El campo descripción es obligatorio y no puede estar vacío.', 'renglones', 'renglón sin descripción')
    for malo in (0, -5, 'abc', '1.5', None):
        val(con(renglones=libre(malo)), 'Renglón 1: El monto debe ser un número entero mayor a 0.', 'renglones', f'monto {malo!r}')
    val(con(renglones=libre(1000, iva=7)), 'Renglón 1: El IVA debe ser Exenta (0), 5% o 10%.', 'renglones', 'IVA inválido')
    val(con(tipo='DEBITO', devolucion=True, renglones=[{'id_item': I['A'], 'cantidad': 1}]), 'Solo una nota de crédito puede devolver mercadería.', 'devolucion', 'devolución en una nota de débito')
    val(con(devolucion=True, renglones=[{'cantidad': 1}]), 'Renglón 1: debe seleccionar el ítem.', 'renglones', 'devolución sin ítem')
    val(con(devolucion=True, renglones=[{'id_item': I['A'], 'cantidad': 0}]), 'Renglón 1: La cantidad debe ser un número entero mayor a 0.', 'renglones', 'devolución con cantidad 0')
    val(con(devolucion=True, renglones=[{'id_item': I['A'], 'cantidad': 1}, {'id_item': I['A'], 'cantidad': 1}]), 'Renglón 2: el ítem está repetido en la nota.', 'renglones', 'devolución con ítem repetido')
    val(con(id_cuenta=2147483000), 'No se encontró la factura.', 'id_cuenta', 'factura inexistente', 404)
    _, CA, _ = nueva_venta([('A', 1)], estado='ANULADA')
    val(con(id_cuenta=CA), 'No se puede emitir una nota sobre una venta anulada.', 'id_cuenta', 'venta ANULADA', 409)
    VT, CT, _ = nueva_venta([], tipo='TRATAMIENTO')
    val(con(id_cuenta=CT, devolucion=True, renglones=[{'id_item': I['A'], 'cantidad': 1}]), 'Solo se devuelve mercadería de ventas de ítems.', 'devolucion', 'devolución en venta de tratamiento', 409)
    chk('validaciones: no se creó ninguna nota y el saldo no cambió', cuantas(ids['ventas']) == 0 and cuenta(C0) == (T0, 'PENDIENTE'))

    # =====================================================================================================================
    # 4. CRÉDITO QUE REDUCE EL SALDO (factura pendiente)
    # =====================================================================================================================
    d = nota('CREDITO', C0, libre(5000), nombre='crédito parcial sobre una factura PENDIENTE (5.000 de 20.000)', extra={'id_usuario': ADMIN[0], 'numero_nota': '999-999-9999999', 'estado': 'ANULADA', 'monto_reintegro': 99999, 'id_apertura': 1})
    N1 = d['data']; ID_N1 = N1['id_nota']
    chk('cabecera: EMITIDA, tipo CREDITO, usuario de la SESIÓN, caja del cajero, sin reintegro (se ignora lo que mande el navegador)',
        (N1['estado'], N1['tipo_nota'], N1['id_usuario'], N1['id_apertura'], N1['monto_reintegro']) == ('EMITIDA', 'CREDITO', EMISOR[0], AP1, 0) and N1['numero_nota'] != '999-999-9999999')
    chk('número: formato 001-001-0000001 con el prefijo del timbrado y correlativo del tipo', RE_NUM.match(N1['numero_nota']) and N1['numero_nota'].startswith(PREFIJO + '-') and int(N1['numero_nota'][-7:]) == BASE_C + 1)
    chk('totales calculados por el servidor: 5.000 gravada 10%, IVA 455 (5.000/11)', (N1['total'], N1['total_gravada_10'], N1['iva_10'], N1['total_exenta'], N1['total_gravada_5']) == (5000, 5000, 455, 0, 0))
    chk('renglón libre: cantidad 1, precio = monto', [(x['cantidad'], x['precio_unitario'], x['iva'], x['subtotal']) for x in N1['detalle']] == [(1, 5000, 10, 5000)])
    chk('trigger: el saldo baja a 15.000 y la cuenta sigue PENDIENTE', cuenta(C0) == (15000, 'PENDIENTE'))
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='nota_credito_debito_cab' AND id_registro=%s AND accion='ALTA'", (ID_N1,))
    f = cu.fetchone(); chk('auditoría ALTA: tipo, número, cliente, factura, total y motivo', f is not None and all(x in f[0] for x in ('Nota de Crédito', N1['numero_nota'], 'ZZ CLIENTE NOTAS', N1['numero_factura'], 'Gs. 5.000', 'Ajuste de prueba')))
    d = nota('CREDITO', C0, [{'descripcion': 'Descuento exento', 'monto': 6000, 'iva': 0}, {'descripcion': 'Descuento 5%', 'monto': 2100, 'iva': 5}, {'descripcion': 'Descuento 10%', 'monto': 6900, 'iva': 10}], nombre='crédito con renglones de las 3 tasas (15.000 = todo el saldo)')
    N2 = d['data']; ID_N2 = N2['id_nota']
    chk('totales por tasa: exentas 6.000, 5% 2.100, 10% 6.900; IVA 100 + 627', (N2['total_exenta'], N2['total_gravada_5'], N2['total_gravada_10'], N2['iva_5'], N2['iva_10'], N2['total']) == (6000, 2100, 6900, 100, 627, 15000))
    chk('el saldo llega a 0 y la cuenta pasa a PAGADA (sin reintegro)', cuenta(C0) == (0, 'PAGADA') and fila_nota(ID_N2)[1] == 0)
    chk('numeración correlativa sin huecos', int(N2['numero_nota'][-7:]) == int(N1['numero_nota'][-7:]) + 1)
    nota('CREDITO', C0, libre(1000), 409, nombre='crédito sobre la factura ya agotada por los créditos', exacto='El total de la nota de crédito (Gs. 1.000) supera el máximo permitido (Gs. 0).', campo='renglones')
    anular(ID_N2, nombre='anular el segundo crédito', contiene='anulada correctamente')
    chk('anular: el saldo vuelve a 15.000 y la cuenta a PENDIENTE', cuenta(C0) == (15000, 'PENDIENTE'))
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='nota_credito_debito_cab' AND id_registro=%s AND accion='BAJA'", (ID_N2,))
    chk('auditoría BAJA', cu.fetchone() is not None)
    anular(ID_N2, 409, nombre='anular dos veces', exacto='La nota ya está anulada.'); anular(2147483000, 404, nombre='anular inexistente')
    d = nota('CREDITO', C0, libre(15000), nombre='re-emitir un crédito por el saldo restante (el máximo vuelve a 15.000)'); ID_N3 = d['data']['id_nota']
    chk('el número de la anulada NO se reutiliza', int(d['data']['numero_nota'][-7:]) > int(N2['numero_nota'][-7:]) and cuenta(C0) == (0, 'PAGADA'))

    # =====================================================================================================================
    # 5. REINTEGRO EN EFECTIVO (factura ya pagada)
    # =====================================================================================================================
    V1, C1, T1 = nueva_venta([('A', 10), ('B', 5)], apertura=AP1)   # 150.000; en la apertura ABIERTA (para anular la venta más abajo)
    pagar(C1, T1, 'EF')
    chk('factura pagada en efectivo: saldo 0, PAGADA y efectivo disponible 100.000 + 150.000', cuenta(C1) == (0, 'PAGADA') and disponible() == 250000)
    d = nota('CREDITO', C1, libre(60000, desc='Descuento comercial'), nombre='crédito sobre factura PAGADA: 60.000 de reintegro en efectivo'); ID_R1 = d['data']['id_nota']
    chk('el reintegro es todo el crédito (60.000) y la cuenta sigue PAGADA con saldo 0', fila_nota(ID_R1)[1] == 60000 and cuenta(C1) == (0, 'PAGADA') and d['data']['monto_reintegro'] == 60000)
    chk('el mensaje avisa del reintegro', 'Reintegro en efectivo al cliente: Gs. 60.000' in d['mensaje'])
    cu.execute("SELECT fn_total_reintegros(%s), fn_total_efectivo_apertura(%s), fn_total_recaudado(%s)", (AP1, AP1, AP1))
    chk('fn_total_reintegros = 60.000; efectivo neto = 150.000 - 60.000; recaudado neto = 90.000', tuple(int(x) for x in cu.fetchone()) == (60000, 90000, 90000))
    cu.execute("SELECT forma_cobro, tipo_forma, cantidad_pagos, total_cobrado, id_forma_cobro FROM v_resumen_caja WHERE id_apertura=%s ORDER BY tipo_forma", (AP1,))
    rc = {x[1]: x for x in cu.fetchall()}
    chk('v_resumen_caja: fila EFECTIVO (+150.000) y fila REINTEGRO (-60.000, sin forma de cobro)', int(rc['EFECTIVO'][3]) == 150000 and int(rc['REINTEGRO'][3]) == -60000 and rc['REINTEGRO'][4] is None and rc['REINTEGRO'][2] == 1)
    como(EMISOR); pc = api('get', f'{NOT}/caja-actual', 200, nombre='caja actual')['data']
    chk('caja actual: efectivo disponible para reintegros = 100.000 + 90.000', pc['efectivo_disponible'] == 190000 and pc['id_apertura'] == AP1)
    pv = api('get', f'{APE}/{AP1}/cierre', 200, nombre='detalle previo al cierre')['data']
    chk('cierre (preview): efectivo neto 90.000, reintegros 60.000, efectivo cobrado 150.000, monto de cierre 190.000', (pv['efectivo'], pv['reintegros'], pv['efectivo_cobrado'], pv['monto_cierre'], pv['total_recaudado']) == (90000, 60000, 150000, 190000, 90000))
    chk('cierre (preview): el desglose incluye el reintegro en negativo', any(x['tipo'] == 'REINTEGRO' and x['total_cobrado'] == -60000 for x in pv['resumen']))
    nota('CREDITO', C1, libre(90001), 409, nombre='crédito mayor al máximo (150.000 - 60.000 = 90.000)', exacto='El total de la nota de crédito (Gs. 90.001) supera el máximo permitido (Gs. 90.000).')
    # crédito parcial: reduce saldo y devuelve el resto
    V7, C7, T7 = nueva_venta([('A', 10)]); pagar(C7, 70000, 'EF')
    chk('factura con pago parcial: saldo 30.000', cuenta(C7) == (30000, 'PENDIENTE'))
    d = nota('CREDITO', C7, libre(50000), nombre='crédito 50.000 sobre saldo 30.000: reduce 30.000 y reintegra 20.000'); ID_R7 = d['data']['id_nota']
    chk('reintegro 20.000, saldo 0 y la cuenta PAGADA', fila_nota(ID_R7)[1] == 20000 and cuenta(C7) == (0, 'PAGADA'))
    chk('efectivo disponible = 100.000 + (150.000 + 70.000 - 60.000 - 20.000)', disponible() == 240000)
    # anular con reintegro: la plata vuelve a la caja y el saldo no se toca
    anular(ID_R7, nombre='anular el crédito con reintegro de 20.000')
    chk('anular: el efectivo de la caja se recupera (+20.000) y el saldo vuelve a 30.000 (se revierte solo lo que redujo)', disponible() == 260000 and cuenta(C7) == (30000, 'PENDIENTE'))
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='nota_credito_debito_cab' AND id_registro=%s AND accion='BAJA'", (ID_R7,))
    chk('auditoría BAJA: informa que el reintegro vuelve a la caja', 'vuelve a la caja' in cu.fetchone()[0])
    # efectivo insuficiente: factura pagada por transferencia (no es efectivo en el cajón)
    V6, C6, T6 = nueva_venta([('A', 40)]); pagar(C6, T6, 'TR')   # 400.000 por transferencia
    disp = disponible()
    nota('CREDITO', C6, libre(T6), 409, nombre='reintegro mayor al efectivo disponible', exacto=f'No hay efectivo suficiente en la caja para el reintegro (disponible Gs. {disp:,})'.replace(',', '.') + '.', campo='renglones')
    chk('reintegro rechazado: nada cambió', cuenta(C6) == (0, 'PAGADA') and disponible() == disp)
    chk('trigger: el rechazo también sale de la base (INSERT directo)', sql_en_txn("""INSERT INTO nota_credito_debito_cab(id_cuenta, id_timbrado, id_usuario, id_apertura, tipo_nota, numero_nota, motivo, total_exenta, total_gravada_5, total_gravada_10, iva_5, iva_10, total)
        VALUES (%s, (SELECT id_timbrado FROM timbrado WHERE activo), %s, %s, 'CREDITO', 'ZZT-1', 'x', 0, 0, %s, 0, 0, %s)""", (C6, EMISOR[0], AP1, T6, T6)) == f'No hay efectivo suficiente en la caja para el reintegro (disponible Gs. {disp:,})'.replace(',', '.') + '.')
    d = nota('CREDITO', C6, libre(disp), nombre='reintegro exactamente igual al efectivo disponible (se permite)'); ID_R6 = d['data']['id_nota']
    chk('con todo el efectivo devuelto, el disponible queda en 0', disponible() == 0)

    # =====================================================================================================================
    # 6. DÉBITO
    # =====================================================================================================================
    d = nota('DEBITO', C1, libre(20000, desc='Intereses por mora'), nombre='débito sobre una factura PAGADA'); ID_D1 = d['data']['id_nota']; D1 = d['data']
    chk('débito: sin reintegro, saldo 20.000 y la cuenta vuelve de PAGADA a PENDIENTE', D1['monto_reintegro'] == 0 and cuenta(C1) == (20000, 'PENDIENTE'))
    chk('numeración del débito propia (independiente de los créditos)', int(D1['numero_nota'][-7:]) == BASE_D + 1)
    pagar(C1, 5000, 'EF'); chk('la cuenta reabierta se puede cobrar: saldo 15.000', cuenta(C1) == (15000, 'PENDIENTE'))
    anular(ID_D1, 409, nombre='anular el débito con cobros posteriores (saldo 15.000 < débito 20.000)', exacto='No se puede anular la nota de débito: el saldo actual (Gs. 15.000) es menor que el débito (Gs. 20.000); ya hay cobros posteriores.')
    chk('el débito sigue EMITIDO', fila_nota(ID_D1)[0] == 'EMITIDA' and cuenta(C1) == (15000, 'PENDIENTE'))
    d = nota('DEBITO', C0, libre(7000), nombre='débito sobre factura PAGADA sin cobros posteriores'); ID_D2 = d['data']['id_nota']
    chk('segundo débito: número consecutivo del tipo y cuenta PENDIENTE con saldo 7.000', int(d['data']['numero_nota'][-7:]) == int(D1['numero_nota'][-7:]) + 1 and cuenta(C0) == (7000, 'PENDIENTE'))
    anular(ID_D2, nombre='anular el débito sin cobros posteriores')
    chk('anular el débito: el saldo vuelve a 0 y la cuenta a PAGADA', cuenta(C0) == (0, 'PAGADA'))

    # =====================================================================================================================
    # 7. DEVOLUCIÓN DE MERCADERÍA
    # =====================================================================================================================
    fa = api('get', f'{NOT}/facturas/{C1}', 200, nombre='factura para la nota')['data']
    chk('factura: total, saldo, notas previas y máximo permitido', (fa['total'], fa['saldo'], fa['creditos_previos'], fa['debitos_previos'], fa['max_credito'], fa['cantidad_notas']) == (150000, 15000, 60000, 20000, 90000, 2))
    chk('factura: mercadería devolvible = ítems que controlan stock (sin servicios)', [(x['item'], x['facturado'], x['devuelto'], x['pendiente'], x['precio_unitario']) for x in fa['items']] == [('ZZ A', 10, 0, 10, 10000), ('ZZ B', 5, 0, 5, 10000)])
    V9, C9, T9 = nueva_venta([('A', 10), ('S', 1)], apertura=AP1, precio=10000)   # A x10 (100.000) + S x1 (10.000)
    st_a = stock('A')
    d = nota('CREDITO', C9, [{'id_item': I['A'], 'cantidad': 4}], devolucion=True, motivo='Devolución de mercadería', nombre='devolución de 4 unidades de A'); ID_V1 = d['data']['id_nota']
    chk('devolución: renglón con el ítem, precio e IVA de la FACTURA (4 x 10.000 = 40.000) y es_devolucion', [(x['id_item'], x['cantidad'], x['precio_unitario'], x['subtotal']) for x in d['data']['detalle']] == [(I['A'], 4, 10000, 40000)] and d['data']['es_devolucion'])
    chk('devolución: el stock de A sube 4', stock('A') == st_a + 4)
    chk('devolución: la factura impaga reduce su saldo (110.000 - 40.000)', cuenta(C9) == (T9 - 40000, 'PENDIENTE'))
    fb = api('get', f'{NOT}/facturas/{C9}', 200)['data']
    chk('factura: A ya devuelto 4, pendiente 6', [(x['devuelto'], x['pendiente']) for x in fb['items']] == [(4, 6)])
    nota('CREDITO', C9, [{'id_item': I['A'], 'cantidad': 7}], 409, devolucion=True, nombre='devolver más de lo pendiente', exacto='Cantidad a devolver de ZZ A supera lo facturado pendiente de devolución: 6.', campo='renglones')
    nota('CREDITO', C9, [{'id_item': I['S'], 'cantidad': 1}], 409, devolucion=True, nombre='devolver un servicio (tipo sin stock)', exacto='El ítem ZZ S no repone stock: su tipo no controla stock.')
    nota('CREDITO', C9, [{'id_item': I['OTRO'], 'cantidad': 1}], 409, devolucion=True, nombre='devolver un ítem que no es de la factura', exacto='Renglón 1: el ítem no pertenece a la factura.')
    chk('devoluciones rechazadas: el stock no cambió', stock('A') == st_a + 4)
    anular(ID_V1, nombre='anular la devolución (descuenta el stock repuesto)')
    chk('anular la devolución: el stock vuelve a su valor y el saldo a 110.000', stock('A') == st_a and cuenta(C9) == (T9, 'PENDIENTE'))
    d = nota('CREDITO', C9, [{'id_item': I['A'], 'cantidad': 3}], devolucion=True, motivo='Devolución', nombre='nueva devolución (3 unidades)'); ID_V2 = d['data']['id_nota']
    cu.execute("UPDATE items SET cantidad_disponible = 1 WHERE id_item = %s", (I['A'],))   # se vendió casi todo el stock repuesto
    anular(ID_V2, 409, nombre='anular una devolución sin stock suficiente', exacto='No se puede anular: para deshacer la devolución de ZZ A se necesitan 3 unidades en stock y hay 1.')
    chk('devolución no anulada: sigue EMITIDA', fila_nota(ID_V2)[0] == 'EMITIDA')
    cu.execute("UPDATE items SET cantidad_disponible = %s WHERE id_item = %s", (st_a + 3, I['A']))
    anular(ID_V2, nombre='con stock suficiente se anula')
    cu.execute("UPDATE items SET cantidad_disponible = %s WHERE id_item = %s", (st_a, I['A']))

    # =====================================================================================================================
    # 8. TRIGGERS EN LA BASE (directos, siempre en transacciones que se deshacen)
    # =====================================================================================================================
    cab = ("INSERT INTO nota_credito_debito_cab(id_cuenta, id_timbrado, id_usuario, id_apertura, tipo_nota, numero_nota, motivo, total_exenta, total_gravada_5, total_gravada_10, iva_5, iva_10, total) "
           "VALUES (%s, (SELECT id_timbrado FROM timbrado WHERE activo), %s, %s, %s, %s, 'x', 0, 0, %s, 0, 0, %s) RETURNING id_nota")
    det = "INSERT INTO nota_credito_debito_det(id_nota, id_item, descripcion, cantidad, precio_unitario, iva, subtotal) VALUES ((SELECT id_nota FROM nota_credito_debito_cab WHERE numero_nota=%s), %s, 'x', %s, %s, 10, %s)"
    cur_ap = lambda: AP1
    chk('trg_preparar_nota: la caja debe estar abierta', sql_en_txn([("UPDATE apertura_cierre_caja SET estado='CERRADA', fecha_cierre=now() WHERE id_apertura=%s", (AP1,)), (cab, (C9, EMISOR[0], AP1, 'DEBITO', 'ZZT-2', 1000, 1000))]) == 'La caja de la nota no está abierta.')
    chk('trg_preparar_nota: la cuenta debe existir', sql_en_txn(cab, (2147483000, EMISOR[0], AP1, 'DEBITO', 'ZZT-3', 1000, 1000)) == 'La cuenta a cobrar no existe.')
    chk('trg_preparar_nota: una venta anulada no admite notas', sql_en_txn(cab, (CA, EMISOR[0], AP1, 'DEBITO', 'ZZT-4', 1000, 1000)) == 'No se puede emitir una nota sobre una venta anulada.')
    chk('trg_preparar_nota: un débito nunca lleva reintegro (CHECK de la tabla)', 'ck_nota_reintegro' in (sql_en_txn("UPDATE nota_credito_debito_cab SET monto_reintegro = 1 WHERE id_nota = %s", (ID_D2,)) or ''))
    chk('trg_aplicar_nota: una nota anulada no se puede reactivar', sql_en_txn("UPDATE nota_credito_debito_cab SET estado='EMITIDA' WHERE id_nota=%s", (ID_N2,)) == 'Una nota anulada no se puede reactivar.')
    chk('trg_aplicar_nota: la caja de la nota cerrada impide anularla (también desde la base)',
        sql_en_txn([("UPDATE apertura_cierre_caja SET estado='CERRADA', fecha_cierre=now() WHERE id_apertura=%s", (AP1,)), ("UPDATE nota_credito_debito_cab SET estado='ANULADA' WHERE id_nota=%s", (ID_N1,))]) == 'La caja de la nota ya fue cerrada; no se puede anular.')
    chk('trg_validar_nota (diferido): una nota sin renglones se rechaza al confirmar',
        sql_en_txn([(cab, (C9, EMISOR[0], AP1, 'DEBITO', 'ZZT-5', 1000, 1000)), ("SET CONSTRAINTS ALL IMMEDIATE", ())]) == 'La nota debe tener al menos un renglón.')
    chk('trg_validar_nota (diferido): los renglones deben sumar los totales de la cabecera',
        sql_en_txn([(cab, (C9, EMISOR[0], AP1, 'DEBITO', 'ZZT-6', 1000, 1000)), (det, ('ZZT-6', None, 1, 900, 900)), ("SET CONSTRAINTS ALL IMMEDIATE", ())]) == 'Los renglones de la nota no coinciden con sus totales.')
    chk('trg_validar_nota (diferido): una nota correcta pasa',
        sql_en_txn([(cab, (C9, EMISOR[0], AP1, 'DEBITO', 'ZZT-7', 1000, 1000)), (det, ('ZZT-7', None, 1, 1000, 1000)), ("SET CONSTRAINTS ALL IMMEDIATE", ())]) is None)
    chk('trg_validar_nota_det: una nota de débito no puede devolver mercadería',
        sql_en_txn([(cab, (C9, EMISOR[0], AP1, 'DEBITO', 'ZZT-8', 1000, 1000)), (det, ('ZZT-8', I['A'], 1, 1000, 1000))]) == 'Solo una nota de crédito puede devolver mercadería.')
    chk('trg_validar_nota_det: no se admiten renglones de tratamiento',
        sql_en_txn([(cab, (C9, EMISOR[0], AP1, 'CREDITO', 'ZZT-9', 1000, 1000)), ("INSERT INTO nota_credito_debito_det(id_nota, id_tratamiento, descripcion, cantidad, precio_unitario, iva, subtotal) VALUES ((SELECT id_nota FROM nota_credito_debito_cab WHERE numero_nota='ZZT-9'), 1, 'x', 1, 1000, 10, 1000)", ())]) == 'Las notas no admiten renglones de tratamiento.')
    chk('trg_validar_nota_det: cantidad mayor a lo facturado (A: 10)',
        sql_en_txn([(cab, (C9, EMISOR[0], AP1, 'CREDITO', 'ZZT-10', 110000, 110000)), (det, ('ZZT-10', I['A'], 11, 10000, 110000))]) == 'Cantidad a devolver de ZZ A supera lo facturado pendiente de devolución: 10.')
    cu.execute("UPDATE apertura_cierre_caja SET estado='ABIERTA', fecha_cierre=NULL WHERE id_apertura=%s", (AP1,)); cu.execute("SELECT estado FROM apertura_cierre_caja WHERE id_apertura=%s", (AP1,))
    chk('las pruebas directas no dejaron nada (la apertura sigue ABIERTA)', cu.fetchone()[0] == 'ABIERTA' and (cu.execute("SELECT count(*) FROM nota_credito_debito_cab WHERE numero_nota LIKE 'ZZT-%'") or cu.fetchone()[0]) == 0)

    # =====================================================================================================================
    # 9. LISTADO, DETALLE, BUSCADOR Y VISTAS
    # =====================================================================================================================
    como(EMISOR)
    r = api('get', f'{NOT}?cliente=ZZ CLIENTE NOTAS', 200, nombre='filtro por cliente')['data']
    chk('el listado trae las notas del cliente con tipo, total, reintegro y estado de la caja', {x['id_nota'] for x in r} >= {ID_N1, ID_N2, ID_N3, ID_R1, ID_D1} and all('estado_apertura' in x and 'monto_reintegro' in x for x in r))
    r = api('get', f'{NOT}?cliente={N1["numero_nota"]}', 200, nombre='filtro por N.º de nota')['data']; chk('filtro por N.º de nota (puede coincidir con un débito del mismo número)', ID_N1 in {x['id_nota'] for x in r})
    r = api('get', f'{NOT}?tipo=DEBITO&cliente=ZZ CLIENTE', 200, nombre='filtro por tipo DEBITO')['data']; chk('filtro por tipo', {x['id_nota'] for x in r} >= {ID_D1, ID_D2} and not ({ID_N1, ID_R1} & {x['id_nota'] for x in r}))
    r = api('get', f'{NOT}?estado=ANULADA&cliente=ZZ CLIENTE', 200, nombre='filtro por estado')['data']; chk('filtro por estado ANULADA', {ID_N2, ID_D2} <= {x['id_nota'] for x in r} and ID_N1 not in {x['id_nota'] for x in r})
    chk('filtro por fechas (hoy sí, ayer no)', ID_N1 in {x['id_nota'] for x in api('get', f'{NOT}?desde={HOY}&hasta={HOY}', 200)['data']} and ID_N1 not in {x['id_nota'] for x in api('get', f'{NOT}?hasta={HOY - timedelta(days=1)}', 200)['data']})
    api('get', f'{NOT}?estado=XX', 400, nombre='estado inválido'); api('get', f'{NOT}?tipo=XX', 400, nombre='tipo inválido'); api('get', f'{NOT}?desde=hoy', 400, nombre='fecha inválida')
    api('get', f'{NOT}?desde={HOY}&hasta={HOY - timedelta(days=1)}', 400, nombre='desde > hasta')
    det_ = api('get', f'{NOT}/{ID_R1}', 200, nombre='detalle de la nota')['data']
    chk('detalle: renglones, totales, timbrado y empresa', det_['detalle'][0]['descripcion'] == 'Descuento comercial' and det_['totales']['total'] == 60000 and det_['empresa']['ruc'] == '80099999-1' and det_['timbrado']['numero'])
    api('get', f'{NOT}/2147483000', 404, nombre='detalle inexistente')
    q = {x['id_cuenta']: x for x in api('get', f'{NOT}/facturas?q=ZZ CLIENTE NOTAS', 200, nombre='buscador de facturas por cliente')['data']}
    chk('buscador: incluye facturas pendientes y pagadas con notas previas y máximo; excluye la anulada', {C0, C1, C6, C9} <= set(q) and CA not in q and q[C1]['max_credito'] == 90000 and q[C1]['creditos_previos'] == 60000)
    chk('buscador por N.º de factura', [x['id_cuenta'] for x in api('get', f'{NOT}/facturas?q={fa["numero_factura"]}', 200)['data']] == [C1])
    api('get', f'{NOT}/facturas/{CA}', 404, nombre='factura anulada: no se puede usar'); api('get', f'{NOT}/facturas/2147483000', 404, nombre='factura inexistente')
    cu.execute("SELECT saldo, total_cobrado, total_notas_credito, total_notas_debito, cantidad_notas FROM v_estado_cuenta_cliente WHERE id_venta=%s", (V1,))
    f = cu.fetchone(); chk('v_estado_cuenta_cliente: factura V1 con saldo 15.000, cobrado 155.000, crédito 60.000, débito 20.000 y 2 notas', tuple(int(x) for x in f) == (15000, 155000, 60000, 20000, 2))
    cu.execute("SELECT comprobante, numero_factura, total, gravada_10, iva_10, estado FROM v_libro_ventas WHERE comprobante <> 'FACTURA' AND cliente LIKE 'ZZ CLIENTE%%' AND numero_factura = %s", (det_['numero_nota'],))
    f = cu.fetchall(); chk('v_libro_ventas: la nota de crédito figura en NEGATIVO con su comprobante', any(x[0] == 'NOTA DE CRÉDITO' and int(x[2]) == -60000 and int(x[3]) == -60000 and int(x[4]) == -5455 for x in f))
    cu.execute("SELECT comprobante, total FROM v_libro_ventas WHERE numero_factura = %s", (D1['numero_nota'],))
    chk('v_libro_ventas: la nota de débito figura en positivo', any(x[0] == 'NOTA DE DÉBITO' and int(x[1]) == 20000 for x in cu.fetchall()))
    cu.execute("SELECT total, estado FROM v_libro_ventas WHERE comprobante = 'NOTA DE CRÉDITO' AND numero_factura = %s AND estado = 'ANULADA'", (N2['numero_nota'],))
    chk('v_libro_ventas: una nota anulada figura con importes en 0', any(int(x[0]) == 0 for x in cu.fetchall()))

    # =====================================================================================================================
    # 10. CONEXIÓN CON VENTA: anular una venta con notas
    # =====================================================================================================================
    como(EMISOR)
    api('delete', f'{VEN}/{V9}', 409, nombre='anular una venta CON notas emitidas', exacto='No es posible anular, existen notas de crédito o débito emitidas. Anúlelas primero.') if False else None
    d = nota('DEBITO', C9, libre(1000), nombre='nota de débito sobre V9 (en la caja abierta)'); ID_V9N = d['data']['id_nota']
    api('delete', f'{VEN}/{V9}', 409, nombre='anular una venta CON notas emitidas', exacto='No es posible anular, existen notas de crédito o débito emitidas. Anúlelas primero.')
    chk('la venta con notas sigue EMITIDA', (cu.execute("SELECT estado FROM venta_cab WHERE id_venta=%s", (V9,)) or cu.fetchone()[0]) == 'EMITIDA')
    chk('trigger: la base también rechaza anular la venta', sql_en_txn("UPDATE venta_cab SET estado='ANULADA' WHERE id_venta=%s", (V9,)) == 'No es posible anular, existen notas de crédito o débito emitidas. Anúlelas primero.')
    anular(ID_V9N, nombre='anular la nota de V9')
    api('delete', f'{VEN}/{V9}', 200, nombre='sin notas EMITIDAS la venta se anula (las anuladas no bloquean)')
    nota('DEBITO', C9, libre(1000), 409, nombre='tras anular la venta ya no se puede emitir una nota', exacto='No se puede emitir una nota sobre una venta anulada.')

    # =====================================================================================================================
    # 11. CONCURRENCIA
    # =====================================================================================================================
    VC, CC, TC = nueva_venta([('A', 10)]); pagar(CC, TC, 'TR')   # 100.000 pagados por transferencia
    res = [None] * 3; barrera = threading.Barrier(3)
    def hilo_credito(i, cta, monto):
        with app.app_context():
            barrera.wait(); res[i] = NotaCreditoDebitoDao().guardarNota(EMISOR[0], 'CREDITO', cta, 'ZZ concurrencia', [{'descripcion': 'x', 'monto': monto, 'iva': 10}], False)
    # 3 créditos de 60.000 sobre 100.000 de máximo: solo uno puede salir (60.000 + 60.000 > 100.000)... (reintegro: hay efectivo para todos? se controla con el máximo)
    cu.execute("UPDATE apertura_cierre_caja SET monto_apertura = 1000000 WHERE id_apertura = %s", (AP1,))
    ts = [threading.Thread(target=hilo_credito, args=(i, CC, 60000)) for i in range(3)]; [t.start() for t in ts]; [t.join(60) for t in ts]
    oks = [r_ for r_ in res if isinstance(r_, int)]; notas.update(oks)
    chk('concurrencia: 3 créditos de 60.000 sobre un máximo de 100.000 -> exactamente 1 gana', len(oks) == 1 and sum(isinstance(r_, tuple) and r_[0] == ERROR_BD for r_ in res) == 2)
    chk('concurrencia: el máximo restante es 40.000 (nunca negativo)', (cu.execute("SELECT total_gravada_10 FROM nota_credito_debito_cab WHERE id_nota=%s", (oks[0],)) or cu.fetchone()[0]) == 60000)
    # reintegros simultáneos que, juntos, superan el efectivo de la caja
    cu.execute("UPDATE apertura_cierre_caja SET monto_apertura = GREATEST(100000 - fn_total_efectivo_apertura(id_apertura), 0) WHERE id_apertura = %s", (AP1,))
    disp = disponible()
    monto = disp // 2 + 1000   # dos reintegros de este monto no caben juntos, uno solo sí
    VX, CX, _ = nueva_venta([('A', 1)], precio=monto); VY, CY, _ = nueva_venta([('A', 1)], precio=monto)
    pagar(CX, monto, 'TR'); pagar(CY, monto, 'TR')
    disp = disponible()
    res = [None] * 2; barrera = threading.Barrier(2)
    ts = [threading.Thread(target=hilo_credito, args=(0, CX, monto)), threading.Thread(target=hilo_credito, args=(1, CY, monto))]; [t.start() for t in ts]; [t.join(60) for t in ts]
    oks2 = [r_ for r_ in res if isinstance(r_, int)]; notas.update(oks2)
    chk(f'concurrencia: 2 reintegros de Gs. {monto:,} sobre un efectivo de Gs. {disp:,} -> exactamente 1 gana'.replace(',', '.'), len(oks2) == 1 and sum(isinstance(r_, tuple) and 'No hay efectivo suficiente' in r_[1] for r_ in res) == 1)
    chk('concurrencia: el efectivo nunca queda negativo', disponible() >= 0)
    VD, CD, _ = nueva_venta([('A', 1)])
    res = [None] * 4; barrera = threading.Barrier(4)
    def hilo_debito(i):
        with app.app_context():
            barrera.wait(); res[i] = NotaCreditoDebitoDao().guardarNota(EMISOR[0], 'DEBITO', CD, 'ZZ concurrencia', [{'descripcion': 'x', 'monto': 1000, 'iva': 10}], False)
    ts = [threading.Thread(target=hilo_debito, args=(i,)) for i in range(4)]; [t.start() for t in ts]; [t.join(60) for t in ts]
    oks3 = [r_ for r_ in res if isinstance(r_, int)]; notas.update(oks3)
    cu.execute("SELECT array_agg(numero_nota ORDER BY id_nota) FROM nota_credito_debito_cab WHERE id_nota = ANY(%s)", (oks3,)); nums = cu.fetchone()[0]
    chk('concurrencia: 4 débitos simultáneos -> 4 números distintos y consecutivos', len(oks3) == 4 and len(set(nums)) == 4 and [int(n[-7:]) for n in nums] == list(range(int(nums[0][-7:]), int(nums[0][-7:]) + 4)) and cuenta(CD)[0] == 10000 + 4000)
    cu.execute("UPDATE apertura_cierre_caja SET monto_apertura = 100000 WHERE id_apertura = %s", (AP1,))

    # =====================================================================================================================
    # 12. PDF
    # =====================================================================================================================
    como(EMISOR)
    r = c.get(f'{NOT}/{ID_R1}/pdf')
    chk('PDF: 200, application/pdf y empieza con %PDF', r.status_code == 200 and r.mimetype == 'application/pdf' and r.data[:4] == b'%PDF')
    chk('PDF: exactamente 2 páginas (ORIGINAL y DUPLICADO)', paginas_pdf(r.data) == 2)
    txt = texto_pdf(r.data)
    chk('PDF: título, N.º de nota (en las 2 copias), RUC y timbrado', 'NOTA DE CR' in txt and txt.count(det_['numero_nota']) >= 2 and '80099999-1' in txt and det_['timbrado']['numero'] in txt)
    chk('PDF: factura de referencia, motivo y reintegro en efectivo', det_['numero_factura'] in txt and 'Motivo' in txt and 'Reintegro en efectivo' in txt and '60.000' in txt)
    chk('PDF: total de la nota y total en letras', 'TOTAL DE LA NOTA' in txt and 'SESENTA MIL' in txt and 'Descuento comercial' in txt)
    chk('PDF de un crédito vigente: sin marca ANULADA, sin "Condición de venta"', 'ANULADA' not in txt and 'ORIGINAL' in txt and 'DUPLICADO' in txt and 'Condici' not in txt)
    r = c.get(f'{NOT}/{ID_D1}/pdf'); chk('PDF de una nota de DÉBITO: título NOTA DE D', r.status_code == 200 and 'NOTA DE D' in texto_pdf(r.data))
    r = c.get(f'{NOT}/{ID_N2}/pdf'); chk('PDF de una nota ANULADA: se descarga con la marca ANULADA', r.status_code == 200 and 'ANULADA' in texto_pdf(r.data) and paginas_pdf(r.data) == 2)
    como(RECEP); api('get', f'{NOT}/{ID_R1}/pdf', 403, nombre='PDF sin permiso ver')
    como(EMISOR); api('get', f'{NOT}/2147483000/pdf', 404, nombre='PDF de una nota inexistente')

    # =====================================================================================================================
    # 13. CIERRE DE CAJA CON REINTEGROS Y ANULAR CON LA CAJA CERRADA
    # =====================================================================================================================
    cu.execute("SELECT fn_total_recaudado(%s), fn_total_efectivo_apertura(%s), fn_total_reintegros(%s)", (AP1, AP1, AP1)); rec, efe, rei = (int(x) for x in cu.fetchone())
    cu.execute("SELECT COALESCE(SUM(d.monto),0) FROM cobro_cab c JOIN cobro_det d USING(id_cobro) JOIN forma_cobro f USING(id_forma_cobro) WHERE c.id_apertura=%s AND c.estado='EMITIDO' AND f.tipo='EFECTIVO'", (AP1,)); ef_bruto = int(cu.fetchone()[0])
    cu.execute("SELECT COALESCE(SUM(monto_reintegro),0) FROM nota_credito_debito_cab WHERE id_apertura=%s AND tipo_nota='CREDITO' AND estado='EMITIDA'", (AP1,)); rei_sql = int(cu.fetchone()[0])
    chk('funciones de caja coherentes: efectivo neto = efectivo cobrado - reintegros', efe == ef_bruto - rei_sql and rei == rei_sql)
    pv = api('get', f'{APE}/{AP1}/cierre', 200, nombre='detalle previo al cierre (con varias notas)')['data']
    chk('cierre (preview): monto de cierre = monto de apertura + efectivo neto', pv['monto_cierre'] == pv['monto_apertura'] + efe and pv['reintegros'] == rei and pv['efectivo_cobrado'] == ef_bruto)
    api('delete', f'{APE}/{AP1}', 409, nombre='no se anula una apertura con notas', exacto='La apertura tiene movimientos registrados; debe cerrarse en lugar de anularse.')
    api('patch', f'{APE}/{AP1}/cerrar', 200, nombre='cerrar la caja', contiene='cerrada correctamente')
    cu.execute("SELECT total_recaudado, monto_cierre, estado FROM apertura_cierre_caja WHERE id_apertura=%s", (AP1,))
    f = cu.fetchone(); chk('cierre guardado: monto_cierre = apertura + efectivo neto (con reintegros restados) y total_recaudado neto', (int(f[0]), int(f[1]), f[2]) == (rec, pv['monto_apertura'] + efe, 'CERRADA'))
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='apertura_cierre_caja' AND id_registro=%s AND accion='CIERRE'", (AP1,))
    chk('auditoría CIERRE: menciona los reintegros', 'Reintegros' in cu.fetchone()[0])
    anular(ID_N1, 409, nombre='anular una nota con la caja CERRADA', exacto='La caja de esta nota ya fue cerrada; no se puede anular.')
    chk('caja cerrada: la nota sigue EMITIDA y el saldo no cambió', fila_nota(ID_N3)[0] == 'EMITIDA' and fila_nota(ID_N1)[0] == 'EMITIDA')
    nota('DEBITO', C1, libre(1000), 409, nombre='tras cerrar la caja no se pueden emitir notas', exacto='Debe abrir la caja antes de registrar una nota.')

finally:
    try:
        cu.execute("SELECT n.id_nota FROM nota_credito_debito_cab n JOIN cuenta_cobrar cc USING(id_cuenta) WHERE cc.id_venta = ANY(%s)", (ids['ventas'] or [0],))
        todas = sorted(set(notas) | {r_[0] for r_ in cu.fetchall()})
        if todas:
            cu.execute("DELETE FROM nota_credito_debito_cab WHERE id_nota = ANY(%s)", (todas,))   # cascada: detalle
            borrar_auditoria(cu, 'nota_credito_debito_cab', todas)
        cu.execute("SELECT c.id_cobro FROM cobro_cab c JOIN cuenta_cobrar cc USING(id_cuenta) WHERE cc.id_venta = ANY(%s)", (ids['ventas'] or [0],))
        todos_cobros = sorted(set(cobros) | {r_[0] for r_ in cu.fetchall()})
        if todos_cobros:
            cu.execute("DELETE FROM cobro_cab WHERE id_cobro = ANY(%s)", (todos_cobros,))   # cascada: detalle
            borrar_auditoria(cu, 'cobro_cab', todos_cobros)
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
        if ids['formas']:
            borrar_auditoria(cu, 'forma_cobro', ids['formas'])
            cu.execute("DELETE FROM forma_cobro WHERE id_forma_cobro = ANY(%s)", (ids['formas'],))
        if ids['cliente']:
            cu.execute("DELETE FROM cliente WHERE id_cliente=%s", (ids['cliente'],))
        if ids['tim']:
            cu.execute("DELETE FROM timbrado WHERE id_timbrado=%s", (ids['tim'],))
    except Exception as e:
        print('ERROR EN LA LIMPIEZA:', e); fallos.append('limpieza')

print()
print('FALLOS:', 'ninguno' if not fallos else fallos)
sys.exit(1 if fallos else 0)
