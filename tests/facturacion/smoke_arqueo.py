"""Registrar Arqueo de Caja (con Recaudación a depositar): objetos de base (sp_registrar_arqueo, fn_formas_arqueo, triggers, v_arqueos_diferencias),
monto del sistema calculado en la base (fondo inicial, reintegros, formas), validaciones, "nadie arquea su propia caja" (API, procedimiento y trigger),
observación obligatoria con diferencias, recaudación a depositar (efectivo - fondo + cheques), marcar depositada, anular, conexión con Apertura de Caja,
concurrencia, PDF y permisos.

Usa datos ZZ (caja, aperturas CERRADAS con cobros y un reintegro creados por SQL, formas de cobro, cuenta bancaria, arqueos y recaudaciones) que borra POR
ID. No depende de que alguien tenga una caja abierta ni la toca: sus aperturas ABIERTAS son de un usuario sin caja y duran una transacción."""
import sys, pathlib, threading, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from datetime import date, timedelta
import psycopg2
from app import app
from tests._conexion_pruebas import Conexion
from app.dao.modulo_facturacion.arqueo.ArqueoDao import ArqueoDao, ERROR_BD, RECAUDACION_DEPOSITADA, NO_PENDIENTE
from tests.facturacion._limpieza import borrar_auditoria
from tests.facturacion._pdf import paginas_pdf, texto_pdf

c = app.test_client()
fallos = []
ARQ, REC, APE = '/api/v1/arqueos', '/api/v1/recaudaciones', '/api/v1/aperturas-caja'
HOY = date.today()
MSG_PROPIA = 'No puede arquear su propia caja; el arqueo debe hacerlo otro usuario.'
stamp = str(int(time.time()))[-8:]


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
ADMIN = next((u for u in usuarios if u[2] == 'Administrador'), None)
CAJERO = next((u for u in usuarios if u[2] == 'Cajero'), None)
RECEP = next((u for u in usuarios if u[2] == 'Recepcion'), None)
OWN = next((u for u in usuarios if u[0] not in OCUPADOS and u[0] not in ((ADMIN or (0,))[0], (CAJERO or (0,))[0])), None)   # dueño de las cajas de prueba
if not (ADMIN and CAJERO and RECEP and OWN):
    print('ABORTADO: se necesitan un Administrador, un Cajero, uno de Recepción y otro usuario sin caja abierta (dueño de las cajas de prueba).'); sys.exit(1)


def como(u):
    with c.session_transaction() as s:
        s['id_usuario'] = u[0]; s['id_rol'] = u[1]; s['nombre_rol'] = u[2]


ids = {'caja': None, 'tim': None, 'cliente': None, 'ap': [], 'ventas': [], 'cobros': [], 'notas': [], 'formas': [], 'cuentas': [], 'emisoras': []}
F = {}
seq = [0]


def sql_en_txn(sql, params=(), despues=None):
    """Corre SQL en una transacción propia que SIEMPRE se deshace. Devuelve el mensaje de error o None (o la fila de `despues`)."""
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


def construir_apertura(owner, fondo, cobros, reintegro=0):
    """Apertura ZZ CERRADA con cobros EMITIDOS (cada uno paga una venta ZZ completa) y, si se pide, un reintegro en efectivo (nota de crédito sobre la
    factura pagada en efectivo). Todo en UNA transacción (los triggers diferidos de cobros y notas validan al confirmar). `cobros` = [(clave, monto)].
    Devuelve el id de la apertura."""
    k = Conexion().getConexion(); kc = k.cursor()
    try:
        kc.execute("INSERT INTO apertura_cierre_caja(id_caja, id_usuario, monto_apertura) VALUES (%s, %s, %s) RETURNING id_apertura", (ids['caja'], owner[0], fondo))
        ap = kc.fetchone()[0]; ids['ap'].append(ap)
        efectivo, cuenta_ef = 0, None
        for clave, monto in cobros:
            seq[0] += 1
            kc.execute("""INSERT INTO venta_cab(id_apertura, id_cliente, id_usuario, id_timbrado, numero_factura, tipo_venta, condicion, total_exenta, total_gravada_5,
                            total_gravada_10, iva_5, iva_10, total) VALUES (%s, %s, %s, %s, %s, 'ITEMS', 'CONTADO', 0, 0, %s, 0, %s, %s) RETURNING id_venta""",
                       (ap, ids['cliente'], owner[0], ids['tim'], f'ZZQ{stamp}{seq[0]:03d}', monto, round(monto / 11), monto))
            v = kc.fetchone()[0]; ids['ventas'].append(v)
            kc.execute("SELECT id_cuenta FROM cuenta_cobrar WHERE id_venta=%s", (v,)); cta = kc.fetchone()[0]
            kc.execute("INSERT INTO cobro_cab(id_cuenta, id_apertura, id_usuario, numero_recibo, total) VALUES (%s, %s, %s, %s, %s) RETURNING id_cobro", (cta, ap, owner[0], f'ZZQ-{stamp[-4:]}{seq[0]:03d}', monto))
            idc = kc.fetchone()[0]; ids['cobros'].append(idc)
            kc.execute("INSERT INTO cobro_det(id_cobro, id_forma_cobro, monto, numero_referencia) VALUES (%s, %s, %s, %s) RETURNING id_cobro_det", (idc, F[clave], monto, 'ZZ-REF' if clave == 'TR' else None))
            det = kc.fetchone()[0]
            if clave == 'CH':
                kc.execute("INSERT INTO cobro_cheque(id_cobro_det, id_entidad_emisora, numero_cheque, titular, fecha_emision, fecha_cobro) VALUES (%s, 1, 'ZZ1', 'ZZ', CURRENT_DATE, CURRENT_DATE)", (det,))
            if clave == 'TJ':
                kc.execute("INSERT INTO cobro_tarjeta(id_cobro_det, id_entidad_adherida, tipo_tarjeta, ultimos_digitos, numero_autorizacion) "
                           "VALUES (%s, (SELECT id_entidad_adherida FROM entidad_adherida WHERE activo LIMIT 1), 'CREDITO', '1234', 'ZZA')", (det,))
            if clave == 'EF':
                efectivo += monto; cuenta_ef = cuenta_ef or cta
        if reintegro:
            seq[0] += 1
            kc.execute("""INSERT INTO nota_credito_debito_cab(id_cuenta, id_timbrado, id_usuario, id_apertura, tipo_nota, numero_nota, motivo, total_exenta, total_gravada_5,
                            total_gravada_10, iva_5, iva_10, total) VALUES (%s, (SELECT id_timbrado FROM timbrado WHERE activo), %s, %s, 'CREDITO', %s, 'ZZ reintegro', 0, 0, %s, 0, 0, %s)
                          RETURNING id_nota""", (cuenta_ef, owner[0], ap, f'ZZQ-{stamp[-4:]}{seq[0]:03d}', reintegro, reintegro))
            idn = kc.fetchone()[0]; ids['notas'].append(idn)
            kc.execute("INSERT INTO nota_credito_debito_det(id_nota, descripcion, cantidad, precio_unitario, iva, subtotal) VALUES (%s, 'ZZ', 1, %s, 10, %s)", (idn, reintegro, reintegro))
        kc.execute("UPDATE apertura_cierre_caja SET estado='CERRADA', fecha_cierre=now(), total_recaudado=%s, monto_cierre=%s WHERE id_apertura=%s",
                   (sum(m for _, m in cobros) - reintegro, fondo + efectivo - reintegro, ap))
        k.commit()
        return ap
    except Exception:
        k.rollback(); raise
    finally:
        kc.close(); k.close()


def formas(ap):
    cu.execute("SELECT forma_cobro, tipo, cobrado, monto_sistema FROM fn_formas_arqueo(%s)", (ap,)); return [(x[0], x[1], int(x[2]), int(x[3])) for x in cu.fetchall()]


def cuerpo(ap, contados, obs=None, **extra):
    d = {'id_apertura': ap, 'formas': [{'id_forma_cobro': F[k], 'monto_contado': m} for k, m in contados]}
    if obs is not None:
        d['observacion'] = obs
    d.update(extra)
    return d


def arquear(ap, contados, esperado=201, usuario=None, obs=None, **kw):
    como(usuario or ADMIN)
    extra = kw.pop('extra', {})
    d = api('post', ARQ, esperado, cuerpo(ap, contados, obs, **extra), **kw)
    return d


def arqueos_de(aps):
    cu.execute("SELECT id_arqueo FROM arqueo_caja WHERE id_apertura = ANY(%s)", (aps,)); return [r_[0] for r_ in cu.fetchall()]


try:
    # =====================================================================================================================
    # DATOS DE PRUEBA
    # =====================================================================================================================
    cu.execute("SELECT fn_forma_efectivo_arqueo()"); F['EF'] = cu.fetchone()[0]
    for clave, desc, tipo in (('CH', 'ZZ ARQ CHEQUE', 'CHEQUE'), ('TJ', 'ZZ ARQ TARJETA', 'TARJETA'), ('TR', 'ZZ ARQ TRANSFERENCIA', 'TRANSFERENCIA')):
        cu.execute("INSERT INTO forma_cobro(descripcion, tipo) VALUES (%s, %s) RETURNING id_forma_cobro", (desc, tipo)); F[clave] = cu.fetchone()[0]; ids['formas'].append(F[clave])
    cu.execute("SELECT codigo FROM consultorio ORDER BY codigo LIMIT 1"); COD = cu.fetchone()[0]
    cu.execute("INSERT INTO caja(id_consultorio, descripcion) VALUES (%s, 'ZZ CAJA ARQUEO') RETURNING id_caja", (COD,)); ids['caja'] = cu.fetchone()[0]
    cu.execute("INSERT INTO timbrado(numero_timbrado, fecha_inicio, fecha_fin, establecimiento, punto_expedicion, numero_desde, numero_hasta, activo) "
               "VALUES ('ZZ000006', %s, %s, '994', '994', 1, 10, false) RETURNING id_timbrado", (HOY - timedelta(days=30), HOY + timedelta(days=30))); ids['tim'] = cu.fetchone()[0]
    cu.execute("INSERT INTO cliente(nombre, apellido, ci_ruc) VALUES ('ZZ CLIENTE', 'ARQUEO', %s) RETURNING id_cliente", ('ZZK' + stamp,)); ids['cliente'] = cu.fetchone()[0]
    cu.execute("INSERT INTO entidad_emisora(descripcion, direccion, telefono, correo) VALUES ('ZZ BANCO ARQUEO', 'ZZ', '0981000000', 'zz@zz.com') RETURNING id_entidad_emisora"); BZ = cu.fetchone()[0]; ids['emisoras'].append(BZ)
    cu.execute("INSERT INTO cuenta_bancaria(id_entidad_emisora, tipo_cuenta, numero_cuenta, titular) VALUES (%s, 'CORRIENTE', %s, 'ZZ TITULAR') RETURNING id_cuenta_bancaria", (BZ, '8' + stamp)); CTA = cu.fetchone()[0]; ids['cuentas'].append(CTA)
    cu.execute("INSERT INTO cuenta_bancaria(id_entidad_emisora, tipo_cuenta, numero_cuenta, titular, activo) VALUES (%s, 'CAJA DE AHORRO', %s, 'ZZ TITULAR', false) RETURNING id_cuenta_bancaria", (BZ, '7' + stamp)); CTA_IN = cu.fetchone()[0]; ids['cuentas'].append(CTA_IN)

    A1 = construir_apertura(OWN, 100000, [('EF', 300000), ('CH', 150000), ('TJ', 80000), ('TR', 50000)], reintegro=20000)
    A2 = construir_apertura(OWN, 100000, [('EF', 300000), ('CH', 150000), ('TJ', 80000), ('TR', 50000)])
    A3 = construir_apertura(OWN, 100000, [('CH', 50000)])
    A4 = construir_apertura(OWN, 100000, [])
    A5 = construir_apertura(OWN, 100000, [('EF', 200000)])
    A7 = construir_apertura(OWN, 100000, [('EF', 100000)])
    A8 = construir_apertura(OWN, 100000, [('EF', 100000)])
    cu.execute("INSERT INTO apertura_cierre_caja(id_caja, id_usuario, monto_apertura, estado, fecha_cierre, total_recaudado, monto_cierre) VALUES (%s, %s, 50000, 'CERRADA', now(), 0, 50000) RETURNING id_apertura", (ids['caja'], ADMIN[0]))
    A_ADM = cu.fetchone()[0]; ids['ap'].append(A_ADM)
    cu.execute("INSERT INTO apertura_cierre_caja(id_caja, id_usuario, monto_apertura, estado, fecha_cierre, total_recaudado, monto_cierre) VALUES (%s, %s, 50000, 'CERRADA', now(), 0, 50000) RETURNING id_apertura", (ids['caja'], CAJERO[0]))
    A_CAJ = cu.fetchone()[0]; ids['ap'].append(A_CAJ)

    # =====================================================================================================================
    # 1. OBJETOS DE BASE DE DATOS
    # =====================================================================================================================
    cu.execute("SELECT count(*) FROM pg_proc WHERE proname='sp_registrar_arqueo' AND prokind='p' AND obj_description(oid,'pg_proc') IS NOT NULL"); chk('sp_registrar_arqueo es un PROCEDIMIENTO con COMMENT ON', cu.fetchone()[0] == 1)
    cu.execute("SELECT count(*) FROM pg_proc WHERE proname IN ('fn_forma_efectivo_arqueo','fn_formas_arqueo','fn_validar_arqueo','fn_arqueo_estado','fn_recaudacion_estado') AND obj_description(oid,'pg_proc') IS NOT NULL")
    chk('las 5 funciones tienen COMMENT ON', cu.fetchone()[0] == 5)
    cu.execute("SELECT count(*) FROM pg_trigger t JOIN pg_description d ON d.objoid = t.oid WHERE t.tgname IN ('trg_validar_arqueo','trg_arqueo_estado','trg_recaudacion_estado')")
    chk('los 3 triggers tienen COMMENT ON', cu.fetchone()[0] == 3)
    cu.execute("SELECT count(*) FROM pg_description WHERE objoid = 'v_arqueos_diferencias'::regclass AND objsubid = 0"); chk('v_arqueos_diferencias tiene COMMENT ON', cu.fetchone()[0] == 1)
    cu.execute("SELECT string_agg(column_name, ',' ORDER BY ordinal_position) FROM information_schema.columns WHERE table_name='v_arqueos_diferencias'")
    chk('v_arqueos_diferencias: columnas', cu.fetchone()[0] == 'id_arqueo,id_apertura,caja,id_cajero,cajero,fecha_apertura,fecha_cierre,fecha_arqueo,id_arqueador,arqueador,total_sistema,total_contado,diferencia,resultado,estado,observacion')
    cu.execute("SELECT array_agg(column_name::text ORDER BY ordinal_position) FROM information_schema.columns WHERE table_name='arqueo_caja'")
    chk('arqueo_caja: columnas tal cual las creó el DER (sin cambios)', cu.fetchone()[0] == ['id_arqueo', 'id_apertura', 'id_usuario', 'fecha', 'total_sistema', 'total_contado', 'diferencia', 'observacion', 'estado'])
    cu.execute("SELECT array_agg(column_name::text ORDER BY ordinal_position) FROM information_schema.columns WHERE table_name='recaudacion_depositar'")
    chk('recaudacion_depositar: columnas del DER + id_cuenta_bancaria', cu.fetchone()[0] == ['id_recaudacion', 'id_arqueo', 'id_usuario', 'fecha_generacion', 'monto_efectivo', 'monto_cheque', 'total', 'estado', 'fecha_deposito', 'numero_boleta', 'id_cuenta_bancaria'])
    cu.execute("SELECT id_menu FROM menu WHERE clave='arqueo' AND activo"); chk('menu: existe la entrada "arqueo"', cu.fetchone() is not None)
    cu.execute("SELECT array_agg(accion ORDER BY accion) FROM permisos p JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND id_menu = (SELECT id_menu FROM menu WHERE clave='arqueo' AND activo = true)")
    chk('el Cajero tiene ver, nuevo, anular y estado sobre arqueo', cu.fetchone()[0] == ['anular', 'estado', 'nuevo', 'ver'])
    cu.execute("SELECT count(*) FROM permisos p JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero'"); chk('el Cajero queda con 35 filas de permisos', cu.fetchone()[0] == 35)

    # =====================================================================================================================
    # 2. EL MONTO DEL SISTEMA LO CALCULA LA BASE
    # =====================================================================================================================
    fa = formas(A1)
    chk('A1: efectivo = 300.000 cobrado + 100.000 de fondo - 20.000 de reintegro = 380.000; las demás formas, lo cobrado',
        [(x[1], x[2], x[3]) for x in fa] == [('EFECTIVO', 300000, 380000), ('CHEQUE', 150000, 150000), ('TARJETA', 80000, 80000), ('TRANSFERENCIA', 50000, 50000)] and fa[0][0] != '')
    chk('A1: la forma EFECTIVO va primero y las demás por descripción', [x[1] for x in fa] == ['EFECTIVO', 'CHEQUE', 'TARJETA', 'TRANSFERENCIA'])
    chk('A4 (sin cobros): solo la forma EFECTIVO, con el fondo inicial', [(x[1], x[2], x[3]) for x in formas(A4)] == [('EFECTIVO', 0, 100000)])
    cu.execute("SELECT count(*) FROM fn_formas_arqueo(2147483000)"); chk('una apertura inexistente no devuelve formas', cu.fetchone()[0] == 0)

    # =====================================================================================================================
    # 3. PERMISOS
    # =====================================================================================================================
    como(RECEP)
    for url, nombre in ((ARQ, 'listado'), (f'{ARQ}/1', 'detalle'), (f'{ARQ}/1/pdf', 'PDF'), (f'{ARQ}/aperturas', 'aperturas sin arqueo'), (f'{ARQ}/aperturas/{A1}/formas', 'formas'), (REC, 'recaudaciones')):
        api('get', url, 403, nombre=f'Recepción sin permiso: {nombre}')
    api('post', ARQ, 403, {}, nombre='Recepción: alta'); api('delete', f'{ARQ}/1', 403, nombre='Recepción: anular'); api('patch', f'{REC}/1/depositar', 403, {}, nombre='Recepción: depositar')
    chk('vista: Recepción 403', c.get('/referenciales/arqueo/arqueo-index').status_code == 403)
    como(CAJERO); api('get', ARQ, 200, nombre='Cajero: listado'); chk('vista: Cajero 200', c.get('/referenciales/arqueo/arqueo-index').status_code == 200)
    como(ADMIN); chk('vista: Administrador 200', c.get('/referenciales/arqueo/arqueo-index').status_code == 200)

    # =====================================================================================================================
    # 4. APERTURAS SIN ARQUEO Y FORMAS (como las ve cada usuario)
    # =====================================================================================================================
    como(ADMIN)
    sin_arqueo = {x['id_apertura']: x for x in api('get', f'{ARQ}/aperturas', 200, nombre='aperturas cerradas sin arqueo (Administrador)')['data']}
    chk('incluye las ZZ ajenas y la del Cajero; excluye la PROPIA del Administrador', {A1, A2, A3, A4, A5, A_CAJ} <= set(sin_arqueo) and A_ADM not in sin_arqueo)
    chk('trae caja, cajero, fechas y montos del cierre', sin_arqueo[A1]['caja'] == 'ZZ CAJA ARQUEO' and sin_arqueo[A1]['monto_apertura'] == 100000 and sin_arqueo[A1]['monto_cierre'] == 100000 + 300000 - 20000)
    como(CAJERO); chk('el Cajero ve la del Administrador pero no la suya', {A_ADM} <= {x['id_apertura'] for x in api('get', f'{ARQ}/aperturas', 200)['data']} and A_CAJ not in {x['id_apertura'] for x in api('get', f'{ARQ}/aperturas', 200)['data']})
    como(ADMIN)
    d = api('get', f'{ARQ}/aperturas/{A1}/formas', 200, nombre='formas de A1')['data']
    chk('formas: el sistema calculado por la base, el fondo y los reintegros', d['monto_apertura'] == 100000 and d['reintegros'] == 20000 and d['propia'] is False and [x['monto_sistema'] for x in d['formas']] == [380000, 150000, 80000, 50000])
    chk('formas de la apertura PROPIA: marcada como propia', api('get', f'{ARQ}/aperturas/{A_ADM}/formas', 200)['data']['propia'] is True)
    api('get', f'{ARQ}/aperturas/2147483000/formas', 404, nombre='formas de una apertura inexistente')

    # =====================================================================================================================
    # 5. VALIDACIONES DE LA API Y DEL PROCEDIMIENTO
    # =====================================================================================================================
    ok_a1 = [('EF', 380000), ('CH', 150000), ('TJ', 80000), ('TR', 50000)]
    def val(cuerpo_, msg, camp, nombre, code=400):
        como(ADMIN); api('post', ARQ, code, cuerpo_, nombre=f'validación: {nombre}', exacto=msg, campo=camp)
    val({'formas': []}, 'Debe seleccionar una apertura de caja.', 'id_apertura', 'sin apertura')
    val({'id_apertura': A1}, 'Debe indicar el monto contado de cada forma de cobro.', 'formas', 'sin formas')
    val({'id_apertura': A1, 'formas': []}, 'Debe indicar el monto contado de cada forma de cobro.', 'formas', 'formas vacío')
    val({'id_apertura': A1, 'formas': [{'monto_contado': 1}]}, 'Forma 1: debe seleccionar la forma de cobro.', 'formas', 'forma sin id')
    val({'id_apertura': A1, 'formas': [{'id_forma_cobro': F['EF'], 'monto_contado': -1}]}, 'Forma 1: El monto no puede ser negativo.', 'formas', 'monto negativo')
    val({'id_apertura': A1, 'formas': [{'id_forma_cobro': F['EF'], 'monto_contado': 'abc'}]}, 'Forma 1: El monto debe ser un número entero (guaraníes, sin decimales).', 'formas', 'monto texto')
    val({'id_apertura': A1, 'formas': [{'id_forma_cobro': F['EF'], 'monto_contado': '1.5'}]}, 'Forma 1: El monto debe ser un número entero (guaraníes, sin decimales).', 'formas', 'monto decimal')
    val({'id_apertura': A1, 'formas': [{'id_forma_cobro': F['EF'], 'monto_contado': ''}]}, 'Forma 1: El campo monto es obligatorio y no puede estar vacío.', 'formas', 'monto vacío')
    val({'id_apertura': A1, 'formas': [{'id_forma_cobro': F['EF'], 'monto_contado': 1}, {'id_forma_cobro': F['EF'], 'monto_contado': 2}]}, 'Forma 2: la forma de cobro está repetida.', 'formas', 'forma repetida')
    val({'id_apertura': A1, 'formas': [{'id_forma_cobro': F['EF'], 'monto_contado': 1}] * 21}, 'Un arqueo no puede tener más de 20 formas de cobro.', 'formas', 'demasiadas formas')
    val({**cuerpo(A1, ok_a1), 'observacion': 'o' * 201}, 'La observación no puede superar los 200 caracteres.', 'observacion', 'observación larga')
    val(cuerpo(2147483000, ok_a1), 'No se encontró la apertura de caja.', 'id_apertura', 'apertura inexistente', 404)
    val(cuerpo(A1, ok_a1[:3]), 'Falta contar la forma de cobro: ZZ ARQ TRANSFERENCIA.', 'formas', 'falta una forma (el procedimiento lo exige)')
    val(cuerpo(A4, [('EF', 100000), ('CH', 0)]), 'La forma de cobro ZZ ARQ CHEQUE no corresponde a este arqueo.', 'formas', 'forma sin movimiento en la apertura')
    val(cuerpo(A1, [('EF', 380000), ('CH', 150000), ('TJ', 80000), ('TR', 40000)]), 'Debe ingresar una observación: el arqueo tiene diferencias.', 'observacion', 'diferencia sin observación')
    val(cuerpo(A1, [('EF', 380000), ('CH', 150000), ('TJ', 80000), ('TR', 40000)], obs='   '), 'Debe ingresar una observación: el arqueo tiene diferencias.', 'observacion', 'observación en blanco con diferencia')
    val(cuerpo(A_ADM, [('EF', 50000)]), MSG_PROPIA, 'id_apertura', 'el Administrador no arquea SU caja', 409)
    como(CAJERO); api('post', ARQ, 409, cuerpo(A_CAJ, [('EF', 50000)]), nombre='validación: el Cajero no arquea SU caja', exacto=MSG_PROPIA, campo='id_apertura')
    # apertura ABIERTA (de OWN) persistente solo durante este bloque
    cu.execute("INSERT INTO apertura_cierre_caja(id_caja, id_usuario, monto_apertura) VALUES (%s, %s, 0) RETURNING id_apertura", (ids['caja'], OWN[0])); A_AB = cu.fetchone()[0]; ids['ap'].append(A_AB)
    val(cuerpo(A_AB, [('EF', 0)]), 'Solo se puede arquear una apertura CERRADA.', 'id_apertura', 'apertura ABIERTA', 409)
    cu.execute("DELETE FROM apertura_cierre_caja WHERE id_apertura=%s", (A_AB,)); ids['ap'].remove(A_AB)
    chk('validaciones: no se creó ningún arqueo', len(arqueos_de([A1, A2, A3, A4, A_ADM, A_CAJ])) == 0)
    # directamente contra el procedimiento y el trigger (en transacciones que se deshacen)
    call = "CALL sp_registrar_arqueo(%s, %s, %s::int[], %s::numeric[], %s, NULL, NULL)"
    chk('sp: apertura inexistente', sql_en_txn(call, (2147483000, ADMIN[0], [F['EF']], [1], None)) == 'La apertura de caja no existe.')
    chk('sp: nadie arquea su propia caja (el dueño de la apertura)', sql_en_txn(call, (A1, OWN[0], [F['EF'], F['CH'], F['TJ'], F['TR']], [380000, 150000, 80000, 50000], None)) == MSG_PROPIA)
    chk('sp: arreglos de distinto largo', sql_en_txn(call, (A4, ADMIN[0], [F['EF']], [1, 2], None)) == 'Debe indicar el monto contado de cada forma de cobro.')
    chk('sp: formas repetidas', sql_en_txn(call, (A4, ADMIN[0], [F['EF'], F['EF']], [1, 2], None)) == 'Hay formas de cobro repetidas en el arqueo.')
    chk('sp: monto negativo', sql_en_txn(call, (A4, ADMIN[0], [F['EF']], [-1], None)) == 'Los montos contados deben ser números enteros mayores o iguales a 0.')
    chk('sp: monto con decimales', sql_en_txn(call, (A4, ADMIN[0], [F['EF']], [1.5], None)) == 'Los montos contados deben ser números enteros mayores o iguales a 0.')
    chk('sp: observación de más de 200 caracteres', sql_en_txn(call, (A4, ADMIN[0], [F['EF']], [100000], 'x' * 201)) == 'La observación no puede superar los 200 caracteres.')
    chk('sp: un arqueo correcto devuelve ids (y se deshace)', sql_en_txn(call, (A4, ADMIN[0], [F['EF']], [100000], None), despues=("SELECT count(*) FROM arqueo_caja WHERE id_apertura=%s", (A4,))) == (1,))
    ins = "INSERT INTO arqueo_caja(id_apertura, id_usuario, total_sistema, total_contado, diferencia) VALUES (%s, %s, 0, 0, 0)"
    chk('trg_validar_arqueo: una apertura ABIERTA no se arquea (también por INSERT directo)',
        sql_en_txn([("INSERT INTO apertura_cierre_caja(id_caja, id_usuario, monto_apertura) VALUES (%s, %s, 0)", (ids['caja'], OWN[0])), ("INSERT INTO arqueo_caja(id_apertura, id_usuario, total_sistema, total_contado, diferencia) VALUES (currval('apertura_cierre_caja_id_apertura_seq'), %s, 0, 0, 0)", (ADMIN[0],))]) == 'Solo se puede arquear una apertura CERRADA.')
    chk('trg_validar_arqueo: ni la propia caja (INSERT directo)', sql_en_txn(ins, (A_ADM, ADMIN[0])) == MSG_PROPIA)
    chk('trg_validar_arqueo: ni una apertura inexistente', sql_en_txn(ins, (2147483000, ADMIN[0])) is not None)

    # =====================================================================================================================
    # 6. ARQUEO QUE CUADRA (A1) Y RECAUDACIÓN A DEPOSITAR
    # =====================================================================================================================
    d = arquear(A1, ok_a1, nombre='arqueo de A1 que CUADRA (con datos falsos en el cuerpo)', extra={'total_sistema': 1, 'id_usuario': OWN[0], 'diferencia': 99, 'estado': 'ANULADO', 'monto_sistema': 5})
    Q1 = d['data']; ID_Q1 = Q1['id_arqueo']
    chk('cabecera: REGISTRADO, quien arqueó = la sesión, totales del SISTEMA (660.000) y diferencia 0', (Q1['estado'], Q1['id_arqueador'], Q1['total_sistema'], Q1['total_contado'], Q1['diferencia'], Q1['resultado']) == ('REGISTRADO', ADMIN[0], 660000, 660000, 0, 'CUADRA'))
    chk('detalle: el monto del sistema sale de la base (efectivo 380.000 con fondo y reintegro)', [(x['tipo'], x['monto_sistema'], x['monto_contado'], x['diferencia']) for x in Q1['detalle']] ==
        [('EFECTIVO', 380000, 380000, 0), ('CHEQUE', 150000, 150000, 0), ('TARJETA', 80000, 80000, 0), ('TRANSFERENCIA', 50000, 50000, 0)])
    R1 = Q1['recaudacion']
    chk('recaudación PENDIENTE = (efectivo 380.000 - fondo 100.000) + cheques 150.000 = 430.000; tarjetas y transferencias no se depositan', R1 is not None and (R1['estado'], R1['monto_efectivo'], R1['monto_cheque'], R1['total']) == ('PENDIENTE', 280000, 150000, 430000))
    chk('el mensaje informa el resultado y la recaudación', 'cuadra' in d['mensaje'] and 'Recaudación a depositar: Gs. 430.000' in d['mensaje'])
    cu.execute("SELECT detalle, id_usuario FROM auditoria_cambios WHERE entidad='arqueo_caja' AND id_registro=%s AND accion='ALTA'", (ID_Q1,))
    f = cu.fetchone(); chk('auditoría ALTA: caja, cajero, totales, resultado y recaudación', f is not None and f[1] == ADMIN[0] and all(x in f[0] for x in ('ZZ CAJA ARQUEO', 'Total sistema: Gs. 660.000', 'Resultado: CUADRA', 'Recaudación a depositar: Gs. 430.000')))
    arquear(A1, ok_a1, 409, nombre='un segundo arqueo de la misma apertura', exacto='La apertura ya tiene un arqueo registrado.', campo='id_apertura')
    chk('la apertura ya no figura entre las pendientes de arqueo', A1 not in {x['id_apertura'] for x in api('get', f'{ARQ}/aperturas', 200)['data']})
    cu.execute("SELECT cajero, arqueador, total_sistema, total_contado, diferencia, resultado FROM v_arqueos_diferencias WHERE id_arqueo=%s", (ID_Q1,))
    f = cu.fetchone(); chk('v_arqueos_diferencias: cajero, arqueador, totales y CUADRA', f is not None and f[0] and f[1] and (int(f[2]), int(f[3]), int(f[4]), f[5]) == (660000, 660000, 0, 'CUADRA'))

    # =====================================================================================================================
    # 7. DIFERENCIAS (A2, A3, A4)
    # =====================================================================================================================
    comp = [('EF', 390000), ('CH', 150000), ('TJ', 90000), ('TR', 50000)]
    arquear(A2, comp, 400, nombre='diferencias que se compensan (-10.000 / +10.000) SIN observación', exacto='Debe ingresar una observación: el arqueo tiene diferencias.', campo='observacion')
    d = arquear(A2, comp, obs='Faltaron 10.000 en efectivo y sobraron 10.000 en tarjeta', nombre='con observación se registra'); Q2 = d['data']
    chk('el total cuadra (0) aunque dos formas tengan diferencia; el detalle las muestra', Q2['diferencia'] == 0 and Q2['resultado'] == 'CUADRA' and [x['diferencia'] for x in Q2['detalle']] == [-10000, 0, 10000, 0] and Q2['observacion'].startswith('Faltaron'))
    chk('recaudación de A2 = (390.000 - 100.000) + 150.000 = 440.000 (se deposita lo CONTADO)', (Q2['recaudacion']['monto_efectivo'], Q2['recaudacion']['monto_cheque'], Q2['recaudacion']['total']) == (290000, 150000, 440000))
    d = arquear(A3, [('EF', 60000), ('CH', 50000)], obs='Faltante en caja', nombre='efectivo contado MENOR que el fondo inicial', usuario=CAJERO); Q3 = d['data']
    chk('A3: FALTANTE de 40.000; quien arqueó fue el Cajero (sesión)', (Q3['resultado'], Q3['diferencia'], Q3['id_arqueador']) == ('FALTANTE', -40000, CAJERO[0]))
    chk('A3: el efectivo a depositar es 0 (nunca negativo) y solo se depositan los cheques', (Q3['recaudacion']['monto_efectivo'], Q3['recaudacion']['monto_cheque'], Q3['recaudacion']['total']) == (0, 50000, 50000))
    d = arquear(A4, [('EF', 100000)], nombre='apertura sin cobros contada igual al fondo'); Q4 = d['data']
    chk('A4: CUADRA y NO se genera recaudación (nada que depositar)', Q4['resultado'] == 'CUADRA' and Q4['recaudacion'] is None and 'No hay recaudación a depositar' in d['mensaje'])
    d = arquear(A_CAJ, [('EF', 120000)], obs='Sobrante', nombre='el Administrador arquea la caja del Cajero'); Q_CAJ = d['data']
    chk('A_CAJ: SOBRANTE de 70.000 sobre el sistema (50.000)', (Q_CAJ['resultado'], Q_CAJ['diferencia'], Q_CAJ['total_sistema']) == ('SOBRANTE', 70000, 50000) and 'sobrante (Gs. 70.000)' in d['mensaje'])
    como(CAJERO); d = api('post', ARQ, 201, cuerpo(A_ADM, [('EF', 50000)]), nombre='el Cajero arquea la caja del Administrador'); Q_ADM = d['data']
    chk('A_ADM: lo registró el Cajero y cuadra', Q_ADM['id_arqueador'] == CAJERO[0] and Q_ADM['resultado'] == 'CUADRA')
    cu.execute("SELECT resultado, count(*) FROM v_arqueos_diferencias WHERE id_arqueo = ANY(%s) GROUP BY 1 ORDER BY 1", ([ID_Q1, Q2['id_arqueo'], Q3['id_arqueo'], Q4['id_arqueo'], Q_CAJ['id_arqueo'], Q_ADM['id_arqueo']],))
    chk('v_arqueos_diferencias: CUADRA x4, FALTANTE x1, SOBRANTE x1', cu.fetchall() == [('CUADRA', 4), ('FALTANTE', 1), ('SOBRANTE', 1)])

    # =====================================================================================================================
    # 8. LISTADO, DETALLE Y FILTROS
    # =====================================================================================================================
    como(ADMIN)
    todos = [Q1['id_arqueo'], Q2['id_arqueo'], Q3['id_arqueo'], Q4['id_arqueo'], Q_CAJ['id_arqueo'], Q_ADM['id_arqueo']]
    r = api('get', f'{ARQ}?texto=ZZ CAJA ARQUEO', 200, nombre='filtro por caja')['data']
    chk('el listado trae los arqueos con caja, cajero, arqueador, totales, resultado y la recaudación', {x['id_arqueo'] for x in r} >= set(todos) and all('estado_recaudacion' in x and 'resultado' in x for x in r))
    chk('filtro por resultado FALTANTE', [x['id_arqueo'] for x in api('get', f'{ARQ}?resultado=FALTANTE&texto=ZZ CAJA', 200)['data']] == [Q3['id_arqueo']])
    chk('filtro por resultado SOBRANTE', [x['id_arqueo'] for x in api('get', f'{ARQ}?resultado=SOBRANTE&texto=ZZ CAJA', 200)['data']] == [Q_CAJ['id_arqueo']])
    chk('filtro por estado REGISTRADO y por fechas (hoy sí, ayer no)', ID_Q1 in {x['id_arqueo'] for x in api('get', f'{ARQ}?estado=REGISTRADO&desde={HOY}&hasta={HOY}', 200)['data']} and ID_Q1 not in {x['id_arqueo'] for x in api('get', f'{ARQ}?hasta={HOY - timedelta(days=1)}', 200)['data']})
    api('get', f'{ARQ}?estado=XX', 400, nombre='estado inválido'); api('get', f'{ARQ}?resultado=XX', 400, nombre='resultado inválido'); api('get', f'{ARQ}?desde=hoy', 400, nombre='fecha inválida')
    api('get', f'{ARQ}?desde={HOY}&hasta={HOY - timedelta(days=1)}', 400, nombre='desde > hasta')
    dd = api('get', f'{ARQ}/{ID_Q1}', 200, nombre='detalle')['data']
    chk('detalle: formas, recaudación, apertura y empresa', len(dd['detalle']) == 4 and dd['recaudacion']['total'] == 430000 and dd['monto_apertura'] == 100000 and dd['empresa']['ruc'] == '80099999-1')
    api('get', f'{ARQ}/2147483000', 404, nombre='detalle inexistente')
    rr = {x['id_arqueo']: x for x in api('get', REC, 200, nombre='recaudaciones')['data']}
    chk('recaudaciones: las 3 PENDIENTES con caja y montos; el arqueo sin recaudación no aparece', {ID_Q1, Q2['id_arqueo'], Q3['id_arqueo']} <= set(rr) and Q4['id_arqueo'] not in rr and rr[ID_Q1]['total'] == 430000)
    chk('filtro de recaudaciones por estado', all(x['estado'] == 'PENDIENTE' for x in api('get', f'{REC}?estado=PENDIENTE', 200)['data'])); api('get', f'{REC}?estado=XX', 400, nombre='estado de recaudación inválido')
    ap_ = {x['id_apertura']: x for x in api('get', APE, 200, nombre='listado de aperturas de caja (conexión)')['data']}
    chk('Apertura de Caja muestra si la apertura tiene arqueo (A1 sí; A5 no; las ABIERTAS/otras no)', ap_[A1]['tiene_arqueo'] is True and ap_[A5]['tiene_arqueo'] is False and ap_[A5]['estado'] == 'CERRADA')

    # =====================================================================================================================
    # 9. MARCAR DEPOSITADA
    # =====================================================================================================================
    ID_R1 = R1['id_recaudacion']
    dep = {'id_cuenta_bancaria': CTA, 'numero_boleta': 'zz-123', 'fecha_deposito': HOY.isoformat()}
    como(ADMIN)
    api('patch', f'{REC}/{ID_R1}/depositar', 400, {**dep, 'id_cuenta_bancaria': None}, nombre='sin cuenta', exacto='Debe seleccionar la cuenta bancaria del depósito.', campo='id_cuenta_bancaria')
    api('patch', f'{REC}/{ID_R1}/depositar', 400, {**dep, 'numero_boleta': ''}, nombre='sin boleta', exacto='El campo número de boleta es obligatorio y no puede estar vacío.', campo='numero_boleta')
    api('patch', f'{REC}/{ID_R1}/depositar', 400, {**dep, 'numero_boleta': 'con%raro'}, nombre='boleta con símbolos raros', campo='numero_boleta')
    api('patch', f'{REC}/{ID_R1}/depositar', 400, {**dep, 'fecha_deposito': 'hoy'}, nombre='fecha inválida', exacto='La fecha del depósito no es válida (use AAAA-MM-DD).', campo='fecha_deposito')
    api('patch', f'{REC}/{ID_R1}/depositar', 400, {**dep, 'fecha_deposito': (HOY + timedelta(days=1)).isoformat()}, nombre='fecha futura', exacto='La fecha del depósito no puede ser posterior a hoy.', campo='fecha_deposito')
    api('patch', f'{REC}/{ID_R1}/depositar', 400, {**dep, 'fecha_deposito': (HOY - timedelta(days=1)).isoformat()}, nombre='fecha anterior al arqueo', exacto='La fecha del depósito no puede ser anterior a la del arqueo.', campo='fecha_deposito')
    api('patch', f'{REC}/{ID_R1}/depositar', 409, {**dep, 'id_cuenta_bancaria': CTA_IN}, nombre='cuenta ANULADA', exacto='La cuenta bancaria no existe o está anulada.', campo='id_cuenta_bancaria')
    api('patch', f'{REC}/{ID_R1}/depositar', 409, {**dep, 'id_cuenta_bancaria': 2147483000}, nombre='cuenta inexistente', campo='id_cuenta_bancaria')
    api('patch', f'{REC}/2147483000/depositar', 404, dep, nombre='recaudación inexistente')
    como(CAJERO)
    d = api('patch', f'{REC}/{ID_R1}/depositar', 200, dep, nombre='el Cajero (con "estado") marca la recaudación como depositada', contiene='depositada en')
    chk('queda DEPOSITADA con cuenta, boleta en MAYÚSCULAS y fecha', (d['data']['estado'], d['data']['numero_boleta'], d['data']['fecha_deposito'], d['data']['id_cuenta_bancaria']) == ('DEPOSITADA', 'ZZ-123', HOY.isoformat(), CTA))
    cu.execute("SELECT detalle, id_usuario FROM auditoria_cambios WHERE entidad='recaudacion_depositar' AND id_registro=%s AND accion='MODIFICACION'", (ID_R1,))
    f = cu.fetchone(); chk('auditoría: PENDIENTE -> DEPOSITADA con cuenta, boleta y fecha', f is not None and f[1] == CAJERO[0] and 'PENDIENTE -> DEPOSITADA' in f[0] and 'ZZ-123' in f[0] and 'ZZ BANCO ARQUEO' in f[0])
    api('patch', f'{REC}/{ID_R1}/depositar', 409, dep, nombre='depositar dos veces', exacto='La recaudación ya está depositada.')
    chk('trg_recaudacion_estado: una depositada no vuelve a PENDIENTE', sql_en_txn("UPDATE recaudacion_depositar SET estado='PENDIENTE' WHERE id_recaudacion=%s", (ID_R1,)) == 'Una recaudación depositada o anulada no cambia de estado.')
    chk('el listado del arqueo muestra la recaudación DEPOSITADA y bloquea anular', next(x for x in api('get', f'{ARQ}?texto=ZZ CAJA ARQUEO', 200)['data'] if x['id_arqueo'] == ID_Q1)['estado_recaudacion'] == 'DEPOSITADA')
    como(RECEP); api('patch', f'{REC}/{rr[Q3["id_arqueo"]]["id_recaudacion"]}/depositar', 403, dep, nombre='sin el permiso "estado" no se deposita')
    como(ADMIN)
    api('delete', f'/api/v1/cuentas-bancarias/{CTA}', 409, nombre='la cuenta con un depósito no se puede dar de baja', exacto='No se puede dar de baja, la cuenta bancaria está usada en el depósito de una recaudación.')

    # =====================================================================================================================
    # 10. ANULAR ARQUEO
    # =====================================================================================================================
    api('delete', f'{ARQ}/{ID_Q1}', 409, nombre='anular un arqueo con la recaudación DEPOSITADA', exacto='No se puede anular el arqueo: su recaudación ya fue depositada.')
    chk('trg_arqueo_estado: tampoco desde la base', sql_en_txn("UPDATE arqueo_caja SET estado='ANULADO' WHERE id_arqueo=%s", (ID_Q1,)) == 'No se puede anular el arqueo: su recaudación ya fue depositada.')
    como(RECEP); api('delete', f'{ARQ}/{Q3["id_arqueo"]}', 403, nombre='sin el permiso "anular" no se anula')
    como(CAJERO)
    d = api('delete', f'{ARQ}/{Q3["id_arqueo"]}', 200, nombre='anular un arqueo con la recaudación PENDIENTE', contiene='anulado correctamente')
    chk('el mensaje avisa que la recaudación también se anuló', 'recaudación a depositar también quedó anulada' in d['mensaje'])
    cu.execute("SELECT q.estado, r.estado FROM arqueo_caja q JOIN recaudacion_depositar r USING(id_arqueo) WHERE q.id_arqueo=%s", (Q3['id_arqueo'],)); chk('arqueo ANULADO y recaudación ANULADA', cu.fetchone() == ('ANULADO', 'ANULADA'))
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='arqueo_caja' AND id_registro=%s AND accion='BAJA'", (Q3['id_arqueo'],)); chk('auditoría BAJA', 'recaudación' in cu.fetchone()[0])
    api('delete', f'{ARQ}/{Q3["id_arqueo"]}', 409, nombre='anular dos veces', exacto='El arqueo ya está anulado.'); api('delete', f'{ARQ}/2147483000', 404, nombre='anular inexistente')
    chk('la apertura A3 vuelve a figurar como pendiente de arqueo', A3 in {x['id_apertura'] for x in api('get', f'{ARQ}/aperturas', 200)['data']})
    chk('la recaudación anulada ya no se puede depositar (otro estado)', sql_en_txn("UPDATE recaudacion_depositar SET estado='DEPOSITADA' WHERE id_arqueo=%s", (Q3['id_arqueo'],)) == 'Una recaudación depositada o anulada no cambia de estado.')
    chk('trg_arqueo_estado: un arqueo anulado no se reactiva', sql_en_txn("UPDATE arqueo_caja SET estado='REGISTRADO' WHERE id_arqueo=%s", (Q3['id_arqueo'],)) == 'Un arqueo anulado no se puede reactivar.')
    como(ADMIN)
    d = arquear(A3, [('EF', 100000), ('CH', 50000)], nombre='la apertura se puede arquear de nuevo tras anular el arqueo'); Q3b = d['data']
    chk('el nuevo arqueo cuadra y genera su recaudación (cheques 50.000)', Q3b['resultado'] == 'CUADRA' and Q3b['recaudacion']['total'] == 50000 and Q3b['id_arqueo'] != Q3['id_arqueo'])
    chk('Apertura de Caja: tiene_arqueo cuenta solo los REGISTRADOS (A3 ahora sí)', {x['id_apertura']: x for x in api('get', APE, 200)['data']}[A3]['tiene_arqueo'] is True)

    # =====================================================================================================================
    # 11. CONCURRENCIA
    # =====================================================================================================================
    res = [None] * 2; barrera = threading.Barrier(2)
    def hilo(i, usuario):
        with app.app_context():
            barrera.wait(); res[i] = ArqueoDao().registrarArqueo(A7, usuario[0], [F['EF']], [200000], None)
    ts = [threading.Thread(target=hilo, args=(0, ADMIN)), threading.Thread(target=hilo, args=(1, CAJERO))]; [t.start() for t in ts]; [t.join(60) for t in ts]
    oks = [r_ for r_ in res if isinstance(r_, tuple) and r_[0] != ERROR_BD]
    chk('concurrencia: 2 arqueos simultáneos de la misma apertura -> exactamente 1 gana', len(oks) == 1 and sum(isinstance(r_, tuple) and r_[0] == ERROR_BD and r_[1] == 'La apertura ya tiene un arqueo registrado.' for r_ in res) == 1)
    chk('concurrencia: queda un solo arqueo REGISTRADO', len(arqueos_de([A7])) == 1)
    d = arquear(A8, [('EF', 200000)], nombre='A8 para la carrera depositar / anular'); Q8 = d['data']; RID8 = Q8['recaudacion']['id_recaudacion']
    res = [None] * 2; barrera = threading.Barrier(2)
    def hilo_dep():
        with app.app_context():
            barrera.wait(); res[0] = ArqueoDao().marcarDepositada(RID8, CTA, 'ZZ-CARRERA', HOY)
    def hilo_anu():
        with app.app_context():
            barrera.wait(); res[1] = ArqueoDao().anularArqueo(Q8['id_arqueo'])
    ts = [threading.Thread(target=hilo_dep), threading.Thread(target=hilo_anu)]; [t.start() for t in ts]; [t.join(60) for t in ts]
    cu.execute("SELECT q.estado, r.estado FROM arqueo_caja q JOIN recaudacion_depositar r USING(id_arqueo) WHERE q.id_arqueo=%s", (Q8['id_arqueo'],)); est = cu.fetchone()
    chk('concurrencia: depositar vs anular -> uno solo gana y los estados quedan coherentes',
        est in (('REGISTRADO', 'DEPOSITADA'), ('ANULADO', 'ANULADA')) and ((res[0] is True and res[1] == RECAUDACION_DEPOSITADA) or (isinstance(res[0], tuple) and res[0][0] == NO_PENDIENTE and isinstance(res[1], dict))))

    # =====================================================================================================================
    # 12. PDF
    # =====================================================================================================================
    como(CAJERO); r = c.get(f'{ARQ}/{Q2["id_arqueo"]}/pdf')
    chk('PDF: 200, application/pdf y empieza con %PDF', r.status_code == 200 and r.mimetype == 'application/pdf' and r.data[:4] == b'%PDF')
    chk('PDF: exactamente 2 páginas (ORIGINAL y DUPLICADO)', paginas_pdf(r.data) == 2)
    txt = texto_pdf(r.data)
    chk('PDF: título, número, caja, cajero y fondo inicial', 'ARQUEO DE CAJA' in txt and f'Arqueo N' in txt and 'ZZ CAJA ARQUEO' in txt and '100.000' in txt)
    chk('PDF: sistema / contado / diferencia por forma y totales', all(x in txt for x in ('ZZ ARQ CHEQUE', '390.000', '400.000', '-10.000', '+10.000')) and 'TOTAL' in txt)
    chk('PDF: resultado, observación y recaudación a depositar', 'Resultado' in txt and 'Faltaron 10.000' in txt and 'RECAUDACI' in txt and '440.000' in txt)
    chk('PDF de un arqueo vigente: sin marca ANULADO', 'ANULADO' not in txt and 'ORIGINAL' in txt and 'DUPLICADO' in txt)
    r = c.get(f'{ARQ}/{Q3["id_arqueo"]}/pdf'); chk('PDF de un arqueo ANULADO: se descarga con la marca', r.status_code == 200 and 'ANULADO' in texto_pdf(r.data))
    r = c.get(f'{ARQ}/{Q4["id_arqueo"]}/pdf'); chk('PDF de un arqueo sin recaudación lo aclara', 'No hay recaudaci' in texto_pdf(r.data))
    r = c.get(f'{ARQ}/{ID_Q1}/pdf'); chk('PDF de una recaudación DEPOSITADA incluye la cuenta y la boleta', 'ZZ-123' in texto_pdf(r.data) and 'ZZ BANCO ARQUEO' in texto_pdf(r.data))
    como(RECEP); api('get', f'{ARQ}/{ID_Q1}/pdf', 403, nombre='PDF sin permiso ver')
    como(ADMIN); api('get', f'{ARQ}/2147483000/pdf', 404, nombre='PDF de un arqueo inexistente')

finally:
    try:
        cu.execute("SELECT id_arqueo FROM arqueo_caja WHERE id_apertura = ANY(%s)", (ids['ap'] or [0],))
        arqs = [r_[0] for r_ in cu.fetchall()]
        if arqs:
            cu.execute("SELECT id_recaudacion FROM recaudacion_depositar WHERE id_arqueo = ANY(%s)", (arqs,))
            recs = [r_[0] for r_ in cu.fetchall()]
            borrar_auditoria(cu, 'recaudacion_depositar', recs)
            cu.execute("DELETE FROM recaudacion_depositar WHERE id_arqueo = ANY(%s)", (arqs,))
            cu.execute("DELETE FROM arqueo_caja WHERE id_arqueo = ANY(%s)", (arqs,))   # cascada: detalle
            borrar_auditoria(cu, 'arqueo_caja', arqs)
        if ids['notas']:
            cu.execute("DELETE FROM nota_credito_debito_cab WHERE id_nota = ANY(%s)", (ids['notas'],))   # cascada: detalle
        if ids['cobros']:
            cu.execute("DELETE FROM cobro_cab WHERE id_cobro = ANY(%s)", (ids['cobros'],))   # cascada: detalle, tarjeta y cheque
        if ids['ventas']:
            cu.execute("DELETE FROM cuenta_cobrar WHERE id_venta = ANY(%s)", (ids['ventas'],))
            cu.execute("DELETE FROM venta_cab WHERE id_venta = ANY(%s)", (ids['ventas'],))
        if ids['ap']:
            borrar_auditoria(cu, 'apertura_cierre_caja', ids['ap'])
            cu.execute("DELETE FROM apertura_cierre_caja WHERE id_apertura = ANY(%s)", (ids['ap'],))
        if ids['caja']:
            cu.execute("DELETE FROM caja WHERE id_caja=%s", (ids['caja'],))
        if ids['cuentas']:
            cu.execute("DELETE FROM cuenta_bancaria WHERE id_cuenta_bancaria = ANY(%s)", (ids['cuentas'],))
        if ids['emisoras']:
            cu.execute("DELETE FROM entidad_emisora WHERE id_entidad_emisora = ANY(%s)", (ids['emisoras'],))
        if ids['formas']:
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
