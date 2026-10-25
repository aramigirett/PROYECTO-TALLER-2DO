"""Etapa 6 (commit 1): Receta — alta con las reglas del análisis (al menos un medicamento activo sin repetir, dosis / frecuencia / duración, indicaciones, vínculos
opcionales con un diagnóstico vigente y un tratamiento no cancelado de la MISMA consulta), solo el médico de la consulta con la consulta programada / en proceso
(revalidado en la transacción), anular (definitivo, con cascada, no con la consulta finalizada), privacidad de las lecturas, esquema y auditoría sin contenido clínico.
Datos `ZZ` de tests/consultorio/_fixtures.py (se borran por ID con su auditoría).
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


URL = '/api/v1/recetas'
SECRETO = 'RESERVADO-RC-7712'
HOY = datetime.date.today()
registradas = []

try:
    f_rec, u_rec = fx.recepcion()
    med, u_med = fx.medico()
    med2, u_med2 = fx.medico()
    pac, cons = fx.paciente(), fx.consultorio()
    m1, m2, m_inactivo = fx.medicamento(), fx.medicamento(), fx.medicamento(activo=False)
    tipo_dx, sintoma, tipo_trat = fx.tipo_diagnostico(), fx.sintoma(), fx.tipo_tratamiento()
    admin = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Administrador' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    cajero = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    C_REC, C_MED, C_MED2, C_ADM, C_CAJ = cliente(u_rec), cliente(u_med), cliente(u_med2), cliente(admin), cliente(cajero)

    def consulta_nueva(estado='en_proceso'):
        return fx.registrar_consulta(fx.cita(med, pac, cons, f_rec), f_rec, estado)

    def diagnostico(consulta, activo=True):
        cu.execute("WITH dx AS (INSERT INTO diagnosticos(codigo, id_consulta_cab, id_paciente, id_medico, id_tipo_diagnostico, descripcion_diagnostico, fecha_diagnostico, activo) "
                   "SELECT %s, %s, id_paciente, id_medico, %s, 'ZZ', CURRENT_DATE, %s FROM consultas_cab WHERE id_consulta_cab = %s RETURNING id_diagnostico), "
                   "sx AS (INSERT INTO diagnostico_sintoma(id_diagnostico, id_sintoma) SELECT id_diagnostico, %s FROM dx) SELECT id_diagnostico FROM dx",
                   (f'ZQ{int(time.time() * 1000) % 10**8}', consulta, tipo_dx, activo, consulta, sintoma))
        i = cu.fetchone()[0]; cx.commit(); return i

    def tratamiento(consulta, estado='pendiente'):
        cu.execute("INSERT INTO tratamientos(id_consulta_cab, id_paciente, id_medico, id_tipo_tratamiento, descripcion_tratamiento, fecha_tratamiento, estado) "
                   "SELECT %s, id_paciente, id_medico, %s, 'ZZ', CURRENT_DATE, %s FROM consultas_cab WHERE id_consulta_cab = %s RETURNING id_tratamiento", (consulta, tipo_trat, estado, consulta))
        i = cu.fetchone()[0]; cx.commit(); return i

    c1 = consulta_nueva()
    MED = lambda mid, **kw: {'id_medicamento': mid, 'dosis': '500 mg', 'frecuencia': 'cada 8 horas', 'duracion': '7 días', **kw}
    base = {'id_consulta_cab': c1, 'indicaciones_generales': 'Tomar con comida ' + SECRETO, 'medicamentos': [MED(m1), MED(m2, dosis='1 comprimido ' + SECRETO)]}

    def alta(c, datos, esperado, nombre, **kw):
        d = llamar(c, 'post', URL, esperado, datos, nombre, **kw)
        if esperado == 201:
            registradas.append(d['data']['id_receta'])
        return d

    print('\n=== Esquema')
    chk('único parcial por receta + medicamento y trigger diferido en la base',
        'uk_receta_medicamento_activo' in {x[0] for x in q("SELECT indexname FROM pg_indexes WHERE tablename='receta_medicamento'")}
        and 'trg_receta_con_medicamento' in {x[0] for x in q("SELECT tgname FROM pg_trigger WHERE tgrelid='recetas'::regclass")})

    def rechaza(sql, p, nombre):
        try:
            cu.execute(sql, p); cx.commit(); ok = False
        except Exception:
            cx.rollback(); ok = True
        chk(f'la base rechaza: {nombre}', ok)
    rechaza("INSERT INTO recetas(id_consulta_cab, indicaciones_generales) VALUES (%s,'ZZ')", (c1,), 'una receta vigente sin ningún medicamento (trigger diferido)')
    rechaza("INSERT INTO recetas(id_consulta_cab, indicaciones_generales, activo) VALUES (%s,'   ',false)", (c1,), 'indicaciones en blanco')
    chk('...y no dejó nada', q("SELECT COUNT(*) FROM recetas WHERE id_consulta_cab=%s", (c1,))[0][0] == 0)

    print('\n=== Permisos y quién registra')
    chk('sin sesión -> 401', app.test_client().post(URL, json=base).status_code == 401)
    llamar(C_CAJ, 'post', URL, 403, base, 'el Cajero no registra')
    llamar(C_REC, 'post', URL, 403, base, 'Recepción no registra')
    llamar(C_REC, 'get', URL, 403, None, 'Recepción no lista recetas')
    llamar(C_ADM, 'post', URL, 403, base, 'el Administrador no registra (no es el médico de la consulta)', contiene='Solo el médico')
    llamar(C_MED2, 'post', URL, 403, base, 'otro médico no registra en la consulta ajena')
    chk('...no se creó nada', q("SELECT COUNT(*) FROM recetas WHERE id_consulta_cab=%s", (c1,))[0][0] == 0)

    print('\n=== Validaciones del servidor')
    llamar(C_MED, 'post', URL, 400, {k: v for k, v in base.items() if k != 'id_consulta_cab'}, 'sin consulta', campo='id_consulta_cab')
    llamar(C_MED, 'post', URL, 404, {**base, 'id_consulta_cab': 99999999}, 'consulta inexistente')
    llamar(C_MED, 'post', URL, 400, {**base, 'indicaciones_generales': '  '}, 'indicaciones en blanco', campo='indicaciones_generales')
    llamar(C_MED, 'post', URL, 400, {**base, 'indicaciones_generales': 'a' * 2001}, 'indicaciones de 2001', campo='indicaciones_generales')
    llamar(C_MED, 'post', URL, 400, {**base, 'medicamentos': []}, 'sin medicamentos', contiene='al menos un medicamento', campo='medicamentos')
    llamar(C_MED, 'post', URL, 400, {**base, 'medicamentos': [MED(m1, dosis='')]}, 'sin dosis', campo='medicamentos')
    llamar(C_MED, 'post', URL, 400, {**base, 'medicamentos': [MED(m1, frecuencia='  ')]}, 'sin frecuencia', campo='medicamentos')
    llamar(C_MED, 'post', URL, 400, {**base, 'medicamentos': [MED(m1, duracion=None)]}, 'sin duración', campo='medicamentos')
    llamar(C_MED, 'post', URL, 400, {**base, 'medicamentos': [MED(m1, dosis='a' * 101)]}, 'dosis de 101', campo='medicamentos')
    llamar(C_MED, 'post', URL, 400, {**base, 'medicamentos': [MED(m1), MED(m1, dosis='otra')]}, 'medicamento repetido', contiene='No repita', campo='medicamentos')
    llamar(C_MED, 'post', URL, 400, {**base, 'medicamentos': [MED(99999999)]}, 'medicamento inexistente', campo='medicamentos')
    llamar(C_MED, 'post', URL, 409, {**base, 'medicamentos': [MED(m1), MED(m_inactivo)]}, 'medicamento inactivo', contiene='inactivos', campo='medicamentos')
    llamar(C_MED, 'post', URL, 400, {**base, 'id_diagnostico': 'x'}, 'diagnóstico no numérico', campo='id_diagnostico')
    llamar(C_MED, 'post', URL, 400, {**base, 'id_tratamiento': 'x'}, 'tratamiento no numérico', campo='id_tratamiento')
    c_otra = consulta_nueva()
    dx_ajeno, dx_anulado, dx_ok = diagnostico(c_otra), diagnostico(c1, activo=False), diagnostico(c1)
    t_ajeno, t_cancelado, t_ok = tratamiento(c_otra), tratamiento(c1, 'cancelado'), tratamiento(c1)
    llamar(C_MED, 'post', URL, 400, {**base, 'id_diagnostico': dx_ajeno}, 'diagnóstico de OTRA consulta', campo='id_diagnostico')
    llamar(C_MED, 'post', URL, 400, {**base, 'id_diagnostico': dx_anulado}, 'diagnóstico anulado', campo='id_diagnostico')
    llamar(C_MED, 'post', URL, 400, {**base, 'id_tratamiento': t_ajeno}, 'tratamiento de OTRA consulta', campo='id_tratamiento')
    llamar(C_MED, 'post', URL, 400, {**base, 'id_tratamiento': t_cancelado}, 'tratamiento cancelado', campo='id_tratamiento')
    chk('...ninguno de los rechazos dejó una receta', q("SELECT COUNT(*) FROM recetas WHERE id_consulta_cab IN (%s,%s)", (c1, c_otra))[0][0] == 0)

    print('\n=== Alta correcta')
    d = alta(C_MED, {**base, 'id_diagnostico': dx_ok, 'id_tratamiento': t_ok, 'fecha_receta': '2020-01-01', 'activo': False, 'id_paciente': 1}, 201, 'el médico registra (con campos que el servidor ignora)')
    r1 = d['data']['id_receta']
    chk('...N.º RCT derivado del id', d['data']['numero'] == f'RCT-{r1:07d}' and d['data']['numero'] in d['mensaje'])
    f = q("SELECT fecha_receta, activo, id_diagnostico, id_tratamiento FROM recetas WHERE id_receta=%s", (r1,))[0]
    chk('...fecha de hoy fijada por el servidor, vigente y con sus vínculos', f == (HOY, True, dx_ok, t_ok))
    chk('...con sus 2 medicamentos', q("SELECT COUNT(*) FROM receta_medicamento WHERE id_receta=%s AND activo", (r1,))[0][0] == 2)
    alta(C_MED, {**base, 'medicamentos': [MED(m1)]}, 201, 'otra receta con el mismo medicamento (en otra receta sí se repite)')
    c_prog = consulta_nueva('programada')
    alta(C_MED, {**base, 'id_consulta_cab': c_prog}, 201, 'consulta programada también admite')
    for estado in ('finalizada', 'cancelada'):
        alta(C_MED, {**base, 'id_consulta_cab': consulta_nueva(estado)}, 409, f'consulta {estado}', contiene=estado)

    print('\n=== Lecturas: privacidad')
    lista = llamar(C_MED, 'get', f'{URL}?consulta={c1}', 200, None, 'el médico lista las de su consulta')
    chk('...2 recetas con paciente, N.º y medicamentos', lista['total'] == 2 and {'numero', 'nombre_paciente', 'medicamentos', 'fecha_receta'} <= set(lista['data'][0]) and len(lista['data'][1]['medicamentos']) == 2)
    chk('un médico ajeno no ve ninguna', llamar(C_MED2, 'get', f'{URL}?consulta={c1}', 200, None, 'otro médico lista')['total'] == 0)
    chk('el Administrador ve todas', llamar(C_ADM, 'get', f'{URL}?consulta={c1}', 200, None, 'el Administrador lista')['total'] == 2)
    llamar(C_MED, 'get', f'{URL}/{r1}', 200, None, 'el médico abre el detalle')
    llamar(C_MED2, 'get', f'{URL}/{r1}', 403, None, 'otro médico NO abre el detalle')
    llamar(C_ADM, 'get', f'{URL}/{r1}', 200, None, 'el Administrador abre el detalle')
    llamar(C_MED, 'get', f'{URL}?desde=x', 400, None, 'fecha inválida en el filtro')
    llamar(C_MED, 'get', f'{URL}?consulta=x', 400, None, 'consulta no numérica en el filtro')
    llamar(C_MED, 'get', f'{URL}/99999999', 404, None, 'receta inexistente')

    print('\n=== Anular (definitivo)')
    llamar(C_REC, 'delete', f'{URL}/{r1}', 403, None, 'Recepción no anula')
    llamar(C_MED2, 'delete', f'{URL}/{r1}', 403, None, 'otro médico no anula')
    llamar(C_ADM, 'delete', f'{URL}/{r1}', 403, None, 'el Administrador no anula')
    llamar(C_MED, 'delete', f'{URL}/{r1}', 200, None, 'el médico anula', contiene='anulada')
    chk('...cascada: la receta y sus medicamentos quedan inactivos', q("SELECT activo FROM recetas WHERE id_receta=%s", (r1,))[0][0] is False
        and q("SELECT COUNT(*) FROM receta_medicamento WHERE id_receta=%s AND activo", (r1,))[0][0] == 0)
    llamar(C_MED, 'delete', f'{URL}/{r1}', 404, None, 'anular dos veces')
    chk('...ya no figura en el listado', llamar(C_MED, 'get', f'{URL}?consulta={c1}', 200, None, 'lista')['total'] == 1)
    c_fin = consulta_nueva('en_proceso')
    r_fin = alta(C_MED, {**base, 'id_consulta_cab': c_fin}, 201, 'receta en una consulta que luego se finaliza')['data']['id_receta']
    cu.execute("UPDATE consultas_cab SET estado='finalizada' WHERE id_consulta_cab=%s", (c_fin,)); cx.commit()
    llamar(C_MED, 'delete', f'{URL}/{r_fin}', 409, None, 'con la consulta finalizada no se anula', contiene='finalizada')

    print('\n=== Auditoría sin contenido clínico')
    for i in registradas:
        fx.auditoria_de('recetas', i)
    filas = q("SELECT accion, modulo, valores_nuevos, id_usuario, detalle FROM auditoria_cambios WHERE entidad='recetas' AND id_registro=%s ORDER BY id_auditoria_cambio", (r1,))
    chk('r1: ALTA y BAJA con módulo Consultorio y el usuario', [f[0] for f in filas] == ['ALTA', 'BAJA'] and all(f[1] == 'Módulo Consultorio' and f[3] == u_med for f in filas))
    chk('...el ALTA lleva N.º de receta, consulta y paciente con CI', all(x in filas[0][4] for x in (f'RCT-{r1:07d}', 'Consulta: CON-', 'ZZ PACIENTE', 'CI ')))
    chk('...la BAJA dice Anulado', filas[1][2] == {'Estado': 'Anulado'})
    todo = q("SELECT detalle, valores_anteriores::text, valores_nuevos::text FROM auditoria_cambios WHERE entidad='recetas' AND id_registro = ANY(%s)", (registradas,))
    chk('NINGUNA fila de auditoría contiene indicaciones, medicamentos ni dosis', not any(SECRETO in (x or '') or 'ZZ MEDICAMENTO' in (x or '') for fila in todo for x in fila))

    print('\n=== Carreras')
    c3 = consulta_nueva()
    m3 = fx.medicamento()
    cu.execute("SELECT 1 FROM medicamentos WHERE id_medicamento=%s FOR UPDATE", (m3,))   # la baja del referencial tiene la fila
    res = []
    h = threading.Thread(target=lambda: res.append(C_MED.post(URL, json={**base, 'id_consulta_cab': c3, 'medicamentos': [MED(m3)]}).status_code)); h.start()
    time.sleep(0.8)
    cu.execute("UPDATE medicamentos SET activo=false WHERE id_medicamento=%s", (m3,)); cx.commit(); h.join()
    chk(f'el medicamento se anula mientras se guarda: se rechaza (409): {res}', res == [409])
    cu.execute("SELECT 1 FROM consultas_cab WHERE id_consulta_cab=%s FOR UPDATE", (c3,))
    res = []
    h = threading.Thread(target=lambda: res.append(C_MED.post(URL, json={**base, 'id_consulta_cab': c3}).status_code)); h.start()
    time.sleep(0.8)
    cu.execute("UPDATE consultas_cab SET estado='cancelada' WHERE id_consulta_cab=%s", (c3,)); cx.commit(); h.join()
    chk(f'la consulta se cancela mientras se guarda: se rechaza (409): {res}', res == [409])
    chk('...y no quedó ninguna receta en esa consulta', q("SELECT COUNT(*) FROM recetas WHERE id_consulta_cab=%s", (c3,))[0][0] == 0)
    res, barrera, cls = [], threading.Barrier(2), [cliente(u_med), cliente(u_med)]

    def alta_sinc(c):
        barrera.wait(); res.append(c.post(URL, json=base).status_code)
    hs = [threading.Thread(target=alta_sinc, args=(c,)) for c in cls]
    [x.start() for x in hs]; [x.join() for x in hs]
    chk(f'dos altas simultáneas: las dos entran: {res}', sorted(res) == [201, 201])

    for (i,) in q("SELECT id_receta FROM recetas WHERE id_consulta_cab IN (SELECT id_consulta_cab FROM consultas_cab WHERE id_paciente=%s)", (pac,)):
        fx.auditoria_de('recetas', i)
    for (i,) in q("SELECT id_consulta_cab FROM consultas_cab WHERE id_paciente=%s", (pac,)):
        fx.auditoria_de('consultas_cab', i)
finally:
    cx.rollback()
    fx.limpiar()

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
