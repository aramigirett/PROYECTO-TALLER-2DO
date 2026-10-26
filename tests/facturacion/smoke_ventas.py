"""Registrar Ventas y Cuentas a Cobrar (etapa 1): empresa/timbrado, sp_siguiente_numero_factura (numeración, vigencia,
rango, concurrencia), triggers (cuenta a cobrar creada y anulada, auditoría inmutable), vista v_estado_cuenta_cliente,
nueva venta de ítems (sin caja abierta, pedido facturado dos veces, totales e IVA calculados por el servidor), anulación
(vuelta del pedido a PENDIENTE, número no reutilizado, caja cerrada), permisos y bloqueos cruzados.

TIMBRADO: el SP incrementa numero_actual y esos números no se reutilizan, así que el test DESACTIVA el timbrado real,
crea uno ZZ (establecimiento/punto 998-998) y, en el finally, lo borra y REACTIVA el real (verificando que su
numero_actual no cambió). Mientras corre (unos segundos) no hay timbrado real activo: no correrlo con el sistema en uso.

Usa usuarios REALES (Administrador, Cajero y Recepción) con sesiones simuladas y datos ZZ que borra POR ID. Aborta si el
Cajero tiene una caja abierta de verdad (cerrarla antes)."""
import sys, pathlib, re, threading, time, base64, zlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from datetime import date, timedelta
import psycopg2
from app import app
from tests._conexion_pruebas import Conexion
from app.dao.modulo_facturacion.venta.VentaDao import (
    VentaDao, PEDIDO_NO_PENDIENTE, TRATAMIENTO_FACTURADO, TRATAMIENTO_CANCELADO)
from app.dao.modulo_facturacion.apertura_caja.AperturaCajaDao import AperturaCajaDao
from app.dao.modulo_facturacion.cliente.ClienteDao import ClienteDao
from app.dao.modulo_facturacion.items.ItemDao import ItemDao
from app.dao.referenciales_consultorio.tratamiento.TratamientoDao import TratamientoDao
from app.Services.factura_pdf_service import generarFacturaPdf, calcular_datos_factura
from app.dao.modulo_facturacion.pedido_cliente.PedidoClienteDao import calcular_totales
from app.rutas.modulo_facturacion.utils import calcular_dv_ruc
from tests.facturacion._limpieza import borrar_auditoria
from tests.consultorio._fixtures import Fixtures

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
fx = Fixtures(cx)   # médico y consulta ZZ: solo el médico de una consulta abierta anula un tratamiento (Consultorio, etapa 5)

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

ids = {'tipo': [], 'dep': None, 'item': {}, 'cliente': [], 'caja': None, 'ap': [], 'tim': None, 'real': [],
       'tipo_trat': [], 'trat': [], 'paciente': None}

def paginas_pdf(pdf):
    """Cantidad de páginas de un PDF de ReportLab (cuenta los objetos /Type /Page, no /Type /Pages)."""
    return len(re.findall(rb'/Type /Page(?!s)', pdf))

def texto_pdf(pdf):
    """Texto de un PDF de ReportLab sin librerías externas: decodifica los streams (ASCII85 + Flate) y junta las cadenas Tj."""
    textos = []
    for m in re.finditer(rb'stream\r?\n(.*?)endstream', pdf, re.S):
        datos = m.group(1).strip()
        try:
            if datos.endswith(b'~>'):
                datos = base64.a85decode(datos[:-2])
            datos = zlib.decompress(datos)
        except Exception:
            continue
        for s in re.findall(rb'\((.*?)(?<!\\)\) Tj', datos, re.S):
            textos.append(s.decode('latin-1').replace('\\(', '(').replace('\\)', ')').replace('\\\\', '\\'))
    return '\n'.join(textos)
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
        and dire == 'AVDA. MCAL. LÓPEZ 1234 - ASUNCIÓN' and tel == '021600600' and act == 'SERVICIOS ODONTOLÓGICOS')
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

    # ---------- etapa 2: esquema ----------
    cu.execute("SELECT character_maximum_length FROM information_schema.columns WHERE table_name='venta_det' AND column_name='descripcion'")
    chk('etapa 2: venta_det.descripcion es VARCHAR(200)', cu.fetchone()[0] == 200)
    cu.execute("SELECT count(*) FROM pg_indexes WHERE indexname IN ('ix_venta_det_tratamiento', 'ix_venta_det_item')")
    chk('etapa 2: índices por tratamiento e ítem en venta_det', cu.fetchone()[0] == 2)

    # ---------- decisión: ItemDao.esta_en_uso NO bloquea por ventas EMITIDAS (solo por pedidos PENDIENTES) ----------
    cu.execute("SELECT count(*) FROM venta_cab v JOIN venta_det d USING(id_venta) WHERE d.id_item = %s AND v.estado = 'EMITIDA'", (ids['item']['A'],))
    chk('el ítem A figura en una venta EMITIDA (pedido FACTURADO)', cu.fetchone()[0] >= 1 and estado_pedido(p1) == 'FACTURADO')
    with app.app_context():
        chk('ítem en una venta EMITIDA: la baja NO se bloquea (la factura copia descripción, precio e IVA)', ItemDao().esta_en_uso(ids['item']['A']) is False)

    # ---------- factura en PDF ----------
    cu.execute("SELECT numero_factura FROM venta_cab WHERE id_venta=%s", (v1b,)); n_v1b = cu.fetchone()[0]
    como(CAJERO)
    r = c.get(f'{VEN}/{v1b}/pdf')
    chk('PDF: 200, application/pdf y empieza con %PDF', r.status_code == 200 and r.mimetype == 'application/pdf' and r.data[:4] == b'%PDF')
    chk('PDF: exactamente 2 páginas (ORIGINAL y DUPLICADO)', paginas_pdf(r.data) == 2)
    txt = texto_pdf(r.data)
    chk('PDF: contiene el número de factura', txt.count(n_v1b) >= 2)
    chk('PDF: contiene el RUC de la empresa y el número de timbrado', '80099999-1' in txt and 'ZZ000001' in txt)
    chk('PDF: contiene el total (77.000) y el total en letras', '77.000' in txt and 'SETENTA Y SIETE MIL' in txt and 'SON GUARAN' in txt)
    chk('PDF: ORIGINAL y DUPLICADO, FACTURA, cliente y liquidación del IVA', 'ORIGINAL' in txt and 'DUPLICADO' in txt and 'FACTURA' in txt
        and 'ZZ CLIENTE VENTA' in txt and '2.727' in txt and '2.000' in txt)
    chk('PDF de una factura vigente: sin marca ANULADA', 'ANULADA' not in txt)
    r = c.get(f'{VEN}/{v1}/pdf')
    chk('PDF de una factura ANULADA: se descarga igual, con la marca ANULADA', r.status_code == 200 and 'ANULADA' in texto_pdf(r.data) and paginas_pdf(r.data) == 2)
    como(RECEP); api('get', f'{VEN}/{v1b}/pdf', 403, nombre='PDF sin permiso ver (Recepción)')
    como(CAJERO); api('get', f'{VEN}/2147483000/pdf', 404, nombre='PDF de una venta inexistente')
    # el CÁLCULO (datos) está separado del DIBUJO (layout)
    with app.app_context():
        venta_dict = VentaDao().getVentaById(v1b)
    datos = calcular_datos_factura(venta_dict)
    lin = {l['descripcion']: l for l in datos['lineas']}
    chk('datos: cada renglón va en UNA sola columna (Exentas / 5% / 10%)',
        (lin['ZZ VTA ITEM A']['exenta'], lin['ZZ VTA ITEM A']['gravada_5'], lin['ZZ VTA ITEM A']['gravada_10']) == ('', '', '30.000')
        and (lin['ZZ VTA ITEM B']['exenta'], lin['ZZ VTA ITEM B']['gravada_5'], lin['ZZ VTA ITEM B']['gravada_10']) == ('', '42.000', '')
        and (lin['ZZ VTA ITEM C']['exenta'], lin['ZZ VTA ITEM C']['gravada_5'], lin['ZZ VTA ITEM C']['gravada_10']) == ('5.000', '', ''))
    chk('datos: subtotales, total, total en letras y liquidación del IVA',
        datos['subtotales'] == {'exenta': '5.000', 'gravada_5': '42.000', 'gravada_10': '30.000'} and datos['total'] == '77.000'
        and datos['total_letras'] == 'SON GUARANÍES: SETENTA Y SIETE MIL.' and datos['iva'] == {'iva_5': '2.000', 'iva_10': '2.727', 'total': '4.727'})
    chk('datos: es un dict puro (serializable, sin objetos de ReportLab) y trae los datos de empresa y timbrado',
        bool(json.dumps(datos)) and datos['empresa']['ruc'] == '80099999-1' and datos['timbrado']['numero'] == 'ZZ000001' and datos['condicion'] == 'Contado')
    larga = dict(venta_dict)
    base = venta_dict['detalle'][0]
    larga['detalle'] = [dict(base, descripcion=f'RENGLON {i} ' + 'DESCRIPCION MUY LARGA DEL TRATAMIENTO ' * (1 + i % 4), cantidad=1,
                             precio_unitario=10000, subtotal=10000, iva=10) for i in range(45)]
    larga['totales'] = calcular_totales(larga['detalle']); larga['iva_5'], larga['iva_10'] = larga['totales']['iva_5'], larga['totales']['iva_10']
    pdf_largo = generarFacturaPdf(larga); n_pag = paginas_pdf(pdf_largo)
    chk('factura larga: cada copia sigue en páginas adicionales (total par y mayor que 2)', n_pag > 2 and n_pag % 2 == 0)
    chk('factura larga: el pie (TOTAL A PAGAR) aparece una vez por copia', texto_pdf(pdf_largo).count('TOTAL A PAGAR') == 2)

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

    # =================================================================================================================
    # ETAPA 2: venta de tratamiento, anulación con y sin casilla, bloqueo en Consultorio
    # =================================================================================================================
    LARGA = 'ZZ TRAT B ' + 'X' * 190       # 200 caracteres: la descripción NO se recorta
    cu.execute("INSERT INTO tipos_tratamiento(descripcion, precio, iva) VALUES ('ZZ TRAT A', 120000, 10) RETURNING id_tipo_tratamiento"); TA = cu.fetchone()[0]
    cu.execute("INSERT INTO tipos_tratamiento(descripcion, precio, iva) VALUES (%s, 50000, 5) RETURNING id_tipo_tratamiento", (LARGA,)); TB = cu.fetchone()[0]
    cu.execute("INSERT INTO tipos_tratamiento(descripcion, precio, iva) VALUES ('ZZ TRAT C', 30000, 0) RETURNING id_tipo_tratamiento"); TC = cu.fetchone()[0]
    ids['tipo_trat'] = [TA, TB, TC]
    cu.execute("SELECT id_ciudad FROM ciudades ORDER BY 1 LIMIT 1"); ciudad = cu.fetchone()[0]
    cu.execute("INSERT INTO paciente(nombre, apellido, cedula_entidad, id_ciudad) VALUES ('ZZ', 'PACIENTE', %s, %s) RETURNING id_paciente", ('ZZP' + stamp, ciudad)); PAC = cu.fetchone()[0]
    cu.execute("INSERT INTO paciente(nombre, apellido, cedula_entidad, id_ciudad) VALUES ('ZZ', 'OTRO PACIENTE', %s, %s) RETURNING id_paciente", ('ZZO' + stamp, ciudad)); PAC2 = cu.fetchone()[0]
    ids['paciente'] = [PAC, PAC2]
    cu.execute("INSERT INTO cliente(nombre, apellido, ci_ruc, id_paciente) VALUES ('ZZ CLIENTE', 'TRAT', %s, %s) RETURNING id_cliente", ('ZZT' + stamp, PAC)); CLI_T = cu.fetchone()[0]
    ids['cliente'].append(CLI_T)
    f_rec, _u_rec = fx.recepcion()
    MEDICO, u_medico = fx.medico()
    CONSULTA = fx.registrar_consulta(fx.cita(MEDICO, PAC, fx.consultorio(), f_rec), f_rec, 'en_proceso')
    cu.execute("SELECT u.id_usuario, u.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.id_usuario=%s", (u_medico,)); MEDU = cu.fetchone()

    def mktrat(tipo, estado='pendiente', paciente=None):
        cu.execute("INSERT INTO tratamientos(id_consulta_cab, id_paciente, id_medico, id_tipo_tratamiento, descripcion_tratamiento, fecha_tratamiento, estado) "
                   "VALUES (%s,%s,%s,%s,'ZZ prueba de venta', CURRENT_DATE, %s) RETURNING id_tratamiento", (CONSULTA, paciente or PAC, MEDICO, tipo, estado))
        tid = cu.fetchone()[0]; ids['trat'].append(tid); fx.auditoria_de('tratamientos', tid); return tid
    T1 = mktrat(TA); T2 = mktrat(TB, 'finalizado'); T3 = mktrat(TC, 'cancelado'); T4 = mktrat(TC); T5 = mktrat(TC); T6 = mktrat(TC, paciente=PAC2)

    def venta_trat(cli, pac, trats, cond='CONTADO', esperado=201, **kw):
        como(CAJERO)
        d = api('post', VEN, esperado, {'tipo_venta': 'TRATAMIENTO', 'id_cliente': cli, 'id_paciente': pac, 'ids_tratamiento': trats, 'condicion': cond}, **kw)
        if esperado == 201:
            ventas.add(d['data']['id_venta'])
        return d

    # ---- sin caja abierta ----
    n_antes = tim('numero_actual')
    venta_trat(CLI_T, PAC, [T1], esperado=409, nombre='venta de tratamiento SIN caja abierta', exacto='Debe abrir la caja antes de registrar una venta.')
    chk('sin caja: no se quemó número', tim('numero_actual') == n_antes)
    with app.app_context():
        ap3 = AperturaCajaDao().abrirCaja(CAJERO[0], ids['caja'], 50000); ids['ap'].append(ap3)
    chk('apertura de caja 3 abierta por el Cajero', isinstance(ap3, int))

    # ---- buscadores ----
    como(RECEP); api('get', f'{VEN}/pacientes?q=ZZ', 403, nombre='Recepción: buscador de pacientes'); api('get', f'{VEN}/tratamientos?id_paciente={PAC}', 403, nombre='Recepción: tratamientos')
    como(CAJERO)
    api('get', f'{VEN}/pacientes?q=Z', 400, nombre='pacientes: menos de 2 caracteres', exacto='Ingrese al menos 2 caracteres para buscar.')
    r = api('get', f'{VEN}/pacientes?q=ZZP{stamp}', 200, nombre='buscar paciente por cédula')['data']
    chk('buscador de pacientes: devuelve id, nombre y cédula (nada más)', [x['id_paciente'] for x in r] == [PAC] and set(r[0]) == {'id_paciente', 'nombre', 'cedula'})
    r = api('get', f'{VEN}/clientes?q=ZZ CLIENTE TRAT', 200, nombre='buscar cliente')['data']
    chk('buscador de clientes: trae el paciente vinculado (se precarga)', len(r) == 1 and r[0]['id_paciente'] == PAC and r[0]['paciente'] == 'ZZ PACIENTE')
    r = api('get', f'{VEN}/clientes?q=', 200)['data']; chk('buscador de clientes: SIN NOMBRE primero', r and r[0]['ci_ruc'] == '44444401-7')
    api('get', f'{VEN}/tratamientos', 400, nombre='tratamientos sin paciente', campo='id_paciente')
    r = api('get', f'{VEN}/tratamientos?id_paciente={PAC}', 200, nombre='tratamientos facturables del paciente')['data']
    por_id = {x['id_tratamiento']: x for x in r}
    chk('lista: no cancelados y sin venta EMITIDA (T1, T2, T4, T5; sin T3 cancelado ni el de otro paciente)', set(por_id) == {T1, T2, T4, T5})
    chk('lista: precio e IVA vigentes del tipo y descripción del tipo', (por_id[T1]['descripcion'], por_id[T1]['precio'], por_id[T1]['iva']) == ('ZZ TRAT A', 120000, 10)
        and (por_id[T2]['precio'], por_id[T2]['iva'], por_id[T2]['descripcion']) == (50000, 5, LARGA))

    # ---- validaciones ----
    def val(cuerpo, msg, camp, nombre, code=400):
        como(CAJERO); api('post', VEN, code, cuerpo, nombre=f'validación: {nombre}', exacto=msg, campo=camp)
    base_t = {'tipo_venta': 'TRATAMIENTO', 'id_cliente': CLI_T, 'id_paciente': PAC, 'ids_tratamiento': [T1], 'condicion': 'CONTADO'}
    val({**base_t, 'tipo_venta': 'OTRO'}, 'El tipo de venta debe ser ITEMS o TRATAMIENTO.', 'tipo_venta', 'tipo de venta inválido')
    val({**base_t, 'id_cliente': None}, 'Debe seleccionar un cliente.', 'id_cliente', 'sin cliente')
    val({**base_t, 'id_paciente': None}, 'Debe seleccionar un paciente.', 'id_paciente', 'sin paciente')
    val({**base_t, 'ids_tratamiento': []}, 'Debe seleccionar al menos un tratamiento.', 'ids_tratamiento', 'sin tratamientos')
    val({**base_t, 'ids_tratamiento': [T1, T1]}, 'Un tratamiento no puede repetirse en la misma factura.', 'ids_tratamiento', 'tratamiento repetido')
    val({**base_t, 'ids_tratamiento': ['x']}, 'Uno de los tratamientos seleccionados no es válido.', 'ids_tratamiento', 'id inválido')
    val({**base_t, 'ids_tratamiento': [2147483000]}, 'Uno de los tratamientos seleccionados no existe.', 'ids_tratamiento', 'tratamiento inexistente')
    val({**base_t, 'condicion': 'CHEQUE'}, 'La condición debe ser Contado o Crédito.', 'condicion', 'condición inválida')
    val({**base_t, 'id_cliente': 2147483000}, 'El cliente seleccionado no existe o está inactivo.', 'id_cliente', 'cliente inexistente')
    val({**base_t, 'id_paciente': 2147483000}, 'El paciente seleccionado no existe.', 'id_paciente', 'paciente inexistente')
    val({**base_t, 'ids_tratamiento': [T6]}, 'El tratamiento ZZ TRAT C no pertenece al paciente seleccionado.', 'ids_tratamiento', 'tratamiento de otro paciente')
    val({**base_t, 'ids_tratamiento': [T1, T3]}, 'El tratamiento ZZ TRAT C está cancelado y no se puede facturar.', 'ids_tratamiento', 'tratamiento cancelado', 409)
    chk('validaciones: no se creó ninguna venta ni se quemó un número', tim('numero_actual') == n_antes)

    # ---- alta: precio e IVA del TIPO, descripción completa, totales del servidor ----
    como(CAJERO)
    d = venta_trat(CLI_T, PAC, [T1, T2], nombre='venta de tratamiento CONTADO (T1 + T2)')
    vt = d['data']; v_t1 = vt['id_venta']
    chk('tipo TRATAMIENTO, sin pedido, EMITIDA, cajero de la sesión y apertura abierta', (vt['tipo_venta'], vt['id_pedido'], vt['estado'], vt['id_usuario'], vt['id_apertura']) == ('TRATAMIENTO', None, 'EMITIDA', CAJERO[0], ap3))
    chk('totales: gravada 10% 120.000, gravada 5% 50.000, total 170.000', (vt['total_exenta'], vt['total_gravada_5'], vt['total_gravada_10'], vt['total']) == (0, 50000, 120000, 170000))
    chk('IVA liquidado: 5% = 50.000/21 = 2.381 y 10% = 120.000/11 = 10.909', (vt['iva_5'], vt['iva_10']) == (2381, 10909))
    dt = {x['id_tratamiento']: x for x in vt['detalle']}
    chk('renglones: cantidad 1, precio e IVA copiados del tipo', (dt[T1]['cantidad'], dt[T1]['precio_unitario'], dt[T1]['iva'], dt[T1]['subtotal']) == (1, 120000, 10, 120000)
        and (dt[T2]['cantidad'], dt[T2]['precio_unitario'], dt[T2]['iva']) == (1, 50000, 5) and dt[T1]['id_item'] is None)
    chk('la descripción de 200 caracteres se copia COMPLETA (sin recortar)', dt[T2]['descripcion'] == LARGA and len(dt[T2]['descripcion']) == 200)
    cu.execute("SELECT saldo, monto_total, fecha_vencimiento, estado FROM cuenta_cobrar WHERE id_venta=%s", (v_t1,))
    chk('trigger: la cuenta a cobrar se crea con saldo = total (170.000), contado, PENDIENTE', cu.fetchone() == (170000, 170000, HOY, 'PENDIENTE'))
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='venta_cab' AND id_registro=%s AND accion='ALTA'", (v_t1,))
    a = cu.fetchone()[0]; chk('auditoría ALTA: lista los tratamientos (sin pedido)', 'Tratamientos: ZZ TRAT A' in a and 'Pedido' not in a and 'Gs. 170.000' in a)
    cu.execute("UPDATE tipos_tratamiento SET precio = 999999 WHERE id_tipo_tratamiento=%s", (TA,))
    d = api('get', f'{VEN}/{v_t1}', 200, nombre='la venta guarda su propio precio')['data']
    chk('si el precio del tipo cambia después, la factura conserva el suyo', {x['id_tratamiento']: x for x in d['detalle']}[T1]['precio_unitario'] == 120000)
    cu.execute("UPDATE tipos_tratamiento SET precio = 120000 WHERE id_tipo_tratamiento=%s", (TA,))
    r = api('get', f'{VEN}/tratamientos?id_paciente={PAC}', 200)['data']
    chk('los tratamientos facturados ya no se listan como facturables', {x['id_tratamiento'] for x in r} == {T4, T5})
    r = api('get', f'{VEN}?tipo=TRATAMIENTO&cliente=ZZ CLIENTE TRAT', 200)['data']; chk('listado: filtro por tipo TRATAMIENTO', [x['id_venta'] for x in r] == [v_t1])

    # ---- doble facturación ----
    cu.execute("SELECT numero_factura FROM venta_cab WHERE id_venta=%s", (v_t1,)); n_t1 = cu.fetchone()[0]
    n_ant = tim('numero_actual')
    venta_trat(CLI_T, PAC, [T1], esperado=409, nombre='facturar de nuevo un tratamiento ya facturado', exacto=f'El tratamiento ZZ TRAT A ya fue facturado en la factura {n_t1}.', campo='ids_tratamiento')
    venta_trat(CLI_T, PAC, [T4, T2], esperado=409, nombre='uno libre + uno ya facturado: no se factura nada', contiene='ya fue facturado en la factura')
    chk('doble facturación: no se quemó número y T4 sigue libre', tim('numero_actual') == n_ant and T4 in {x['id_tratamiento'] for x in c.get(f'{VEN}/tratamientos?id_paciente={PAC}').get_json()['data']})

    # ---- bloqueo en Consultorio ----
    como(MEDU)
    api('delete', f'/api/v1/tratamientos/{T1}', 409, nombre='Consultorio: anular un tratamiento FACTURADO', exacto='El tratamiento ya fue facturado; anule primero la factura.')
    cu.execute("SELECT estado FROM tratamientos WHERE id_tratamiento=%s", (T1,)); chk('Consultorio: el tratamiento facturado sigue sin cancelar', cu.fetchone()[0] == 'pendiente')
    with app.app_context():
        chk('Consultorio: TratamientoDao.anularTratamiento devuelve "FACTURADO"', TratamientoDao().anularTratamiento(T2, MEDICO).get('error') == 'FACTURADO')
    api('delete', f'/api/v1/tratamientos/{T4}', 200, nombre='Consultorio: un tratamiento SIN factura se anula normalmente')
    cu.execute("SELECT estado FROM tratamientos WHERE id_tratamiento=%s", (T4,)); chk('Consultorio: T4 quedó cancelado', cu.fetchone()[0] == 'cancelado')
    venta_trat(CLI_T, PAC, [T4], esperado=409, nombre='un tratamiento cancelado no se factura', contiene='está cancelado')

    # ---- concurrencia: el mismo tratamiento, 3 cajeros a la vez ----
    n_ant = tim('numero_actual')
    res = [None] * 3; barrera = threading.Barrier(3)
    def hilo_trat(i):
        with app.app_context():
            barrera.wait(); res[i] = VentaDao().guardarVentaTratamientos(CAJERO[0], CLI_T, PAC, [T5], 'CONTADO')
    ts = [threading.Thread(target=hilo_trat, args=(i,)) for i in range(3)]; [t.start() for t in ts]; [t.join(60) for t in ts]
    oks = [r for r in res if isinstance(r, int)]; ventas.update(oks)
    chk('concurrencia: 3 intentos de facturar el mismo tratamiento -> exactamente 1 gana', len(oks) == 1 and sum(isinstance(r, tuple) and r[0] == TRATAMIENTO_FACTURADO for r in res) == 2)
    chk('concurrencia: solo se consumió UN número', tim('numero_actual') == n_ant + 1)
    v_t5 = oks[0]
    # facturar vs cancelar el mismo tratamiento a la vez: nunca pueden ganar los dos
    T7 = mktrat(TC); res = [None, None]; barrera = threading.Barrier(2)
    def hilo_venta7():
        with app.app_context():
            barrera.wait(); res[0] = VentaDao().guardarVentaTratamientos(CAJERO[0], CLI_T, PAC, [T7], 'CONTADO')
    def hilo_cancelar7():
        with app.app_context():
            barrera.wait(); res[1] = TratamientoDao().anularTratamiento(T7, MEDICO)
    ts = [threading.Thread(target=hilo_venta7), threading.Thread(target=hilo_cancelar7)]; [t.start() for t in ts]; [t.join(60) for t in ts]
    if isinstance(res[0], int):
        ventas.add(res[0])
    gana_venta = isinstance(res[0], int) and res[1].get('error') == 'FACTURADO'
    gana_cancelar = res[1].get('ok') is True and isinstance(res[0], tuple) and res[0][0] == TRATAMIENTO_CANCELADO
    chk('concurrencia: facturar y cancelar el mismo tratamiento a la vez -> gana UNO solo, nunca los dos', gana_venta or gana_cancelar)

    # ---- anular la venta de tratamiento: los tratamientos quedan libres ----
    como(ADMIN)
    d = api('delete', f'{VEN}/{v_t1}?anular_pedido=1', 200, nombre='anular la venta de tratamiento (la casilla del pedido no aplica)', contiene='anulada correctamente')
    cu.execute("SELECT estado FROM venta_cab WHERE id_venta=%s", (v_t1,)); chk('venta de tratamiento ANULADA', cu.fetchone()[0] == 'ANULADA')
    cu.execute("SELECT estado FROM cuenta_cobrar WHERE id_venta=%s", (v_t1,)); chk('trigger: la cuenta a cobrar pasa a ANULADA', cu.fetchone()[0] == 'ANULADA')
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='venta_cab' AND id_registro=%s AND accion='BAJA'", (v_t1,))
    chk('auditoría BAJA: "los tratamientos quedan libres"', 'quedan libres' in cu.fetchone()[0])
    r = api('get', f'{VEN}/tratamientos?id_paciente={PAC}', 200)['data']
    chk('los tratamientos T1 y T2 quedan libres para volver a facturarse', {T1, T2} <= {x['id_tratamiento'] for x in r})
    d = venta_trat(CLI_T, PAC, [T1, T2], 'CREDITO', nombre='volver a facturar los mismos tratamientos (CRÉDITO)')
    v_t1b = d['data']['id_venta']
    chk('la nueva factura tiene un número mayor y vence a los 30 días', d['data']['numero_factura'] > n_t1)
    cu.execute("SELECT fecha_vencimiento FROM cuenta_cobrar WHERE id_venta=%s", (v_t1b,)); chk('trigger: crédito vence a los 30 días', cu.fetchone()[0] == HOY + timedelta(days=30))
    como(ADMIN); api('delete', f'{VEN}/{v_t1b}', 200, nombre='anular otra vez')
    como(MEDU); api('delete', f'/api/v1/tratamientos/{T2}', 200, nombre='Consultorio: con la factura anulada el tratamiento se puede cancelar')
    como(ADMIN)

    # ---- anular una venta de ítems: SIN la casilla -> el pedido vuelve a PENDIENTE (stock sigue descontado) ----
    sA0 = stock('A')
    pA = pedido(CLI, lineas(('A', 2), ('C', 1)), nombre='pedido para anular SIN casilla')
    sA1 = stock('A'); chk('el pedido descontó 2 unidades de A', sA1 == sA0 - 2)
    d = venta(pA, nombre='venta del pedido (sin casilla)'); vA = d['data']['id_venta']
    como(ADMIN); api('delete', f'{VEN}/{vA}', 200, nombre='anular SIN la casilla')
    chk('sin casilla: el pedido vuelve a PENDIENTE y el stock sigue descontado', estado_pedido(pA) == 'PENDIENTE' and stock('A') == sA1)

    # ---- CON la casilla -> pedido ANULADO y stock repuesto, todo junto ----
    d = venta(pA, nombre='volver a facturar el pedido'); vA2 = d['data']['id_venta']
    como(ADMIN)
    d = api('delete', f'{VEN}/{vA2}?anular_pedido=1', 200, nombre='anular CON la casilla (venta + pedido + stock)', contiene='también se anuló')
    cu.execute("SELECT estado FROM venta_cab WHERE id_venta=%s", (vA2,)); chk('con casilla: la venta queda ANULADA', cu.fetchone()[0] == 'ANULADA')
    chk('con casilla: el pedido queda ANULADO', estado_pedido(pA) == 'ANULADO')
    chk('con casilla: el stock se repone (A vuelve a su valor original)', stock('A') == sA0)
    cu.execute("SELECT estado FROM cuenta_cobrar WHERE id_venta=%s", (vA2,)); chk('con casilla: la cuenta a cobrar también se anula', cu.fetchone()[0] == 'ANULADA')
    cu.execute("SELECT accion, detalle FROM auditoria_cambios WHERE entidad='pedido_venta_cab' AND id_registro=%s ORDER BY id_auditoria_cambio DESC LIMIT 1", (pA,))
    f = cu.fetchone(); chk('con casilla: auditoría BAJA del pedido con el stock repuesto', f[0] == 'BAJA' and 'ZZ VTA ITEM A +2' in f[1])
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='venta_cab' AND id_registro=%s AND accion='BAJA'", (vA2,))
    chk('con casilla: auditoría BAJA de la venta con el pedido anulado y el stock', 'anulado' in cu.fetchone()[0])
    r = api('get', f'{VEN}/pedidos?q={pA}', 200)['data']; chk('con casilla: el pedido ya no aparece como PENDIENTE para facturar', pA not in {x['id_pedido'] for x in r})
    venta(pA, esperado=409, nombre='con casilla: no se puede facturar el pedido anulado', exacto='El pedido está anulado y no se puede facturar.')
    como(ADMIN); api('delete', f'{VEN}/{vA2}?anular_pedido=1', 409, nombre='anular dos veces con casilla', exacto='La venta ya está anulada.')

    # ---- con casilla pero la caja ya está cerrada: no se anula nada ----
    pB = pedido(CLI, lineas(('B', 1)), nombre='pedido para la prueba de caja cerrada'); sB = stock('B')
    d = venta(pB, nombre='venta antes del cierre'); vB = d['data']['id_venta']
    with app.app_context():
        AperturaCajaDao().cerrarApertura(ap3, CAJERO[0], False)
    como(ADMIN)
    api('delete', f'{VEN}/{vB}?anular_pedido=1', 409, nombre='con casilla y caja CERRADA', exacto='La caja de esta venta ya fue cerrada; utilice una Nota de Crédito.')
    chk('caja cerrada + casilla: venta EMITIDA, pedido FACTURADO y stock intactos', estado_pedido(pB) == 'FACTURADO' and stock('B') == sB)

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
        if ids['trat']:
            cu.execute("DELETE FROM tratamientos WHERE id_tratamiento = ANY(%s)", (ids['trat'],))
        fx.limpiar()   # la consulta, el médico y su usuario ZZ (con sus tratamientos y su auditoría)
        if ids['tipo_trat']:
            cu.execute("DELETE FROM tipos_tratamiento WHERE id_tipo_tratamiento = ANY(%s)", (ids['tipo_trat'],))
        if ids['cliente']:
            cu.execute("DELETE FROM cliente WHERE id_cliente = ANY(%s)", (ids['cliente'],))
        if ids['paciente']:
            cu.execute("DELETE FROM paciente WHERE id_paciente = ANY(%s)", (ids['paciente'],))
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
