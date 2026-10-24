"""Registrar Apertura y Cierre de Caja: apertura (con los dos bloqueos de apertura doble), anular, cerrar,
visibilidad por rol, filtros, permisos por acción, auditoría y la baja de Caja bloqueada con una apertura abierta.

Usa usuarios REALES (un Administrador, un Cajero y uno de Recepción) con sesiones simuladas, y cajas de prueba
(prefijo ZZ) que crea y borra. Si alguno de esos usuarios tiene una caja abierta de verdad, aborta sin tocar nada."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from tests.facturacion._limpieza import borrar_auditoria
from datetime import date, timedelta
from unittest import mock
import psycopg2
from app import app
from tests._conexion_pruebas import Conexion
from app.dao.modulo_facturacion.apertura_caja.AperturaCajaDao import AperturaCajaDao
from app.rutas.modulo_facturacion import utils
from app.rutas.modulo_seguridad.menu_catalog import CATALOGO_MENU, MODULOS

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SQL = RAIZ / 'app' / 'dao' / 'modulo_facturacion' / 'schema_apertura_cierre_caja.sql'
c = app.test_client()
fallos = []
MSG_MONTO = 'El monto de apertura debe ser un número entero mayor o igual a 0.'
MSG_USUARIO = 'Debe cerrar la apertura actual antes de abrir una nueva.'
MSG_CAJA = 'La caja ya está abierta por otro usuario.'
MSG_CAJA_INVALIDA = 'La caja seleccionada no existe o está inactiva.'
MSG_MOV = 'La apertura tiene movimientos registrados; debe cerrarse en lugar de anularse.'
MSG_BAJA_CAJA = 'No se puede dar de baja, la caja tiene una apertura activa.'
MSG_PROPIO_ANULAR = 'Solo el cajero que abrió la caja (o un Administrador) puede anular la apertura.'
MSG_PROPIO_CERRAR = 'Solo el cajero que abrió la caja (o un Administrador) puede cerrar la apertura.'

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

AP = '/api/v1/aperturas-caja'
cx = Conexion().getConexion(); cu = cx.cursor()

# ---------- usuarios reales para las sesiones ----------
cu.execute("""SELECT u.id_usuario, r.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol)
              WHERE u.activo ORDER BY u.id_usuario""")
usuarios = cu.fetchall()
def primero(rol):
    return next((u for u in usuarios if u[2] == rol), None)
ADMIN, CAJERO, OTRO = primero('Administrador'), primero('Cajero'), primero('Recepcion')
if not (ADMIN and CAJERO and OTRO):
    print('ABORTADO: se necesitan un usuario Administrador, uno Cajero y uno de Recepción.'); sys.exit(1)
cu.execute("SELECT id_usuario, count(*) FROM apertura_cierre_caja WHERE estado='ABIERTA' AND id_usuario = ANY(%s) GROUP BY 1",
           ([ADMIN[0], CAJERO[0], OTRO[0]],))
reales = cu.fetchall()
if reales:
    print(f'ABORTADO: hay aperturas ABIERTAS reales de los usuarios {reales}; ciérrelas antes de correr este test.'); sys.exit(1)

def como(u):
    with c.session_transaction() as s:
        s['id_usuario'] = u[0]; s['id_rol'] = u[1]; s['nombre_rol'] = u[2]

cajas = {}; aperturas = set(); permisos_agregados = []
cu.execute("SELECT COALESCE(max(id_apertura), 0) FROM apertura_cierre_caja"); ID0 = cu.fetchone()[0]
cu.execute("SELECT codigo FROM consultorio ORDER BY codigo LIMIT 1"); CONSULTORIO = cu.fetchone()[0]

def estado_db(i):
    cu.execute("SELECT estado FROM apertura_cierre_caja WHERE id_apertura=%s", (i,)); return cu.fetchone()[0]

def abrir(u, caja, monto, esperado=201, **kw):
    como(u)
    d = api('post', AP, esperado, {'id_caja': cajas[caja], 'monto_apertura': monto}, kw.pop('nombre', f'abrir {caja} ({u[2]}, {monto})'), **kw)
    if esperado == 201:
        aperturas.add(d['data']['id_apertura'])
    return d

try:
    # ---------- estructura ----------
    cu.execute("SELECT column_name, data_type, numeric_precision, is_nullable FROM information_schema.columns WHERE table_name='apertura_cierre_caja' ORDER BY ordinal_position")
    cols = {r[0]: r[1:] for r in cu.fetchall()}
    chk('tabla: columnas pedidas', list(cols) == ['id_apertura', 'id_caja', 'id_usuario', 'fecha_apertura', 'monto_apertura', 'fecha_cierre', 'total_recaudado', 'monto_cierre', 'estado'])
    chk('tabla: monto_apertura NUMERIC(12,0) NOT NULL; total/cierre NULL', cols['monto_apertura'] == ('numeric', 12, 'NO') and cols['total_recaudado'][2] == 'YES' and cols['monto_cierre'][2] == 'YES' and cols['fecha_cierre'][2] == 'YES')
    cu.execute("SELECT indexname, indexdef FROM pg_indexes WHERE tablename='apertura_cierre_caja' AND indexname LIKE 'ux_%'")
    idx = dict(cu.fetchall())
    chk('índice único PARCIAL por usuario (ABIERTA)', "UNIQUE" in idx.get('ux_apertura_usuario_abierta', '') and "'ABIERTA'" in idx.get('ux_apertura_usuario_abierta', ''))
    chk('índice único PARCIAL por caja (ABIERTA)', "UNIQUE" in idx.get('ux_apertura_caja_abierta', '') and "'ABIERTA'" in idx.get('ux_apertura_caja_abierta', ''))
    cu.execute("SELECT confdeltype FROM pg_constraint WHERE conrelid='apertura_cierre_caja'::regclass AND contype='f'")
    chk('FK a caja y a usuarios con RESTRICT', [r[0] for r in cu.fetchall()] == ['r', 'r'])
    cu.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='auditoria_cambios_accion_check'")
    chk("auditoría admite 'CIERRE'", "'CIERRE'" in cu.fetchone()[0])
    sql = SQL.read_text(encoding='utf-8')
    antes = (cu.execute("SELECT count(*) FROM pg_indexes WHERE tablename='apertura_cierre_caja'") or cu.fetchone()[0])
    cu.execute(sql); cx.commit(); cu.execute(sql); cx.commit()
    cu.execute("SELECT count(*) FROM pg_indexes WHERE tablename='apertura_cierre_caja'")
    chk('la migración es IDEMPOTENTE (re-ejecutada 2 veces: mismos índices, sin errores)', cu.fetchone()[0] == antes)
    cu.execute("SELECT string_agg(accion, ',' ORDER BY accion) FROM permisos p JOIN roles r USING(id_rol) WHERE id_menu = (SELECT id_menu FROM menu WHERE clave='aperturacaja' AND activo = true) AND r.nombre_rol='Cajero'")
    chk('permisos: el Cajero tiene ver, nuevo, anular y estado', cu.fetchone()[0] == 'anular,estado,nuevo,ver')
    cu.execute("SELECT count(*) FROM permisos p JOIN roles r USING(id_rol) WHERE id_menu = (SELECT id_menu FROM menu WHERE clave='aperturacaja' AND activo = true) AND r.nombre_rol='Medico'")
    chk('permisos: el Médico no recibe nada por el seed', cu.fetchone()[0] == 0)
    ent = [e for e in CATALOGO_MENU if e['ventana'] == 'aperturacaja']
    chk('catálogo: "Apertura y Cierre de Caja" en el Módulo Facturación (no en Referenciales) con ver/nuevo/anular/estado',
        len(ent) == 1 and ent[0]['modulo'] == 'Módulo Facturación' and ent[0]['acciones'] == ['ver', 'nuevo', 'anular', 'estado'] and any(m['modulo'] == 'Módulo Facturación' for m in MODULOS))

    # ---------- validador de monto ----------
    vm = utils.validar_monto
    chk('validar_monto: 0 es válido (fondo inicial)', vm(0) == (0, None) and vm('0') == (0, None) and vm('150000') == (150000, None))
    chk('validar_monto: inválidos', all(vm(x)[1] for x in (-1, '-5', 'abc', '', '  ', None, True, False, 1.5, '15.5', 10 ** 12)))
    chk('validar_monto: máximo NUMERIC(12,0)', vm(999_999_999_999)[1] is None)

    # ---------- sin sesión / sin permisos ----------
    api('get', AP, 401, nombre='sin sesión')
    como(OTRO)
    for metodo, url in [('get', AP), ('get', AP + '/actual'), ('get', AP + '/cajas-disponibles'), ('post', AP), ('delete', AP + '/1'), ('get', AP + '/1/cierre'), ('patch', AP + '/1/cerrar')]:
        api(metodo, url, 403, nombre=f'rol sin permisos: {metodo.upper()} {url.replace("/api/v1", "")} -> 403')
    r = c.get('/referenciales/apertura-caja/apertura-caja-index'); chk('rol sin permisos: la vista da 403', r.status_code == 403)

    # cajas de prueba (como Administrador)
    como(ADMIN)
    for k in ('A', 'B', 'C', 'D'):
        d = api('post', '/api/v1/cajas', 201, {'id_consultorio': CONSULTORIO, 'descripcion': f'zz caja ap {k.lower()}'}, f'caja de prueba {k}')
        cajas[k] = d['data']['id_caja']
    api('delete', f"/api/v1/cajas/{cajas['D']}", 200, nombre='caja D anulada (queda inactiva)')

    # a Recepción se le dan permisos SOLO durante el test (para tener un segundo cajero con acceso)
    for acc in ('ver', 'nuevo', 'anular', 'estado'):
        cu.execute("INSERT INTO permisos (id_rol, id_menu, accion) SELECT %s, id_menu, %s FROM menu WHERE clave='aperturacaja' AND activo = true ON CONFLICT DO NOTHING RETURNING accion", (OTRO[1], acc))
        if cu.fetchone():
            permisos_agregados.append(acc)
    cx.commit()

    # ---------- APERTURA: validaciones ----------
    como(CAJERO)
    d = api('get', AP + '/cajas-disponibles', 200, nombre='cajas disponibles (Cajero)')
    ids = {x['id_caja'] for x in d['data']}
    chk('disponibles: trae las activas sin abrir (A, B, C) con su consultorio y NO la inactiva (D)',
        {cajas['A'], cajas['B'], cajas['C']} <= ids and cajas['D'] not in ids and all(x['consultorio'] for x in d['data']))
    api('post', AP, 400, {'monto_apertura': 0}, 'abrir sin caja', exacto='Debe seleccionar una caja.', campo='id_caja')
    api('post', AP, 400, {'id_caja': 'abc', 'monto_apertura': 0}, 'abrir con caja no numérica', campo='id_caja')
    api('post', AP, 400, {'id_caja': 999999, 'monto_apertura': 0}, 'abrir caja inexistente', exacto=MSG_CAJA_INVALIDA, campo='id_caja')
    api('post', AP, 400, {'id_caja': cajas['D'], 'monto_apertura': 0}, 'abrir caja INACTIVA', exacto=MSG_CAJA_INVALIDA, campo='id_caja')
    for malo in [-1, '-5', 'abc', '', '  ', None, True, 1.5, '15.5', 10 ** 12]:
        api('post', AP, 400, {'id_caja': cajas['A'], 'monto_apertura': malo}, f'abrir con monto inválido {malo!r}', exacto=MSG_MONTO, campo='monto_apertura')
    api('post', AP, 400, {'id_caja': cajas['A']}, 'abrir sin la clave monto_apertura', exacto=MSG_MONTO, campo='monto_apertura')
    cu.execute("SELECT count(*) FROM apertura_cierre_caja WHERE id_apertura > %s", (ID0,)); chk('ninguna apertura inválida creó filas', cu.fetchone()[0] == 0)

    # ---------- APERTURA: alta y cajero tomado de la sesión ----------
    como(CAJERO)
    d = api('post', AP, 201, {'id_caja': cajas['A'], 'monto_apertura': 0, 'id_usuario': ADMIN[0]}, 'abrir caja A con fondo 0 (y un id_usuario falso en el cuerpo)')
    a = d['data']['id_apertura']; aperturas.add(a)
    chk('el cajero sale de la SESIÓN, no del cuerpo', d['data']['id_usuario'] == CAJERO[0] and d['data']['cajero'])
    chk('apertura: ABIERTA, fecha_apertura puesta, sin cierre ni totales, con caja y consultorio',
        d['data']['estado'] == 'ABIERTA' and d['data']['fecha_apertura'] and d['data']['fecha_cierre'] is None and d['data']['total_recaudado'] is None
        and d['data']['monto_cierre'] is None and d['data']['monto_apertura'] == 0 and d['data']['caja'] == 'ZZ CAJA AP A' and d['data']['consultorio'])
    d = api('get', AP + '/actual', 200, nombre='actual (Cajero)'); chk('actual: es la A', d['data']['id_apertura'] == a)
    d = api('get', AP + '/cajas-disponibles', 200, nombre='disponibles tras abrir'); chk('A ya no está disponible', cajas['A'] not in {x['id_caja'] for x in d['data']})

    # ---------- LOS DOS BLOQUEOS DE APERTURA DOBLE ----------
    abrir(CAJERO, 'B', 1000, 409, exacto=MSG_USUARIO, nombre='BLOQUEO 1: el mismo cajero abre OTRA caja')
    abrir(CAJERO, 'A', 1000, 409, exacto=MSG_USUARIO, nombre='BLOQUEO 1: el mismo cajero abre la MISMA caja otra vez')
    abrir(OTRO, 'A', 1000, 409, exacto=MSG_CAJA, campo='id_caja', nombre='BLOQUEO 2: otro cajero abre la caja ya abierta')
    cu.execute("SELECT count(*) FROM apertura_cierre_caja WHERE id_apertura > %s", (ID0,)); chk('los bloqueos no crearon filas (solo la A)', cu.fetchone()[0] == 1)
    # y la base los garantiza aunque se salte la aplicación
    for uid, caja, idx_esperado in [(OTRO[0], cajas['A'], 'ux_apertura_caja_abierta'), (CAJERO[0], cajas['B'], 'ux_apertura_usuario_abierta')]:
        try:
            cu.execute("INSERT INTO apertura_cierre_caja(id_caja, id_usuario, monto_apertura) VALUES (%s,%s,0)", (caja, uid)); cx.commit()
            chk(f'la BASE rechaza el INSERT duplicado ({idx_esperado})', False)
        except psycopg2.errors.UniqueViolation as e:
            cx.rollback(); chk(f'la BASE rechaza el INSERT duplicado ({idx_esperado})', e.diag.constraint_name == idx_esperado)
    como(CAJERO)
    abrir(OTRO, 'B', 150000, nombre='otro cajero (Recepción) abre la caja B con 150.000')
    b = max(aperturas)

    # ---------- LISTADO: visibilidad por rol y filtros ----------
    como(CAJERO); d = api('get', AP, 200, nombre='listado del Cajero')
    chk('el Cajero ve SOLO las propias', d['data'] and all(x['id_usuario'] == CAJERO[0] for x in d['data']) and a in {x['id_apertura'] for x in d['data']})
    como(OTRO); d = api('get', AP, 200, nombre='listado de Recepción')
    chk('Recepción ve SOLO las propias', all(x['id_usuario'] == OTRO[0] for x in d['data']) and b in {x['id_apertura'] for x in d['data']} and a not in {x['id_apertura'] for x in d['data']})
    como(ADMIN); d = api('get', AP, 200, nombre='listado del Administrador')
    vistas = {x['id_apertura'] for x in d['data']}
    chk('el Administrador ve TODAS (la A del Cajero y la B de Recepción)', {a, b} <= vistas)
    fila = [x for x in d['data'] if x['id_apertura'] == a][0]
    chk('el listado trae caja, consultorio, cajero, fechas, montos y estado', all(k in fila for k in ('caja', 'consultorio', 'cajero', 'fecha_apertura', 'fecha_cierre', 'monto_apertura', 'monto_cierre', 'estado')))
    d = api('get', AP + '/actual', 200, nombre='actual del Administrador'); chk('el Administrador no tiene caja abierta: data = null', d['data'] is None)
    d = api('get', AP + '?estado=ABIERTA', 200, nombre='filtro estado=ABIERTA'); chk('filtro por estado', all(x['estado'] == 'ABIERTA' for x in d['data']) and {a, b} <= {x['id_apertura'] for x in d['data']})
    d = api('get', AP + '?estado=cerrada', 200, nombre='filtro estado en minúsculas'); chk('estado CERRADA no trae las abiertas', a not in {x['id_apertura'] for x in d['data']})
    api('get', AP + '?estado=XYZ', 400, nombre='estado inválido', exacto='El estado debe ser ABIERTA, CERRADA o ANULADA.')
    hoy = date.today(); ayer = hoy - timedelta(days=1); manana = hoy + timedelta(days=1)
    d = api('get', f'{AP}?desde={hoy}&hasta={hoy}', 200, nombre='fechas desde=hasta=hoy'); chk('hoy incluye las de hoy (hasta inclusivo)', {a, b} <= {x['id_apertura'] for x in d['data']})
    d = api('get', f'{AP}?hasta={ayer}', 200, nombre='hasta=ayer'); chk('hasta=ayer no trae las de hoy', not ({a, b} & {x['id_apertura'] for x in d['data']}))
    d = api('get', f'{AP}?desde={manana}', 200, nombre='desde=mañana'); chk('desde=mañana no trae nada de hoy', not ({a, b} & {x['id_apertura'] for x in d['data']}))
    api('get', f'{AP}?desde=2026-13-45', 400, nombre='fecha con formato inválido', exacto='Las fechas deben tener el formato AAAA-MM-DD.')
    api('get', f'{AP}?desde={hoy}&hasta={ayer}', 400, nombre='desde posterior a hasta', exacto='La fecha "desde" no puede ser posterior a "hasta".')

    # ---------- BAJA DE CAJA con apertura abierta ----------
    como(ADMIN)
    api('delete', f"/api/v1/cajas/{cajas['A']}", 409, nombre='baja de la caja A (abierta) BLOQUEADA', exacto=MSG_BAJA_CAJA)
    cu.execute("SELECT activo FROM caja WHERE id_caja=%s", (cajas['A'],)); chk('la caja A sigue activa', cu.fetchone()[0] is True)

    # ---------- ANULAR ----------
    como(CAJERO)
    api('delete', f'{AP}/{b}', 403, nombre='el Cajero NO puede anular la apertura de otro', exacto=MSG_PROPIO_ANULAR)
    chk('...y la ajena sigue ABIERTA', estado_db(b) == 'ABIERTA')
    como(OTRO)
    with mock.patch.object(AperturaCajaDao, '_motivo_con_movimientos', return_value=MSG_MOV):
        api('delete', f'{AP}/{b}', 409, nombre='anular con movimientos registrados BLOQUEADO', exacto=MSG_MOV)
    chk('...y la apertura sigue ABIERTA', estado_db(b) == 'ABIERTA')
    d = api('delete', f'{AP}/{b}', 200, nombre='el dueño anula su apertura', contiene='anulada')
    chk('anulada: estado ANULADA', d['data']['estado'] == 'ANULADA' and estado_db(b) == 'ANULADA')
    api('delete', f'{AP}/{b}', 409, nombre='anular una ya anulada', exacto='La apertura ya no está abierta (estado: ANULADA).')
    api('get', f'{AP}/{b}/cierre', 409, nombre='el detalle de cierre de una anulada', exacto='La apertura ya no está abierta (estado: ANULADA).')
    api('delete', f'{AP}/999999', 404, nombre='anular una inexistente')
    d = api('get', AP + '/cajas-disponibles', 200, nombre='disponibles tras anular'); chk('la caja B queda libre', cajas['B'] in {x['id_caja'] for x in d['data']})
    abrir(OTRO, 'C', 20000, nombre='Recepción abre la caja C')
    cc = max(aperturas)
    como(ADMIN)
    d = api('delete', f'{AP}/{cc}', 200, nombre='el Administrador anula la apertura de OTRO cajero')
    chk('...queda ANULADA', estado_db(cc) == 'ANULADA')
    como(CAJERO)
    api('delete', f"{AP}/{a}", 403, nombre='(control) anular sin ser dueño ni admin', exacto=MSG_PROPIO_ANULAR) if False else None

    # ---------- CIERRE ----------
    como(OTRO)
    api('get', f'{AP}/{a}/cierre', 403, nombre='detalle de cierre de la apertura de OTRO', exacto=MSG_PROPIO_CERRAR)
    api('patch', f'{AP}/{a}/cerrar', 403, nombre='cerrar la apertura de OTRO cajero', exacto=MSG_PROPIO_CERRAR)
    chk('...sigue ABIERTA', estado_db(a) == 'ABIERTA')
    como(CAJERO)
    d = api('get', f'{AP}/{a}/cierre', 200, nombre='detalle de cierre (fondo 0)')
    chk('detalle: apertura 0 + recaudado 0 = cierre 0, con caja, consultorio y cajero',
        (d['data']['monto_apertura'], d['data']['total_recaudado'], d['data']['monto_cierre']) == (0, 0, 0) and d['data']['caja'] and d['data']['consultorio'] and d['data']['cajero'])
    cu.execute("SELECT estado, fecha_cierre FROM apertura_cierre_caja WHERE id_apertura=%s", (a,)); chk('ver el detalle NO cierra nada', cu.fetchone() == ('ABIERTA', None))
    d = api('patch', f'{AP}/{a}/cerrar', 200, {'monto_cierre': 999999, 'total_recaudado': 999999}, 'cerrar (con importes falsos en el cuerpo)', contiene='cerrada')
    cu.execute("SELECT estado, fecha_cierre IS NOT NULL, total_recaudado, monto_cierre, monto_apertura FROM apertura_cierre_caja WHERE id_apertura=%s", (a,))
    chk('cerrada: CERRADA, fecha_cierre puesta, total 0 y cierre = apertura (los importes del cliente se ignoran)', cu.fetchone() == ('CERRADA', True, 0, 0, 0))
    chk('la respuesta trae la apertura cerrada', d['data']['estado'] == 'CERRADA' and d['data']['monto_cierre'] == 0)
    api('patch', f'{AP}/{a}/cerrar', 409, nombre='cerrar una ya cerrada', exacto='La apertura ya no está abierta (estado: CERRADA).')
    api('delete', f'{AP}/{a}', 409, nombre='anular una ya cerrada', exacto='La apertura ya no está abierta (estado: CERRADA).')
    api('patch', f'{AP}/999999/cerrar', 404, nombre='cerrar una inexistente')
    d = api('get', AP + '/actual', 200, nombre='actual tras cerrar'); chk('ya no tiene caja abierta', d['data'] is None)
    d = api('get', AP + '/cajas-disponibles', 200, nombre='disponibles tras cerrar'); chk('la caja A vuelve a estar disponible', cajas['A'] in {x['id_caja'] for x in d['data']})

    # el fondo suma al cierre; el total recaudado (hoy 0) también cuando exista
    d = abrir(CAJERO, 'A', 150000, nombre='el Cajero abre de nuevo (ya cerró la anterior) con 150.000'); a2 = d['data']['id_apertura']
    d = api('get', f'{AP}/{a2}/cierre', 200, nombre='detalle: fondo 150.000'); chk('150.000 + 0 = 150.000', (d['data']['monto_apertura'], d['data']['total_recaudado'], d['data']['monto_cierre']) == (150000, 0, 150000))
    # Desde Cobranzas el cierre suma solo el EFECTIVO: se simulan 250.000 recaudados, todos en efectivo.
    with mock.patch.object(AperturaCajaDao, '_total_recaudado', return_value=250000), mock.patch.object(AperturaCajaDao, '_total_efectivo', return_value=250000):
        d = api('get', f'{AP}/{a2}/cierre', 200, nombre='detalle con 250.000 recaudados (simulado)')
        chk('apertura + recaudado = cierre: 150.000 + 250.000 = 400.000', (d['data']['monto_apertura'], d['data']['total_recaudado'], d['data']['monto_cierre']) == (150000, 250000, 400000))
        como(ADMIN)
        d = api('patch', f'{AP}/{a2}/cerrar', 200, nombre='el Administrador cierra la apertura del Cajero (con 250.000 simulados)')
    cu.execute("SELECT total_recaudado, monto_cierre, estado FROM apertura_cierre_caja WHERE id_apertura=%s", (a2,)); chk('guardado: total 250.000, cierre 400.000, CERRADA', cu.fetchone() == (250000, 400000, 'CERRADA'))
    chk('el mensaje informa el monto de cierre', 'Gs. 400.000' in d['mensaje'])

    # ---------- BAJA DE CAJA: permitida con la apertura cerrada o anulada ----------
    como(ADMIN)
    api('delete', f"/api/v1/cajas/{cajas['C']}", 200, nombre='baja de la caja C (su apertura está ANULADA)')
    api('delete', f"/api/v1/cajas/{cajas['A']}", 200, nombre='baja de la caja A (sus aperturas están CERRADAS)')
    abrir(CAJERO, 'B', 5000, nombre='abre B para el control de la baja'); b2 = max(aperturas)
    como(ADMIN)  # el Cajero ya no puede anular cajas (solo ver); la baja la hace el Administrador
    api('delete', f"/api/v1/cajas/{cajas['B']}", 409, nombre='baja de B con apertura ABIERTA otra vez bloqueada', exacto=MSG_BAJA_CAJA)
    como(CAJERO); api('patch', f'{AP}/{b2}/cerrar', 200, nombre='cierra B')
    como(ADMIN); api('delete', f"/api/v1/cajas/{cajas['B']}", 200, nombre='y ahora la baja de B sí se permite')
    como(CAJERO); api('post', AP, 400, {'id_caja': cajas['A'], 'monto_apertura': 0}, 'no se puede abrir una caja ya anulada', exacto=MSG_CAJA_INVALIDA, campo='id_caja')

    # ---------- AUDITORÍA ----------
    def aud(i):
        cu.execute("SELECT accion, id_usuario, ip, detalle FROM auditoria_cambios WHERE entidad='apertura_cierre_caja' AND id_registro=%s ORDER BY id_auditoria_cambio", (i,)); return cu.fetchall()
    x = aud(a)
    chk('auditoría de A: ALTA y CIERRE', [r[0] for r in x] == ['ALTA', 'CIERRE'])
    chk('ALTA registra caja, consultorio, cajero y monto', 'Caja: ZZ CAJA AP A' in x[0][3] and 'Consultorio:' in x[0][3] and 'Cajero:' in x[0][3] and 'Monto de apertura: Gs. 0' in x[0][3])
    chk('CIERRE registra apertura, recaudado y cierre', 'Monto de apertura: Gs. 0' in x[1][3] and 'Total recaudado: Gs. 0' in x[1][3] and 'Monto de cierre: Gs. 0' in x[1][3])
    chk('auditoría: usuario e IP de la sesión (el Cajero)', all(r[1] == CAJERO[0] and r[2] == '127.0.0.1' for r in x))
    x = aud(b)
    chk('auditoría de B: ALTA (por Recepción) y BAJA', [r[0] for r in x] == ['ALTA', 'BAJA'] and all(r[1] == OTRO[0] for r in x))
    x = aud(cc)
    chk('auditoría de C: ALTA (Recepción) y BAJA hecha por el ADMINISTRADOR', [r[0] for r in x] == ['ALTA', 'BAJA'] and x[0][1] == OTRO[0] and x[1][1] == ADMIN[0])
    x = aud(a2)
    chk('auditoría de A2: el cierre lo hizo el Administrador y registra 250.000 / 400.000', x[-1][0] == 'CIERRE' and x[-1][1] == ADMIN[0] and 'Total recaudado: Gs. 250.000' in x[-1][3] and 'Monto de cierre: Gs. 400.000' in x[-1][3])
    cu.execute("SELECT count(*) FROM auditoria_cambios WHERE entidad='apertura_cierre_caja' AND id_registro = ANY(%s)", (list(aperturas),))
    chk('los intentos rechazados NO se auditan (solo hechos consumados)', cu.fetchone()[0] == 2 * len(aperturas))   # cada apertura finalizada: ALTA + (BAJA o CIERRE)

    # ---------- PERMISOS POR ACCIÓN (Cajero) ----------
    cu.execute("SELECT accion FROM permisos WHERE id_menu = (SELECT id_menu FROM menu WHERE clave='aperturacaja' AND activo = true) AND id_rol=%s", (CAJERO[1],)); tenia = [r[0] for r in cu.fetchall()]
    def sin_permiso(acc):
        cu.execute("DELETE FROM permisos WHERE id_menu = (SELECT id_menu FROM menu WHERE clave='aperturacaja' AND activo = true) AND id_rol=%s AND accion=%s", (CAJERO[1], acc)); cx.commit()
    def con_permiso(acc):
        cu.execute("INSERT INTO permisos (id_rol, id_menu, accion) SELECT %s, id_menu, %s FROM menu WHERE clave='aperturacaja' AND activo = true ON CONFLICT DO NOTHING", (CAJERO[1], acc)); cx.commit()
    try:
        como(ADMIN)
        k = abrir(OTRO, 'A', 0, 409, nombre='(control) la caja A ya no está activa', exacto=MSG_CAJA_INVALIDA) if False else None
        # caja nueva para este bloque
        como(ADMIN); cz = api('post', '/api/v1/cajas', 201, {'id_consultorio': CONSULTORIO, 'descripcion': 'zz caja ap e'}, 'caja E')['data']['id_caja']; cajas['E'] = cz
        como(CAJERO)
        sin_permiso('nuevo'); api('post', AP, 403, {'id_caja': cz, 'monto_apertura': 0}, 'Cajero SIN "nuevo" no abre'); api('get', AP + '/cajas-disponibles', 403, nombre='...ni ve las cajas disponibles'); con_permiso('nuevo')
        e = abrir(CAJERO, 'E', 0, nombre='con "nuevo" abre la caja E')['data']['id_apertura']
        sin_permiso('estado'); api('get', f'{AP}/{e}/cierre', 403, nombre='Cajero SIN "estado" no ve el cierre'); api('patch', f'{AP}/{e}/cerrar', 403, nombre='...ni cierra'); con_permiso('estado')
        sin_permiso('anular'); api('delete', f'{AP}/{e}', 403, nombre='Cajero SIN "anular" no anula'); con_permiso('anular')
        sin_permiso('ver'); api('get', AP, 403, nombre='Cajero SIN "ver" no lista'); api('get', AP + '/actual', 403, nombre='...ni ve su estado'); r = c.get('/referenciales/apertura-caja/apertura-caja-index'); chk('...ni abre la vista', r.status_code == 403); con_permiso('ver')
        r = c.get('/referenciales/apertura-caja/apertura-caja-index')
        chk('con todos los permisos la vista carga (tarjeta de estado, filtros, helper y validadores)',
            r.status_code == 200 and b'tarjetaEstado' in r.data and b'filtroEstado' in r.data and b'filtroDesde' in r.data and b'filtroHasta' in r.data
            and b'facturacion-listado.js' in r.data and b'facturacion-validadores.js' in r.data)
        chk('la vista ofrece Abrir / Cerrar / Anular y el detalle del cierre', b'Abrir Caja' in r.data and b'Cerrar Caja' in r.data and b'Anular Apertura' in r.data and b'Confirmar cierre' in r.data)
        chk('el menú muestra "Apertura y Cierre de Caja" bajo "Facturación"', b'Apertura y Cierre de Caja' in r.data)
        como(CAJERO); api('patch', f'{AP}/{e}/cerrar', 200, nombre='cierra E')
    finally:
        for acc in ('ver', 'nuevo', 'anular', 'estado'):
            if acc in tenia:
                con_permiso(acc)
finally:
    # limpieza acotada a lo creado por este test (aperturas -> auditoría -> cajas -> permisos agregados)
    cx.rollback()
    cu.execute("SELECT id_apertura FROM apertura_cierre_caja WHERE id_apertura > %s AND id_caja = ANY(%s)", (ID0, list(cajas.values())))
    todas = set(aperturas) | {r[0] for r in cu.fetchall()}
    if todas:
        borrar_auditoria(cu, 'apertura_cierre_caja', list(todas))
        cu.execute("DELETE FROM apertura_cierre_caja WHERE id_apertura = ANY(%s)", (list(todas),))
    if cajas:
        borrar_auditoria(cu, 'caja', list(cajas.values()))
        cu.execute("DELETE FROM caja WHERE id_caja = ANY(%s)", (list(cajas.values()),))
    for acc in permisos_agregados:
        cu.execute("DELETE FROM permisos WHERE id_menu = (SELECT id_menu FROM menu WHERE clave='aperturacaja' AND activo = true) AND id_rol=%s AND accion=%s", (OTRO[1], acc))
    cx.commit(); cu.close(); cx.close()
print('FALLOS:', fallos or 'ninguno')
