"""Etapa 5 (commit 1): Tratamiento — alta con las reglas del análisis (tipo activo, descripción, diagnóstico vigente de la misma consulta, fecha no futura),
solo el médico de la consulta con la consulta programada / en proceso (revalidado en la transacción), anular (definitivo) y finalizar, privacidad de las
lecturas, esquema y auditoría sin contenido clínico. Datos `ZZ` de tests/consultorio/_fixtures.py (se borran por ID con su auditoría).
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


URL = '/api/v1/tratamientos'
SECRETO = 'RESERVADO-TR-8841'
registrados = []   # ids de tratamientos creados por la API (para borrar su auditoría)
HOY = datetime.date.today()

try:
    f_rec, u_rec = fx.recepcion()
    med, u_med = fx.medico()
    med2, u_med2 = fx.medico()
    pac, cons = fx.paciente(), fx.consultorio()
    tipo, tipo_inactivo = fx.tipo_tratamiento(), fx.tipo_tratamiento(activo=False)
    tipo_dx, sintoma = fx.tipo_diagnostico(), fx.sintoma()
    admin = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Administrador' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    cajero = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    C_REC, C_MED, C_MED2, C_ADM, C_CAJ = cliente(u_rec), cliente(u_med), cliente(u_med2), cliente(admin), cliente(cajero)

    def consulta_nueva(estado='programada', medico=None):
        return fx.registrar_consulta(fx.cita(medico or med, pac, cons, f_rec), f_rec, estado)

    c1 = consulta_nueva('en_proceso')
    base = {'id_consulta_cab': c1, 'id_tipo_tratamiento': tipo, 'descripcion_tratamiento': 'Limpieza completa ' + SECRETO, 'fecha_tratamiento': HOY.isoformat()}

    def alta(c, datos, esperado, nombre, **kw):
        d = llamar(c, 'post', URL, esperado, datos, nombre, **kw)
        if esperado == 201:
            registrados.append(d['data']['id_tratamiento'])
        return d

    def diagnostico(consulta, activo=True):
        cu.execute("WITH dx AS (INSERT INTO diagnosticos(codigo, id_consulta_cab, id_paciente, id_medico, id_tipo_diagnostico, descripcion_diagnostico, fecha_diagnostico, activo) "
                   "SELECT %s, %s, id_paciente, id_medico, %s, 'ZZ', CURRENT_DATE, %s FROM consultas_cab WHERE id_consulta_cab = %s RETURNING id_diagnostico), "
                   "sx AS (INSERT INTO diagnostico_sintoma(id_diagnostico, id_sintoma) SELECT id_diagnostico, %s FROM dx) SELECT id_diagnostico FROM dx",
                   (f'ZQ{int(time.time() * 1000) % 10**8}', consulta, tipo_dx, activo, consulta, sintoma))
        i = cu.fetchone()[0]; cx.commit(); return i

    print('\n=== Esquema')
    chk('estado NOT NULL y descripción no vacía en la base', q("SELECT is_nullable FROM information_schema.columns WHERE table_name='tratamientos' AND column_name='estado'")[0][0] == 'NO'
        and 'chk_tratamiento_descripcion' in {x[0] for x in q("SELECT conname FROM pg_constraint WHERE conrelid='tratamientos'::regclass")})

    print('\n=== Permisos y quién registra')
    chk('sin sesión -> 401', app.test_client().post(URL, json=base).status_code == 401)
    llamar(C_CAJ, 'post', URL, 403, base, 'el Cajero no registra')
    llamar(C_REC, 'post', URL, 403, base, 'Recepción no registra')
    llamar(C_REC, 'get', URL, 403, None, 'Recepción no lista tratamientos')
    llamar(C_ADM, 'post', URL, 403, base, 'el Administrador no registra (no es el médico de la consulta)', contiene='Solo el médico')
    llamar(C_MED2, 'post', URL, 403, base, 'otro médico no registra en la consulta ajena')
    chk('...y no se creó nada', q("SELECT COUNT(*) FROM tratamientos WHERE id_consulta_cab=%s", (c1,))[0][0] == 0)

    print('\n=== Validaciones del servidor')
    llamar(C_MED, 'post', URL, 400, {k: v for k, v in base.items() if k != 'id_consulta_cab'}, 'sin consulta', campo='id_consulta_cab')
    llamar(C_MED, 'post', URL, 400, {**base, 'id_consulta_cab': 'x'}, 'consulta no numérica', campo='id_consulta_cab')
    llamar(C_MED, 'post', URL, 404, {**base, 'id_consulta_cab': 99999999}, 'consulta inexistente')
    llamar(C_MED, 'post', URL, 400, {**base, 'id_tipo_tratamiento': None}, 'sin tipo', campo='id_tipo_tratamiento')
    llamar(C_MED, 'post', URL, 400, {**base, 'id_tipo_tratamiento': 'x'}, 'tipo no numérico', campo='id_tipo_tratamiento')
    llamar(C_MED, 'post', URL, 400, {**base, 'id_tipo_tratamiento': 99999999}, 'tipo inexistente', campo='id_tipo_tratamiento')
    llamar(C_MED, 'post', URL, 409, {**base, 'id_tipo_tratamiento': tipo_inactivo}, 'tipo inactivo', contiene='inactivo', campo='id_tipo_tratamiento')
    llamar(C_MED, 'post', URL, 400, {**base, 'descripcion_tratamiento': '   '}, 'descripción en blanco', campo='descripcion_tratamiento')
    llamar(C_MED, 'post', URL, 400, {**base, 'descripcion_tratamiento': 'a' * 1001}, 'descripción de 1001', campo='descripcion_tratamiento')
    llamar(C_MED, 'post', URL, 400, {**base, 'fecha_tratamiento': (HOY + datetime.timedelta(days=1)).isoformat()}, 'fecha futura', contiene='futura', campo='fecha_tratamiento')
    llamar(C_MED, 'post', URL, 400, {**base, 'fecha_tratamiento': '2026-02-30'}, 'fecha imposible', campo='fecha_tratamiento')
    llamar(C_MED, 'post', URL, 400, {**base, 'id_diagnostico': 'x'}, 'diagnóstico no numérico', campo='id_diagnostico')
    llamar(C_MED, 'post', URL, 400, {**base, 'id_diagnostico': 99999999}, 'diagnóstico inexistente', campo='id_diagnostico')
    c_otra = consulta_nueva('en_proceso')
    dx_ajeno, dx_anulado, dx_ok = diagnostico(c_otra), diagnostico(c1, activo=False), diagnostico(c1)
    llamar(C_MED, 'post', URL, 400, {**base, 'id_diagnostico': dx_ajeno}, 'diagnóstico de OTRA consulta', campo='id_diagnostico')
    llamar(C_MED, 'post', URL, 400, {**base, 'id_diagnostico': dx_anulado}, 'diagnóstico anulado', campo='id_diagnostico')
    chk('...ninguno de los rechazos dejó un tratamiento', q("SELECT COUNT(*) FROM tratamientos WHERE id_consulta_cab IN (%s,%s)", (c1, c_otra))[0][0] == 0)

    print('\n=== Alta correcta')
    d = alta(C_MED, {**base, 'id_diagnostico': dx_ok, 'id_paciente': 1, 'id_medico': 1, 'id_consultorio': 1, 'estado': 'finalizado'}, 201, 'el médico registra (con campos que el servidor ignora)')
    t1 = d['data']['id_tratamiento']
    f = q("SELECT id_paciente, id_medico, id_consultorio, estado, fecha_tratamiento, id_diagnostico, id_consulta_cab FROM tratamientos WHERE id_tratamiento=%s", (t1,))[0]
    chk('paciente, médico y consultorio salen de la consulta; estado pendiente', f[:4] == (pac, med, cons, 'pendiente') and f[4] == HOY and f[5] == dx_ok and f[6] == c1)
    d = alta(C_MED, {k: v for k, v in base.items() if k != 'fecha_tratamiento'}, 201, 'sin fecha: el servidor propone hoy')
    chk('...la fecha queda en hoy', q("SELECT fecha_tratamiento FROM tratamientos WHERE id_tratamiento=%s", (d['data']['id_tratamiento'],))[0][0] == HOY)
    t_viejo = alta(C_MED, {**base, 'fecha_tratamiento': '2026-01-15'}, 201, 'fecha pasada (editable)')['data']['id_tratamiento']
    chk('...se guardó la fecha elegida', q("SELECT fecha_tratamiento FROM tratamientos WHERE id_tratamiento=%s", (t_viejo,))[0][0] == datetime.date(2026, 1, 15))

    print('\n=== La consulta debe estar abierta')
    for estado, esperado_txt in (('finalizada', 'finalizada'), ('cancelada', 'cancelada')):
        c_e = consulta_nueva(estado)
        alta(C_MED, {**base, 'id_consulta_cab': c_e}, 409, f'consulta {estado}', contiene=esperado_txt)
    c_prog = consulta_nueva('programada')
    alta(C_MED, {**base, 'id_consulta_cab': c_prog}, 201, 'consulta programada también admite')

    print('\n=== Lecturas: privacidad')
    lista = llamar(C_MED, 'get', f'{URL}?consulta={c1}', 200, None, 'el médico lista los de su consulta')
    chk('...trae tipo, estado, paciente y cantidad de sesiones, sin 500', lista['total'] == 3 and {'tipo_tratamiento', 'estado', 'nombre_paciente', 'cantidad_sesiones', 'facturado'} <= set(lista['data'][0]))
    chk('un médico ajeno no ve ninguno', llamar(C_MED2, 'get', f'{URL}?consulta={c1}', 200, None, 'otro médico lista')['total'] == 0)
    chk('el Administrador ve todos', llamar(C_ADM, 'get', f'{URL}?consulta={c1}', 200, None, 'el Administrador lista')['total'] == 3)
    llamar(C_MED, 'get', f'{URL}/{t1}', 200, None, 'el médico abre el detalle')
    llamar(C_MED2, 'get', f'{URL}/{t1}', 403, None, 'otro médico NO abre el detalle')
    llamar(C_ADM, 'get', f'{URL}/{t1}', 200, None, 'el Administrador abre el detalle')
    llamar(C_MED, 'get', f'{URL}/consulta/{c1}', 200, None, 'lookup por consulta (Receta y Órdenes)')
    llamar(C_MED2, 'get', f'{URL}/consulta/{c1}', 403, None, 'el lookup por consulta ajena no se abre')
    llamar(C_REC, 'get', f'{URL}/consulta/{c1}', 403, None, 'Recepción no usa el lookup de tratamientos')
    llamar(C_MED, 'get', f'{URL}?estado=raro', 400, None, 'estado inválido en el filtro')
    llamar(C_MED, 'get', f'{URL}?desde=x', 400, None, 'fecha inválida en el filtro')
    llamar(C_MED, 'get', f'{URL}?paciente=x', 400, None, 'paciente no numérico en el filtro')
    chk('el filtro en_curso trae pendientes y en seguimiento', llamar(C_MED, 'get', f'{URL}?en_curso=1&paciente={pac}', 200, None, 'en_curso')['total'] == 4)

    print('\n=== Anular (definitivo)')
    llamar(C_REC, 'delete', f'{URL}/{t_viejo}', 403, None, 'Recepción no anula')
    llamar(C_MED2, 'delete', f'{URL}/{t_viejo}', 403, None, 'otro médico no anula')
    llamar(C_ADM, 'delete', f'{URL}/{t_viejo}', 403, None, 'el Administrador no anula')
    llamar(C_MED, 'delete', f'{URL}/{t_viejo}', 200, None, 'el médico anula', contiene='anulado')
    chk('...queda cancelado', q("SELECT estado FROM tratamientos WHERE id_tratamiento=%s", (t_viejo,))[0][0] == 'cancelado')
    llamar(C_MED, 'delete', f'{URL}/{t_viejo}', 404, None, 'anular dos veces')
    llamar(C_MED, 'get', f'{URL}/{t_viejo}', 404, None, 'el anulado ya no se abre')
    llamar(C_MED, 'delete', f'{URL}/99999999', 404, None, 'anular inexistente')
    # con una sesión vigente no se anula
    t_ses = alta(C_MED, base, 201, 'otro tratamiento para sesiones')['data']['id_tratamiento']
    proc = fx.tipo_procedimiento()
    cu.execute("WITH s AS (INSERT INTO sesiones_tratamiento(id_tratamiento, id_consulta_cab, numero_sesion, descripcion_procedimiento) VALUES (%s,%s,1,'ZZ') RETURNING id_sesion) "
               "INSERT INTO sesion_procedimientos(id_sesion, id_tipo_procedimiento) SELECT id_sesion, %s FROM s", (t_ses, c1, proc)); cx.commit()
    llamar(C_MED, 'delete', f'{URL}/{t_ses}', 409, None, 'con sesiones vigentes no se anula', contiene='sesiones')
    # la consulta que lo creó se finaliza: no se anula
    c_fin = consulta_nueva('en_proceso')
    t_fin = alta(C_MED, {**base, 'id_consulta_cab': c_fin}, 201, 'tratamiento en otra consulta')['data']['id_tratamiento']
    cu.execute("UPDATE consultas_cab SET estado='finalizada' WHERE id_consulta_cab=%s", (c_fin,)); cx.commit()
    llamar(C_MED, 'delete', f'{URL}/{t_fin}', 409, None, 'con la consulta finalizada no se anula', contiene='finalizada')

    print('\n=== Finalizar')
    llamar(C_MED, 'put', f'{URL}/{t1}/finalizar', 409, None, 'pendiente: no se finaliza', contiene='pendiente')
    cu.execute("UPDATE tratamientos SET estado='en_seguimiento' WHERE id_tratamiento IN (%s,%s)", (t1, t_fin)); cx.commit()
    llamar(C_REC, 'put', f'{URL}/{t1}/finalizar', 403, None, 'Recepción no finaliza')
    llamar(C_MED2, 'put', f'{URL}/{t1}/finalizar', 403, None, 'otro médico no finaliza')
    llamar(C_ADM, 'put', f'{URL}/{t1}/finalizar', 403, None, 'el Administrador no finaliza')
    llamar(C_MED, 'put', f'{URL}/{t1}/finalizar', 200, None, 'el médico finaliza', contiene='finalizado')
    llamar(C_MED, 'put', f'{URL}/{t1}/finalizar', 409, None, 'ya finalizado', contiene='ya está finalizado')
    llamar(C_MED, 'put', f'{URL}/{t_fin}/finalizar', 200, None, 'finalizar NO exige la consulta abierta (varias visitas)')
    llamar(C_MED, 'put', f'{URL}/{t_viejo}/finalizar', 404, None, 'un anulado no se finaliza')

    print('\n=== Auditoría sin contenido clínico')
    for i in registrados:
        fx.auditoria_de('tratamientos', i)
    filas = q("SELECT accion, modulo, valores_anteriores, valores_nuevos, id_usuario, detalle FROM auditoria_cambios WHERE entidad='tratamientos' AND id_registro=%s ORDER BY id_auditoria_cambio", (t1,))
    chk('t1: ALTA y MODIFICACION (finalizar) con módulo Consultorio y el usuario', [f[0] for f in filas] == ['ALTA', 'MODIFICACION'] and all(f[1] == 'Módulo Consultorio' and f[4] == u_med for f in filas))
    chk('...el ALTA lleva consulta, paciente y tipo', 'Consulta: CON-' in filas[0][5] and 'ZZ PACIENTE' in filas[0][5] and 'ZZ TIPO TRAT' in filas[0][5])
    chk('...la finalización guarda solo el estado', filas[1][2] == {'Estado': 'En seguimiento'} and filas[1][3] == {'Estado': 'Finalizado'})
    chk('...la baja de t_viejo dice Anulado', q("SELECT valores_nuevos FROM auditoria_cambios WHERE entidad='tratamientos' AND id_registro=%s AND accion='BAJA'", (t_viejo,))[0][0] == {'Estado': 'Anulado'})
    todo = q("SELECT detalle, valores_anteriores::text, valores_nuevos::text FROM auditoria_cambios WHERE entidad='tratamientos' AND id_registro = ANY(%s)", (registrados,))
    chk('NINGUNA fila de auditoría contiene la descripción', not any(SECRETO in (x or '') for fila in todo for x in fila))

    print('\n=== Carreras')
    # a) el tipo se anula mientras se guarda: el alta espera el bloqueo FOR SHARE y después lo ve inactivo
    c3 = consulta_nueva('en_proceso')
    tipo2 = fx.tipo_tratamiento()
    cu.execute("SELECT 1 FROM tipos_tratamiento WHERE id_tipo_tratamiento=%s FOR UPDATE", (tipo2,))
    res = []
    h = threading.Thread(target=lambda: res.append(C_MED.post(URL, json={**base, 'id_consulta_cab': c3, 'id_tipo_tratamiento': tipo2}).status_code)); h.start()
    time.sleep(0.8)
    cu.execute("UPDATE tipos_tratamiento SET activo=false WHERE id_tipo_tratamiento=%s", (tipo2,)); cx.commit(); h.join()
    chk(f'el tipo se anula mientras se guarda: el alta se rechaza (409): {res}', res == [409])
    # b) la consulta se cancela mientras se guarda
    cu.execute("SELECT 1 FROM consultas_cab WHERE id_consulta_cab=%s FOR UPDATE", (c3,))
    res = []
    h = threading.Thread(target=lambda: res.append(C_MED.post(URL, json={**base, 'id_consulta_cab': c3}).status_code)); h.start()
    time.sleep(0.8)
    cu.execute("UPDATE consultas_cab SET estado='cancelada' WHERE id_consulta_cab=%s", (c3,)); cx.commit(); h.join()
    chk(f'la consulta se cancela mientras se guarda: se rechaza (409): {res}', res == [409])
    chk('...y no quedó ningún tratamiento en esa consulta', q("SELECT COUNT(*) FROM tratamientos WHERE id_consulta_cab=%s", (c3,))[0][0] == 0)
    # c) dos altas simultáneas entran las dos
    res, barrera = [], threading.Barrier(2)

    cls = [cliente(u_med), cliente(u_med)]

    def alta_sinc(c):
        barrera.wait(); res.append(c.post(URL, json=base).status_code)
    hs = [threading.Thread(target=alta_sinc, args=(c,)) for c in cls]
    [x.start() for x in hs]; [x.join() for x in hs]
    chk(f'dos altas simultáneas: las dos entran: {res}', sorted(res) == [201, 201])
    for (i,) in q("SELECT id_tratamiento FROM tratamientos WHERE id_consulta_cab = ANY(%s)", ([c1, c_otra, c_prog, c_fin, c3],)):
        fx.auditoria_de('tratamientos', i)
    for i in (c1, c_otra, c_prog, c_fin, c3):
        fx.auditoria_de('consultas_cab', i)
finally:
    cx.rollback()
    fx.limpiar()

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
