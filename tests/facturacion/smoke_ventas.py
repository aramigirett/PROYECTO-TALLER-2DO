"""Registrar Ventas y Cuentas a Cobrar (etapa 1): empresa/timbrado, sp_siguiente_numero_factura (numeración, vigencia,
rango, concurrencia), triggers (cuenta a cobrar creada y anulada, auditoría inmutable), vista v_estado_cuenta_cliente,
nueva venta de ítems (sin caja abierta, pedido facturado dos veces, totales e IVA calculados por el servidor), anulación
(vuelta del pedido a PENDIENTE, número no reutilizado, caja cerrada), permisos y bloqueos cruzados.

TIMBRADO: el SP incrementa numero_actual y esos números no se reutilizan, así que el test DESACTIVA el timbrado real,
crea uno ZZ (establecimiento/punto 998-998) y, en el finally, lo borra y REACTIVA el real (verificando que su
numero_actual no cambió). Mientras corre (unos segundos) no hay timbrado real activo: no correrlo con el sistema en uso.

Usa usuarios REALES (Administrador, Cajero y Recepción) con sesiones simuladas y datos ZZ que borra POR ID. Aborta si el
Cajero tiene una caja abierta de verdad (cerrarla antes)."""
import sys, pathlib, re, threading, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from datetime import date, timedelta
import psycopg2
from app import app
from app.conexion.Conexion import Conexion
from app.dao.modulo_facturacion.venta.VentaDao import VentaDao, PEDIDO_NO_PENDIENTE
from app.dao.modulo_facturacion.apertura_caja.AperturaCajaDao import AperturaCajaDao
from app.dao.modulo_facturacion.cliente.ClienteDao import ClienteDao
from app.rutas.modulo_facturacion.utils import calcular_dv_ruc
from tests.facturacion._limpieza import borrar_auditoria

RAIZ = pathlib.Path(__file__).resolve().parents[2]
c = app.test_client()
fallos = []
VEN, PED, AP = '/api/v1/ventas', '/api/v1/pedidos-cliente', '/api/v1/aperturas-caja'

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
cu.execute("SELECT count(*) FROM apertura_cierre_caja WHERE estado='ABIERTA' AND id_usuario = ANY(%s)", ([CAJERO[0], ADMIN[0]],))
if cu.fetchone()[0]:
    print('ABORTADO: el Cajero o el Administrador tiene una caja ABIERTA real; ciérrela antes de correr este test.'); sys.exit(1)

def como(u):
    with c.session_transaction() as s:
        s['id_usuario'] = u[0]; s['id_rol'] = u[1]; s['nombre_rol'] = u[2]

ids = {'tipo': [], 'dep': None, 'item': {}, 'cliente': [], 'caja': None, 'ap': [], 'tim': None, 'real': []}
pedidos, ventas = set(), set()
HOY = date.today()

def tim(campo):
    cu.execute(f"SELECT {campo} FROM timbrado WHERE id_timbrado=%s", (ids['tim'],)); return cu.fetchone()[0]

def set_tim(**kw):
    cu.execute("UPDATE timbrado SET " + ", ".join(f"{k}=%s" for k in kw) + " WHERE id_timbrado=%s", (*kw.values(), ids['tim']))

def stock(k):
    cu.execute("SELECT cantidad_disponible FROM items WHERE id_item=%s", (ids['item'][k],)); return cu.fetchone()[0]

def mkitem(clave, tipo, desc, precio, iva, cant):
    cu.execute("INSERT INTO items(id_tipo_item, descripcion, precio_unitario, iva, cantidad_disponible, id_deposito) "
               "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id_item", (tipo, desc, precio, iva, cant, ids['dep']))
    ids['item'][clave] = cu.fetchone()[0]

def lineas(*pares):
    return [{'id_item': ids['item'][k], 'cantidad': q} for k, q in pares]

def pedido(cli, items, **kw):
    como(CAJERO)
    d = api('post', PED, 201, {'id_cliente': cli, 'items': items}, nombre=kw.pop('nombre', 'pedido de prueba'))
    pid = d['data']['id_pedido']; pedidos.add(pid); return pid

def estado_pedido(p):
    cu.execute("SELECT estado FROM pedido_venta_cab WHERE id_pedido=%s", (p,)); return cu.fetchone()[0]

def venta(pid, cond='CONTADO', esperado=201, **kw):
    como(CAJERO)
    d = api('post', VEN, esperado, {'id_pedido': pid, 'condicion': cond}, **kw)
    if esperado == 201:
        ventas.add(d['data']['id_venta'])
    return d

def conn_nueva():
    k = Conexion().getConexion(); return k, k.cursor()

try:
    # ---------- configuración inicial: swap del timbrado ----------
    cu.execute("SELECT id_timbrado, numero_actual FROM timbrado WHERE activo=true")
    reales = cu.fetchall(); ids['real'] = [r[0] for r in reales]
    actual_real = {r[0]: r[1] for r in reales}
    cu.execute("UPDATE timbrado SET activo=false WHERE activo=true")
    cu.execute("INSERT INTO timbrado(numero_timbrado, fecha_inicio, fecha_fin, establecimiento, punto_expedicion, numero_desde, numero_hasta, numero_actual, activo) "
               "VALUES ('ZZ000001', %s, %s, '998', '998', 1, 100, 0, true) RETURNING id_timbrado", (HOY - timedelta(days=30), HOY + timedelta(days=30)))
    ids['tim'] = cu.fetchone()[0]

    cu.execute("INSERT INTO tipo_items(descripcion, controla_stock) VALUES ('ZZ TIPO VTA CON', true) RETURNING id_tipo_item"); T1 = cu.fetchone()[0]
    cu.execute("INSERT INTO tipo_items(descripcion, controla_stock) VALUES ('ZZ TIPO VTA SIN', false) RETURNING id_tipo_item"); T2 = cu.fetchone()[0]
    ids['tipo'] = [T1, T2]
    cu.execute("INSERT INTO deposito(descripcion, ubicacion) VALUES ('ZZ DEPOSITO VTA', 'ZZ') RETURNING id_deposito"); ids['dep'] = cu.fetchone()[0]
    mkitem('A', T1, 'ZZ VTA ITEM A', 10000, 10, 200)
    mkitem('B', T1, 'ZZ VTA ITEM B', 21000, 5, 200)
    mkitem('C', T2, 'ZZ VTA ITEM C', 5000, 0, 0)
    stamp = str(int(time.time()))[-8:]
    cu.execute("INSERT INTO cliente(nombre, apellido, ci_ruc) VALUES ('ZZ CLIENTE', 'VENTA', %s) RETURNING id_cliente", ('ZZV' + stamp,)); CLI = cu.fetchone()[0]
    cu.execute("INSERT INTO cliente(nombre, apellido, ci_ruc) VALUES ('ZZ CLIENTE', 'DOS', %s) RETURNING id_cliente", ('ZZW' + stamp,)); CLI2 = cu.fetchone()[0]
    ids['cliente'] = [CLI, CLI2]
    cu.execute("SELECT codigo FROM consultorio ORDER BY codigo LIMIT 1"); COD = cu.fetchone()[0]
    cu.execute("INSERT INTO caja(id_consultorio, descripcion) VALUES (%s, 'ZZ CAJA VTA') RETURNING id_caja", (COD,)); ids['caja'] = cu.fetchone()[0]

    # ---------- empresa y timbrado (datos del script) ----------
    cu.execute("SELECT count(*), min(razon_social), min(ruc), min(direccion), min(telefono), min(actividad_economica) FROM empresa")
    n, rs, ruc, dire, tel, act = cu.fetchone()
    chk('empresa: una sola fila con los datos pedidos', n == 1 and rs == 'CLÍNICA ODONTOLÓGICA ODONTOCLINIC S.A.'
        and dire == 'AVDA. MCAL. LÓPEZ 1234 - ASUNCIÓN' and tel == '021 600 600' and act == 'SERVICIOS ODONTOLÓGICOS')
    chk('empresa: RUC 80099999-1 con dígito verificador válido (calcular_dv_ruc)', ruc == '80099999-' + str(calcular_dv_ruc('80099999')) and ruc.endswith('-1'))
    cu.execute("SELECT fecha_inicio, fecha_fin, establecimiento, punto_expedicion, numero_desde, numero_hasta FROM timbrado WHERE numero_timbrado='12345678'")
    f = cu.fetchone()
    chk('timbrado real 12345678: 2026-10-01 a 2027-09-30, 001-001, del 1 al 5000',
        f == (date(2026, 10, 1), date(2027, 9, 30), '001', '001', 1, 5000))
    cu.execute("SELECT indexdef FROM pg_indexes WHERE indexname='ux_timbrado_activo'")
    chk('un solo timbrado activo: índice único parcial', 'UNIQUE' in cu.fetchone()[0])
    try:
        cu.execute("INSERT INTO timbrado(numero_timbrado, fecha_inicio, fecha_fin, establecimiento, punto_expedicion, numero_desde, numero_hasta) "
                   "VALUES ('ZZ000002', %s, %s, '997', '997', 1, 10)", (HOY, HOY)); ok = False
        cu.execute("DELETE FROM timbrado WHERE numero_timbrado='ZZ000002'")
    except psycopg2.errors.UniqueViolation:
        ok = True
    chk('no se puede activar un segundo timbrado', ok)

    # ---------- estructura de tablas ----------
    cu.execute("SELECT column_name FROM information_schema.columns WHERE table_name='venta_cab' ORDER BY ordinal_position")
    chk('venta_cab: columnas', [r[0] for r in cu.fetchall()] == ['id_venta', 'id_apertura', 'id_cliente', 'id_usuario', 'id_timbrado', 'numero_factura', 'fecha',
        'tipo_venta', 'id_pedido', 'condicion', 'total_exenta', 'total_gravada_5', 'total_gravada_10', 'iva_5', 'iva_10', 'total', 'estado'])
    cu.execute("SELECT column_name FROM information_schema.columns WHERE table_name='venta_det' ORDER BY ordinal_position")
    chk('venta_det: columnas', [r[0] for r in cu.fetchall()] == ['id_venta_det', 'id_venta', 'id_item', 'id_tratamiento', 'descripcion', 'cantidad', 'precio_unitario', 'iva', 'subtotal'])
    cu.execute("SELECT column_name FROM information_schema.columns WHERE table_name='cuenta_cobrar' ORDER BY ordinal_position")
    chk('cuenta_cobrar: columnas', [r[0] for r in cu.fetchall()] == ['id_cuenta', 'id_venta', 'id_cliente', 'monto_total', 'saldo', 'fecha_vencimiento', 'estado'])
    cu.execute("SELECT indexdef FROM pg_indexes WHERE indexname='ux_venta_pedido_emitida'")
    d = cu.fetchone()[0]; chk("índice único parcial (id_pedido) WHERE estado = 'EMITIDA'", 'UNIQUE' in d and 'EMITIDA' in d)
    cu.execute("SELECT confdeltype FROM pg_constraint WHERE conrelid IN ('venta_cab'::regclass,'venta_det'::regclass,'cuenta_cobrar'::regclass) AND contype='f'")
    fk = [r[0] for r in cu.fetchall()]; chk('FK de ventas/detalle/cuenta todas RESTRICT', len(fk) == 10 and set(fk) == {'r'})
    cu.execute("SELECT count(*) FROM pg_constraint WHERE conname IN ('ck_venta_tipo','ck_venta_condicion','ck_venta_estado','ck_cuenta_estado','ck_venta_det_item_o_tratamiento','uq_venta_numero_factura','uq_cuenta_venta')")
    chk('CHECK y UNIQUE pedidos están creados (7)', cu.fetchone()[0] == 7)

    # ---------- sp_siguiente_numero_factura ----------
    k, kc = conn_nueva()
    try:
        kc.execute("CALL sp_siguiente_numero_factura(NULL, NULL)"); r1 = kc.fetchone()
        kc.execute("CALL sp_siguiente_numero_factura(NULL, NULL)"); r2 = kc.fetchone()
        chk("SP: numeración '998-998-0000001' y '998-998-0000002' (7 dígitos, consecutivos)", r1 == (ids['tim'], '998-998-0000001') and r2 == (ids['tim'], '998-998-0000002'))
        kc.execute("SELECT numero_actual FROM timbrado WHERE id_timbrado=%s", (ids['tim'],)); chk('SP: incrementa numero_actual', kc.fetchone()[0] == 2)
    finally:
        k.rollback(); kc.close(); k.close()
    chk('SP: si la transacción se deshace, el número no se quema', tim('numero_actual') == 0)

    def sp_error(cambios, texto, nombre):
        k, kc = conn_nueva()
        try:
            kc.execute("UPDATE timbrado SET " + cambios + " WHERE id_timbrado=%s", (ids['tim'],))
            try:
                kc.execute("CALL sp_siguiente_numero_factura(NULL, NULL)"); msg = 'SIN ERROR'
            except psycopg2.errors.RaiseException as e:
                msg = e.diag.message_primary
        finally:
            k.rollback(); kc.close(); k.close()
        chk(f'SP: {nombre} -> "{texto}"', msg == texto)
    sp_error("activo=false", 'No hay timbrado activo', 'sin timbrado activo')
    sp_error(f"fecha_fin='{HOY - timedelta(days=1)}'", 'El timbrado está vencido', 'vencido')
    sp_error(f"fecha_inicio='{HOY + timedelta(days=1)}', fecha_fin='{HOY + timedelta(days=9)}'", 'El timbrado aún no está vigente', 'aún no vigente')
    sp_error("numero_actual=numero_hasta", 'Se agotó el rango de numeración del timbrado', 'rango agotado')
    k, kc = conn_nueva()
    try:
        kc.execute("UPDATE timbrado SET numero_desde=50, numero_hasta=60, numero_actual=0 WHERE id_timbrado=%s", (ids['tim'],))
        kc.execute("CALL sp_siguiente_numero_factura(NULL, NULL)"); r = kc.fetchone()
    finally:
        k.rollback(); kc.close(); k.close()
    chk('SP: si numero_actual está antes del rango, arranca en numero_desde (50)', r[1] == '998-998-0000050')
    cu.execute("SELECT prokind, obj_description(oid, 'pg_proc') FROM pg_proc WHERE proname='sp_siguiente_numero_factura'")
    f = cu.fetchone(); chk('SP: es un PROCEDURE y tiene COMMENT ON', f is not None and f[0] == 'p' and bool(f[1]))
    cu.execute("""SELECT count(*) FROM pg_trigger t JOIN pg_description d ON d.objoid = t.oid WHERE t.tgname IN
                  ('trg_generar_cuenta_cobrar','trg_anular_cuenta_cobrar','trg_auditoria_inmutable')""")
    chk('triggers: los 3 (4 con la doble tabla de auditoría) tienen COMMENT ON', cu.fetchone()[0] == 4)

    # concurrencia del SP: dos transacciones simultáneas -> números distintos y consecutivos
    salida = []
    barrera = threading.Barrier(2)
    def hilo():
        k, kc = conn_nueva()
        try:
            barrera.wait()
            kc.execute("CALL sp_siguiente_numero_factura(NULL, NULL)"); salida.append(kc.fetchone()[1])
            time.sleep(0.4)   # retiene el bloqueo del timbrado: la otra transacción debe esperar
            k.commit()
        finally:
            kc.close(); k.close()
    ts = [threading.Thread(target=hilo) for _ in range(2)]; [t.start() for t in ts]; [t.join(60) for t in ts]
    chk('SP concurrente: 2 transacciones reciben números distintos y consecutivos', sorted(salida) == ['998-998-0000001', '998-998-0000002'])
    set_tim(numero_actual=0)

    # ---------- triggers de auditoría inmutable ----------
    cu.execute("INSERT INTO auditoria_cambios(id_usuario, entidad, id_registro, accion, detalle) VALUES (%s, 'zz_venta_test', 1, 'ALTA', 'ZZ') RETURNING id_auditoria_cambio", (ADMIN[0],))
    aid = cu.fetchone()[0]
    chk('auditoría: INSERT sigue permitido', aid is not None)
    MSG_AUD = 'Los registros de auditoría no se pueden modificar ni eliminar.'
    def bloqueado(sql, params=()):
        try:
            cu.execute(sql, params); return 'SIN ERROR'
        except psycopg2.errors.RaiseException as e:
            return e.diag.message_primary
    chk('auditoria_cambios: UPDATE rechazado', bloqueado("UPDATE auditoria_cambios SET detalle='X' WHERE id_auditoria_cambio=%s", (aid,)) == MSG_AUD)
    chk('auditoria_cambios: DELETE rechazado', bloqueado("DELETE FROM auditoria_cambios WHERE id_auditoria_cambio=%s", (aid,)) == MSG_AUD)
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE id_auditoria_cambio=%s", (aid,)); chk('auditoria_cambios: el registro quedó intacto', cu.fetchone()[0] == 'ZZ')
    cu.execute("SELECT count(*) FROM auditoria_acceso")
    if cu.fetchone()[0]:
        chk('auditoria_acceso: UPDATE rechazado', bloqueado("UPDATE auditoria_acceso SET ci_ruc_ingresado = ci_ruc_ingresado WHERE ctid = (SELECT ctid FROM auditoria_acceso LIMIT 1)") == MSG_AUD)
        chk('auditoria_acceso: DELETE rechazado', bloqueado("DELETE FROM auditoria_acceso WHERE ctid = (SELECT ctid FROM auditoria_acceso LIMIT 1)") == MSG_AUD)
    borrar_auditoria(cu, 'zz_venta_test', [1])
    cu.execute("SELECT count(*) FROM auditoria_cambios WHERE id_auditoria_cambio=%s", (aid,))
    chk('auditoría: el helper de limpieza de tests sí puede borrar lo suyo (session_replication_role)', cu.fetchone()[0] == 0)
    cu.execute("SHOW session_replication_role"); chk('auditoría: el helper restablece session_replication_role', cu.fetchone()[0] == 'origin')
    codigo = ''.join(p.read_text(encoding='utf-8', errors='ignore') for p in (RAIZ / 'app').rglob('*.py'))
    chk('la aplicación no hace UPDATE/DELETE/TRUNCATE sobre las tablas de auditoría (solo INSERT)',
        not re.search(r'(UPDATE|DELETE\s+FROM|TRUNCATE)\s+(TABLE\s+)?auditoria_', codigo, re.I))

    # ---------- permisos ----------
    como(RECEP)
    api('get', VEN, 403, nombre='Recepción sin permiso: listado'); api('post', VEN, 403, {}, nombre='Recepción sin permiso: alta')
    api('delete', f'{VEN}/1', 403, nombre='Recepción sin permiso: anular'); api('get', f'{VEN}/pedidos', 403, nombre='Recepción: buscador de pedidos')
    r = c.get('/referenciales/venta/venta-index'); chk('vista: Recepción 403', r.status_code == 403)
    como(CAJERO)
    api('get', VEN, 200, nombre='Cajero: listado'); r = c.get('/referenciales/venta/venta-index'); chk('vista: Cajero 200', r.status_code == 200)

    # ---------- venta sin caja abierta ----------
    p0 = pedido(CLI, lineas(('C', 1)), nombre='pedido para probar la venta sin caja')
    d = api('get', f'{VEN}/caja-actual', 200, nombre='caja-actual sin apertura'); chk('caja-actual: null sin apertura', d['data'] is None)
    venta(p0, esperado=409, nombre='venta SIN caja abierta', exacto='Debe abrir la caja antes de registrar una venta.')
    chk('sin caja: el pedido sigue PENDIENTE y no se quemó ningún número', estado_pedido(p0) == 'PENDIENTE' and tim('numero_actual') == 0)

    with app.app_context():
        ap1 = AperturaCajaDao().abrirCaja(CAJERO[0], ids['caja'], 100000); ids['ap'].append(ap1)
    chk('apertura de caja ZZ abierta por el Cajero', isinstance(ap1, int))
    d = api('get', f'{VEN}/caja-actual', 200, nombre='caja-actual con apertura'); chk('caja-actual: devuelve la caja ZZ', d['data'] and d['data']['caja'] == 'ZZ CAJA VTA')

    # ---------- validaciones ----------
    api('post', VEN, 400, {'condicion': 'CONTADO'}, nombre='sin pedido', exacto='Debe seleccionar un pedido.', campo='id_pedido')
    api('post', VEN, 400, {'id_pedido': p0}, nombre='sin condición', exacto='La condición debe ser Contado o Crédito.', campo='condicion')
    api('post', VEN, 400, {'id_pedido': p0, 'condicion': 'CHEQUE'}, nombre='condición inválida', exacto='La condición debe ser Contado o Crédito.', campo='condicion')
    api('post', VEN, 404, {'id_pedido': 2147483000, 'condicion': 'CONTADO'}, nombre='pedido inexistente', exacto='No se encontró el pedido seleccionado.')
    api('post', VEN, 400, {}, nombre='cuerpo vacío')

    # ---------- venta feliz: precio del PEDIDO, totales calculados por el servidor ----------
    p1 = pedido(CLI, lineas(('A', 3), ('B', 2), ('C', 1)), nombre='pedido 1: A x3 + B x2 + C x1')   # 30.000 + 42.000 + 5.000 = 77.000
    cu.execute("UPDATE items SET precio_unitario = 99999 WHERE id_item=%s", (ids['item']['A'],))   # el ítem cambia DESPUÉS del pedido
    sA, sB = stock('A'), stock('B')
    cuerpo = {'id_pedido': p1, 'condicion': 'contado', 'total': 1, 'id_usuario': ADMIN[0], 'estado': 'ANULADA', 'numero_factura': 'X',
              'items': [{'id_item': 1, 'cantidad': 99, 'precio_unitario': 1}]}
    d = api('post', VEN, 201, cuerpo, nombre='venta CONTADO con datos falsificados por el navegador')
    v1 = d['data']['id_venta']; ventas.add(v1); v = d['data']
    chk("número de factura '998-998-0000001' (del SP)", v['numero_factura'] == '998-998-0000001')
    chk('mensaje con el número de factura', '998-998-0000001' in d['mensaje'])
    chk('estado EMITIDA, tipo ITEMS, condición CONTADO, pedido enlazado', (v['estado'], v['tipo_venta'], v['condicion'], v['id_pedido']) == ('EMITIDA', 'ITEMS', 'CONTADO', p1))
    chk('cajero = el de la sesión, apertura = la ABIERTA del cajero (no lo enviado)', v['id_usuario'] == CAJERO[0] and v['id_apertura'] == ap1)
    chk('totales del servidor: exenta 5.000, gravada 5% 42.000, gravada 10% 30.000, total 77.000',
        (v['total_exenta'], v['total_gravada_5'], v['total_gravada_10'], v['total']) == (5000, 42000, 30000, 77000))
    chk('IVA liquidado: 5% = 42.000/21 = 2.000 y 10% = 30.000/11 = 2.727', (v['iva_5'], v['iva_10']) == (2000, 2727))
    det = {x['descripcion']: x for x in v['detalle']}
    chk('detalle copiado del pedido (precio 10.000, no el nuevo 99.999 del ítem)', det['ZZ VTA ITEM A']['precio_unitario'] == 10000 and det['ZZ VTA ITEM A']['subtotal'] == 30000
        and det['ZZ VTA ITEM B']['iva'] == 5 and det['ZZ VTA ITEM C']['iva'] == 0 and len(v['detalle']) == 3)
    chk('la venta NO toca el stock (ya se descontó en el pedido)', (stock('A'), stock('B')) == (sA, sB))
    chk('el pedido pasó a FACTURADO', estado_pedido(p1) == 'FACTURADO')
    chk('timbrado: numero_actual = 1', tim('numero_actual') == 1)
    cu.execute("UPDATE items SET precio_unitario = 10000 WHERE id_item=%s", (ids['item']['A'],))
    chk('comprobante: trae empresa y timbrado', v['empresa']['ruc'] == '80099999-1' and v['timbrado']['numero'] == 'ZZ000001')

    # trigger: cuenta a cobrar creada
    cu.execute("SELECT id_cliente, monto_total, saldo, fecha_vencimiento, estado FROM cuenta_cobrar WHERE id_venta=%s", (v1,))
    cc = cu.fetchone()
    chk('trigger: cuenta a cobrar creada con saldo = total, PENDIENTE', cc and cc[0] == CLI and cc[1] == 77000 and cc[2] == 77000 and cc[4] == 'PENDIENTE')
    chk('trigger: CONTADO vence el mismo día de la venta', cc[3] == HOY)
    chk('venta: estado_cuenta y saldo en el detalle', v['estado_cuenta'] == 'PENDIENTE' and v['saldo'] == 77000)
    try:
        cu.execute("INSERT INTO cuenta_cobrar(id_venta, id_cliente, monto_total, saldo, fecha_vencimiento) VALUES (%s,%s,1,1,%s)", (v1, CLI, HOY)); ok = False
    except psycopg2.errors.UniqueViolation:
        ok = True
    chk('cuenta_cobrar: una sola cuenta por venta (UNIQUE id_venta)', ok)
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='venta_cab' AND id_registro=%s AND accion='ALTA'", (v1,))
    a = cu.fetchall(); chk('auditoría ALTA de la venta con factura, cliente, pedido, condición y total', len(a) == 1 and '998-998-0000001' in a[0][0] and 'ZZ CLIENTE VENTA' in a[0][0] and f'Pedido N.º {p1}' in a[0][0] and 'Contado' in a[0][0] and 'Gs. 77.000' in a[0][0])
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='pedido_venta_cab' AND id_registro=%s AND accion='MODIFICACION'", (p1,))
    chk('auditoría del pedido: PENDIENTE -> FACTURADO', 'PENDIENTE -> FACTURADO' in cu.fetchone()[0])

    # ---------- pedido facturado dos veces ----------
    venta(p1, esperado=409, nombre='facturar el mismo pedido otra vez', exacto='El pedido ya fue facturado.')
    chk('segundo intento: no se quemó número', tim('numero_actual') == 1)
    como(CAJERO); api('delete', f'{PED}/{p1}', 409, nombre='un pedido FACTURADO no se anula', exacto='El pedido ya fue facturado; no se puede anular.')
    api('get', f'{VEN}/pedidos/{p1}', 409, nombre='precargar un pedido facturado', exacto='El pedido ya fue facturado.')
    como(CAJERO)
    ped_anulado = pedido(CLI, lineas(('C', 1)), nombre='pedido que se anula')
    api('delete', f'{PED}/{ped_anulado}', 200, nombre='anular ese pedido')
    venta(ped_anulado, esperado=409, nombre='facturar un pedido ANULADO', exacto='El pedido está anulado y no se puede facturar.')

    # ---------- concurrencia: el mismo pedido, 3 cajeros a la vez ----------
    p2 = pedido(CLI, lineas(('A', 1)), nombre='pedido 2 (concurrencia)')
    n_antes = tim('numero_actual')
    res = [None] * 3; barrera = threading.Barrier(3)
    def hilo_venta(i):
        with app.app_context():
            barrera.wait(); res[i] = VentaDao().guardarVentaItems(CAJERO[0], p2, 'CONTADO')
    ts = [threading.Thread(target=hilo_venta, args=(i,)) for i in range(3)]; [t.start() for t in ts]; [t.join(60) for t in ts]
    oks = [r for r in res if isinstance(r, int)]; ventas.update(oks)
    chk('concurrencia: 3 intentos de facturar el mismo pedido -> exactamente 1 gana', len(oks) == 1 and sum(r == (PEDIDO_NO_PENDIENTE, 'FACTURADO') for r in res) == 2)
    chk('concurrencia: solo se consumió UN número (los perdedores deshacen el suyo)', tim('numero_actual') == n_antes + 1)
    v2 = oks[0]

    # ---------- crédito: vencimiento a 30 días ----------
    p3 = pedido(CLI2, lineas(('B', 1)), nombre='pedido 3 (crédito)')
    d = venta(p3, 'CREDITO', nombre='venta a CRÉDITO'); v3 = d['data']['id_venta']
    cu.execute("SELECT fecha_vencimiento, saldo FROM cuenta_cobrar WHERE id_venta=%s", (v3,)); cc = cu.fetchone()
    chk('trigger: CRÉDITO vence a los 30 días y saldo = total (21.000)', cc[0] == HOY + timedelta(days=30) and cc[1] == 21000)
    chk('venta de 1 ítem al 5%: gravada_5 21.000, IVA 1.000', (d['data']['total_gravada_5'], d['data']['iva_5'], d['data']['iva_10']) == (21000, 1000, 0))

    # ---------- buscador de pedidos y preselección ----------
    p4 = pedido(CLI2, lineas(('C', 2)), nombre='pedido 4 (queda PENDIENTE)')
    r = api('get', f'{VEN}/pedidos?q={p4}', 200, nombre='buscar pedido por N.º')['data']
    # un número también puede coincidir con la CI/RUC de un cliente real: el pedido con ese N.º exacto va primero
    chk('buscador por N.º devuelve ese pedido PENDIENTE en primer lugar', bool(r) and r[0]['id_pedido'] == p4 and all(x['id_pedido'] != p3 for x in r))
    r = api('get', f'{VEN}/pedidos?q=ZZ CLIENTE DOS', 200, nombre='buscar pedido por cliente')['data']
    chk('buscador por cliente: solo PENDIENTES (no los facturados)', p4 in {x['id_pedido'] for x in r} and p3 not in {x['id_pedido'] for x in r} and p1 not in {x['id_pedido'] for x in r})
    d = api('get', f'{VEN}/pedidos/{p4}', 200, nombre='precargar el pedido')['data']
    chk('precarga: cliente e ítems del pedido', d['cliente'] == 'ZZ CLIENTE DOS' and len(d['detalle']) == 1 and d['detalle'][0]['cantidad'] == 2)
    api('get', f'{VEN}/pedidos/2147483000', 404, nombre='precargar un pedido inexistente')

    # ---------- listado, filtros, detalle ----------
    como(ADMIN); lst_a = {x['id_venta'] for x in api('get', VEN, 200, nombre='Administrador: listado')['data']}
    como(CAJERO); lst_c = {x['id_venta'] for x in api('get', VEN, 200, nombre='Cajero: listado')['data']}
    chk('listado compartido: ambos ven todas las ventas de prueba', {v1, v2, v3} <= lst_a and {v1, v2, v3} <= lst_c)
    r = api('get', f'{VEN}?cliente=998-998-0000001', 200, nombre='filtro por N.º de factura')['data']; chk('filtro por N.º de factura', [x['id_venta'] for x in r] == [v1])
    r = api('get', f'{VEN}?cliente=ZZ CLIENTE DOS', 200)['data']; chk('filtro por cliente', {x['id_venta'] for x in r} == {v3})
    r = api('get', f'{VEN}?tipo=ITEMS&estado=EMITIDA&cliente=ZZ CLIENTE', 200)['data']; chk('filtros tipo + estado', {v1, v2, v3} <= {x['id_venta'] for x in r})
    r = api('get', f'{VEN}?tipo=TRATAMIENTO&cliente=ZZ CLIENTE', 200)['data']; chk('filtro tipo TRATAMIENTO: ninguna de prueba', not r)
    chk('filtro fechas: hoy incluye; ayer no', v1 in {x['id_venta'] for x in api('get', f'{VEN}?desde={HOY}&hasta={HOY}', 200)['data']}
        and v1 not in {x['id_venta'] for x in api('get', f'{VEN}?hasta={HOY - timedelta(days=1)}', 200)['data']})
    api('get', f'{VEN}?estado=XX', 400, nombre='estado inválido'); api('get', f'{VEN}?tipo=XX', 400, nombre='tipo inválido')
    api('get', f'{VEN}?desde=hoy', 400, nombre='fecha inválida'); api('get', f'{VEN}?desde={HOY}&hasta={HOY - timedelta(days=1)}', 400, nombre='desde > hasta')
    d = api('get', f'{VEN}/{v1}', 200, nombre='detalle (comprobante)')['data']
    chk('detalle: factura, cliente, cajero, caja, 3 renglones, totales', d['numero_factura'] == '998-998-0000001' and d['cliente'] == 'ZZ CLIENTE VENTA'
        and d['caja'] == 'ZZ CAJA VTA' and len(d['detalle']) == 3 and d['totales']['total'] == 77000)
    api('get', f'{VEN}/2147483000', 404, nombre='detalle inexistente')

    # ---------- vista v_estado_cuenta_cliente ----------
    cu.execute("SELECT numero_factura, condicion, total, saldo, estado_cuenta, saldo_total_cliente FROM v_estado_cuenta_cliente WHERE id_cliente=%s ORDER BY id_venta", (CLI,))
    f = cu.fetchall()
    chk('vista: una fila por factura del cliente con número, condición, total, saldo y estado de la cuenta',
        len(f) == 2 and f[0][:5] == ('998-998-0000001', 'CONTADO', 77000, 77000, 'PENDIENTE'))
    cu.execute("SELECT total FROM venta_cab WHERE id_venta=%s", (v2,)); t2 = cu.fetchone()[0]
    chk('vista: saldo_total_cliente = suma de los saldos pendientes del cliente', all(r[5] == 77000 + t2 for r in f))
    cu.execute("SELECT obj_description('v_estado_cuenta_cliente'::regclass, 'pg_class')"); chk('vista: tiene COMMENT ON', bool(cu.fetchone()[0]))

    # ---------- anular: cuenta anulada, pedido vuelve a PENDIENTE, número no se reutiliza ----------
    como(ADMIN)
    d = api('delete', f'{VEN}/{v1}', 200, nombre='anular la venta 1 (Administrador, caja abierta)', contiene='anulada correctamente')
    cu.execute("SELECT estado, numero_factura FROM venta_cab WHERE id_venta=%s", (v1,)); chk('la venta pasa a ANULADA y conserva su número', cu.fetchone() == ('ANULADA', '998-998-0000001'))
    cu.execute("SELECT estado FROM cuenta_cobrar WHERE id_venta=%s", (v1,)); chk('trigger: la cuenta a cobrar pasa a ANULADA', cu.fetchone()[0] == 'ANULADA')
    chk('el pedido vuelve a PENDIENTE', estado_pedido(p1) == 'PENDIENTE')
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='venta_cab' AND id_registro=%s AND accion='BAJA'", (v1,))
    chk('auditoría BAJA de la venta (quién anuló = Administrador)', 'vuelve a PENDIENTE' in cu.fetchone()[0])
    cu.execute("SELECT id_usuario FROM auditoria_cambios WHERE entidad='venta_cab' AND id_registro=%s AND accion='BAJA'", (v1,))
    chk('auditoría BAJA registra al usuario que anuló', cu.fetchone()[0] == ADMIN[0])
    api('delete', f'{VEN}/{v1}', 409, nombre='anular dos veces', exacto='La venta ya está anulada.')
    api('delete', f'{VEN}/2147483000', 404, nombre='anular inexistente')
    cu.execute("SELECT estado_cuenta, saldo_total_cliente FROM v_estado_cuenta_cliente WHERE id_venta=%s", (v1,))
    estado_cuenta, saldo_total = cu.fetchone()
    chk('vista: la venta anulada aparece con la cuenta ANULADA y fuera del saldo total del cliente', estado_cuenta == 'ANULADA' and saldo_total == t2)
    d = venta(p1, nombre='volver a facturar el pedido anulado')
    v1b = d['data']['id_venta']
    chk('el número anulado NO se reutiliza (la nueva factura tiene un número mayor)', d['data']['numero_factura'] != '998-998-0000001' and d['data']['numero_factura'] > '998-998-0000001')
    cu.execute("SELECT count(*) FROM venta_cab WHERE id_pedido=%s", (p1,)); chk('el pedido tiene 2 ventas (una ANULADA y una EMITIDA)', cu.fetchone()[0] == 2)

    # ---------- bloqueos cruzados con la apertura ----------
    como(CAJERO); api('delete', f'{AP}/{ap1}', 409, nombre='no se anula una apertura con ventas EMITIDAS',
                      exacto='La apertura tiene movimientos registrados; debe cerrarse en lugar de anularse.')
    with app.app_context():
        r = ClienteDao().deleteCliente(CLI)
    chk('baja de cliente con ventas EMITIDAS bloqueada', r == ('EN_USO', 'No se puede dar de baja, el cliente tiene ventas registradas.'))

    # ---------- errores del timbrado: se muestran tal cual ----------
    p5 = pedido(CLI2, lineas(('C', 1)), nombre='pedido 5 (errores de timbrado)')
    antes = tim('numero_actual')
    set_tim(fecha_fin=HOY - timedelta(days=1))
    venta(p5, esperado=409, nombre='timbrado vencido', exacto='El timbrado está vencido'); set_tim(fecha_fin=HOY + timedelta(days=30))
    set_tim(fecha_inicio=HOY + timedelta(days=1))
    venta(p5, esperado=409, nombre='timbrado aún no vigente', exacto='El timbrado aún no está vigente'); set_tim(fecha_inicio=HOY - timedelta(days=30))
    set_tim(numero_actual=100)
    venta(p5, esperado=409, nombre='rango agotado', exacto='Se agotó el rango de numeración del timbrado'); set_tim(numero_actual=antes)
    set_tim(activo=False)
    venta(p5, esperado=409, nombre='sin timbrado activo', exacto='No hay timbrado activo'); set_tim(activo=True)
    chk('errores de timbrado: el pedido sigue PENDIENTE', estado_pedido(p5) == 'PENDIENTE')
    chk('errores de timbrado: ninguna venta creada ni número consumido', tim('numero_actual') == antes)

    # ---------- caja cerrada: ya no se puede anular ----------
    como(CAJERO)
    api('delete', f'{VEN}/{v3}', 200, nombre='anular la venta 3 mientras la caja sigue abierta')
    with app.app_context():
        cierre = AperturaCajaDao().cerrarApertura(ap1, CAJERO[0], False)
    chk('la apertura se cierra', isinstance(cierre, dict))
    como(ADMIN)
    api('delete', f'{VEN}/{v1b}', 409, nombre='anular con la caja CERRADA', exacto='La caja de esta venta ya fue cerrada; utilice una Nota de Crédito.')
    cu.execute("SELECT estado FROM venta_cab WHERE id_venta=%s", (v1b,)); chk('caja cerrada: la venta sigue EMITIDA', cu.fetchone()[0] == 'EMITIDA')
    chk('caja cerrada: el pedido sigue FACTURADO', estado_pedido(p1) == 'FACTURADO')
    r = api('get', f'{VEN}?cliente=ZZ CLIENTE VENTA', 200)['data']
    chk('el listado informa el estado de la apertura (CERRADA)', any(x['id_venta'] == v1b and x['estado_apertura'] == 'CERRADA' for x in r))
    venta(p5, esperado=409, nombre='tras cerrar la caja no se puede vender', exacto='Debe abrir la caja antes de registrar una venta.')

    # ---------- apertura anulable cuando sus ventas están anuladas ----------
    with app.app_context():
        ap2 = AperturaCajaDao().abrirCaja(CAJERO[0], ids['caja'], 0); ids['ap'].append(ap2)
    como(CAJERO)
    d = venta(p4, nombre='venta en la segunda apertura'); v4 = d['data']['id_venta']
    api('delete', f'{AP}/{ap2}', 409, nombre='apertura 2 con venta EMITIDA: no se anula')
    api('delete', f'{VEN}/{v4}', 200, nombre='anular la venta de la apertura 2')
    api('delete', f'{AP}/{ap2}', 200, nombre='con la venta ANULADA la apertura sí se puede anular')
    cu.execute("SELECT estado FROM apertura_cierre_caja WHERE id_apertura=%s", (ap2,)); chk('apertura 2 ANULADA', cu.fetchone()[0] == 'ANULADA')

    # ---------- el timbrado real no se tocó ----------
    cu.execute("SELECT id_timbrado, numero_actual FROM timbrado WHERE id_timbrado = ANY(%s)", (ids['real'],))
    chk('timbrado real: numero_actual intacto durante todo el test', {r[0]: r[1] for r in cu.fetchall()} == actual_real)

finally:
    try:
        v_ids = set(ventas)
        cu.execute("SELECT id_venta FROM venta_cab WHERE id_timbrado = %s OR id_cliente = ANY(%s)", (ids['tim'], ids['cliente'] or [0]))
        v_ids |= {r[0] for r in cu.fetchall()}
        p_ids = set(pedidos)
        cu.execute("SELECT id_pedido FROM pedido_venta_cab WHERE id_cliente = ANY(%s)", (ids['cliente'] or [0],))
        p_ids |= {r[0] for r in cu.fetchall()}
        v_ids, p_ids = sorted(v_ids), sorted(p_ids)
        if v_ids:
            cu.execute("DELETE FROM cuenta_cobrar WHERE id_venta = ANY(%s)", (v_ids,))
            cu.execute("DELETE FROM venta_det WHERE id_venta = ANY(%s)", (v_ids,))
            cu.execute("DELETE FROM venta_cab WHERE id_venta = ANY(%s)", (v_ids,))
            borrar_auditoria(cu, 'venta_cab', v_ids)
        if p_ids:
            cu.execute("DELETE FROM pedido_venta_det WHERE id_pedido = ANY(%s)", (p_ids,))
            cu.execute("DELETE FROM pedido_venta_cab WHERE id_pedido = ANY(%s)", (p_ids,))
            borrar_auditoria(cu, 'pedido_venta_cab', p_ids)
        if ids['ap']:
            borrar_auditoria(cu, 'apertura_cierre_caja', ids['ap'])   # la anulación de la apertura 2 por API audita BAJA
            cu.execute("DELETE FROM apertura_cierre_caja WHERE id_apertura = ANY(%s)", (ids['ap'],))
        if ids['caja']:
            cu.execute("DELETE FROM caja WHERE id_caja=%s", (ids['caja'],))
        if ids['item']:
            cu.execute("DELETE FROM items WHERE id_item = ANY(%s)", (list(ids['item'].values()),))
        if ids['tipo']:
            cu.execute("DELETE FROM tipo_items WHERE id_tipo_item = ANY(%s)", (ids['tipo'],))
        if ids['dep']:
            cu.execute("DELETE FROM deposito WHERE id_deposito=%s", (ids['dep'],))
        if ids['cliente']:
            cu.execute("DELETE FROM cliente WHERE id_cliente = ANY(%s)", (ids['cliente'],))
        if ids['tim']:
            cu.execute("DELETE FROM timbrado WHERE id_timbrado=%s", (ids['tim'],))
    except Exception as e:
        print('ERROR EN LA LIMPIEZA:', e); fallos.append('limpieza')
    finally:
        if ids['real']:   # SIEMPRE se restaura el timbrado real
            cu.execute("UPDATE timbrado SET activo=true WHERE id_timbrado = ANY(%s)", (ids['real'],))
    cu.execute("SELECT count(*) FROM timbrado WHERE activo=true"); n_act = cu.fetchone()[0]
    if n_act != len(ids['real']):
        fallos.append('timbrado real no restaurado')

print()
print('FALLOS:', 'ninguno' if not fallos else fallos)
sys.exit(1 if fallos else 0)
