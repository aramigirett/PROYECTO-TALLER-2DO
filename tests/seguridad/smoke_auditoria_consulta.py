"""Etapa C (Rúbrica 9, Auditoría): columnas nuevas de auditoria_cambios (modulo, valores_anteriores / valores_nuevos JSONB, detalle TEXT) con
comentarios, trigger de inmutabilidad y permisos de odontoclinic_app (solo SELECT / INSERT) intactos; registro estructurado (solo lo que cambió,
estado en BAJA / REACTIVACION, módulo, texto sin cortar); parser para filas viejas; pantalla Auditoría de Cambios (solo Administrador, filtros,
paginación, orden, detalle campo / anterior / nuevo, solo lectura, buscador); exportación a PDF y CSV con filtros, tope de filas con aviso y auditoría
de cada exportación; vista v_auditoria_anomalias con sus umbrales configurables y las alertas del API; Tablero de Accesos (Tabler, exportación,
enlace cruzado). Datos de prueba: filas de auditoría con entidad `zz_*` / ids altos y la auditoría que el propio test genera, que borra POR ID
(saltando el trigger solo en su conexión)."""
import csv, datetime, io, pathlib, sys, time
RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import psycopg2
from app import app
from app.conexion.Conexion import Conexion as ConexionApp
from tests._conexion_pruebas import Conexion
from tests.facturacion._pdf import paginas_pdf, texto_pdf
from app.Services import auditoria_detalle as ad
from app.rutas.modulo_facturacion.utils import auditar, detalle_cambios
from app.rutas.modulo_seguridad import auditoria_cambios_api as cambios_api
from app.rutas.modulo_seguridad.menu_catalog import CATALOGO_MENU, VENTANAS_SOLO_ADMIN

fallos = []
c = app.test_client()
API = '/api/v1/auditoria-cambios'


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


cx = Conexion().getConexion(); cx.autocommit = True; cu = cx.cursor()
cu.execute("SELECT COALESCE(MAX(id_auditoria_cambio), 0) FROM auditoria_cambios"); BASE = cu.fetchone()[0]
cu.execute("SELECT u.id_usuario, r.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.activo ORDER BY 1")
usuarios = cu.fetchall()
ADMIN = next((u for u in usuarios if u[2] == 'Administrador'), None)
CAJERO = next((u for u in usuarios if u[2] == 'Cajero'), None)
RECEP = next((u for u in usuarios if u[2] == 'Recepcion'), None)
if not (ADMIN and CAJERO and RECEP):
    print('ABORTADO: se necesitan un Administrador, un Cajero y uno de Recepción.'); sys.exit(1)
cu.execute("SELECT max_bajas_dia, max_reactivaciones, dias_reactivaciones, hora_inicio, hora_fin, ultimo_dia_laboral, ventana_alertas_dias FROM auditoria_umbrales")
UMBRALES_ORIGINALES = cu.fetchone()
creados = []     # id_auditoria_cambio de las filas de prueba insertadas a mano


def como(u):
    with c.session_transaction() as s:
        s.clear()
        if u:
            s['id_usuario'] = u[0]; s['id_rol'] = u[1]; s['nombre_rol'] = u[2]; s['nombre_completo'] = 'USUARIO PRUEBA'


def ins(entidad, id_registro, accion='ALTA', detalle='', cuando=None, usuario=None, modulo=None, anteriores=None, nuevos=None):
    """Inserta una fila de auditoría de prueba como postgres (no pasa por la app) y devuelve su id."""
    import json
    cu.execute("""INSERT INTO auditoria_cambios (fecha_hora, id_usuario, entidad, id_registro, accion, detalle, ip, modulo, valores_anteriores, valores_nuevos)
                  VALUES (COALESCE(%s, NOW()), %s, %s, %s, %s, %s, '127.0.0.1', %s, %s::jsonb, %s::jsonb) RETURNING id_auditoria_cambio""",
               (cuando, (usuario or ADMIN)[0], entidad, id_registro, accion, detalle, modulo,
                json.dumps(anteriores) if anteriores is not None else None, json.dumps(nuevos) if nuevos is not None else None))
    i = cu.fetchone()[0]
    creados.append(i)
    return i


def ultima_fila(entidad, id_registro):
    cu.execute("""SELECT id_auditoria_cambio, modulo, valores_anteriores, valores_nuevos, detalle, accion, id_usuario, ip FROM auditoria_cambios
                  WHERE id_auditoria_cambio > %s AND entidad = %s AND id_registro = %s ORDER BY 1 DESC LIMIT 1""", (BASE, entidad, id_registro))
    r = cu.fetchone()
    if r:
        creados.append(r[0])
    return r


def get(url):
    r = c.get(url)
    return r, (r.get_json(silent=True) or {})


def dias_libres(cantidad):
    """Fechas de los últimos 28 días sin ninguna fila de auditoría (más recientes primero), para probar las alertas sin mezclar datos reales."""
    cu.execute("SELECT DISTINCT fecha_hora::date FROM auditoria_cambios WHERE fecha_hora >= CURRENT_DATE - 28")
    ocupados = {r[0] for r in cu.fetchall()}
    hoy = datetime.date.today()
    return [d for d in (hoy - datetime.timedelta(days=i) for i in range(1, 28)) if d not in ocupados][:cantidad]


try:
    # =========================================================================================================================
    # 1. ESQUEMA: columnas, comentarios, trigger de inmutabilidad y permisos de la app
    # =========================================================================================================================
    cu.execute("""SELECT column_name, data_type, character_maximum_length, is_nullable FROM information_schema.columns
                  WHERE table_name = 'auditoria_cambios' AND column_name IN ('modulo', 'valores_anteriores', 'valores_nuevos', 'detalle')""")
    cols = {r[0]: r[1:] for r in cu.fetchall()}
    chk('modulo es VARCHAR(30) NULL', cols.get('modulo') == ('character varying', 30, 'YES'))
    chk('valores_anteriores y valores_nuevos son JSONB NULL', cols.get('valores_anteriores', ('',))[0] == 'jsonb' and cols.get('valores_nuevos', ('',))[0] == 'jsonb'
        and cols['valores_anteriores'][2] == 'YES' and cols['valores_nuevos'][2] == 'YES')
    chk('detalle pasó a TEXT', cols.get('detalle', ('',))[0] == 'text')
    cu.execute("""SELECT a.attname FROM pg_description d JOIN pg_attribute a ON a.attrelid = d.objoid AND a.attnum = d.objsubid
                  WHERE d.objoid = 'auditoria_cambios'::regclass AND a.attname IN ('modulo', 'valores_anteriores', 'valores_nuevos', 'detalle')""")
    chk('COMMENT ON en las columnas nuevas y en detalle', {r[0] for r in cu.fetchall()} == {'modulo', 'valores_anteriores', 'valores_nuevos', 'detalle'})
    cu.execute("SELECT obj_description('v_auditoria_anomalias'::regclass), obj_description('auditoria_umbrales'::regclass)")
    chk('COMMENT ON la vista y la tabla de umbrales', all(cu.fetchone()))
    cu.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'auditoria_cambios'::regclass AND contype = 'c' AND conname = 'auditoria_cambios_accion_check'")
    definicion = cu.fetchone()[0]
    chk('el CHECK de acción admite EXPORTACION y conserva las anteriores', all(a in definicion for a in ('EXPORTACION', 'CIERRE', 'REACTIVACION')))
    cu.execute("SELECT * FROM auditoria_umbrales")
    chk('umbrales por defecto: 5 bajas, 3 reactivaciones en 30 días, 07:00 a 20:00, lunes a sábado',
        (UMBRALES_ORIGINALES[0], UMBRALES_ORIGINALES[1], UMBRALES_ORIGINALES[2], str(UMBRALES_ORIGINALES[3])[:5], str(UMBRALES_ORIGINALES[4])[:5], UMBRALES_ORIGINALES[5])
        == (5, 3, 30, '07:00', '20:00', 6))
    cu.execute("SELECT count(*) FROM menu WHERE clave = 'auditoriacambios' AND activo = true")
    chk('fila en la tabla menu', cu.fetchone()[0] == 1)
    cu.execute("SELECT count(*) FROM permisos WHERE id_menu = (SELECT id_menu FROM menu WHERE clave='auditoriacambios' AND activo = true)")
    chk('ningún rol tiene permisos sobre la ventana (solo Administrador)', cu.fetchone()[0] == 0)

    # La aplicación (odontoclinic_app): sigue pudiendo insertar y leer con las columnas nuevas, pero no UPDATE / DELETE, ni cambiar umbrales
    capp = ConexionApp().getConexion(); capp.autocommit = True; ka = capp.cursor()
    ka.execute("SELECT current_user"); chk('la app se conecta como odontoclinic_app', ka.fetchone()[0] == 'odontoclinic_app')
    ka.execute("""INSERT INTO auditoria_cambios (id_usuario, entidad, id_registro, accion, detalle, ip, modulo, valores_anteriores, valores_nuevos)
                  VALUES (%s, 'zz_permisos', 1, 'ALTA', 'x', '127.0.0.1', 'Módulo Seguridad', NULL, '{"a": 1}'::jsonb) RETURNING id_auditoria_cambio""", (ADMIN[0],))
    creados.append(ka.fetchone()[0])
    chk('la app inserta con las columnas nuevas', True)
    ka.execute("SELECT modulo, valores_nuevos FROM auditoria_cambios WHERE id_auditoria_cambio = %s", (creados[-1],))
    chk('la app lee el JSONB como dict', ka.fetchone() == ('Módulo Seguridad', {'a': 1}))
    for sentencia, nombre in (("UPDATE auditoria_cambios SET modulo = 'x' WHERE id_auditoria_cambio = %s", 'UPDATE de la auditoría'),
                              ("UPDATE auditoria_cambios SET valores_nuevos = '{}'::jsonb WHERE id_auditoria_cambio = %s", 'UPDATE de las columnas nuevas'),
                              ("DELETE FROM auditoria_cambios WHERE id_auditoria_cambio = %s", 'DELETE de la auditoría')):
        try:
            ka.execute(sentencia, (creados[-1],)); chk(f'la app NO puede {nombre}', False)
        except psycopg2.errors.InsufficientPrivilege:
            chk(f'la app NO puede {nombre} (permiso denegado)', True)
    for sentencia, nombre in (("UPDATE auditoria_umbrales SET max_bajas_dia = 99", 'cambiar los umbrales'),
                              ("INSERT INTO auditoria_umbrales (id_umbral) VALUES (2)", 'insertar umbrales'),
                              ("DELETE FROM auditoria_umbrales", 'borrar los umbrales')):
        try:
            ka.execute(sentencia); chk(f'la app NO puede {nombre}', False)
        except psycopg2.errors.InsufficientPrivilege:
            chk(f'la app NO puede {nombre} (solo lectura)', True)
    ka.execute("SELECT count(*) FROM auditoria_umbrales"); chk('la app lee los umbrales', ka.fetchone()[0] == 1)
    ka.execute("SELECT count(*) FROM v_auditoria_anomalias"); chk('la app lee la vista de anomalías', ka.fetchone()[0] >= 0)
    for sentencia, nombre in (("UPDATE auditoria_cambios SET modulo = 'x' WHERE id_auditoria_cambio = %s", 'UPDATE'),
                              ("DELETE FROM auditoria_cambios WHERE id_auditoria_cambio = %s", 'DELETE')):
        try:
            cu.execute(sentencia, (creados[-1],)); chk(f'el trigger rechaza {nombre} aun como postgres', False)
        except psycopg2.Error as e:
            chk(f'el trigger rechaza {nombre} aun como postgres', 'no se pueden modificar ni eliminar' in str(e))
    ka.close(); capp.close()

    # =========================================================================================================================
    # 2. SERVICIO PURO: módulo, parser, estado, filas
    # =========================================================================================================================
    chk('módulo de las entidades', ad.modulo_de('venta_cab') == 'Módulo Facturación' and ad.modulo_de('caja') == 'Referenciales Facturación'
        and ad.modulo_de('backup') == 'Módulo Seguridad' and ad.modulo_de('desconocida') is None)
    chk('todos los módulos entran en VARCHAR(30)', all(len(m) <= 30 for m in ad.MODULOS))
    chk('parser ALTA', ad.parsear_detalle('Descripción: X; Tipo: EFECTIVO', 'ALTA') == ({}, {'Descripción': 'X', 'Tipo': 'EFECTIVO'}))
    chk('parser MODIFICACION', ad.parsear_detalle('Teléfono: 1 -> 2; Correo: a -> b', 'MODIFICACION') == ({'Teléfono': '1', 'Correo': 'a'}, {'Teléfono': '2', 'Correo': 'b'}))
    chk('parser: modificación con un segmento sin flecha -> None', ad.parsear_detalle('Teléfono: 1 -> 2; algo suelto', 'MODIFICACION') is None)
    chk('parser: texto libre / vacío / BAJA / recortado con "..." -> None',
        ad.parsear_detalle('Copia x.dump (1 MB)', 'ALTA') is None and ad.parsear_detalle('', 'ALTA') is None
        and ad.parsear_detalle('Descripción: X', 'BAJA') is None and ad.parsear_detalle('A: 1; B: 2...', 'ALTA') is None)
    chk('parser: campo repetido -> None', ad.parsear_detalle('A: 1; A: 2', 'ALTA') is None)
    chk('estado de BAJA: catálogo = Inactivo, movimiento = Anulado',
        ad.estado_de_accion('BAJA', 'caja') == ({'Estado': 'Activo'}, {'Estado': 'Inactivo'}) and ad.estado_de_accion('BAJA', 'venta_cab')[1] == {'Estado': 'Anulado'})
    chk('estado de REACTIVACION y CIERRE', ad.estado_de_accion('REACTIVACION', 'caja') == ({'Estado': 'Inactivo'}, {'Estado': 'Activo'})
        and ad.estado_de_accion('CIERRE', 'apertura_cierre_caja') == ({'Estado': 'Abierta'}, {'Estado': 'Cerrada'}) and ad.estado_de_accion('ALTA', 'caja') == (None, None))
    f, t = ad.filas_detalle({'accion': 'MODIFICACION', 'entidad': 'caja', 'detalle': 'texto', 'valores_anteriores': {'A': 1}, 'valores_nuevos': {'A': 2, 'B': 'x'}})
    chk('filas desde el JSON (anterior vacío donde no hay)', f == [{'campo': 'A', 'anterior': '1', 'nuevo': '2'}, {'campo': 'B', 'anterior': '', 'nuevo': 'x'}] and not t)
    f, t = ad.filas_detalle({'accion': 'MODIFICACION', 'entidad': 'caja', 'detalle': 'Teléfono: 1 -> 2', 'valores_anteriores': None, 'valores_nuevos': None})
    chk('filas de una fila vieja: salen del texto', f == [{'campo': 'Teléfono', 'anterior': '1', 'nuevo': '2'}])
    f, t = ad.filas_detalle({'accion': 'BAJA', 'entidad': 'caja', 'detalle': 'Descripción: CAJA', 'valores_anteriores': None, 'valores_nuevos': None})
    chk('fila vieja de BAJA: Estado + el texto', f == [{'campo': 'Estado', 'anterior': 'Activo', 'nuevo': 'Inactivo'}] and t)
    f, t = ad.filas_detalle({'accion': 'EXPORTACION', 'entidad': 'auditoria_cambios', 'detalle': 'CSV; 3 filas', 'valores_anteriores': None, 'valores_nuevos': None})
    chk('texto que no se puede separar -> una fila "Detalle"', f == [{'campo': 'Detalle', 'anterior': '', 'nuevo': 'CSV; 3 filas'}])
    chk('BAJA se muestra como "Baja / Anulación"', ad.etiqueta_accion('BAJA') == 'Baja / Anulación' and ad.etiqueta_accion('ALTA') == 'Alta')

    # =========================================================================================================================
    # 3. REGISTRO ESTRUCTURADO (utils.auditar + detalle_cambios) sin tocar las APIs
    # =========================================================================================================================
    ID_A = 987654100
    with app.test_request_context('/', environ_base={'REMOTE_ADDR': '127.0.0.1'}):
        from flask import session
        session['id_usuario'] = ADMIN[0]
        et = {'tel': 'Teléfono', 'mail': 'Correo', 'ok': 'Activo'}
        auditar('cliente', ID_A, 'MODIFICACION', detalle_cambios({'tel': '1', 'mail': 'a', 'ok': True}, {'tel': '2', 'mail': 'a', 'ok': False}, et))
        auditar('cliente', ID_A + 1, 'ALTA', detalle_cambios({}, {'tel': '1', 'mail': 'a', 'ok': True}, et))
        auditar('caja', ID_A + 2, 'BAJA', 'Descripción: CAJA X')
        auditar('venta_cab', ID_A + 3, 'BAJA', 'Factura 001-001-0000001')
        auditar('caja', ID_A + 4, 'REACTIVACION', 'Descripción: CAJA X')
        auditar('apertura_cierre_caja', ID_A + 5, 'CIERRE', 'Cierre de prueba')
        auditar('marca_tarjeta', ID_A + 6, 'MODIFICACION', 'Descripción: VISA -> VISA 2')           # texto armado a mano
        auditar('backup', ID_A + 7, 'ALTA', 'Copia odontosisbd_x.dump (1 MB)')                         # no se puede separar
        auditar('cliente', ID_A + 8, 'MODIFICACION', detalle_cambios({'tel': '1'}, {'tel': '1'}, {'tel': 'Teléfono'}))   # sin cambios
        auditar('cliente', ID_A + 9, 'ALTA', 'Nota: ' + 'X' * 600)
        auditar('entidad_rara', ID_A + 10, 'ALTA', 'Algo: 1')
    r = ultima_fila('cliente', ID_A)
    chk('MODIFICACION: módulo, solo lo que cambió (no el Correo) y bool como Sí/No', r and r[1] == 'Referenciales Facturación' and r[2] == {'Teléfono': '1', 'Activo': 'Sí'} and r[3] == {'Teléfono': '2', 'Activo': 'No'})
    chk('MODIFICACION: usuario e IP del request', r and r[6] == ADMIN[0] and r[7] == '127.0.0.1')
    r = ultima_fila('cliente', ID_A + 1)
    chk('ALTA: solo valores nuevos (anteriores NULL)', r and r[2] is None and r[3] == {'Teléfono': '1', 'Correo': 'a', 'Activo': 'Sí'})
    r = ultima_fila('caja', ID_A + 2); chk('BAJA de catálogo: Activo -> Inactivo', r and r[2] == {'Estado': 'Activo'} and r[3] == {'Estado': 'Inactivo'})
    r = ultima_fila('venta_cab', ID_A + 3); chk('BAJA de movimiento: Activo -> Anulado, módulo Facturación', r and r[3] == {'Estado': 'Anulado'} and r[1] == 'Módulo Facturación')
    r = ultima_fila('caja', ID_A + 4); chk('REACTIVACION: Inactivo -> Activo', r and r[2] == {'Estado': 'Inactivo'} and r[3] == {'Estado': 'Activo'})
    r = ultima_fila('apertura_cierre_caja', ID_A + 5); chk('CIERRE: Abierta -> Cerrada', r and r[2] == {'Estado': 'Abierta'} and r[3] == {'Estado': 'Cerrada'})
    r = ultima_fila('marca_tarjeta', ID_A + 6); chk('texto armado a mano: se separa con el parser', r and r[2] == {'Descripción': 'VISA'} and r[3] == {'Descripción': 'VISA 2'})
    r = ultima_fila('backup', ID_A + 7); chk('texto que no se puede separar: JSON NULL, módulo Seguridad', r and r[2] is None and r[3] is None and r[1] == 'Módulo Seguridad')
    r = ultima_fila('cliente', ID_A + 8); chk('edición sin cambios: JSON NULL (no inventa campos)', r and r[2] is None and r[3] is None)
    r = ultima_fila('cliente', ID_A + 9); chk('el detalle ya no se corta a 255 caracteres', r and len(r[4]) == len('Nota: ') + 600)
    r = ultima_fila('entidad_rara', ID_A + 10); chk('entidad fuera del mapa: modulo NULL, se muestra como "Otro"', r and r[1] is None)

    # =========================================================================================================================
    # 4. PANTALLA Y API: solo Administrador, filtros, paginación, orden, detalle, solo lectura
    # =========================================================================================================================
    como(None)
    r, d = get(API); chk('sin sesión -> 401 en el API', r.status_code == 401)
    r = c.get('/referenciales/auditoria-cambios/auditoria-cambios-index'); chk('sin sesión la vista redirige al login', r.status_code == 302)
    for u, nombre in ((CAJERO, 'Cajero'), (RECEP, 'Recepción')):
        como(u)
        for url in (API, API + '/filtros', API + '/alertas', API + '/1', API + '/exportar?formato=csv'):
            chk(f'{nombre}: {url} -> 403', get(url)[0].status_code == 403)
        chk(f'{nombre}: la vista -> 403', c.get('/referenciales/auditoria-cambios/auditoria-cambios-index').status_code == 403)
        chk(f'{nombre}: el buscador no la ofrece', not any(x['etiqueta'] == 'Auditoría de Cambios' for x in get('/api/v1/menu/buscar?q=audit')[1]['data']))
    como(ADMIN)
    r = c.get('/referenciales/auditoria-cambios/auditoria-cambios-index'); html = r.get_data(as_text=True)
    chk('Administrador: la vista abre en Tabler (base_tabler)', r.status_code == 200 and 'tabler.min.css' in html and 'bootstrap.min.css' not in html)
    chk('la vista tiene filtros, alertas con badge, exportación y enlace al Tablero', all(x in html for x in ('id="fUsuario"', 'id="fModulo"', 'id="fEntidad"', 'id="fAccion"', 'id="badgeAlertas"', 'id="btnPdf"', 'id="btnCsv"', 'auditoria-index')))
    chk('la vista arranca con los últimos 7 días', 'setDate(hoy.getDate() - 6)' in html)
    chk('el sidebar del Administrador incluye la pantalla', 'Auditoría de Cambios' in html and 'auditoria-cambios-index' in html)
    chk('el buscador general la encuentra (por "cambios" y por "auditoria")',
        all(any(x['etiqueta'] == 'Auditoría de Cambios' for x in get(f'/api/v1/menu/buscar?q={q}')[1]['data']) for q in ('cambios', 'auditoria')))
    ent = next(i for i in CATALOGO_MENU if i['ventana'] == 'auditoriacambios')
    chk('catálogo: solo_admin, solo "ver", en el módulo Seguridad', ent.get('solo_admin') and ent['acciones'] == ['ver'] and ent['modulo'] == 'Módulo Seguridad' and 'auditoriacambios' in VENTANAS_SOLO_ADMIN)

    # Datos propios para filtros y paginación (entidad zz_pag, 30 filas con fecha distinta, y una fila vieja sin JSON)
    hoy = datetime.datetime.now()
    for i in range(30):
        ins('zz_pag', 5000 + i, 'ALTA', ' '.join(f'Campo{j}: valor largo de prueba {i}-{j}' for j in range(1, 8)) + '; x', cuando=hoy - datetime.timedelta(seconds=i + 1))
    id_viejo = ins('cliente', 987654001, 'MODIFICACION', 'Teléfono: 111 -> 222; Correo: a@x -> b@x', cuando=hoy - datetime.timedelta(seconds=60))
    id_viejo_baja = ins('caja', 987654002, 'BAJA', 'Descripción: CAJA VIEJA', cuando=hoy - datetime.timedelta(seconds=61))
    id_json = ins('cliente', 987654003, 'MODIFICACION', 'Teléfono: 1 -> 2', cuando=hoy - datetime.timedelta(seconds=62), modulo='Referenciales Facturación',
                  anteriores={'Teléfono': '1'}, nuevos={'Teléfono': '2'})
    hoy_s, ayer_s = hoy.date().isoformat(), (hoy.date() - datetime.timedelta(days=1)).isoformat()

    r, d = get(f'{API}?entidad=zz_pag&por_pagina=10')
    chk('paginación: total 30, 3 páginas, 10 filas', d.get('total') == 30 and d.get('paginas') == 3 and len(d['data']) == 10)
    r, d3 = get(f'{API}?entidad=zz_pag&por_pagina=10&pagina=3')
    chk('página 3: 10 filas y sin repetir las de la 1', len(d3['data']) == 10 and not {x['id_registro'] for x in d3['data']} & {x['id_registro'] for x in d['data']})
    chk('orden: del más reciente al más antiguo', [x['fecha_hora'] for x in d['data']] == sorted((x['fecha_hora'] for x in d['data']), reverse=True) and d['data'][0]['id_registro'] == 5000)
    chk('cada fila trae fecha, usuario, IP, módulo, entidad, id y acción', all(k in d['data'][0] for k in ('fecha_hora', 'usuario', 'ip', 'modulo', 'entidad', 'entidad_etiqueta', 'id_registro', 'accion', 'accion_etiqueta')))
    chk('módulo "Otro" para una entidad desconocida', d['data'][0]['modulo'] == 'Otro')
    chk('por_pagina se limita a 100', get(f'{API}?por_pagina=5000')[1]['por_pagina'] == 100)
    r, d = get(f'{API}?entidad=zz_pag&accion=ALTA'); chk('filtro por acción', d['total'] == 30)
    r, d = get(f'{API}?entidad=zz_pag&accion=BAJA'); chk('filtro por acción sin coincidencias', d['total'] == 0 and d['data'] == [])
    r, d = get(f'{API}?entidad=zz_pag&id_registro=5003'); chk('filtro por N.º de registro', d['total'] == 1 and d['data'][0]['id_registro'] == 5003)
    r, d = get(f'{API}?entidad=zz_pag&id_usuario={ADMIN[0]}'); chk('filtro por usuario', d['total'] == 30)
    r, d = get(f'{API}?entidad=zz_pag&id_usuario={CAJERO[0]}'); chk('filtro por otro usuario -> 0', d['total'] == 0)
    r, d = get(f'{API}?entidad=zz_pag&desde={hoy_s}&hasta={hoy_s}'); chk('filtro de fechas (hasta inclusivo)', d['total'] == 30)
    r, d = get(f'{API}?entidad=zz_pag&desde={ayer_s}&hasta={ayer_s}'); chk('filtro de fechas fuera de rango -> 0', d['total'] == 0)
    r, d = get(f'{API}?modulo=Referenciales Facturación&entidad=cliente&id_registro=987654001')
    chk('filtro por módulo alcanza también las filas viejas (modulo NULL)', d['total'] == 1)
    r, d = get(f'{API}?modulo=Módulo Facturación&entidad=cliente&id_registro=987654001'); chk('filtro por otro módulo las excluye', d['total'] == 0)
    for url in (f'{API}?desde=2026-13-01', f'{API}?desde=2026-10-10&hasta=2026-10-01', f'{API}?accion=BORRAR', f'{API}?modulo=Otro', f'{API}?entidad=a;b',
                f'{API}?id_usuario=abc', f'{API}?id_registro=-1'):
        chk(f'400 con filtros inválidos: {url}', get(url)[0].status_code == 400)
    r, d = get(API + '/filtros')
    chk('opciones de filtro: usuarios, 7 módulos, entidades con etiqueta y las 6 acciones',
        r.status_code == 200 and any(u['id_usuario'] == ADMIN[0] for u in d['data']['usuarios']) and len(d['data']['modulos']) == 7
        and {'valor': 'venta_cab', 'etiqueta': 'Venta'} in d['data']['entidades'] and len(d['data']['acciones']) == 6)
    chk('la acción BAJA se ofrece como "Baja / Anulación"', {'valor': 'BAJA', 'etiqueta': 'Baja / Anulación'} in d['data']['acciones'])

    r, d = get(f'{API}/{id_json}')
    chk('detalle desde el JSON: campo / anterior / nuevo', d['data']['campos'] == [{'campo': 'Teléfono', 'anterior': '1', 'nuevo': '2'}] and 'valores_nuevos' not in d['data'])
    r, d = get(f'{API}/{id_viejo}')
    chk('detalle de una fila vieja: lo arma el parser', d['data']['campos'] == [{'campo': 'Teléfono', 'anterior': '111', 'nuevo': '222'}, {'campo': 'Correo', 'anterior': 'a@x', 'nuevo': 'b@x'}]
        and d['data']['modulo'] == 'Referenciales Facturación' and d['data']['entidad_etiqueta'] == 'Cliente')
    r, d = get(f'{API}/{id_viejo_baja}')
    chk('detalle de una BAJA vieja: Estado y "Baja / Anulación"', d['data']['campos'] == [{'campo': 'Estado', 'anterior': 'Activo', 'nuevo': 'Inactivo'}]
        and d['data']['accion_etiqueta'] == 'Baja / Anulación' and d['data']['mostrar_texto'] and d['data']['detalle'] == 'Descripción: CAJA VIEJA')
    chk('detalle inexistente -> 404', get(f'{API}/2147483000')[0].status_code == 404)
    for m in ('post', 'put', 'delete', 'patch'):
        for url in (API, f'{API}/{id_json}', f'{API}/alertas', f'{API}/exportar'):
            chk(f'solo lectura: {m.upper()} {url} -> 405', getattr(c, m)(url, json={}).status_code == 405)
    cu.execute("SELECT count(*) FROM auditoria_cambios WHERE id_auditoria_cambio = ANY(%s)", ([id_json, id_viejo],))
    chk('ninguna llamada modificó ni borró los registros', cu.fetchone()[0] == 2)

    # =========================================================================================================================
    # 5. EXPORTACIÓN a PDF y CSV
    # =========================================================================================================================
    filtro = f'entidad=zz_pag&desde={hoy_s}&hasta={hoy_s}&accion=ALTA'
    cu.execute("SELECT count(*) FROM auditoria_cambios WHERE id_auditoria_cambio > %s AND accion = 'EXPORTACION'", (BASE,)); antes = cu.fetchone()[0]
    r = c.get(f'{API}/exportar?formato=pdf&{filtro}')
    chk('PDF: 200, application/pdf y empieza con %PDF', r.status_code == 200 and r.mimetype == 'application/pdf' and r.data[:4] == b'%PDF')
    t = texto_pdf(r.data); t = t if isinstance(t, str) else t.decode('latin-1', 'ignore')
    chk('PDF: empresa, título, filtros aplicados, fecha de emisión y usuario que lo genera',
        'ODONTOCLINIC' in t and 'DE CAMBIOS' in t and 'Filtros aplicados' in t and 'zz_pag' in t and 'Emitido el' in t and 'USUARIO PRUEBA' in t)
    chk('PDF: 30 filas largas ocupan más de una página', paginas_pdf(r.data) >= 2)
    chk('PDF: muestra "Alta" (acción legible)', 'Alta' in t)
    r = c.get(f'{API}/exportar?formato=csv&{filtro}')
    cuerpo = r.data
    chk('CSV: 200, text/csv, adjunto y BOM UTF-8', r.status_code == 200 and r.mimetype == 'text/csv' and 'attachment' in r.headers['Content-Disposition'] and cuerpo[:3] == b'\xef\xbb\xbf')
    filas = list(csv.reader(io.StringIO(cuerpo.decode('utf-8-sig')), delimiter=';'))
    enc = next(i for i, f in enumerate(filas) if f and f[0] == 'Fecha y hora')
    chk('CSV: filtros aplicados, emitido por y 30 filas de datos', any(f[:2] == ['Filtro', 'Entidad'] for f in filas) and any('USUARIO PRUEBA' in f for f in filas[:3]) and len(filas) - enc - 1 == 30)
    chk('CSV: columnas fecha, usuario, IP, módulo, entidad, ID, acción, detalle', filas[enc] == ['Fecha y hora', 'Usuario', 'IP', 'Módulo', 'Entidad', 'ID', 'Acción', 'Detalle'])
    chk('CSV: solo las filas del filtro', all(f[4] == 'zz_pag' for f in filas[enc + 1:]))
    r = c.get(f'{API}/exportar?formato=csv&entidad=caja&id_registro=987654002&desde={hoy_s}&hasta={hoy_s}')
    filas = list(csv.reader(io.StringIO(r.data.decode('utf-8-sig')), delimiter=';'))
    chk('CSV: la BAJA se exporta como "Baja / Anulación"', any(len(f) > 6 and f[6] == 'Baja / Anulación' for f in filas))
    ins('zz_csv', 1, 'ALTA', '=HYPERLINK("http://x")', cuando=hoy)
    r = c.get(f'{API}/exportar?formato=csv&entidad=zz_csv')
    chk('CSV: un texto que empieza con "=" no se interpreta como fórmula', "'=HYPERLINK" in r.data.decode('utf-8-sig'))
    cambios_api.TOPE_EXPORTACION = 7
    try:
        r = c.get(f'{API}/exportar?formato=csv&{filtro}')
        filas = list(csv.reader(io.StringIO(r.data.decode('utf-8-sig')), delimiter=';'))
        enc = next(i for i, f in enumerate(filas) if f and f[0] == 'Fecha y hora')
        chk('tope: solo 7 filas y aviso con el total', len(filas) - enc - 1 == 7 and any(f[0] == 'Aviso' and '30' in f[1] and '7' in f[1] for f in filas))
        rp = c.get(f'{API}/exportar?formato=pdf&{filtro}'); tp = texto_pdf(rp.data); tp = tp if isinstance(tp, str) else tp.decode('latin-1', 'ignore')
        chk('tope: el PDF también avisa', 'acote las fechas' in tp)
    finally:
        cambios_api.TOPE_EXPORTACION = 5000
    chk('formato inválido -> 400', c.get(f'{API}/exportar?formato=xls').status_code == 400 and c.get(f'{API}/exportar').status_code == 400)
    chk('filtros inválidos en la exportación -> 400', c.get(f'{API}/exportar?formato=csv&desde=ayer').status_code == 400
        and c.get(f'{API}/exportar?formato=csv&desde=2026-10-10&hasta=2026-10-01').status_code == 400)
    cu.execute("""SELECT entidad, accion, modulo, id_usuario, detalle FROM auditoria_cambios WHERE id_auditoria_cambio > %s AND accion = 'EXPORTACION'
                  AND entidad = 'auditoria_cambios' ORDER BY id_auditoria_cambio""", (BASE,))
    exp = cu.fetchall()
    chk('cada exportación válida quedó auditada (EXPORTACION, módulo Seguridad, usuario)', len(exp) >= 5 and all(e[2] == 'Módulo Seguridad' and e[3] == ADMIN[0] for e in exp))
    chk('la auditoría de la exportación dice formato, filas y filtros', any(e[4].startswith('PDF; 30 filas') and 'Entidad: zz_pag' in e[4] for e in exp) and any(e[4].startswith('CSV; 7 filas de 30') for e in exp))
    cu.execute("SELECT count(*) FROM auditoria_cambios WHERE id_auditoria_cambio > %s AND accion = 'EXPORTACION'", (BASE,))
    chk('una exportación rechazada (400) no deja auditoría', cu.fetchone()[0] - antes == len(exp))

    # =========================================================================================================================
    # 6. ALERTAS: v_auditoria_anomalias y sus umbrales
    # =========================================================================================================================
    libres = dias_libres(6)
    if len(libres) < 6:
        print('AVISO: no hay 6 días libres en la ventana; se omiten las pruebas de horario.')
    else:
        def dia_laboral(d):
            return d.weekday() <= 5
        laborales = [d for d in libres if dia_laboral(d)]
        domingos = [d for d in (datetime.date.today() - datetime.timedelta(days=i) for i in range(1, 28)) if d.weekday() == 6 and d in set(dias_libres(28))]
        a = lambda d, hh, mm=0: datetime.datetime(d.year, d.month, d.day, hh, mm)
        if len(laborales) >= 5 and domingos:
            d_ok, d_antes, d_desde, d_dentro, d_exp = laborales[:5]
            ins('zz_alerta', 1, 'ALTA', 'x', cuando=a(d_ok, 10))                  # dentro de horario
            ins('zz_alerta', 2, 'ALTA', 'x', cuando=a(d_antes, 6, 59))            # 1 minuto antes
            ins('zz_alerta', 3, 'ALTA', 'x', cuando=a(d_desde, 20, 0))            # 20:00 exacto: fuera (hora_fin exclusiva)
            ins('zz_alerta', 4, 'ALTA', 'x', cuando=a(d_dentro, 7, 0))            # 07:00 exacto: dentro (hora_inicio inclusiva)
            ins('zz_alerta', 5, 'EXPORTACION', 'x', cuando=a(d_exp, 23))          # una exportación nunca es "fuera de horario"
            ins('zz_alerta', 6, 'ALTA', 'x', cuando=a(domingos[0], 11))           # domingo
            cu.execute("SELECT tipo, fecha_desde, cantidad, id_usuario, usuario FROM v_auditoria_anomalias WHERE tipo = 'FUERA_DE_HORARIO'")
            fuera = {(r[1]): r for r in cu.fetchall()}
            chk('fuera de horario: 06:59 alerta', d_antes in fuera)
            chk('fuera de horario: 20:00 alerta (hora_fin exclusiva)', d_desde in fuera)
            chk('fuera de horario: domingo alerta', domingos[0] in fuera)
            chk('fuera de horario: 10:00 y 07:00 NO alertan', d_ok not in fuera and d_dentro not in fuera)
            chk('fuera de horario: una EXPORTACION de madrugada NO alerta', d_exp not in fuera)
            chk('la alerta trae usuario y cantidad', fuera[d_antes][3] == ADMIN[0] and fuera[d_antes][2] == 1 and fuera[d_antes][4])
        # Bajas: 5 en un día alertan; 4 no
        if len(laborales) >= 7 or True:
            libres_b = [d for d in dias_libres(28) if d.weekday() <= 5 and d not in (laborales[:5] if len(laborales) >= 5 else [])][:2]
            if len(libres_b) == 2:
                for i in range(5):
                    ins('zz_alerta', 100 + i, 'BAJA', 'x', cuando=a(libres_b[0], 10, i))
                for i in range(4):
                    ins('zz_alerta', 200 + i, 'BAJA', 'x', cuando=a(libres_b[1], 10, i))
                cu.execute("SELECT fecha_desde, cantidad, accion FROM v_auditoria_anomalias WHERE tipo = 'BAJAS_EN_EL_DIA'")
                bajas = {r[0]: r for r in cu.fetchall()}
                chk('bajas: 5 en un día alertan (umbral 5)', libres_b[0] in bajas and bajas[libres_b[0]][1] == 5 and bajas[libres_b[0]][2] == 'BAJA')
                chk('bajas: 4 en un día NO alertan', libres_b[1] not in bajas)
                cu.execute("UPDATE auditoria_umbrales SET max_bajas_dia = 4")
                cu.execute("SELECT count(*) FROM v_auditoria_anomalias WHERE tipo = 'BAJAS_EN_EL_DIA' AND fecha_desde = %s", (libres_b[1],))
                chk('umbral configurable: con max_bajas_dia = 4 el día de 4 bajas alerta', cu.fetchone()[0] == 1)
                cu.execute("UPDATE auditoria_umbrales SET max_bajas_dia = %s", (UMBRALES_ORIGINALES[0],))
    # Reactivaciones repetidas del mismo registro
    for i in range(3):
        ins('zz_alerta', 900, 'REACTIVACION', 'x', cuando=hoy - datetime.timedelta(minutes=i))
    for i in range(2):
        ins('zz_alerta', 901, 'REACTIVACION', 'x', cuando=hoy - datetime.timedelta(minutes=i))
    cu.execute("SELECT id_registro, cantidad, entidad, accion, id_usuario FROM v_auditoria_anomalias WHERE tipo = 'REACTIVACIONES_REPETIDAS' AND entidad = 'zz_alerta'")
    rea = {r[0]: r for r in cu.fetchall()}
    chk('reactivaciones: 3 del mismo registro alertan (umbral 3)', 900 in rea and rea[900][1] == 3 and rea[900][3] == 'REACTIVACION' and rea[900][4] == ADMIN[0])
    chk('reactivaciones: 2 NO alertan', 901 not in rea)
    cu.execute("UPDATE auditoria_umbrales SET max_reactivaciones = 2")
    cu.execute("SELECT count(*) FROM v_auditoria_anomalias WHERE tipo = 'REACTIVACIONES_REPETIDAS' AND id_registro = 901")
    chk('umbral configurable: con max_reactivaciones = 2 alertan las 2', cu.fetchone()[0] == 1)
    cu.execute("UPDATE auditoria_umbrales SET max_reactivaciones = %s", (UMBRALES_ORIGINALES[1],))
    cu.execute("SELECT max_bajas_dia, max_reactivaciones FROM auditoria_umbrales"); chk('umbrales restaurados', cu.fetchone() == UMBRALES_ORIGINALES[:2])

    r, d = get(API + '/alertas')
    al = [x for x in d['data'] if x.get('entidad') == 'zz_alerta' and x['id_registro'] == 900]
    chk('API de alertas: 200 y trae la alerta con tipo, descripción, rango de fechas, usuario y cantidad',
        r.status_code == 200 and al and al[0]['tipo'] == 'REACTIVACIONES_REPETIDAS' and al[0]['cantidad'] == 3 and al[0]['descripcion'] and al[0]['desde'] and al[0]['hasta'] and 'usuario' in al[0])
    # cada alerta lleva al listado ya filtrado: con sus propios datos como filtro, el listado devuelve (al menos) las filas que la dispararon
    r, d2 = get(f"{API}?entidad={al[0]['entidad']}&id_registro={al[0]['id_registro']}&accion={al[0]['accion']}&desde={al[0]['desde']}&hasta={al[0]['hasta']}")
    chk('el filtro de la alerta devuelve las 3 reactivaciones', d2['total'] == 3)
    baja_al = [x for x in d['data'] if x['tipo'] == 'BAJAS_EN_EL_DIA' and x['cantidad'] >= 5]
    if baja_al:
        b = baja_al[0]
        r, d2 = get(f"{API}?id_usuario={b['id_usuario']}&accion={b['accion']}&desde={b['desde']}&hasta={b['hasta']}")
        chk('el filtro de una alerta de bajas devuelve al menos las bajas que la dispararon', d2['total'] >= b['cantidad'])
    chk('el HTML de la pantalla arma ese filtro (aplicarAlerta) y el chip del registro', 'aplicarAlerta' in html and 'chipRegistro' in html)

    # =========================================================================================================================
    # 7. TABLERO DE ACCESOS: Tabler, mismo filtro de fechas, exportación y enlace cruzado
    # =========================================================================================================================
    TAB = '/referenciales/auditoria/auditoria-index'
    r = c.get(TAB); h = r.get_data(as_text=True)
    chk('Tablero: abre en Tabler con filtro de fechas, resultado, PDF, CSV y enlace a Auditoría de Cambios',
        r.status_code == 200 and 'tabler.min.css' in h and all(x in h for x in ('id="fDesde"', 'id="fHasta"', 'id="fResultado"', 'id="btnPdf"', 'id="btnCsv"', 'auditoria-cambios-index')))
    chk('Auditoría de Cambios enlaza al Tablero y el Tablero a Auditoría de Cambios', 'auditoria/auditoria-index' in html and 'auditoria-cambios/auditoria-cambios-index' in h)
    chk('el Tablero ya no usa SB Admin 2 (jQuery / DataTables)', 'DataTable' not in h and 'jquery' not in h.lower())
    chk('el enlace cruzado lleva las fechas elegidas', 'URLSearchParams' in h and 'URLSearchParams' in html)
    como(CAJERO); chk('Tablero: un rol sin permiso -> 403', c.get(TAB).status_code == 403 and c.get('/api/v1/auditoria/intentos/exportar?formato=csv').status_code == 403)
    como(ADMIN)
    cu.execute("SELECT count(*) FROM auditoria_acceso WHERE fecha_hora >= %s::date AND fecha_hora < %s::date + 1", (hoy_s, hoy_s)); n_hoy = cu.fetchone()[0]
    r = c.get(f'/api/v1/auditoria/intentos/exportar?formato=pdf&desde={hoy_s}&hasta={hoy_s}&resultado=EXITOSO')
    tp = texto_pdf(r.data); tp = tp if isinstance(tp, str) else tp.decode('latin-1', 'ignore')
    chk('Tablero PDF: empresa, título, filtros, emisión y usuario', r.status_code == 200 and r.data[:4] == b'%PDF' and 'ODONTOCLINIC' in tp and 'TABLERO DE ACCESOS' in tp
        and 'Filtros aplicados' in tp and 'EXITOSO' in tp and 'Emitido el' in tp and 'USUARIO PRUEBA' in tp)
    r = c.get(f'/api/v1/auditoria/intentos/exportar?formato=csv&desde={hoy_s}&hasta={hoy_s}')
    filas = list(csv.reader(io.StringIO(r.data.decode('utf-8-sig')), delimiter=';'))
    enc = next(i for i, f in enumerate(filas) if f and f[0] == 'Fecha y hora')
    chk('Tablero CSV: BOM, filtros, columnas y todas las filas del día', r.data[:3] == b'\xef\xbb\xbf' and any(f[:2] == ['Filtro', 'Período'] for f in filas)
        and filas[enc] == ['Fecha y hora', 'CI/RUC ingresado', 'Acción', 'Resultado', 'IP', 'País', 'Realizado por'] and len(filas) - enc - 1 == n_hoy)
    chk('Tablero: formato o fechas inválidas -> 400', c.get('/api/v1/auditoria/intentos/exportar?formato=doc').status_code == 400
        and c.get('/api/v1/auditoria/intentos/exportar?formato=csv&desde=x').status_code == 400
        and c.get('/api/v1/auditoria/intentos/exportar?formato=csv&desde=2026-10-10&hasta=2026-10-01').status_code == 400
        and c.get('/api/v1/auditoria/intentos/exportar?formato=csv&resultado=a b').status_code == 400)
    cu.execute("""SELECT detalle, modulo FROM auditoria_cambios WHERE id_auditoria_cambio > %s AND accion = 'EXPORTACION' AND entidad = 'auditoria_acceso' ORDER BY id_auditoria_cambio""", (BASE,))
    ea = cu.fetchall()
    print('   exportaciones del Tablero:', ea)
    chk('cada exportación del Tablero queda auditada', len(ea) == 2 and ea[0][0].startswith('PDF;') and ea[1][0].startswith('CSV;') and 'Resultado: EXITOSO' in ea[0][0] and all(e[1] == 'Módulo Seguridad' for e in ea))
    r, d = get('/api/v1/auditoria/intentos?limite=5')
    chk('el API del Tablero sigue igual (regresión)', r.status_code == 200 and isinstance(d['data'], list) and len(d['data']) <= 5)

finally:
    # Limpieza: SOLO lo creado por este test, por ID. Las exportaciones que generó el test son las nuevas de EXPORTACION de ese usuario/IP.
    cu.execute("""SELECT id_auditoria_cambio FROM auditoria_cambios WHERE id_auditoria_cambio > %s AND accion = 'EXPORTACION' AND id_usuario = %s
                  AND ip = '127.0.0.1' AND entidad IN ('auditoria_cambios', 'auditoria_acceso')""", (BASE, ADMIN[0]))
    ids = set(creados) | {r[0] for r in cu.fetchall()}
    cu.execute("UPDATE auditoria_umbrales SET max_bajas_dia = %s, max_reactivaciones = %s", (UMBRALES_ORIGINALES[0], UMBRALES_ORIGINALES[1]))
    cu.execute("SET session_replication_role = replica")
    cu.execute("DELETE FROM auditoria_cambios WHERE id_auditoria_cambio = ANY(%s)", (list(ids),))
    borradas = cu.rowcount
    cu.execute("RESET session_replication_role")
    print(f'(limpieza: {borradas} filas de auditoría de prueba borradas por ID)')
    cu.close(); cx.close()

print('FALLOS:', 'ninguno' if not fallos else fallos)
