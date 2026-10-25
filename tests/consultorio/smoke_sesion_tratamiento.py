"""Etapa 5 (commit 1): Sesiones de tratamiento (procedimientos e insumos utilizados) — cada sesión se registra dentro de una consulta (también posterior a la
que creó el tratamiento: varias visitas), mismo paciente y médico, solo el médico de la consulta con la consulta abierta (revalidado en la transacción),
uno o más procedimientos y cero o más insumos sin repetir, anular solo la última (cascada; el tratamiento vuelve a pendiente), privacidad de las lecturas,
los objetos de la base y la auditoría sin contenido clínico. Datos `ZZ` de tests/consultorio/_fixtures.py (se borran por ID con su auditoría).
"""
import datetime
import sys
import threading
import time
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from app import app
from tests._conexion_pruebas import Conexion
from tests.consultorio._fixtures import Fixtures

fallos = []


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


cx = Conexion().getConexion(); cu = cx.cursor()
fx = Fixtures(cx)


def q(sql, p=()):
    cu.execute(sql, p)
    return cu.fetchall()


def cliente(id_usuario):
    c = app.test_client()
    id_rol, nombre = q("SELECT u.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.id_usuario=%s", (id_usuario,))[0]
    with c.session_transaction() as s:
        s['id_usuario'] = id_usuario; s['id_rol'] = id_rol; s['nombre_rol'] = nombre
    return c


def llamar(c, metodo, url, esperado, json=None, nombre=None, contiene=None, campo=None):
    r = getattr(c, metodo)(url, json=json) if json is not None else getattr(c, metodo)(url)
    d = r.get_json(silent=True) or {}
    ok = r.status_code == esperado
    texto = d.get('error') or d.get('mensaje') or ''
    if contiene is not None:
        ok = ok and contiene in texto
    if campo is not None:
        ok = ok and d.get('campo') == campo
    chk(f"{nombre or metodo.upper() + ' ' + url} -> {r.status_code}" + ('' if ok else f' {d}'), ok)
    return d


URL = '/api/v1/sesiones-tratamiento'
URL_T = '/api/v1/tratamientos'
SECRETO = 'RESERVADO-SE-3377'
HOY = datetime.date.today()
sesiones = []

try:
    f_rec, u_rec = fx.recepcion()
    med, u_med = fx.medico()
    med2, u_med2 = fx.medico()
    pac, pac2, cons = fx.paciente(), fx.paciente(), fx.consultorio()
    tipo = fx.tipo_tratamiento()
    p1, p2, p_inactivo = fx.tipo_procedimiento(), fx.tipo_procedimiento(), fx.tipo_procedimiento(activo=False)
    i1, i2, i_inactivo = fx.insumo(), fx.insumo(), fx.insumo(activo=False)
    admin = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Administrador' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    cajero = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    C_REC, C_MED, C_MED2, C_ADM, C_CAJ = cliente(u_rec), cliente(u_med), cliente(u_med2), cliente(admin), cliente(cajero)

    def consulta_nueva(estado='en_proceso', medico=None, paciente=None):
        return fx.registrar_consulta(fx.cita(medico or med, paciente or pac, cons, f_rec), f_rec, estado)

    c1, c2 = consulta_nueva(), consulta_nueva()
    c_otro_pac, c_med2 = consulta_nueva(paciente=pac2), consulta_nueva(medico=med2)
    t = C_MED.post(URL_T, json={'id_consulta_cab': c1, 'id_tipo_tratamiento': tipo, 'descripcion_tratamiento': 'Tratamiento largo'}).get_json()['data']['id_tratamiento']
    fx.auditoria_de('tratamientos', t)
    base = {'id_tratamiento': t, 'id_consulta_cab': c1, 'procedimientos': [p1, p2], 'descripcion_procedimiento': 'Se realizó la limpieza ' + SECRETO,
            'observaciones': 'Sin complicaciones', 'insumos': [{'id_insumo': i1, 'cantidad': 2}, {'id_insumo': i2, 'cantidad': 10}]}

    def alta(c, datos, esperado, nombre, **kw):
        d = llamar(c, 'post', URL, esperado, datos, nombre, **kw)
        if esperado == 201:
            sesiones.append(d['data']['id_sesion'])
        return d

    def estado_t():
        return q("SELECT estado FROM tratamientos WHERE id_tratamiento=%s", (t,))[0][0]

    print('\n=== Esquema')
    chk('la sesión ya no tiene id_tipo_procedimiento; tiene id_consulta_cab NOT NULL',
        not q("SELECT 1 FROM information_schema.columns WHERE table_name='sesiones_tratamiento' AND column_name='id_tipo_procedimiento'")
        and q("SELECT is_nullable FROM information_schema.columns WHERE table_name='sesiones_tratamiento' AND column_name='id_consulta_cab'")[0][0] == 'NO')
    chk('sesion_procedimientos con único parcial; sesion_insumos con único parcial y cantidad 1–999',
        {'uk_sesion_procedimiento_activo', 'uk_sesion_insumo_activo'} <= {x[0] for x in q("SELECT indexname FROM pg_indexes WHERE tablename IN ('sesion_procedimientos','sesion_insumos')")}
        and 'chk_sesion_insumo_cantidad' in {x[0] for x in q("SELECT conname FROM pg_constraint WHERE conrelid='sesion_insumos'::regclass")})

    print('\n=== Permisos y quién registra')
    chk('sin sesión -> 401', app.test_client().post(URL, json=base).status_code == 401)
    llamar(C_CAJ, 'post', URL, 403, base, 'el Cajero no registra')
    llamar(C_REC, 'post', URL, 403, base, 'Recepción no registra')
    llamar(C_ADM, 'post', URL, 403, base, 'el Administrador no registra', contiene='Solo el médico')
    llamar(C_MED2, 'post', URL, 403, base, 'otro médico no registra en la consulta ajena')
    d = llamar(C_MED2, 'post', URL, 409, {**base, 'id_consulta_cab': c_med2}, 'otro médico con SU consulta: el tratamiento no es suyo', contiene='mismo paciente y del mismo médico')
    chk('...no se creó nada', q("SELECT COUNT(*) FROM sesiones_tratamiento WHERE id_tratamiento=%s", (t,))[0][0] == 0)

    print('\n=== Validaciones del servidor')
    llamar(C_MED, 'post', URL, 400, {k: v for k, v in base.items() if k != 'id_tratamiento'}, 'sin tratamiento', campo='id_tratamiento')
    llamar(C_MED, 'post', URL, 400, {k: v for k, v in base.items() if k != 'id_consulta_cab'}, 'sin consulta', campo='id_consulta_cab')
    llamar(C_MED, 'post', URL, 404, {**base, 'id_tratamiento': 99999999}, 'tratamiento inexistente')
    llamar(C_MED, 'post', URL, 404, {**base, 'id_consulta_cab': 99999999}, 'consulta inexistente')
    llamar(C_MED, 'post', URL, 400, {**base, 'procedimientos': []}, 'sin procedimientos', campo='procedimientos')
    llamar(C_MED, 'post', URL, 400, {**base, 'procedimientos': ['x']}, 'procedimientos no numéricos', campo='procedimientos')
    llamar(C_MED, 'post', URL, 400, {**base, 'procedimientos': [99999999]}, 'procedimiento inexistente', campo='procedimientos')
    llamar(C_MED, 'post', URL, 409, {**base, 'procedimientos': [p1, p_inactivo]}, 'procedimiento inactivo', contiene='inactivos', campo='procedimientos')
    llamar(C_MED, 'post', URL, 400, {**base, 'descripcion_procedimiento': '  '}, 'descripción en blanco', campo='descripcion_procedimiento')
    llamar(C_MED, 'post', URL, 400, {**base, 'observaciones': 'x' * 2001}, 'observaciones de 2001', campo='observaciones')
    llamar(C_MED, 'post', URL, 400, {**base, 'proxima_cita': (HOY - datetime.timedelta(days=1)).isoformat()}, 'próxima cita en el pasado', campo='proxima_cita')
    llamar(C_MED, 'post', URL, 400, {**base, 'proxima_cita': '2026-02-30'}, 'próxima cita imposible', campo='proxima_cita')
    llamar(C_MED, 'post', URL, 400, {**base, 'insumos': [{'id_insumo': i1, 'cantidad': 0}]}, 'cantidad 0', campo='insumos')
    llamar(C_MED, 'post', URL, 400, {**base, 'insumos': [{'id_insumo': i1, 'cantidad': 1000}]}, 'cantidad 1000', campo='insumos')
    llamar(C_MED, 'post', URL, 400, {**base, 'insumos': [{'id_insumo': i1, 'cantidad': 'x'}]}, 'cantidad no numérica', campo='insumos')
    llamar(C_MED, 'post', URL, 400, {**base, 'insumos': [{'id_insumo': i1, 'cantidad': 1}, {'id_insumo': i1, 'cantidad': 2}]}, 'insumo repetido', contiene='No repita', campo='insumos')
    llamar(C_MED, 'post', URL, 400, {**base, 'insumos': [{'id_insumo': 99999999, 'cantidad': 1}]}, 'insumo inexistente', campo='insumos')
    llamar(C_MED, 'post', URL, 409, {**base, 'insumos': [{'id_insumo': i_inactivo, 'cantidad': 1}]}, 'insumo inactivo', contiene='inactivos', campo='insumos')
    chk('...ningún rechazo dejó una sesión ni cambió el estado', q("SELECT COUNT(*) FROM sesiones_tratamiento WHERE id_tratamiento=%s", (t,))[0][0] == 0 and estado_t() == 'pendiente')

    print('\n=== Alta correcta y varias visitas')
    d = alta(C_MED, {**base, 'id_paciente': 1, 'numero_sesion': 9, 'fecha_sesion': '2020-01-01', 'activo': False}, 201, 'sesión 1 en la consulta 1 (con campos que el servidor ignora)')
    s1 = d['data']['id_sesion']
    chk('...número 1, fecha de hoy, en la consulta indicada', d['data']['numero_sesion'] == 1 and q("SELECT numero_sesion, fecha_sesion, id_consulta_cab, activo FROM sesiones_tratamiento WHERE id_sesion=%s", (s1,))[0] == (1, HOY, c1, True))
    chk('...con 2 procedimientos y 2 insumos', q("SELECT COUNT(*) FROM sesion_procedimientos WHERE id_sesion=%s AND activo", (s1,))[0][0] == 2 and q("SELECT COUNT(*) FROM sesion_insumos WHERE id_sesion=%s AND activo", (s1,))[0][0] == 2)
    chk('...el tratamiento pasó a en_seguimiento', estado_t() == 'en_seguimiento')
    d = alta(C_MED, {**base, 'id_consulta_cab': c2, 'procedimientos': [p1], 'insumos': [], 'proxima_cita': (HOY + datetime.timedelta(days=7)).isoformat()}, 201,
             'sesión 2 en una consulta POSTERIOR, sin insumos (válido)')
    s2 = d['data']['id_sesion']
    chk('...número 2 en la consulta 2', d['data']['numero_sesion'] == 2 and q("SELECT id_consulta_cab FROM sesiones_tratamiento WHERE id_sesion=%s", (s2,))[0][0] == c2)
    alta(C_MED, {**base, 'id_consulta_cab': c_otro_pac}, 409, 'consulta de OTRO paciente', contiene='mismo paciente y del mismo médico')
    for estado in ('finalizada', 'cancelada'):
        c_e = consulta_nueva(estado)
        alta(C_MED, {**base, 'id_consulta_cab': c_e}, 409, f'consulta {estado}', contiene=estado)
    alta(C_MED, {**base, 'id_consulta_cab': consulta_nueva('programada')}, 201, 'consulta programada también admite (sesión 3)')
    s3 = sesiones[-1]
    chk('...número 3', q("SELECT numero_sesion FROM sesiones_tratamiento WHERE id_sesion=%s", (s3,))[0][0] == 3)

    print('\n=== Lecturas: privacidad')
    r = llamar(C_MED, 'get', f'{URL_T}/{t}', 200, None, 'el médico lee el tratamiento con sus sesiones')
    chk('...3 sesiones, de la primera a la última, con consulta, procedimientos e insumos',
        [x['numero_sesion'] for x in r['data']['sesiones']] == [1, 2, 3] and {'numero_consulta', 'procedimientos', 'insumos', 'estado_consulta'} <= set(r['data']['sesiones'][0])
        and len(r['data']['sesiones'][0]['procedimientos']) == 2 and len(r['data']['sesiones'][0]['insumos']) == 2 and r['data']['sesiones'][1]['insumos'] == [])
    llamar(C_MED2, 'get', f'{URL_T}/{t}', 403, None, 'otro médico NO lee las sesiones')
    llamar(C_ADM, 'get', f'{URL_T}/{t}', 200, None, 'el Administrador lee')
    llamar(C_REC, 'get', f'{URL_T}/{t}', 403, None, 'Recepción no lee')
    llamar(C_MED, 'get', f'{URL}/{s1}', 200, None, 'el médico abre una sesión')
    llamar(C_MED2, 'get', f'{URL}/{s1}', 403, None, 'otro médico NO abre la sesión')
    llamar(C_MED, 'get', f'{URL}/99999999', 404, None, 'sesión inexistente')
    d = llamar(C_MED, 'get', f'{URL_T}/{t}', 200, None, 'el detalle del tratamiento trae sus sesiones')
    chk('...3 sesiones y 3 en cantidad_sesiones', len(d['data']['sesiones']) == 3 and d['data']['cantidad_sesiones'] == 3)

    print('\n=== Anular (solo la última, definitivo)')
    llamar(C_MED, 'delete', f'{URL}/{s1}', 409, None, 'la primera no es la última', contiene='última')
    llamar(C_REC, 'delete', f'{URL}/{s3}', 403, None, 'Recepción no anula')
    llamar(C_MED2, 'delete', f'{URL}/{s3}', 403, None, 'otro médico no anula')
    llamar(C_ADM, 'delete', f'{URL}/{s3}', 403, None, 'el Administrador no anula')
    llamar(C_MED, 'delete', f'{URL}/{s3}', 200, None, 'el médico anula la última (3)')
    chk('...cascada: sus procedimientos e insumos quedan inactivos y el estado sigue en_seguimiento',
        q("SELECT COUNT(*) FROM sesion_procedimientos WHERE id_sesion=%s AND activo", (s3,))[0][0] == 0 and estado_t() == 'en_seguimiento')
    llamar(C_MED, 'delete', f'{URL}/{s3}', 404, None, 'anular dos veces')
    d = alta(C_MED, {**base, 'procedimientos': [p2], 'insumos': [{'id_insumo': i1, 'cantidad': 1}]}, 201, 'se reutiliza el número 3')
    chk('...número 3 de nuevo (los números liberados se reutilizan)', d['data']['numero_sesion'] == 3)
    s3b = sesiones[-1]
    # la consulta de la sesión se finaliza: no se anula desde ahí
    cu.execute("UPDATE consultas_cab SET estado='finalizada' WHERE id_consulta_cab=%s", (c1,)); cx.commit()
    llamar(C_MED, 'delete', f'{URL}/{s3b}', 409, None, 'con la consulta de la sesión finalizada no se anula', contiene='finalizada')
    cu.execute("UPDATE consultas_cab SET estado='en_proceso' WHERE id_consulta_cab=%s", (c1,)); cx.commit()
    llamar(C_MED, 'delete', f'{URL}/{s3b}', 200, None, 'reabierta la consulta, se anula')
    llamar(C_MED, 'delete', f'{URL}/{s2}', 200, None, 'se anula la 2')
    chk('...queda la 1 y el tratamiento sigue en seguimiento', estado_t() == 'en_seguimiento')
    llamar(C_MED, 'delete', f'{URL}/{s1}', 200, None, 'se anula la 1 (ya no quedan sesiones)')
    chk('...el tratamiento VUELVE a pendiente', estado_t() == 'pendiente')
    chk('...y se puede anular el tratamiento (sin sesiones vigentes)', C_MED.delete(f'{URL_T}/{t}').status_code == 200)
    llamar(C_MED, 'post', URL, 404, base, 'un tratamiento anulado no admite sesiones')

    print('\n=== Tratamiento finalizado')
    t2 = C_MED.post(URL_T, json={'id_consulta_cab': c2, 'id_tipo_tratamiento': tipo, 'descripcion_tratamiento': 'Otro'}).get_json()['data']['id_tratamiento']
    fx.auditoria_de('tratamientos', t2)
    b2 = {**base, 'id_tratamiento': t2, 'id_consulta_cab': c2}
    s_a = alta(C_MED, b2, 201, 'sesión en el tratamiento 2')['data']['id_sesion']
    llamar(C_MED, 'put', f'{URL_T}/{t2}/finalizar', 200, None, 'se finaliza')
    alta(C_MED, b2, 409, 'un finalizado no admite sesiones', contiene='finalizado')
    llamar(C_MED, 'delete', f'{URL}/{s_a}', 409, None, 'ni anular sus sesiones', contiene='finalizado')

    print('\n=== La base de datos')
    def rechaza(sql, p, nombre):
        try:
            cu.execute(sql, p); cx.commit(); ok = False
        except Exception:
            cx.rollback(); ok = True
        chk(f'la base rechaza: {nombre}', ok)
    t3 = C_MED.post(URL_T, json={'id_consulta_cab': c2, 'id_tipo_tratamiento': tipo, 'descripcion_tratamiento': 'Tercero'}).get_json()['data']['id_tratamiento']
    fx.auditoria_de('tratamientos', t3)
    rechaza("INSERT INTO sesiones_tratamiento(id_tratamiento, id_consulta_cab, numero_sesion, descripcion_procedimiento) VALUES (%s,%s,1,'ZZ')", (t3, c2), 'una sesión sin ningún procedimiento (trigger diferido)')
    rechaza("INSERT INTO sesiones_tratamiento(id_tratamiento, id_consulta_cab, numero_sesion, descripcion_procedimiento) VALUES (%s,%s,1,'ZZ')", (t3, c_otro_pac), 'una consulta de otro paciente')
    rechaza("INSERT INTO sesiones_tratamiento(id_tratamiento, id_consulta_cab, numero_sesion, descripcion_procedimiento) VALUES (%s,%s,1,'  ')", (t3, c2), 'descripción en blanco')
    rechaza("INSERT INTO sesiones_tratamiento(id_tratamiento, id_consulta_cab, numero_sesion, descripcion_procedimiento, proxima_cita) VALUES (%s,%s,1,'ZZ','2000-01-01')", (t3, c2), 'próxima cita anterior a la sesión')
    s_v = alta(C_MED, {**base, 'id_tratamiento': t3, 'id_consulta_cab': c2}, 201, 'sesión para probar los únicos')['data']['id_sesion']
    rechaza("INSERT INTO sesion_insumos(id_sesion, id_insumo, cantidad) VALUES (%s,%s,1)", (s_v, i1), 'el mismo insumo dos veces en la sesión')
    rechaza("INSERT INTO sesion_procedimientos(id_sesion, id_tipo_procedimiento) VALUES (%s,%s)", (s_v, p1), 'el mismo procedimiento dos veces en la sesión')
    rechaza("INSERT INTO sesion_insumos(id_sesion, id_insumo, cantidad) VALUES (%s,%s,1000)", (s_v, i_inactivo), 'cantidad de 1000')

    print('\n=== Referenciales en uso')
    llamar(C_ADM, 'delete', f'/api/v1/tipos-procedimiento-medico/{p1}', 409, None, 'no se anula un procedimiento usado en una sesión', contiene='sesiones')
    llamar(C_ADM, 'delete', f'/api/v1/tipos-insumo/{i1}', 409, None, 'no se anula un insumo usado en una sesión', contiene='sesiones')
    llamar(C_ADM, 'delete', f'/api/v1/tipos-tratamiento/{tipo}', 409, None, 'no se anula un tipo de tratamiento usado')

    print('\n=== Auditoría sin contenido clínico')
    for i in sesiones:
        fx.auditoria_de('sesiones_tratamiento', i)
    filas = q("SELECT accion, modulo, valores_nuevos, id_usuario, detalle FROM auditoria_cambios WHERE entidad='sesiones_tratamiento' AND id_registro=%s ORDER BY id_auditoria_cambio", (s1,))
    chk('s1: ALTA y BAJA con módulo Consultorio y el usuario', [f[0] for f in filas] == ['ALTA', 'BAJA'] and all(f[1] == 'Módulo Consultorio' and f[3] == u_med for f in filas))
    chk('...el ALTA lleva sesión, tratamiento, consulta y paciente', all(x in filas[0][4] for x in ('Sesión: 1', 'ZZ TIPO TRAT', 'Consulta: CON-', 'ZZ PACIENTE')))
    estados = [x[0] for x in q("SELECT valores_nuevos->>'Estado' FROM auditoria_cambios WHERE entidad='tratamientos' AND id_registro=%s AND accion='MODIFICACION' ORDER BY id_auditoria_cambio", (t,))]
    chk(f'los cambios de estado del tratamiento quedan auditados: {estados}', estados == ['En seguimiento', 'Pendiente'])
    todo = q("SELECT detalle, valores_anteriores::text, valores_nuevos::text FROM auditoria_cambios WHERE entidad IN ('sesiones_tratamiento','tratamientos') AND id_registro = ANY(%s)", (sesiones + [t, t2, t3],))
    chk('NINGUNA fila de auditoría contiene la descripción de la sesión', not any(SECRETO in (x or '') for fila in todo for x in fila))

    print('\n=== Carreras')
    c5 = consulta_nueva()
    t5 = C_MED.post(URL_T, json={'id_consulta_cab': c5, 'id_tipo_tratamiento': tipo, 'descripcion_tratamiento': 'Carreras'}).get_json()['data']['id_tratamiento']
    fx.auditoria_de('tratamientos', t5)
    b5 = {**base, 'id_tratamiento': t5, 'id_consulta_cab': c5}
    p3 = fx.tipo_procedimiento()
    cu.execute("SELECT 1 FROM tipo_procedimiento_medico WHERE id_tipo_procedimiento=%s FOR UPDATE", (p3,))   # la baja del referencial tiene la fila
    res = []
    h = threading.Thread(target=lambda: res.append(C_MED.post(URL, json={**b5, 'procedimientos': [p3]}).status_code)); h.start()
    time.sleep(0.8)
    cu.execute("UPDATE tipo_procedimiento_medico SET activo=false WHERE id_tipo_procedimiento=%s", (p3,)); cx.commit(); h.join()
    chk(f'el procedimiento se anula mientras se guarda: se rechaza (409): {res}', res == [409])
    i3 = fx.insumo()
    cu.execute("SELECT 1 FROM insumos WHERE id_insumo=%s FOR UPDATE", (i3,))
    res = []
    h = threading.Thread(target=lambda: res.append(C_MED.post(URL, json={**b5, 'insumos': [{'id_insumo': i3, 'cantidad': 1}]}).status_code)); h.start()
    time.sleep(0.8)
    cu.execute("UPDATE insumos SET activo=false WHERE id_insumo=%s", (i3,)); cx.commit(); h.join()
    chk(f'el insumo se anula mientras se guarda: se rechaza (409): {res}', res == [409])
    cu.execute("SELECT 1 FROM consultas_cab WHERE id_consulta_cab=%s FOR UPDATE", (c5,))
    res = []
    h = threading.Thread(target=lambda: res.append(C_MED.post(URL, json=b5).status_code)); h.start()
    time.sleep(0.8)
    cu.execute("UPDATE consultas_cab SET estado='cancelada' WHERE id_consulta_cab=%s", (c5,)); cx.commit(); h.join()
    chk(f'la consulta se cancela mientras se guarda: se rechaza (409): {res}', res == [409])
    chk('...y no quedó ninguna sesión ni cambió el estado', q("SELECT COUNT(*) FROM sesiones_tratamiento WHERE id_tratamiento=%s", (t5,))[0][0] == 0
        and q("SELECT estado FROM tratamientos WHERE id_tratamiento=%s", (t5,))[0][0] == 'pendiente')
    # dos sesiones simultáneas del mismo tratamiento: números distintos y consecutivos
    cu.execute("UPDATE consultas_cab SET estado='en_proceso' WHERE id_consulta_cab=%s", (c5,)); cx.commit()
    res, barrera = [], threading.Barrier(2)
    cls = [cliente(u_med), cliente(u_med)]

    def alta_sinc(c):
        barrera.wait(); r = c.post(URL, json=b5); res.append(r.status_code)
    hs = [threading.Thread(target=alta_sinc, args=(c,)) for c in cls]
    [x.start() for x in hs]; [x.join() for x in hs]
    chk(f'dos sesiones simultáneas: las dos entran: {res}', sorted(res) == [201, 201])
    chk('...con números 1 y 2', [x[0] for x in q("SELECT numero_sesion FROM sesiones_tratamiento WHERE id_tratamiento=%s AND activo ORDER BY 1", (t5,))] == [1, 2])
    # sesión nueva y finalizar a la vez: el resultado es coherente
    cu.execute("UPDATE consultas_cab SET estado='en_proceso' WHERE id_consulta_cab=%s", (c5,)); cx.commit()
    res = {}
    barrera = threading.Barrier(2)

    def en_hilo(clave, f):
        barrera.wait(); res[clave] = f()
    hs = [threading.Thread(target=en_hilo, args=('sesion', lambda: C_MED.post(URL, json=b5).status_code)),
          threading.Thread(target=en_hilo, args=('fin', lambda: cliente_fin.put(f'{URL_T}/{t5}/finalizar').status_code))]
    cliente_fin = cliente(u_med)
    [x.start() for x in hs]; [x.join() for x in hs]
    n = q("SELECT COUNT(*) FROM sesiones_tratamiento WHERE id_tratamiento=%s AND activo", (t5,))[0][0]
    chk(f'sesión nueva y finalizar a la vez: coherente ({res}, {n} sesiones, estado {q("SELECT estado FROM tratamientos WHERE id_tratamiento=%s", (t5,))[0][0]})',
        res['fin'] == 200 and q("SELECT estado FROM tratamientos WHERE id_tratamiento=%s", (t5,))[0][0] == 'finalizado'
        and ((res['sesion'] == 201 and n == 3) or (res['sesion'] == 409 and n == 2)))

    for (i,) in q("SELECT id_sesion FROM sesiones_tratamiento WHERE id_tratamiento = ANY(%s)", ([t, t2, t3, t5],)):
        fx.auditoria_de('sesiones_tratamiento', i)
    for (i,) in q("SELECT id_tratamiento FROM tratamientos WHERE id_paciente = %s", (pac,)):
        fx.auditoria_de('tratamientos', i)
    for i in (c1, c2, c5, c_otro_pac, c_med2):
        fx.auditoria_de('consultas_cab', i)
finally:
    cx.rollback()
    fx.limpiar()

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
