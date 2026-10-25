"""Etapa 7 (commit 1): Justificativo Médico — se registra 'pendiente', "Generar" lo emite (solo el médico de la consulta, también con la consulta finalizada, no con la
cancelada), "Anular" lo anula (pendiente o emitido; no con la consulta finalizada), días de reposo 1–365, vínculo opcional con un diagnóstico vigente de la misma consulta,
privacidad de las lecturas, auditoría de cada cambio de estado sin contenido clínico y el PDF (BORRADOR / sin marca / ANULADO, N.º JUS, auditoría de cada descarga).
Datos `ZZ` de tests/consultorio/_fixtures.py (se borran por ID con su auditoría).
"""
import datetime
import re
import sys
import threading
import time
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from app import app
from tests._conexion_pruebas import Conexion
from tests.consultorio._fixtures import Fixtures
from tests.facturacion._pdf import texto_pdf

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


URL = '/api/v1/justificativos'
SECRETO = 'RESERVADO-JU-6603'
HOY = datetime.date.today()
registrados = []

try:
    f_rec, u_rec = fx.recepcion()
    med, u_med = fx.medico()
    med2, u_med2 = fx.medico()
    pac, cons = fx.paciente(), fx.consultorio()
    tipo_dx, sintoma = fx.tipo_diagnostico(), fx.sintoma()
    admin = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Administrador' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    cajero = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    C_REC, C_MED, C_MED2, C_ADM, C_CAJ = cliente(u_rec), cliente(u_med), cliente(u_med2), cliente(admin), cliente(cajero)

    def consulta_nueva(estado='en_proceso'):
        return fx.registrar_consulta(fx.cita(med, pac, cons, f_rec), f_rec, estado)

    def diagnostico(consulta, activo=True):
        cu.execute("WITH dx AS (INSERT INTO diagnosticos(codigo, id_consulta_cab, id_paciente, id_medico, id_tipo_diagnostico, descripcion_diagnostico, fecha_diagnostico, activo) "
                   "SELECT %s, %s, id_paciente, id_medico, %s, 'ZZ', CURRENT_DATE, %s FROM consultas_cab WHERE id_consulta_cab = %s RETURNING id_diagnostico), "
                   "sx AS (INSERT INTO diagnostico_sintoma(id_diagnostico, id_sintoma) SELECT id_diagnostico, %s FROM dx) SELECT id_diagnostico FROM dx",
                   (f'ZQ{fx._sufijo()[-8:]}', consulta, tipo_dx, activo, consulta, sintoma))
        i = cu.fetchone()[0]; cx.commit(); return i

    c1 = consulta_nueva()
    base = {'id_consulta_cab': c1, 'dias_reposo': 3, 'recomendaciones': 'Reposo relativo ' + SECRETO}

    def alta(c, datos, esperado, nombre, **kw):
        d = llamar(c, 'post', URL, esperado, datos, nombre, **kw)
        if esperado == 201:
            registrados.append(d['data']['id_justificativo'])
        return d

    def estado(i):
        return q("SELECT estado FROM justificativo_medico WHERE id_justificativo=%s", (i,))[0][0]

    print('\n=== Esquema')
    chk('estados pendiente / emitido / anulado con CHECK, por defecto pendiente y días 1–365',
        {'justificativo_medico_estado_check', 'chk_justificativo_dias'} <= {x[0] for x in q("SELECT conname FROM pg_constraint WHERE conrelid='justificativo_medico'::regclass")}
        and "pendiente" in q("SELECT column_default FROM information_schema.columns WHERE table_name='justificativo_medico' AND column_name='estado'")[0][0])
    for sql, nombre in (("INSERT INTO justificativo_medico(id_consulta_cab, dias_reposo, estado) VALUES (%s,1,'activo')", "el estado viejo 'activo'"),
                        ("INSERT INTO justificativo_medico(id_consulta_cab, dias_reposo) VALUES (%s,366)", '366 días'),
                        ("INSERT INTO justificativo_medico(id_consulta_cab, dias_reposo) VALUES (%s,0)", '0 días')):
        try:
            cu.execute(sql, (c1,)); cx.commit(); ok = False
        except Exception:
            cx.rollback(); ok = True
        chk(f'la base rechaza: {nombre}', ok)

    print('\n=== Permisos y quién registra')
    chk('sin sesión -> 401', app.test_client().post(URL, json=base).status_code == 401)
    llamar(C_CAJ, 'post', URL, 403, base, 'el Cajero no registra')
    llamar(C_REC, 'post', URL, 403, base, 'Recepción no registra')
    llamar(C_REC, 'get', URL, 403, None, 'Recepción no lista')
    llamar(C_ADM, 'post', URL, 403, base, 'el Administrador no registra', contiene='Solo el médico')
    llamar(C_MED2, 'post', URL, 403, base, 'otro médico no registra en la consulta ajena')

    print('\n=== Validaciones del servidor')
    llamar(C_MED, 'post', URL, 400, {k: v for k, v in base.items() if k != 'id_consulta_cab'}, 'sin consulta', campo='id_consulta_cab')
    llamar(C_MED, 'post', URL, 404, {**base, 'id_consulta_cab': 99999999}, 'consulta inexistente')
    for dias, nombre in ((None, 'sin días'), (0, '0 días'), (366, '366 días'), (-1, 'días negativos'), ('x', 'días no numéricos'), ('2.5', 'días con decimales')):
        llamar(C_MED, 'post', URL, 400, {**base, 'dias_reposo': dias}, nombre, campo='dias_reposo')
    llamar(C_MED, 'post', URL, 400, {**base, 'recomendaciones': 'a' * 2001}, 'recomendaciones de 2001', campo='recomendaciones')
    llamar(C_MED, 'post', URL, 400, {**base, 'id_diagnostico': 'x'}, 'diagnóstico no numérico', campo='id_diagnostico')
    c_otra = consulta_nueva()
    dx_ajeno, dx_anulado, dx_ok = diagnostico(c_otra), diagnostico(c1, activo=False), diagnostico(c1)
    llamar(C_MED, 'post', URL, 400, {**base, 'id_diagnostico': dx_ajeno}, 'diagnóstico de OTRA consulta', campo='id_diagnostico')
    llamar(C_MED, 'post', URL, 400, {**base, 'id_diagnostico': dx_anulado}, 'diagnóstico anulado', campo='id_diagnostico')
    chk('...ningún rechazo dejó un justificativo', q("SELECT COUNT(*) FROM justificativo_medico WHERE id_consulta_cab IN (%s,%s)", (c1, c_otra))[0][0] == 0)

    print('\n=== Alta correcta (queda PENDIENTE)')
    d = alta(C_MED, {**base, 'id_diagnostico': dx_ok, 'dias_reposo': '365', 'estado': 'emitido', 'fecha_justificativo': '2020-01-01', 'id_paciente': 1}, 201, 'el médico registra (con campos que el servidor ignora)')
    j1 = d['data']['id_justificativo']
    chk('...N.º JUS derivado del id y mensaje "pendiente"', d['data']['numero'] == f'JUS-{j1:07d}' and 'pendiente' in d['mensaje'])
    chk('...estado pendiente, fecha de hoy, días 365 y el vínculo', q("SELECT estado, fecha_justificativo, dias_reposo, id_diagnostico FROM justificativo_medico WHERE id_justificativo=%s", (j1,))[0] == ('pendiente', HOY, 365, dx_ok))
    c_prog = consulta_nueva('programada')
    alta(C_MED, {**base, 'id_consulta_cab': c_prog}, 201, 'consulta programada también admite')
    for est in ('finalizada', 'cancelada'):
        alta(C_MED, {**base, 'id_consulta_cab': consulta_nueva(est)}, 409, f'consulta {est}', contiene=est)

    print('\n=== Lecturas: privacidad')
    lista = llamar(C_MED, 'get', f'{URL}?consulta={c1}', 200, None, 'el médico lista los de su consulta')
    chk('...1 justificativo con paciente, N.º, estado y días', lista['total'] == 1 and {'numero', 'nombre_paciente', 'estado', 'dias_reposo', 'recomendaciones', 'fecha_justificativo'} <= set(lista['data'][0]))
    chk('un médico ajeno no ve ninguno', llamar(C_MED2, 'get', f'{URL}?consulta={c1}', 200, None, 'otro médico lista')['total'] == 0)
    chk('el Administrador ve todos', llamar(C_ADM, 'get', f'{URL}?consulta={c1}', 200, None, 'el Administrador lista')['total'] == 1)
    llamar(C_MED, 'get', f'{URL}/{j1}', 200, None, 'el médico abre el detalle')
    llamar(C_MED2, 'get', f'{URL}/{j1}', 403, None, 'otro médico NO abre el detalle')
    llamar(C_ADM, 'get', f'{URL}/{j1}', 200, None, 'el Administrador abre el detalle')
    llamar(C_MED, 'get', f'{URL}?estado=raro', 400, None, 'estado inválido en el filtro')
    llamar(C_MED, 'get', f'{URL}?desde=x', 400, None, 'fecha inválida en el filtro')
    chk('el filtro por estado funciona', llamar(C_MED, 'get', f'{URL}?consulta={c1}&estado=emitido', 200, None, 'estado=emitido')['total'] == 0)

    print('\n=== Generar (emitir)')
    llamar(C_REC, 'put', f'{URL}/{j1}/emitir', 403, None, 'Recepción no genera')
    llamar(C_MED2, 'put', f'{URL}/{j1}/emitir', 403, None, 'otro médico no genera')
    llamar(C_ADM, 'put', f'{URL}/{j1}/emitir', 403, None, 'el Administrador no genera')
    llamar(C_CAJ, 'put', f'{URL}/{j1}/emitir', 403, None, 'el Cajero no genera')
    llamar(C_MED, 'put', f'{URL}/99999999/emitir', 404, None, 'justificativo inexistente')
    llamar(C_MED, 'put', f'{URL}/{j1}/emitir', 200, {'estado': 'anulado'}, 'el médico genera (el cuerpo no elige el estado)', contiene='emitido')
    chk('...queda emitido', estado(j1) == 'emitido')
    llamar(C_MED, 'put', f'{URL}/{j1}/emitir', 409, None, 'ya emitido', contiene='ya está emitido')
    # con la consulta FINALIZADA el médico igual genera un pendiente
    j2 = alta(C_MED, base, 201, 'otro justificativo pendiente')['data']['id_justificativo']
    cu.execute("UPDATE consultas_cab SET estado='finalizada' WHERE id_consulta_cab=%s", (c1,)); cx.commit()
    llamar(C_MED, 'put', f'{URL}/{j2}/emitir', 200, None, 'con la consulta FINALIZADA el médico genera el documento')
    chk('...queda emitido', estado(j2) == 'emitido')
    cu.execute("UPDATE consultas_cab SET estado='en_proceso' WHERE id_consulta_cab=%s", (c1,)); cx.commit()
    c_can = consulta_nueva()
    j_can = alta(C_MED, {**base, 'id_consulta_cab': c_can}, 201, 'justificativo en la consulta que se cancela')['data']['id_justificativo']
    cu.execute("UPDATE consultas_cab SET estado='cancelada' WHERE id_consulta_cab=%s", (c_can,)); cx.commit()
    llamar(C_MED, 'put', f'{URL}/{j_can}/emitir', 409, None, 'con la consulta CANCELADA no se genera', contiene='cancelada')
    c_anu = consulta_nueva()
    j_anu = alta(C_MED, {**base, 'id_consulta_cab': c_anu}, 201, 'justificativo en la consulta que se anula')['data']['id_justificativo']
    cu.execute("UPDATE consultas_cab SET activo=false WHERE id_consulta_cab=%s", (c_anu,)); cx.commit()
    llamar(C_MED, 'put', f'{URL}/{j_anu}/emitir', 404, None, 'con la consulta ANULADA no se genera')
    cu.execute("UPDATE consultas_cab SET activo=true WHERE id_consulta_cab=%s", (c_anu,)); cx.commit()

    print('\n=== Anular (definitivo)')
    llamar(C_REC, 'delete', f'{URL}/{j1}', 403, None, 'Recepción no anula')
    llamar(C_MED2, 'delete', f'{URL}/{j1}', 403, None, 'otro médico no anula')
    llamar(C_ADM, 'delete', f'{URL}/{j1}', 403, None, 'el Administrador no anula')
    j3 = alta(C_MED, base, 201, 'un pendiente para anular')['data']['id_justificativo']
    llamar(C_MED, 'delete', f'{URL}/{j3}', 200, None, 'se anula un PENDIENTE', contiene='anulado')
    chk('...queda anulado', estado(j3) == 'anulado')
    llamar(C_MED, 'delete', f'{URL}/{j1}', 200, None, 'se anula un EMITIDO (consulta abierta)')
    chk('...queda anulado', estado(j1) == 'anulado')
    llamar(C_MED, 'delete', f'{URL}/{j1}', 404, None, 'anular dos veces')
    llamar(C_MED, 'put', f'{URL}/{j1}/emitir', 404, None, 'un anulado no se genera')
    chk('...ya no figura en el listado', llamar(C_MED, 'get', f'{URL}?consulta={c1}', 200, None, 'lista')['total'] == 1)
    c_fin = consulta_nueva('en_proceso')
    j_p = alta(C_MED, {**base, 'id_consulta_cab': c_fin}, 201, 'pendiente en una consulta que luego se finaliza')['data']['id_justificativo']
    j_e = alta(C_MED, {**base, 'id_consulta_cab': c_fin}, 201, 'otro, que se emite')['data']['id_justificativo']
    C_MED.put(f'{URL}/{j_e}/emitir')
    cu.execute("UPDATE consultas_cab SET estado='finalizada' WHERE id_consulta_cab=%s", (c_fin,)); cx.commit()
    llamar(C_MED, 'delete', f'{URL}/{j_p}', 409, None, 'con la consulta finalizada no se anula un pendiente', contiene='finalizada')
    llamar(C_MED, 'delete', f'{URL}/{j_e}', 409, None, 'con la consulta finalizada no se anula un emitido', contiene='finalizada')

    print('\n=== PDF')
    j_pdf = alta(C_MED, {**base, 'id_diagnostico': dx_ok, 'dias_reposo': 1}, 201, 'justificativo para el PDF')['data']['id_justificativo']
    numero = f'JUS-{j_pdf:07d}'
    r = C_MED.get(f'{URL}/{j_pdf}/pdf')
    t = texto_pdf(r.data)
    chk(f'el médico descarga -> {r.status_code} application/pdf', r.status_code == 200 and r.mimetype == 'application/pdf' and r.data[:4] == b'%PDF')
    chk('PENDIENTE: marca BORRADOR, título, N.º, paciente con CI, médico, reposo y recomendaciones, firma',
        all(x in t for x in ('BORRADOR', 'JUSTIFICATIVO', numero, 'ZZ PACIENTE', 'ZZ MEDICO', 'reposo por 1 d', SECRETO, 'Firma y sello')) and 'ANULADO' not in t)
    chk('la fecha y la clínica salen en el encabezado', re.search(r'Fecha: \d{2}/\d{2}/\d{4}', t) is not None and 'ODONTOCLINIC' in t)
    C_MED.put(f'{URL}/{j_pdf}/emitir')
    t = texto_pdf(C_MED.get(f'{URL}/{j_pdf}/pdf').data)
    chk('EMITIDO: sin marca', 'BORRADOR' not in t and 'ANULADO' not in t and numero in t and SECRETO in t)
    C_MED.delete(f'{URL}/{j_pdf}')
    t = texto_pdf(C_MED.get(f'{URL}/{j_pdf}/pdf').data)
    chk('ANULADO: marca ANULADO y el contenido intacto', 'ANULADO' in t and 'BORRADOR' not in t and SECRETO in t)
    chk('otro médico y Recepción NO descargan; el Administrador sí',
        C_MED2.get(f'{URL}/{j_pdf}/pdf').status_code == 403 and C_REC.get(f'{URL}/{j_pdf}/pdf').status_code == 403 and C_ADM.get(f'{URL}/{j_pdf}/pdf').status_code == 200
        and app.test_client().get(f'{URL}/{j_pdf}/pdf').status_code == 401 and C_MED.get(f'{URL}/99999999/pdf').status_code == 404)
    fx.auditoria_de('justificativo_medico', j_pdf)
    filas = q("SELECT detalle, id_usuario FROM auditoria_cambios WHERE entidad='justificativo_medico' AND id_registro=%s AND accion='EXPORTACION' ORDER BY id_auditoria_cambio", (j_pdf,))
    chk(f'cada descarga válida queda auditada como EXPORTACION (4: 3 del médico y 1 del Administrador): {len(filas)}', len(filas) == 4 and [f[1] for f in filas] == [u_med, u_med, u_med, admin])
    chk('...con el N.º, la consulta y el paciente, SIN contenido clínico', all(numero in f[0] and 'Consulta CON-' in f[0] and 'ZZ PACIENTE' in f[0] and SECRETO not in f[0] for f in filas))

    print('\n=== Auditoría sin contenido clínico')
    for i in registrados:
        fx.auditoria_de('justificativo_medico', i)
    filas = q("SELECT accion, modulo, valores_anteriores, valores_nuevos, id_usuario, detalle FROM auditoria_cambios WHERE entidad='justificativo_medico' AND id_registro=%s ORDER BY id_auditoria_cambio", (j1,))
    chk('j1: ALTA, MODIFICACION (generar) y BAJA, con módulo Consultorio y el usuario', [f[0] for f in filas] == ['ALTA', 'MODIFICACION', 'BAJA'] and all(f[1] == 'Módulo Consultorio' and f[4] == u_med for f in filas))
    chk('...el ALTA lleva N.º, consulta y paciente con CI', all(x in filas[0][5] for x in (f'JUS-{j1:07d}', 'Consulta: CON-', 'ZZ PACIENTE', 'CI ')))
    chk('...generar guarda Pendiente -> Emitido', (filas[1][2], filas[1][3]) == ({'Estado': 'Pendiente'}, {'Estado': 'Emitido'}))
    chk('...anular guarda Emitido -> Anulado', (filas[2][2], filas[2][3]) == ({'Estado': 'Emitido'}, {'Estado': 'Anulado'}))
    chk('...anular un pendiente guarda Pendiente -> Anulado', q("SELECT valores_anteriores, valores_nuevos FROM auditoria_cambios WHERE entidad='justificativo_medico' AND id_registro=%s AND accion='BAJA'", (j3,))[0] == ({'Estado': 'Pendiente'}, {'Estado': 'Anulado'}))
    todo = q("SELECT detalle, valores_anteriores::text, valores_nuevos::text FROM auditoria_cambios WHERE entidad='justificativo_medico' AND id_registro = ANY(%s)", (registrados,))
    chk('NINGUNA fila de auditoría contiene las recomendaciones', not any(SECRETO in (x or '') for fila in todo for x in fila))

    print('\n=== Carreras')
    c3 = consulta_nueva()
    cu.execute("SELECT 1 FROM consultas_cab WHERE id_consulta_cab=%s FOR UPDATE", (c3,))
    res = []
    h = threading.Thread(target=lambda: res.append(C_MED.post(URL, json={**base, 'id_consulta_cab': c3}).status_code)); h.start()
    time.sleep(0.8)
    cu.execute("UPDATE consultas_cab SET estado='cancelada' WHERE id_consulta_cab=%s", (c3,)); cx.commit(); h.join()
    chk(f'la consulta se cancela mientras se guarda: se rechaza (409): {res}', res == [409])
    chk('...y no quedó ningún justificativo en esa consulta', q("SELECT COUNT(*) FROM justificativo_medico WHERE id_consulta_cab=%s", (c3,))[0][0] == 0)
    c4 = consulta_nueva()
    j_r = alta(C_MED, {**base, 'id_consulta_cab': c4}, 201, 'justificativo para la carrera generar / anular')['data']['id_justificativo']
    res, barrera, cl = {}, threading.Barrier(2), [cliente(u_med), cliente(u_med)]

    def en_hilo(clave, f):
        barrera.wait(); res[clave] = f().status_code
    hs = [threading.Thread(target=en_hilo, args=('emitir', lambda: cl[0].put(f'{URL}/{j_r}/emitir'))), threading.Thread(target=en_hilo, args=('anular', lambda: cl[1].delete(f'{URL}/{j_r}')))]
    [x.start() for x in hs]; [x.join() for x in hs]
    chk(f'generar y anular a la vez: el estado final es anulado y las respuestas son coherentes ({res}, {estado(j_r)})',
        estado(j_r) == 'anulado' and res['anular'] == 200 and res['emitir'] in (200, 404))

    for (i,) in q("SELECT id_justificativo FROM justificativo_medico WHERE id_consulta_cab IN (SELECT id_consulta_cab FROM consultas_cab WHERE id_paciente=%s)", (pac,)):
        fx.auditoria_de('justificativo_medico', i)
    for (i,) in q("SELECT id_consulta_cab FROM consultas_cab WHERE id_paciente=%s", (pac,)):
        fx.auditoria_de('consultas_cab', i)
finally:
    cx.rollback()
    fx.limpiar()

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
