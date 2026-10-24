"""Registrar Cobranzas por Forma de Cobro: columnas nuevas (forma_cobro.tipo, cobro_det.numero_referencia), cobros parcial,
combinado (efectivo + tarjeta + cheque diferido + transferencia) y por saldo, validaciones, tarjeta con entidades inactivas,
triggers (trg_aplicar_cobro, trg_validar_cobro, trg_permisos_resolver_menu), funciones (fn_total_recaudado,
fn_total_efectivo_apertura, fn_siguiente_numero_recibo), vistas (v_resumen_caja, v_estado_cuenta_cliente), anulación (caja
abierta/cerrada), cierre de caja con recaudado real, conexiones (Forma de Cobro, Marca, Adherida, Emisora, Venta, Apertura),
concurrencia, recibo en PDF y permisos.

Usa como CAJERO al Administrador real (así no depende de la caja que tenga abierta el Cajero real) y datos ZZ (caja, cliente,
timbrado inactivo, formas de cobro, entidades, ventas y cobros) que borra POR ID. Las ventas de prueba se insertan por SQL contra
un timbrado ZZ INACTIVO: no consume números del timbrado real. Aborta si el Administrador tiene una caja abierta de verdad."""
import sys, pathlib, re, threading, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from datetime import date, timedelta
import psycopg2
from app import app
from app.conexion.Conexion import Conexion
from app.dao.modulo_facturacion.cobro.CobroDao import CobroDao, CUENTA_NO_PENDIENTE, YA_ANULADO
from app.dao.modulo_facturacion.apertura_caja.AperturaCajaDao import AperturaCajaDao
from app.dao.modulo_facturacion.marca_tarjeta.MarcaTarjetaDao import MarcaTarjetaDao
from app.dao.modulo_facturacion.entidad_adherida.EntidadAdheridaDao import EntidadAdheridaDao
from app.dao.modulo_facturacion.entidad_emisora.EntidadEmisoraDao import EntidadEmisoraDao
from tests.facturacion._limpieza import borrar_auditoria
from tests.facturacion._pdf import paginas_pdf, texto_pdf

c = app.test_client()
fallos = []
COB, VEN, APE, FORMAS = '/api/v1/cobros', '/api/v1/ventas', '/api/v1/aperturas-caja', '/api/v1/formas-cobro'
HOY = date.today()


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
cu.execute("SELECT count(*) FROM apertura_cierre_caja WHERE estado='ABIERTA' AND id_usuario = %s", (ADMIN[0],))
if cu.fetchone()[0]:
    print('ABORTADO: el Administrador tiene una caja ABIERTA real; ciérrela antes de correr este test.'); sys.exit(1)


def como(u):
    with c.session_transaction() as s:
        s['id_usuario'] = u[0]; s['id_rol'] = u[1]; s['nombre_rol'] = u[2]


ids = {'caja': None, 'tim': None, 'cliente': None, 'ap': [], 'formas': [], 'marcas': [], 'emisoras': [], 'adheridas': [],
       'ventas': [], 'cuentas': []}
cobros = set()
ledger = {}          # id_cobro -> [(monto, tipo)]  (solo lo EMITIDO; lo anulado se quita)
numeros = []
stamp = str(int(time.time()))[-8:]
seq = [0]


def sql_en_txn(sql, params=(), inmediato=False, despues=None):
    """Corre SQL en una transacción propia que SIEMPRE se deshace. Devuelve el mensaje de error de la base o None."""
    k = Conexion().getConexion(); kc = k.cursor()
    try:
        if isinstance(sql, str):
            sql = [(sql, params)]
        for s, p in sql:
            kc.execute(s, p)
        if inmediato:
            kc.execute("SET CONSTRAINTS ALL IMMEDIATE")
        if despues:
            kc.execute(despues[0], despues[1]); return kc.fetchone()
        return None
    except psycopg2.Error as e:
        return getattr(getattr(e, 'diag', None), 'message_primary', None) or str(e).splitlines()[0]
    finally:
        k.rollback(); kc.close(); k.close()


def saldo(cuenta):
    cu.execute("SELECT saldo, estado FROM cuenta_cobrar WHERE id_cuenta=%s", (cuenta,)); f = cu.fetchone(); return int(f[0]), f[1]


def nueva_cuenta(total, apertura=None, cliente=None):
    """Venta ZZ por SQL (timbrado ZZ inactivo); el trigger trg_generar_cuenta_cobrar crea la cuenta (CRÉDITO, +30 días)."""
    seq[0] += 1
    cu.execute("""INSERT INTO venta_cab(id_apertura, id_cliente, id_usuario, id_timbrado, numero_factura, tipo_venta, condicion,
                    total_exenta, total_gravada_5, total_gravada_10, iva_5, iva_10, total)
                  VALUES (%s, %s, %s, %s, %s, 'ITEMS', 'CREDITO', 0, 0, %s, 0, %s, %s) RETURNING id_venta""",
               (apertura or ids['ap'][0], cliente or ids['cliente'], ADMIN[0], ids['tim'], f'ZZC{stamp}{seq[0]:03d}', total, round(total / 11), total))
    v = cu.fetchone()[0]; ids['ventas'].append(v)
    cu.execute("SELECT id_cuenta FROM cuenta_cobrar WHERE id_venta=%s", (v,)); cta = cu.fetchone()[0]; ids['cuentas'].append(cta)
    return v, cta


def ef(monto): return {'id_forma_cobro': F['EF'], 'monto': monto}
def tr(monto, ref='TRF-0001'): return {'id_forma_cobro': F['TR'], 'monto': monto, 'numero_referencia': ref}
def tj(monto, forma='TC', adh=None, digitos='1234', aut='AUT123', tipo=None):
    t = {'id_entidad_adherida': adh or A['OK'], 'ultimos_digitos': digitos, 'numero_autorizacion': aut}
    if tipo:
        t['tipo_tarjeta'] = tipo
    return {'id_forma_cobro': F[forma], 'monto': monto, 'tarjeta': t}
def ch(monto, emisora=None, numero='CH001', titular='juan perez', emision=None, cobro=None):
    return {'id_forma_cobro': F['CH'], 'monto': monto,
            'cheque': {'id_entidad_emisora': emisora or E['OK'], 'numero_cheque': numero, 'titular': titular,
                       'fecha_emision': (emision or HOY).isoformat(), 'fecha_cobro': (cobro or HOY).isoformat()}}


def cobrar(cuenta, formas, esperado=201, obs=None, usuario=None, **kw):
    como(usuario or ADMIN)
    cuerpo = {'id_cuenta': cuenta, 'formas': formas}
    if obs is not None:
        cuerpo['observacion'] = obs
    d = api('post', COB, esperado, cuerpo, **kw)
    if esperado == 201:
        idc = d['data']['id_cobro']; cobros.add(idc); numeros.append(d['data']['numero_recibo'])
        ledger[idc] = [(x['monto'], x['tipo']) for x in d['data']['detalle']]
    return d


def anular(idc, esperado=200, **kw):
    como(ADMIN)
    d = api('delete', f'{COB}/{idc}', esperado, **kw)
    if esperado == 200:
        ledger.pop(idc, None)
    return d


try:
    # =====================================================================================================================
    # DATOS DE PRUEBA
    # =====================================================================================================================
    cu.execute("SELECT codigo FROM consultorio ORDER BY codigo LIMIT 1"); COD = cu.fetchone()[0]
    cu.execute("INSERT INTO caja(id_consultorio, descripcion) VALUES (%s, 'ZZ CAJA COBRO') RETURNING id_caja", (COD,)); ids['caja'] = cu.fetchone()[0]
    cu.execute("INSERT INTO timbrado(numero_timbrado, fecha_inicio, fecha_fin, establecimiento, punto_expedicion, numero_desde, numero_hasta, activo) "
               "VALUES ('ZZ000009', %s, %s, '997', '997', 1, 10, false) RETURNING id_timbrado", (HOY - timedelta(days=30), HOY + timedelta(days=30))); ids['tim'] = cu.fetchone()[0]
    cu.execute("INSERT INTO cliente(nombre, apellido, ci_ruc) VALUES ('ZZ CLIENTE', 'COBRO', %s) RETURNING id_cliente", ('ZZK' + stamp,)); ids['cliente'] = cu.fetchone()[0]
    F, M, E, A = {}, {}, {}, {}
    def forma(clave, desc, tipo):
        cu.execute("INSERT INTO forma_cobro(descripcion, tipo) VALUES (%s, %s) RETURNING id_forma_cobro", (desc, tipo)); F[clave] = cu.fetchone()[0]; ids['formas'].append(F[clave])
    forma('EF', 'ZZ EFECTIVO', 'EFECTIVO'); forma('TC', 'ZZ TARJETA DE CRÉDITO', 'TARJETA'); forma('TD', 'ZZ TARJETA DE DÉBITO', 'TARJETA')
    forma('TG', 'ZZ TARJETA GENERICA', 'TARJETA'); forma('CH', 'ZZ CHEQUE', 'CHEQUE'); forma('TR', 'ZZ TRANSFERENCIA', 'TRANSFERENCIA')
    cu.execute("INSERT INTO forma_cobro(descripcion, tipo, activo) VALUES ('ZZ FORMA INACTIVA', 'EFECTIVO', false) RETURNING id_forma_cobro"); F['IN'] = cu.fetchone()[0]; ids['formas'].append(F['IN'])
    cu.execute("SELECT is_nullable FROM information_schema.columns WHERE table_name='forma_cobro' AND column_name='tipo'"); TIPO_NULLABLE = cu.fetchone()[0] == 'YES'
    if TIPO_NULLABLE:
        cu.execute("INSERT INTO forma_cobro(descripcion) VALUES ('ZZ SIN TIPO') RETURNING id_forma_cobro"); F['ST'] = cu.fetchone()[0]; ids['formas'].append(F['ST'])
    for clave, desc, act in (('OK', 'ZZ MARCA', True), ('IN', 'ZZ MARCA INACTIVA', False)):
        cu.execute("INSERT INTO marca_tarjeta(descripcion, activo) VALUES (%s, %s) RETURNING id_marca_tarjeta", (desc, act)); M[clave] = cu.fetchone()[0]; ids['marcas'].append(M[clave])
    for clave, desc, act in (('OK', 'ZZ BANCO', True), ('IN', 'ZZ BANCO INACTIVO', False)):
        cu.execute("INSERT INTO entidad_emisora(descripcion, direccion, telefono, correo, activo) VALUES (%s, 'ZZ', '0981000000', 'zz@zz.com', %s) RETURNING id_entidad_emisora", (desc, act)); E[clave] = cu.fetchone()[0]; ids['emisoras'].append(E[clave])
    for clave, desc, em, ma, act in (('OK', 'ZZ ADHERIDA', 'OK', 'OK', True), ('IN', 'ZZ ADHERIDA INACTIVA', 'OK', 'OK', False),
                                      ('MI', 'ZZ ADHERIDA MARCA INACTIVA', 'OK', 'IN', True), ('EI', 'ZZ ADHERIDA EMISORA INACTIVA', 'IN', 'OK', True)):
        cu.execute("INSERT INTO entidad_adherida(id_entidad_emisora, id_marca_tarjeta, descripcion, direccion, telefono, correo, activo) "
                   "VALUES (%s, %s, %s, 'ZZ', '0981000000', 'zz@zz.com', %s) RETURNING id_entidad_adherida", (E[em], M[ma], desc, act)); A[clave] = cu.fetchone()[0]; ids['adheridas'].append(A[clave])
    # apertura (CERRADA) de apoyo para los datos viejos y la apertura real de la prueba (la abre el Administrador)
    # ---------------------------------------------------------------------------------------------------------------------

    # =====================================================================================================================
    # 1. ESQUEMA, COLUMNAS NUEVAS Y OBJETOS DE BASE DE DATOS
    # =====================================================================================================================
    cu.execute("SELECT data_type, character_maximum_length, is_nullable FROM information_schema.columns WHERE table_name='cobro_det' AND column_name='numero_referencia'")
    chk('cobro_det.numero_referencia VARCHAR(30) NULL', cu.fetchone() == ('character varying', 30, 'YES'))
    cu.execute("SELECT data_type, character_maximum_length FROM information_schema.columns WHERE table_name='forma_cobro' AND column_name='tipo'")
    chk('forma_cobro.tipo VARCHAR(15)', cu.fetchone() == ('character varying', 15))
    cu.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='ck_forma_cobro_tipo'")
    d = cu.fetchone()[0]; chk('forma_cobro.tipo: CHECK EFECTIVO / TARJETA / CHEQUE / TRANSFERENCIA', all(x in d for x in ('EFECTIVO', 'TARJETA', 'CHEQUE', 'TRANSFERENCIA')))
    cu.execute("SELECT count(*) FROM forma_cobro WHERE descripcion IN ('EFECTIVO','TARJETA DE CRÉDITO','TARJETA DE DÉBITO','CHEQUE') AND tipo IS NULL")
    chk('las formas de cobro reales reconocibles quedaron con su tipo', cu.fetchone()[0] == 0)
    try:
        cu.execute("INSERT INTO forma_cobro(descripcion, tipo) VALUES ('ZZ TIPO MALO', 'OTRO')"); ok = False
        cu.execute("DELETE FROM forma_cobro WHERE descripcion='ZZ TIPO MALO'")
    except psycopg2.errors.CheckViolation:
        ok = True
    chk('forma_cobro.tipo: un valor fuera de los 4 se rechaza', ok)
    for tabla, cols in (('cobro_cab', ['id_cobro', 'id_cuenta', 'id_apertura', 'id_usuario', 'numero_recibo', 'fecha', 'total', 'observacion', 'estado']),
                        ('cobro_det', ['id_cobro_det', 'id_cobro', 'id_forma_cobro', 'monto', 'numero_referencia']),
                        ('cobro_tarjeta', ['id_cobro_tarjeta', 'id_cobro_det', 'id_entidad_adherida', 'tipo_tarjeta', 'ultimos_digitos', 'numero_autorizacion']),
                        ('cobro_cheque', ['id_cobro_cheque', 'id_cobro_det', 'id_entidad_emisora', 'numero_cheque', 'titular', 'fecha_emision', 'fecha_cobro'])):
        cu.execute("SELECT array_agg(column_name::text ORDER BY ordinal_position) FROM information_schema.columns WHERE table_name=%s", (tabla,))
        chk(f'{tabla}: columnas tal cual las creó el DER (+ las nuevas)', cu.fetchone()[0] == cols)
    cu.execute("SELECT tgname, tgdeferrable FROM pg_trigger WHERE NOT tgisinternal AND tgname IN ('trg_aplicar_cobro','trg_validar_cobro','trg_permisos_resolver_menu')")
    tg = dict(cu.fetchall()); chk('triggers: trg_aplicar_cobro, trg_validar_cobro (diferido) y trg_permisos_resolver_menu', set(tg) == {'trg_aplicar_cobro', 'trg_validar_cobro', 'trg_permisos_resolver_menu'} and tg['trg_validar_cobro'])
    cu.execute("SELECT count(*) FROM pg_proc WHERE proname IN ('fn_total_recaudado','fn_total_efectivo_apertura','fn_siguiente_numero_recibo','fn_aplicar_cobro','fn_validar_cobro','fn_formato_gs') AND obj_description(oid,'pg_proc') IS NOT NULL")
    chk('las 6 funciones tienen COMMENT ON', cu.fetchone()[0] == 6)
    cu.execute("SELECT count(*) FROM pg_trigger t JOIN pg_description d ON d.objoid = t.oid WHERE t.tgname IN ('trg_aplicar_cobro','trg_validar_cobro')")
    chk('los 2 triggers de cobro tienen COMMENT ON', cu.fetchone()[0] == 2)
    cu.execute("SELECT count(*) FROM pg_description d WHERE d.objoid IN ('v_resumen_caja'::regclass, 'v_estado_cuenta_cliente'::regclass) AND d.objsubid = 0")
    chk('las 2 vistas tienen COMMENT ON', cu.fetchone()[0] == 2)
    cu.execute("SELECT string_agg(column_name, ',' ORDER BY ordinal_position) FROM information_schema.columns WHERE table_name='v_estado_cuenta_cliente'")
    chk('v_estado_cuenta_cliente: conserva las 12 columnas y suma total_cobrado, cantidad_cobros y fecha_ultimo_cobro al final',
        cu.fetchone()[0] == 'id_cliente,cliente,ci_ruc,id_venta,numero_factura,fecha,condicion,total,saldo,estado_cuenta,fecha_vencimiento,saldo_total_cliente,total_cobrado,cantidad_cobros,fecha_ultimo_cobro')
    cu.execute("SELECT fn_formato_gs(1234567), fn_formato_gs(0), fn_formato_gs(999)")
    chk('fn_formato_gs: puntos de miles', cu.fetchone() == ('1.234.567', '0', '999'))
    # trg_permisos_resolver_menu: un INSERT sin id_menu lo resuelve por menu.clave = ventana; sin entrada de menú, rechaza
    cu.execute("SELECT id_menu FROM menu WHERE clave='cobro' AND activo")
    ID_MENU_COBRO = cu.fetchone()
    chk('menu: existe la entrada "cobro" para la ventana nueva', ID_MENU_COBRO is not None)
    msg = sql_en_txn("INSERT INTO permisos(id_rol, ventana, accion) VALUES (%s, 'zz_ventana_inexistente', 'ver')", (RECEP[1],))
    chk('permisos: sin entrada de menú, el INSERT se rechaza con un mensaje claro', msg is not None and 'No existe una entrada de menú activa con la clave "zz_ventana_inexistente"' in msg)
    r = sql_en_txn("INSERT INTO permisos(id_rol, ventana, accion) VALUES (%s, 'cobro', 'estado') RETURNING id_menu", (RECEP[1],), despues=("SELECT id_menu FROM permisos WHERE id_rol=%s AND ventana='cobro' AND accion='estado'", (RECEP[1],)))
    chk('permisos: un INSERT sin id_menu lo completa desde menu.clave', isinstance(r, tuple) and r[0] == ID_MENU_COBRO[0])

    # =====================================================================================================================
    # 2. FORMA DE COBRO: tipo (API)
    # =====================================================================================================================
    como(ADMIN)
    api('post', FORMAS, 400, {'descripcion': 'ZZ API FORMA'}, nombre='forma de cobro sin tipo', exacto='El tipo debe ser Efectivo, Tarjeta, Cheque o Transferencia.', campo='tipo')
    api('post', FORMAS, 400, {'descripcion': 'ZZ API FORMA', 'tipo': 'OTRO'}, nombre='forma de cobro con tipo inválido', campo='tipo')
    d = api('post', FORMAS, 201, {'descripcion': 'zz api forma', 'tipo': 'cheque'}, nombre='forma de cobro con tipo (normaliza mayúsculas)')
    F['API'] = d['data']['id_forma_cobro']; ids['formas'].append(F['API'])
    chk('la API devuelve el tipo en mayúsculas', d['data']['tipo'] == 'CHEQUE')
    r = c.get(f'{FORMAS}?inactivos=1').get_json()['data']
    chk('el listado trae el tipo de cada forma', any(x['id_forma_cobro'] == F['API'] and x['tipo'] == 'CHEQUE' for x in r))
    d = api('put', f'{FORMAS}/{F["API"]}', 200, {'descripcion': 'ZZ API FORMA', 'tipo': 'TRANSFERENCIA'}, nombre='cambiar el tipo (sin cobros)')
    cu.execute("SELECT tipo FROM forma_cobro WHERE id_forma_cobro=%s", (F['API'],)); chk('el tipo cambió', cu.fetchone()[0] == 'TRANSFERENCIA')
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='forma_cobro' AND id_registro=%s AND accion='MODIFICACION'", (F['API'],))
    chk('auditoría MODIFICACION: "Tipo: CHEQUE -> TRANSFERENCIA"', 'Tipo: CHEQUE -> TRANSFERENCIA' in cu.fetchone()[0])
    api('put', f'{FORMAS}/{F["API"]}', 400, {'descripcion': 'ZZ API FORMA'}, nombre='editar sin tipo', campo='tipo')

    # =====================================================================================================================
    # 3. PERMISOS Y SIN CAJA
    # =====================================================================================================================
    como(RECEP)
    api('get', COB, 403, nombre='Recepción sin permiso: listado'); api('post', COB, 403, {}, nombre='Recepción sin permiso: alta')
    api('delete', f'{COB}/1', 403, nombre='Recepción sin permiso: anular'); api('get', f'{COB}/formas', 403, nombre='Recepción: formas de cobro')
    api('get', f'{COB}/cuentas?q=zz', 403, nombre='Recepción: buscador de cuentas')
    chk('vista: Recepción 403', c.get('/referenciales/cobro/cobro-index').status_code == 403)
    como(CAJERO)
    api('get', COB, 200, nombre='Cajero: listado'); chk('vista: Cajero 200', c.get('/referenciales/cobro/cobro-index').status_code == 200)
    api('post', COB, 400, {'formas': []}, nombre='Cajero: el alta valida antes de tocar nada', exacto='Debe seleccionar una cuenta a cobrar.', campo='id_cuenta')

    ap_v = None
    cu.execute("INSERT INTO apertura_cierre_caja(id_caja, id_usuario, monto_apertura, estado, fecha_cierre) VALUES (%s, %s, 0, 'CERRADA', now()) RETURNING id_apertura", (ids['caja'], ADMIN[0]))
    ap_v = cu.fetchone()[0]; ids['ap'].append(ap_v)
    v0, cta0 = nueva_cuenta(100000, apertura=ap_v)
    cobrar(cta0, [ef(1000)], 409, nombre='cobro SIN caja abierta', exacto='Debe abrir la caja antes de registrar un cobro.')
    chk('sin caja: la cuenta no se tocó', saldo(cta0) == (100000, 'PENDIENTE'))
    with app.app_context():
        AP1 = AperturaCajaDao().abrirCaja(ADMIN[0], ids['caja'], 100000)
    ids['ap'].append(AP1); chk('apertura de caja ZZ abierta (Administrador)', isinstance(AP1, int))
    api('get', f'{COB}/caja-actual', 200, nombre='caja-actual')

    # =====================================================================================================================
    # 4. VALIDACIONES
    # =====================================================================================================================
    v1, C1 = nueva_cuenta(1000000)
    como(ADMIN)
    def val(cuerpo, msg, camp, nombre, code=400):
        api('post', COB, code, cuerpo, nombre=f'validación: {nombre}', exacto=msg, campo=camp)
    base = {'id_cuenta': C1}
    val({'formas': [ef(1000)]}, 'Debe seleccionar una cuenta a cobrar.', 'id_cuenta', 'sin cuenta')
    val({**base, 'formas': []}, 'Debe agregar al menos una forma de cobro.', 'formas', 'sin formas')
    val({**base, 'formas': 'x'}, 'Debe agregar al menos una forma de cobro.', 'formas', 'formas no es lista')
    val({**base, 'formas': [ef(0)]}, 'Forma 1: El monto debe ser un número entero mayor a 0.', 'formas', 'monto 0')
    val({**base, 'formas': [ef(-5)]}, 'Forma 1: El monto debe ser un número entero mayor a 0.', 'formas', 'monto negativo')
    val({**base, 'formas': [ef('abc')]}, 'Forma 1: El monto debe ser un número entero mayor a 0.', 'formas', 'monto texto')
    val({**base, 'formas': [ef('1.5')]}, 'Forma 1: El monto debe ser un número entero mayor a 0.', 'formas', 'monto decimal')
    val({**base, 'formas': [{'monto': 10}]}, 'Forma 1: debe seleccionar la forma de cobro.', 'formas', 'sin forma de cobro')
    val({**base, 'formas': [{'id_forma_cobro': 2147483000, 'monto': 10}]}, 'Forma 1: la forma de cobro no existe o está inactiva.', 'formas', 'forma inexistente')
    val({**base, 'formas': [{'id_forma_cobro': F['IN'], 'monto': 10}]}, 'Forma 1: la forma de cobro no existe o está inactiva.', 'formas', 'forma inactiva')
    if TIPO_NULLABLE:
        val({**base, 'formas': [{'id_forma_cobro': F['ST'], 'monto': 10}]}, 'Forma 1: la forma de cobro ZZ SIN TIPO no tiene tipo asignado.', 'formas', 'forma sin tipo')
    val({**base, 'observacion': 'a' * 201, 'formas': [ef(10)]}, 'La observación no puede superar los 200 caracteres.', 'observacion', 'observación larga')
    val({**base, 'formas': [ef(10), tr(10, '')]}, 'Forma 2: El campo número de referencia es obligatorio y no puede estar vacío.', 'formas', 'transferencia sin referencia (fila 2)')
    val({**base, 'formas': [tr(10, 'con%raro')]}, 'Forma 1: El campo número de referencia solo puede contener letras, números, espacios y los símbolos . _ / -', 'formas', 'referencia con símbolos raros')
    val({**base, 'formas': [{'id_forma_cobro': F['TC'], 'monto': 10}]}, 'Forma 1: debe seleccionar la entidad adherida.', 'formas', 'tarjeta sin datos')
    val({**base, 'formas': [tj(10, digitos='12')]}, 'Forma 1: Los últimos dígitos de la tarjeta deben ser 4 números.', 'formas', 'últimos dígitos inválidos')
    val({**base, 'formas': [tj(10, aut='')]}, 'Forma 1: El campo número de autorización es obligatorio y no puede estar vacío.', 'formas', 'autorización vacía')
    val({**base, 'formas': [tj(10, forma='TD', tipo='CREDITO')]}, 'Forma 1: el tipo de tarjeta no coincide con la forma de cobro seleccionada.', 'formas', 'tarjeta débito marcada como crédito')
    val({**base, 'formas': [tj(10, forma='TG', tipo='OTRO')]}, 'Forma 1: el tipo de tarjeta debe ser Crédito o Débito.', 'formas', 'tipo de tarjeta inválido')
    val({**base, 'formas': [{'id_forma_cobro': F['CH'], 'monto': 10}]}, 'Forma 1: debe seleccionar la entidad emisora del cheque.', 'formas', 'cheque sin datos')
    val({**base, 'formas': [ch(10, numero='')]}, 'Forma 1: El campo número de cheque es obligatorio y no puede estar vacío.', 'formas', 'cheque sin número')
    val({**base, 'formas': [ch(10, titular='')]}, 'Forma 1: El campo titular es obligatorio y no puede estar vacío.', 'formas', 'cheque sin titular')
    val({**base, 'formas': [ch(10, emision=HOY + timedelta(days=1), cobro=HOY + timedelta(days=5))]}, 'Forma 1: la fecha de emisión del cheque no puede ser posterior a hoy.', 'formas', 'cheque con emisión FUTURA')
    val({**base, 'formas': [ch(10, emision=HOY, cobro=HOY - timedelta(days=1))]}, 'Forma 1: la fecha de cobro no puede ser anterior a la de emisión.', 'formas', 'cheque con cobro anterior a la emisión')
    cuerpo = ch(10); cuerpo['cheque']['fecha_cobro'] = 'mañana'
    val({**base, 'formas': [cuerpo]}, 'Forma 1: La fecha de cobro no es válida (use AAAA-MM-DD).', 'formas', 'fecha de cobro inválida')
    cuerpo = ch(10, emisora=2147483000)
    val({**base, 'formas': [cuerpo]}, 'Forma 1: la entidad emisora del cheque no existe o está inactiva.', 'formas', 'cheque con emisora inexistente', 409)
    val({**base, 'formas': [ch(10, emisora=E['IN'])]}, 'Forma 1: la entidad emisora del cheque no existe o está inactiva.', 'formas', 'cheque con emisora INACTIVA', 409)
    val({**base, 'formas': [tj(10, adh=A['IN'])]}, 'Forma 1: la entidad adherida no existe o está inactiva.', 'formas', 'tarjeta con adherida INACTIVA', 409)
    val({**base, 'formas': [tj(10, adh=A['MI'])]}, 'Forma 1: la marca de la tarjeta no existe o está inactiva.', 'formas', 'tarjeta con marca INACTIVA', 409)
    val({**base, 'formas': [tj(10, adh=A['EI'])]}, 'Forma 1: la entidad emisora no existe o está inactiva.', 'formas', 'tarjeta con emisora INACTIVA', 409)
    val({**base, 'formas': [tj(10, adh=2147483000)]}, 'Forma 1: la entidad adherida no existe o está inactiva.', 'formas', 'tarjeta con adherida inexistente', 409)
    val({'id_cuenta': 2147483000, 'formas': [ef(10)]}, 'No se encontró la cuenta a cobrar.', 'id_cuenta', 'cuenta inexistente', 404)
    chk('validaciones: ningún cobro se creó y el saldo de C1 no cambió', saldo(C1) == (1000000, 'PENDIENTE')
        and (cu.execute("SELECT count(*) FROM cobro_cab WHERE id_cuenta=%s", (C1,)) or cu.fetchone()[0]) == 0)

    # =====================================================================================================================
    # 5. COBRO PARCIAL, COMBINADO Y POR SALDO
    # =====================================================================================================================
    como(ADMIN)
    d = cobrar(C1, [ef(400000)], nombre='cobro PARCIAL en efectivo (400.000 de 1.000.000)', obs='  primera   cuota ')
    P1 = d['data']; ID1 = P1['id_cobro']
    chk("el recibo tiene formato REC-0000001 (7 dígitos)", re.fullmatch(r'REC-\d{7}', P1['numero_recibo']) is not None)
    chk('cabecera: EMITIDO, total 400.000, cajero y apertura de la SESIÓN, observación normalizada', (P1['estado'], P1['total'], P1['id_usuario'], P1['id_apertura'], P1['observacion']) == ('EMITIDO', 400000, ADMIN[0], AP1, 'primera cuota'))
    chk('trigger: el saldo bajó a 600.000 y la cuenta sigue PENDIENTE', saldo(C1) == (600000, 'PENDIENTE'))
    chk('el cliente sale de la cuenta (no del cobro): el cobro lo informa', P1['cliente'] == 'ZZ CLIENTE COBRO' and P1['numero_factura'].startswith('ZZC'))
    cuerpo = {'id_cuenta': C1, 'formas': [ef(1000)], 'total': 999999, 'id_usuario': CAJERO[0], 'id_apertura': 1, 'id_cliente': 1, 'estado': 'ANULADO', 'numero_recibo': 'REC-9999999'}
    d = api('post', COB, 201, cuerpo, nombre='cobro con datos falsificados por el navegador')
    cobros.add(d['data']['id_cobro']); numeros.append(d['data']['numero_recibo']); ledger[d['data']['id_cobro']] = [(1000, 'EFECTIVO')]
    chk('se ignoran total, usuario, apertura, cliente, estado y recibo enviados', (d['data']['total'], d['data']['id_usuario'], d['data']['id_apertura'], d['data']['estado'], d['data']['numero_recibo']) == (1000, ADMIN[0], AP1, 'EMITIDO', numeros[-1]) and d['data']['numero_recibo'] != 'REC-9999999')
    chk('recibos consecutivos y sin huecos', int(numeros[1][4:]) == int(numeros[0][4:]) + 1)
    IDF = d['data']['id_cobro']
    anular(IDF, nombre='anular el cobro de prueba de 1.000')
    chk('...y el saldo vuelve a 600.000', saldo(C1) == (600000, 'PENDIENTE'))

    # combinado: efectivo + tarjeta de crédito + cheque DIFERIDO + transferencia = 500.000
    d = cobrar(C1, [ef(100000), tj(200000, 'TC'), ch(150000, cobro=HOY + timedelta(days=30)), tr(50000)], nombre='cobro COMBINADO (efectivo + tarjeta + cheque diferido + transferencia)')
    P2 = d['data']; ID2 = P2['id_cobro']
    chk('combinado: total 500.000 y 4 formas', P2['total'] == 500000 and len(P2['detalle']) == 4)
    dd = {x['tipo']: x for x in P2['detalle']}
    chk('combinado: tarjeta con tipo CREDITO (deducido de la forma), últimos 4, autorización y la entidad/marca/emisora de la adherida',
        dd['TARJETA']['tarjeta']['tipo_tarjeta'] == 'CREDITO' and dd['TARJETA']['tarjeta']['ultimos_digitos'] == '1234' and dd['TARJETA']['tarjeta']['numero_autorizacion'] == 'AUT123'
        and (dd['TARJETA']['tarjeta']['entidad_adherida'], dd['TARJETA']['tarjeta']['marca'], dd['TARJETA']['tarjeta']['emisora']) == ('ZZ ADHERIDA', 'ZZ MARCA', 'ZZ BANCO'))
    chk('combinado: cheque diferido (cobro a 30 días) con titular en MAYÚSCULAS', dd['CHEQUE']['cheque']['fecha_cobro'] == (HOY + timedelta(days=30)).isoformat() and dd['CHEQUE']['cheque']['titular'] == 'JUAN PEREZ' and dd['CHEQUE']['cheque']['numero_cheque'] == 'CH001')
    chk('combinado: transferencia con su referencia; las demás sin referencia', dd['TRANSFERENCIA']['numero_referencia'] == 'TRF-0001' and dd['EFECTIVO']['numero_referencia'] is None)
    chk('trigger: saldo 100.000 (1.000.000 - 400.000 - 500.000)', saldo(C1) == (100000, 'PENDIENTE'))
    cu.execute("SELECT count(*) FROM cobro_tarjeta t JOIN cobro_det d USING(id_cobro_det) WHERE d.id_cobro=%s", (ID2,)); n_t = cu.fetchone()[0]
    cu.execute("SELECT count(*) FROM cobro_cheque t JOIN cobro_det d USING(id_cobro_det) WHERE d.id_cobro=%s", (ID2,)); n_c = cu.fetchone()[0]
    chk('una fila de tarjeta y una de cheque, solo para esas formas', (n_t, n_c) == (1, 1))

    d = cobrar(C1, [ef(100000)], nombre='pago FINAL por el saldo (100.000)'); ID3 = d['data']['id_cobro']
    chk('trigger: saldo 0 y la cuenta pasa a PAGADA', saldo(C1) == (0, 'PAGADA'))
    cobrar(C1, [ef(1)], 409, nombre='cobrar una cuenta PAGADA', exacto='La cuenta a cobrar ya está pagada.', campo='id_cuenta')
    anular(ID3, nombre='anular el pago final')
    chk('anular repone el saldo y la cuenta vuelve de PAGADA a PENDIENTE', saldo(C1) == (100000, 'PENDIENTE'))
    d = cobrar(C1, [ef(100000)], nombre='volver a cobrar el saldo'); ID3b = d['data']['id_cobro']
    chk('la cuenta vuelve a PAGADA', saldo(C1) == (0, 'PAGADA'))
    chk('el recibo anulado NO se reutiliza (el nuevo es mayor)', int(numeros[-1][4:]) > int(numeros[-2][4:]))

    # saldo excedido
    v2, C2 = nueva_cuenta(300000)
    cobrar(C2, [ef(300001)], 409, nombre='monto mayor al saldo', exacto='El monto supera el saldo pendiente de Gs. 300.000.', campo='formas')
    cobrar(C2, [ef(200000), tj(100001)], 409, nombre='varias formas que suman más que el saldo', exacto='El monto supera el saldo pendiente de Gs. 300.000.')
    chk('saldo excedido: nada cambió', saldo(C2) == (300000, 'PENDIENTE'))
    d = cobrar(C2, [ef(100000)], nombre='cobro parcial de C2'); ID4 = d['data']['id_cobro']
    cobrar(C2, [ef(200001)], 409, nombre='excedido sobre el saldo restante', exacto='El monto supera el saldo pendiente de Gs. 200.000.')
    d = cobrar(C2, [ef(50000)], nombre='otro cobro de C2'); ID5 = d['data']['id_cobro']
    chk('C2: saldo 150.000', saldo(C2) == (150000, 'PENDIENTE'))

    # =====================================================================================================================
    # 6. TRIGGERS EN LA BASE (directos, siempre en transacciones que se deshacen)
    # =====================================================================================================================
    cab = ("INSERT INTO cobro_cab(id_cuenta, id_apertura, id_usuario, numero_recibo, total) VALUES (%s, %s, %s, %s, %s) RETURNING id_cobro")
    chk('trg_aplicar_cobro: rechaza un total mayor al saldo', sql_en_txn(cab, (C2, AP1, ADMIN[0], 'ZZR-1', 150001)) == 'El monto supera el saldo pendiente de Gs. 150.000.')
    chk('trg_aplicar_cobro: rechaza una cuenta que no está pendiente', sql_en_txn(cab, (C1, AP1, ADMIN[0], 'ZZR-2', 10)) == 'La cuenta a cobrar no está pendiente (estado: PAGADA).')
    r = sql_en_txn([(cab, (C2, AP1, ADMIN[0], 'ZZR-3', 150000))], despues=("SELECT saldo, estado FROM cuenta_cobrar WHERE id_cuenta=%s", (C2,)))
    chk('trg_aplicar_cobro: un cobro por todo el saldo deja saldo 0 y PAGADA (dentro de la transacción)', r == (0, 'PAGADA'))
    r = sql_en_txn([(cab, (C2, AP1, ADMIN[0], 'ZZR-4', 10)), ("UPDATE cobro_cab SET estado='ANULADO' WHERE numero_recibo='ZZR-4'", ())], despues=("SELECT saldo, estado FROM cuenta_cobrar WHERE id_cuenta=%s", (C2,)))
    chk('trg_aplicar_cobro: anular por SQL repone el saldo (150.000) y deja PENDIENTE', r == (150000, 'PENDIENTE'))
    chk('trg_aplicar_cobro: un cobro anulado no se puede reactivar',
        sql_en_txn([(cab, (C2, AP1, ADMIN[0], 'ZZR-5', 10)), ("UPDATE cobro_cab SET estado='ANULADO' WHERE numero_recibo='ZZR-5'", ()),
                    ("UPDATE cobro_cab SET estado='EMITIDO' WHERE numero_recibo='ZZR-5'", ())]) == 'Un cobro anulado no se puede reactivar.')
    chk('trg_validar_cobro (diferido): un cobro sin formas no cierra la suma',
        sql_en_txn(cab, (C2, AP1, ADMIN[0], 'ZZR-6', 5000), inmediato=True) == 'La suma de las formas de cobro (Gs. 0) no coincide con el total del cobro (Gs. 5.000).')
    det = "INSERT INTO cobro_det(id_cobro, id_forma_cobro, monto, numero_referencia) VALUES ((SELECT id_cobro FROM cobro_cab WHERE numero_recibo=%s), %s, %s, %s)"
    chk('trg_validar_cobro: la suma de las formas debe ser el total',
        sql_en_txn([(cab, (C2, AP1, ADMIN[0], 'ZZR-7', 5000)), (det, ('ZZR-7', F['EF'], 4000, None))], inmediato=True) == 'La suma de las formas de cobro (Gs. 4.000) no coincide con el total del cobro (Gs. 5.000).')
    chk('trg_validar_cobro: una tarjeta sin su fila de cobro_tarjeta se rechaza',
        sql_en_txn([(cab, (C2, AP1, ADMIN[0], 'ZZR-8', 5000)), (det, ('ZZR-8', F['TC'], 5000, None))], inmediato=True) == 'Faltan o sobran datos en la forma de cobro: ZZ TARJETA DE CRÉDITO (TARJETA).')
    chk('trg_validar_cobro: un cheque sin su fila de cobro_cheque se rechaza',
        sql_en_txn([(cab, (C2, AP1, ADMIN[0], 'ZZR-9', 5000)), (det, ('ZZR-9', F['CH'], 5000, None))], inmediato=True) == 'Faltan o sobran datos en la forma de cobro: ZZ CHEQUE (CHEQUE).')
    chk('trg_validar_cobro: una transferencia sin referencia se rechaza',
        sql_en_txn([(cab, (C2, AP1, ADMIN[0], 'ZZR-10', 5000)), (det, ('ZZR-10', F['TR'], 5000, None))], inmediato=True) == 'Faltan o sobran datos en la forma de cobro: ZZ TRANSFERENCIA (TRANSFERENCIA).')
    chk('trg_validar_cobro: el efectivo con número de referencia se rechaza (sobran datos)',
        sql_en_txn([(cab, (C2, AP1, ADMIN[0], 'ZZR-11', 5000)), (det, ('ZZR-11', F['EF'], 5000, 'X1'))], inmediato=True) == 'Faltan o sobran datos en la forma de cobro: ZZ EFECTIVO (EFECTIVO).')
    chk('trg_validar_cobro: un cobro correcto (efectivo) pasa',
        sql_en_txn([(cab, (C2, AP1, ADMIN[0], 'ZZR-12', 5000)), (det, ('ZZR-12', F['EF'], 5000, None))], inmediato=True) is None)
    chk('cobro_cab: el número de recibo es único',
        'uq_cobro_numero_recibo' in (sql_en_txn([(cab, (C2, AP1, ADMIN[0], 'ZZR-13', 10)), (cab, (C2, AP1, ADMIN[0], 'ZZR-13', 10))]) or '') or
        'duplicada' in (sql_en_txn([(cab, (C2, AP1, ADMIN[0], 'ZZR-13', 10)), (cab, (C2, AP1, ADMIN[0], 'ZZR-13', 10))]) or ''))
    chk('las pruebas directas no dejaron nada', (cu.execute("SELECT count(*) FROM cobro_cab WHERE numero_recibo LIKE 'ZZR-%'") or cu.fetchone()[0]) == 0 and saldo(C2) == (150000, 'PENDIENTE'))

    # =====================================================================================================================
    # 7. ANULAR (caja abierta) y permisos de anulación
    # =====================================================================================================================
    anular(ID5, nombre='anular un cobro (caja abierta)', contiene='anulado correctamente')
    chk('anular: saldo de C2 repuesto (200.000) y cuenta PENDIENTE', saldo(C2) == (200000, 'PENDIENTE'))
    cu.execute("SELECT estado FROM cobro_cab WHERE id_cobro=%s", (ID5,)); chk('anular: el cobro queda ANULADO', cu.fetchone()[0] == 'ANULADO')
    cu.execute("SELECT id_usuario, detalle FROM auditoria_cambios WHERE entidad='cobro_cab' AND id_registro=%s AND accion='BAJA'", (ID5,))
    f = cu.fetchone(); chk('auditoría BAJA con el recibo y quién anuló', f is not None and f[0] == ADMIN[0] and 'Recibo' in f[1])
    anular(ID5, 409, nombre='anular dos veces', exacto='El cobro ya está anulado.')
    anular(2147483000, 404, nombre='anular inexistente')
    cu.execute("SELECT id_usuario, detalle FROM auditoria_cambios WHERE entidad='cobro_cab' AND id_registro=%s AND accion='ALTA'", (ID2,))
    f = cu.fetchone(); chk('auditoría ALTA: recibo, cliente, factura, total y formas', f is not None and 'ZZ CLIENTE COBRO' in f[1] and 'Gs. 500.000' in f[1] and 'ZZ TARJETA DE CRÉDITO Gs. 200.000' in f[1])

    # =====================================================================================================================
    # 8. LISTADO Y DETALLE
    # =====================================================================================================================
    r = api('get', f'{COB}?cliente=ZZ CLIENTE COBRO', 200, nombre='filtro por cliente')['data']
    chk('el listado trae los cobros del cliente con sus formas', {x['id_cobro'] for x in r} >= {ID1, ID2, ID3, ID3b, ID4} and any('ZZ CHEQUE' in (x['formas'] or '') for x in r))
    r = api('get', f'{COB}?cliente={P2["numero_recibo"]}', 200, nombre='filtro por N.º de recibo')['data']; chk('filtro por recibo', [x['id_cobro'] for x in r] == [ID2])
    r = api('get', f'{COB}?cliente={P2["numero_factura"]}', 200, nombre='filtro por N.º de factura')['data']; chk('filtro por factura', {x['id_cobro'] for x in r} >= {ID1, ID2})
    chk('filtro por estado ANULADO', ID5 in {x['id_cobro'] for x in api('get', f'{COB}?estado=ANULADO&cliente=ZZ CLIENTE', 200)['data']} and ID2 not in {x['id_cobro'] for x in api('get', f'{COB}?estado=ANULADO&cliente=ZZ CLIENTE', 200)['data']})
    chk('filtro por fechas (hoy sí, ayer no)', ID2 in {x['id_cobro'] for x in api('get', f'{COB}?desde={HOY}&hasta={HOY}', 200)['data']} and ID2 not in {x['id_cobro'] for x in api('get', f'{COB}?hasta={HOY - timedelta(days=1)}', 200)['data']})
    api('get', f'{COB}?estado=XX', 400, nombre='estado inválido'); api('get', f'{COB}?desde=hoy', 400, nombre='fecha inválida')
    api('get', f'{COB}?desde={HOY}&hasta={HOY - timedelta(days=1)}', 400, nombre='desde > hasta')
    chk('buscador de cuentas: solo PENDIENTES (C2 sí; C1 PAGADA no)', {x['id_cuenta'] for x in api('get', f'{COB}/cuentas?q=ZZ CLIENTE COBRO', 200)['data']} >= {C2} and C1 not in {x['id_cuenta'] for x in api('get', f'{COB}/cuentas?q=ZZ CLIENTE COBRO', 200)['data']})
    r = api('get', f'{COB}/cuentas?q={P2["numero_factura"]}', 200, nombre='buscar cuenta por N.º de factura')['data']; chk('buscar por factura (C1 está pagada: vacío)', r == [])
    cta = api('get', f'{COB}/cuentas/{C2}', 200, nombre='cuenta por id')['data']
    chk('la cuenta informa total, saldo y vencimiento (+30 días)', (cta['monto_total'], cta['saldo'], cta['fecha_vencimiento']) == (300000, 200000, (HOY + timedelta(days=30)).isoformat()))
    api('get', f'{COB}/cuentas/2147483000', 404, nombre='cuenta inexistente')
    chk('formas disponibles: solo ACTIVAS con tipo (incluye las ZZ, no la inactiva)', F['EF'] in {x['id_forma_cobro'] for x in api('get', f'{COB}/formas', 200)['data']} and F['IN'] not in {x['id_forma_cobro'] for x in api('get', f'{COB}/formas', 200)['data']})
    chk('adheridas disponibles: activas con marca y emisora activas', {A['OK']} <= {x['id_entidad_adherida'] for x in api('get', f'{COB}/adheridas', 200)['data']} and not ({A['IN'], A['MI'], A['EI']} & {x['id_entidad_adherida'] for x in api('get', f'{COB}/adheridas', 200)['data']}))
    chk('emisoras disponibles: solo activas', E['OK'] in {x['id_entidad_emisora'] for x in api('get', f'{COB}/emisoras', 200)['data']} and E['IN'] not in {x['id_entidad_emisora'] for x in api('get', f'{COB}/emisoras', 200)['data']})
    det = api('get', f'{COB}/{ID2}', 200, nombre='detalle del cobro combinado')['data']
    chk('detalle: formas con sus datos y el saldo de la factura tras el cobro (100.000)', len(det['detalle']) == 4 and det['saldo_despues'] == 100000 and det['empresa']['ruc'] == '80099999-1')
    api('get', f'{COB}/2147483000', 404, nombre='detalle inexistente')

    # =====================================================================================================================
    # 9. VISTAS Y FUNCIONES
    # =====================================================================================================================
    esperado_total = sum(m for l in ledger.values() for m, _ in l)
    esperado_efectivo = sum(m for l in ledger.values() for m, t in l if t == 'EFECTIVO')
    cu.execute("SELECT fn_total_recaudado(%s), fn_total_efectivo_apertura(%s)", (AP1, AP1)); f = cu.fetchone()
    chk(f'fn_total_recaudado / fn_total_efectivo_apertura = {esperado_total:,} / {esperado_efectivo:,} (solo EMITIDOS)'.replace(',', '.'), (int(f[0]), int(f[1])) == (esperado_total, esperado_efectivo))
    cu.execute("SELECT fn_total_recaudado(%s), fn_total_efectivo_apertura(%s)", (ap_v, ap_v)); chk('las funciones dan 0 en una apertura sin cobros', tuple(int(x) for x in cu.fetchone()) == (0, 0))
    cu.execute("SELECT forma_cobro, tipo_forma, cantidad_pagos, total_cobrado FROM v_resumen_caja WHERE id_apertura=%s ORDER BY forma_cobro", (AP1,))
    rc = {r[0]: (r[1], r[2], int(r[3])) for r in cu.fetchall()}
    chk('v_resumen_caja: total por forma de cobro (efectivo, tarjeta, cheque, transferencia)', rc.get('ZZ TARJETA DE CRÉDITO') == ('TARJETA', 1, 200000) and rc.get('ZZ CHEQUE') == ('CHEQUE', 1, 150000)
        and rc.get('ZZ TRANSFERENCIA') == ('TRANSFERENCIA', 1, 50000) and rc.get('ZZ EFECTIVO', (0, 0, 0))[2] == esperado_efectivo)
    chk('v_resumen_caja: la suma de las formas = total recaudado (los anulados no cuentan)', sum(v[2] for v in rc.values()) == esperado_total)
    cu.execute("SELECT total, saldo, estado_cuenta, total_cobrado, cantidad_cobros, fecha_ultimo_cobro IS NOT NULL FROM v_estado_cuenta_cliente WHERE id_venta=%s", (v1,))
    f = cu.fetchone(); chk('v_estado_cuenta_cliente: factura C1 pagada: total 1.000.000, saldo 0, PAGADA, cobrado 1.000.000 en 3 cobros emitidos',
                           f is not None and (int(f[0]), int(f[1]), f[2], int(f[3]), f[4], f[5]) == (1000000, 0, 'PAGADA', 1000000, 3, True))
    cu.execute("SELECT saldo, total_cobrado, cantidad_cobros, saldo_total_cliente FROM v_estado_cuenta_cliente WHERE id_venta=%s", (v2,))
    f = cu.fetchone(); chk('v_estado_cuenta_cliente: factura C2: saldo 200.000, cobrado 100.000 en 1 cobro (el anulado no cuenta)', f is not None and (int(f[0]), int(f[1]), f[2]) == (200000, 100000, 1))
    cu.execute("SELECT saldo_total_cliente FROM v_estado_cuenta_cliente WHERE id_cliente=%s LIMIT 1", (ids['cliente'],))
    chk('v_estado_cuenta_cliente: saldo total del cliente = lo pendiente de sus cuentas (C0 100.000 + C2 200.000 + C1 pagada 0)', int(cu.fetchone()[0]) == 300000)

    # =====================================================================================================================
    # 10. CONEXIONES: Forma de Cobro, Marca, Adherida, Emisora
    # =====================================================================================================================
    como(ADMIN)
    api('delete', f'{FORMAS}/{F["EF"]}', 409, nombre='baja de una forma de cobro usada en una cobranza', exacto='No se puede dar de baja, la forma de cobro está usada en una cobranza.')
    api('put', f'{FORMAS}/{F["EF"]}', 409, {'descripcion': 'ZZ EFECTIVO', 'tipo': 'CHEQUE'}, nombre='cambiar el TIPO de una forma ya usada', exacto='No se puede cambiar el tipo: la forma de cobro está usada en cobranzas.', campo='tipo')
    cu.execute("SELECT tipo FROM forma_cobro WHERE id_forma_cobro=%s", (F['EF'],)); chk('el tipo de la forma usada no cambió', cu.fetchone()[0] == 'EFECTIVO')
    api('put', f'{FORMAS}/{F["EF"]}', 200, {'descripcion': 'ZZ EFECTIVO', 'tipo': 'EFECTIVO'}, nombre='editar una forma usada sin cambiar el tipo (sin cambios)')
    with app.app_context():
        chk('Entidad adherida usada con tarjeta: baja bloqueada', EntidadAdheridaDao().esta_en_uso(A['OK']) == 'No se puede dar de baja, la entidad adherida está usada en una cobranza con tarjeta.')
        chk('Entidad adherida: deleteEntidadAdherida devuelve ("EN_USO", motivo)', EntidadAdheridaDao().deleteEntidadAdherida(A['OK'])[0] == 'EN_USO')
        # Marca y emisora devuelven antes el motivo \"asociada a una adherida ACTIVA\": se desactivan las adheridas de prueba (por SQL)
        # para llegar a la verificación de cobros, que es lo que se quiere probar.
        cu.execute('UPDATE entidad_adherida SET activo = false WHERE id_entidad_adherida = ANY(%s)', (list(A.values()),))
        chk('Marca de tarjeta usada con tarjeta: baja bloqueada por la cobranza', MarcaTarjetaDao().esta_en_uso(M['OK']) == 'No se puede dar de baja, la marca está usada en una cobranza con tarjeta.')
        chk('Entidad emisora usada con TARJETA: baja bloqueada por la cobranza', EntidadEmisoraDao().esta_en_uso(E['OK']) in (
            'No se puede dar de baja, el banco está usado en una cobranza con tarjeta.', 'No se puede dar de baja, el banco está usado en una cobranza con cheque.'))
        chk('lo que NO se usó no se bloquea por cobros (marca y emisora inactivas, adherida inactiva)', MarcaTarjetaDao().esta_en_uso(M['IN']) is False
            and EntidadEmisoraDao().esta_en_uso(E['IN']) is False and EntidadAdheridaDao().esta_en_uso(A['IN']) is False)

    # =====================================================================================================================
    # 11. CONEXIONES: Venta (anular con cobros) y cuenta ANULADA
    # =====================================================================================================================
    v3, C3 = nueva_cuenta(100000, apertura=AP1)   # la venta nace en la apertura ABIERTA (si no, anular se frena por caja cerrada)
    d = cobrar(C3, [ef(40000)], nombre='cobro de la cuenta de una venta'); ID6 = d['data']['id_cobro']
    api('delete', f'{VEN}/{v3}', 409, nombre='anular una venta CON cobros', exacto='No es posible anular, existen cobros registrados. Utilice una Nota de Crédito.')
    cu.execute("SELECT estado FROM venta_cab WHERE id_venta=%s", (v3,)); chk('la venta con cobros sigue EMITIDA', cu.fetchone()[0] == 'EMITIDA')
    anular(ID6, nombre='anular ese cobro')
    api('delete', f'{VEN}/{v3}', 200, nombre='sin cobros EMITIDOS la venta se anula (los anulados no bloquean)')
    chk('la cuenta de la venta anulada queda ANULADA', saldo(C3)[1] == 'ANULADA')
    cobrar(C3, [ef(100)], 409, nombre='cobrar una cuenta ANULADA', exacto='La cuenta a cobrar está anulada.', campo='id_cuenta')

    # =====================================================================================================================
    # 12. CONCURRENCIA
    # =====================================================================================================================
    v4, C4 = nueva_cuenta(100000)
    res = [None] * 3; barrera = threading.Barrier(3)
    def forma_dao(monto):
        return {'id_forma_cobro': F['EF'], 'tipo': 'EFECTIVO', 'monto': monto, 'numero_referencia': None, 'tarjeta': None, 'cheque': None}
    def hilo_cobro(i):
        with app.app_context():
            barrera.wait(); res[i] = CobroDao().guardarCobro(ADMIN[0], C4, None, [forma_dao(100000)])
    ts = [threading.Thread(target=hilo_cobro, args=(i,)) for i in range(3)]; [t.start() for t in ts]; [t.join(60) for t in ts]
    oks = [r for r in res if isinstance(r, int)]; cobros.update(oks)
    chk('concurrencia: 3 cobros por todo el saldo a la vez -> exactamente 1 gana', len(oks) == 1 and sum(isinstance(r, tuple) and r[0] == CUENTA_NO_PENDIENTE for r in res) == 2)
    chk('concurrencia: la cuenta queda en saldo 0 y PAGADA (el saldo nunca queda negativo)', saldo(C4) == (0, 'PAGADA'))
    res = [None] * 3; barrera = threading.Barrier(3)
    def hilo_anular(i):
        with app.app_context():
            barrera.wait(); res[i] = CobroDao().anularCobro(oks[0])
    ts = [threading.Thread(target=hilo_anular, args=(i,)) for i in range(3)]; [t.start() for t in ts]; [t.join(60) for t in ts]
    chk('concurrencia: 3 anulaciones del mismo cobro -> 1 anula y 2 reciben "ya anulado"', sum(isinstance(r, dict) for r in res) == 1 and sum(r == YA_ANULADO for r in res) == 2)
    chk('concurrencia: el saldo se repuso UNA sola vez (100.000)', saldo(C4) == (100000, 'PENDIENTE'))
    res = [None] * 4; barrera = threading.Barrier(4)
    def hilo_dist(i):
        with app.app_context():
            barrera.wait(); res[i] = CobroDao().guardarCobro(ADMIN[0], C4, None, [forma_dao(30000)])
    ts = [threading.Thread(target=hilo_dist, args=(i,)) for i in range(4)]; [t.start() for t in ts]; [t.join(60) for t in ts]
    oks2 = [r for r in res if isinstance(r, int)]; cobros.update(oks2)
    cu.execute("SELECT array_agg(numero_recibo ORDER BY id_cobro) FROM cobro_cab WHERE id_cobro = ANY(%s)", (oks2,)); nums = cu.fetchone()[0]
    chk('concurrencia: 4 cobros de 30.000 sobre 100.000 -> ganan 3 (90.000) y el 4.º excede el saldo', len(oks2) == 3 and saldo(C4) == (10000, 'PENDIENTE'))
    chk('concurrencia: los 3 recibos son distintos y consecutivos (sin huecos ni repetidos)', len(set(nums)) == 3 and [int(n[4:]) for n in nums] == list(range(int(nums[0][4:]), int(nums[0][4:]) + 3)))

    # =====================================================================================================================
    # 13. RECIBO EN PDF
    # =====================================================================================================================
    como(CAJERO)
    r = c.get(f'{COB}/{ID2}/pdf')
    chk('PDF: 200, application/pdf y empieza con %PDF', r.status_code == 200 and r.mimetype == 'application/pdf' and r.data[:4] == b'%PDF')
    chk('PDF: exactamente 2 páginas (ORIGINAL y DUPLICADO)', paginas_pdf(r.data) == 2)
    txt = texto_pdf(r.data)
    chk('PDF: contiene el N.º de recibo, el RUC de la empresa y el título', txt.count(P2['numero_recibo']) >= 2 and '80099999-1' in txt and 'RECIBO DE DINERO' in txt)
    chk('PDF: total (500.000) y total en letras', '500.000' in txt and 'QUINIENTOS MIL' in txt and 'SON GUARAN' in txt)
    chk('PDF: cada forma con su detalle (autorización, N.º de cheque, referencia, últimos dígitos)', all(x in txt for x in ('ZZ EFECTIVO', 'ZZ CHEQUE', 'AUT123', 'CH001', 'TRF-0001', '1234')))
    chk('PDF: el cliente, la factura y el saldo tras el cobro', 'ZZ CLIENTE COBRO' in txt and P2['numero_factura'] in txt and '100.000' in txt)
    chk('PDF de un cobro vigente: sin marca ANULADO', 'ANULADO' not in txt and 'ORIGINAL' in txt and 'DUPLICADO' in txt)
    r = c.get(f'{COB}/{ID5}/pdf'); chk('PDF de un cobro ANULADO: se descarga con la marca ANULADO', r.status_code == 200 and 'ANULADO' in texto_pdf(r.data) and paginas_pdf(r.data) == 2)
    como(RECEP); api('get', f'{COB}/{ID2}/pdf', 403, nombre='PDF sin permiso ver')
    como(ADMIN); api('get', f'{COB}/2147483000/pdf', 404, nombre='PDF de un cobro inexistente')

    # =====================================================================================================================
    # 14. CIERRE DE CAJA CON RECAUDADO REAL
    # =====================================================================================================================
    for idc in oks2:   # los 3 cobros concurrentes ganadores (efectivo) entran al libro de control
        ledger[idc] = [(30000, 'EFECTIVO')]
    esperado_total = sum(m for l in ledger.values() for m, _ in l); esperado_efectivo = sum(m for l in ledger.values() for m, t in l if t == 'EFECTIVO')
    como(ADMIN)
    d = api('get', f'{APE}/{AP1}/cierre', 200, nombre='detalle previo al cierre')['data']
    chk('preview: total recaudado = TODO lo cobrado (todas las formas)', d['total_recaudado'] == esperado_total)
    chk('preview: monto de cierre = apertura (100.000) + SOLO el efectivo', d['efectivo'] == esperado_efectivo and d['monto_cierre'] == 100000 + esperado_efectivo)
    chk('preview: el desglose por forma viene de v_resumen_caja y suma el total recaudado', sum(x['total_cobrado'] for x in d['resumen']) == esperado_total and {x['forma_cobro'] for x in d['resumen']} >= {'ZZ EFECTIVO', 'ZZ TARJETA DE CRÉDITO', 'ZZ CHEQUE', 'ZZ TRANSFERENCIA'})
    chk('preview: tarjeta + cheque + transferencia NO suman al monto de cierre', d['monto_cierre'] == 100000 + d['total_recaudado'] - (200000 + 150000 + 50000))
    # un cobro queda pendiente de cerrar para probar "anular con caja cerrada"
    d = cobrar(C4, [ef(10000)], nombre='último cobro antes del cierre'); ID_CERRADO = d['data']['id_cobro']
    esperado_total += 10000; esperado_efectivo += 10000
    api('delete', f'{APE}/{AP1}', 409, nombre='no se anula una apertura con cobros', exacto='La apertura tiene movimientos registrados; debe cerrarse en lugar de anularse.')
    d = api('patch', f'{APE}/{AP1}/cerrar', 200, nombre='cerrar la caja', contiene='cerrada correctamente')
    cu.execute("SELECT total_recaudado, monto_cierre, estado FROM apertura_cierre_caja WHERE id_apertura=%s", (AP1,))
    f = cu.fetchone(); chk('cierre: total_recaudado = todo lo cobrado y monto_cierre = apertura + solo efectivo (guardados)', (int(f[0]), int(f[1]), f[2]) == (esperado_total, 100000 + esperado_efectivo, 'CERRADA'))
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='apertura_cierre_caja' AND id_registro=%s AND accion='CIERRE'", (AP1,))
    chk('auditoría CIERRE: incluye total recaudado, efectivo y monto de cierre', 'Efectivo:' in cu.fetchone()[0])
    anular(ID_CERRADO, 409, nombre='anular un cobro con la caja CERRADA', exacto='La caja de este cobro ya fue cerrada; utilice una Nota de Crédito.')
    cu.execute("SELECT estado FROM cobro_cab WHERE id_cobro=%s", (ID_CERRADO,)); chk('caja cerrada: el cobro sigue EMITIDO', cu.fetchone()[0] == 'EMITIDO')
    chk('caja cerrada: el saldo no se repuso', saldo(C4) == (0, 'PAGADA'))
    r = api('get', f'{COB}?cliente={P2["numero_recibo"]}', 200)['data']; chk('el listado informa el estado de la apertura (CERRADA)', r and r[0]['estado_apertura'] == 'CERRADA')
    cobrar(C2, [ef(1000)], 409, nombre='tras cerrar la caja no se puede cobrar', exacto='Debe abrir la caja antes de registrar un cobro.')

    # =====================================================================================================================
    # 15. APERTURA CON COBROS (sin ventas) no se anula
    # =====================================================================================================================
    with app.app_context():
        AP2 = AperturaCajaDao().abrirCaja(ADMIN[0], ids['caja'], 0)
    ids['ap'].append(AP2)
    d = cobrar(C2, [ef(20000)], nombre='cobro en la segunda apertura (la apertura no tiene ventas)'); ID7 = d['data']['id_cobro']
    api('delete', f'{APE}/{AP2}', 409, nombre='apertura 2: no se anula con un cobro EMITIDO', exacto='La apertura tiene movimientos registrados; debe cerrarse en lugar de anularse.')
    anular(ID7, nombre='anular ese cobro')
    api('delete', f'{APE}/{AP2}', 200, nombre='con el cobro ANULADO la apertura sí se puede anular')
    cu.execute("SELECT estado FROM apertura_cierre_caja WHERE id_apertura=%s", (AP2,)); chk('apertura 2 ANULADA', cu.fetchone()[0] == 'ANULADA')

    # =====================================================================================================================
    # 16. LAS TABLAS DEL DER NO SE MODIFICARON (solo las dos columnas nuevas)
    # =====================================================================================================================
    cu.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('cobro_cab','cobro_det','cobro_tarjeta','cobro_cheque')")
    chk('las 4 tablas del DER siguen siendo las mismas (no se recrearon)', cu.fetchone()[0] == 4)

finally:
    try:
        cu.execute("SELECT id_cobro FROM cobro_cab WHERE id_cuenta = ANY(%s)", (ids['cuentas'] or [0],))
        todos_cobros = sorted(set(cobros) | {r[0] for r in cu.fetchall()})
        if todos_cobros:
            cu.execute("DELETE FROM cobro_cab WHERE id_cobro = ANY(%s)", (todos_cobros,))   # cascada: detalle, tarjeta y cheque
            borrar_auditoria(cu, 'cobro_cab', todos_cobros)
        if ids['ventas']:
            borrar_auditoria(cu, 'venta_cab', ids['ventas'])
            cu.execute("DELETE FROM cuenta_cobrar WHERE id_venta = ANY(%s)", (ids['ventas'],))
            cu.execute("DELETE FROM venta_cab WHERE id_venta = ANY(%s)", (ids['ventas'],))
        if ids['ap']:
            borrar_auditoria(cu, 'apertura_cierre_caja', ids['ap'])
            cu.execute("DELETE FROM apertura_cierre_caja WHERE id_apertura = ANY(%s)", (ids['ap'],))
        if ids['caja']:
            cu.execute("DELETE FROM caja WHERE id_caja=%s", (ids['caja'],))
        if ids['adheridas']:
            cu.execute("DELETE FROM entidad_adherida WHERE id_entidad_adherida = ANY(%s)", (ids['adheridas'],))
        if ids['marcas']:
            cu.execute("DELETE FROM marca_tarjeta WHERE id_marca_tarjeta = ANY(%s)", (ids['marcas'],))
        if ids['emisoras']:
            cu.execute("DELETE FROM entidad_emisora WHERE id_entidad_emisora = ANY(%s)", (ids['emisoras'],))
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
