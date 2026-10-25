"""Etapa 4 (commit 1): Odontograma — uno por consulta con precarga hecha por el servidor, hallazgos FDI (pieza + superficie + estado) con baja lógica,
duplicados solo entre los activos, estados de pieza completa / de superficie, solo el médico de la consulta con la consulta abierta (revalidado en la
transacción), privacidad de las lecturas y auditoría sin piezas, superficies ni estados.
Datos `ZZ` de tests/consultorio/_fixtures.py (se borran por ID con su auditoría).
"""
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


def auditoria(i):
    return q("SELECT accion, modulo, valores_anteriores, valores_nuevos, id_usuario, detalle FROM auditoria_cambios "
             "WHERE entidad='odontograma' AND id_registro=%s ORDER BY id_auditoria_cambio", (i,))


O = '/api/v1/odontogramas'
creados = []   # ids de odontogramas (para la auditoría)

try:
    f_rec, u_rec = fx.recepcion()
    med, u_med = fx.medico()
    med2, u_med2 = fx.medico()
    pac, pac2 = fx.paciente(), fx.paciente()
    cons = fx.consultorio()
    admin = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Administrador' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    cajero = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    C_REC, C_MED, C_MED2, C_ADM, C_CAJ = cliente(u_rec), cliente(u_med), cliente(u_med2), cliente(admin), cliente(cajero)

    # estados dentales reales: uno de pieza completa y uno de superficie; y dos ZZ (uno inactivo)
    PIEZA = q("SELECT id_estado_dental, descripcion FROM estado_dental WHERE aplica_a='PIEZA' AND activo ORDER BY 1")[0]
    PIEZA2 = q("SELECT id_estado_dental FROM estado_dental WHERE aplica_a='PIEZA' AND activo ORDER BY 1")[1][0]
    SUPER = q("SELECT id_estado_dental, descripcion FROM estado_dental WHERE aplica_a='SUPERFICIE' AND activo ORDER BY 1")[0]
    SUPER2 = q("SELECT id_estado_dental FROM estado_dental WHERE aplica_a='SUPERFICIE' AND activo ORDER BY 1")[1][0]
    E_INACTIVO = fx.estado_dental('SUPERFICIE', activo=False)

    def consulta(fecha, estado='programada', medico=None, paciente=None):
        i = fx.registrar_consulta(fx.cita(medico or med, paciente or pac, cons, f_rec), f_rec, estado)
        cu.execute("UPDATE consultas_cab SET fecha_cita=%s, hora_cita='09:00' WHERE id_consulta_cab=%s", (fecha, i)); cx.commit()
        fx.auditoria_de('consultas_cab', i)
        return i

    def crear(c, id_consulta, esperado=201, nombre=None, **kw):
        d = llamar(c, 'post', O, esperado, {'id_consulta_cab': id_consulta}, nombre or f'crear el odontograma de la consulta {id_consulta}', **kw)
        if esperado == 201:
            creados.append(d['data']['id_odontograma'])
        return d

    def hallazgo(c, id_odo, pieza, superficie, estado, esperado=201, nombre=None, observacion=None, **kw):
        cuerpo = {'numero_diente': pieza, 'superficie': superficie, 'id_estado_dental': estado}
        if observacion:
            cuerpo['observacion'] = observacion
        return llamar(c, 'post', f'{O}/{id_odo}/hallazgos', esperado, cuerpo, nombre or f'hallazgo {pieza}/{superficie}/{estado}', **kw)

    def activos(id_odo):
        return q("SELECT numero_diente, superficie, id_estado_dental FROM odontograma_detalle WHERE id_odontograma=%s AND activo ORDER BY 1,2,3", (id_odo,))

    print('\n=== Catálogo y esquema')
    chk('sin sesión: /estados-dentales -> 401', app.test_client().get('/api/v1/estados-dentales').status_code == 401)
    d = llamar(C_CAJ, 'get', '/api/v1/estados-dentales', 200, nombre='cualquiera con sesión lee el catálogo de estados')
    chk('trae id, descripción, color, símbolo y a qué se aplica (22 estados: 7 de superficie y 15 de pieza)',
        len(d['data']) >= 22 and all({'id_estado_dental', 'descripcion', 'color', 'simbolo', 'aplica_a'} <= set(x) for x in d['data'])
        and sum(1 for x in d['data'] if x['aplica_a'] == 'SUPERFICIE' and not x['descripcion'].startswith('ZZ')) == 7)
    chk('el estado dental inactivo no aparece en el catálogo', E_INACTIVO not in {x['id_estado_dental'] for x in d['data']})

    print('\n=== Permisos y quién crea')
    c1 = consulta('2026-06-01')
    chk('sin sesión -> 401', app.test_client().post(O, json={'id_consulta_cab': c1}).status_code == 401)
    crear(C_CAJ, c1, 403, 'el Cajero no crea')
    crear(C_REC, c1, 403, 'Recepción no crea (no tiene la ventana de Odontograma)')
    crear(C_ADM, c1, 403, 'el Administrador no crea (lectura clínica)', contiene='médico de la consulta')
    crear(C_MED2, c1, 403, 'otro médico no crea en la consulta ajena', contiene='médico de la consulta')
    llamar(C_MED, 'post', O, 400, {}, 'sin id_consulta_cab', campo='id_consulta_cab')
    llamar(C_MED, 'post', O, 400, {'id_consulta_cab': 'x'}, 'id_consulta_cab no numérico', campo='id_consulta_cab')
    crear(C_MED, 999999999, 404, 'consulta inexistente')
    chk('los rechazos no dejaron odontogramas', q("SELECT COUNT(*) FROM odontograma WHERE id_consulta_cab=%s", (c1,))[0][0] == 0)

    print('\n=== Alta (sin previo: queda sin hallazgos, y se permite)')
    d = crear(C_MED, c1)
    o1 = d['data']['id_odontograma']
    chk('sin odontograma previo del paciente: nada precargado y sin hallazgos', d['data']['precargado_de'] is None and activos(o1) == [])
    chk('paciente y médico se heredan de la consulta', q("SELECT id_paciente, id_medico, id_consulta_cab, activo FROM odontograma WHERE id_odontograma=%s", (o1,))[0] == (pac, med, c1, True))
    crear(C_MED, c1, 409, 'uno solo por consulta', contiene='Hay uno solo por consulta')
    a = auditoria(o1)
    chk('auditoría ALTA: módulo, quién, consulta y paciente con CI (sin nada clínico)', len(a) == 1 and a[0][0] == 'ALTA' and a[0][1] == 'Módulo Consultorio'
        and a[0][4] == u_med and set(a[0][3]) == {'Consulta', 'Paciente'} and 'CI ZZ' in a[0][3]['Paciente'])
    d = llamar(C_MED, 'get', f'{O}/consulta/{c1}', 200, nombre='el odontograma de la consulta')
    chk('trae la cabecera con consulta, paciente, médico y la lista (vacía) de hallazgos', d['data']['id_odontograma'] == o1 and d['data']['hallazgos'] == [] and d['data']['numero_consulta'] == f'CON-{c1:07d}')
    c_sin = consulta('2026-06-02')
    chk('una consulta sin odontograma devuelve data = null', llamar(C_MED, 'get', f'{O}/consulta/{c_sin}', 200, nombre='consulta sin odontograma')['data'] is None)

    print('\n=== Hallazgos: validaciones')
    for pieza in ('19', '0', '99', '56', '86', '10', 'x', '', None, 1.5, True):
        hallazgo(C_MED, o1, pieza, 'O', SUPER[0], 400, f'pieza {pieza!r} fuera de la nomenclatura FDI', campo='numero_diente')
    for superf in ('X', '', 'OO', None, 5, 'o '):   # 'o ' se normaliza a O: no es inválida
        if superf == 'o ':
            continue
        hallazgo(C_MED, o1, 18, superf, SUPER[0], 400, f'superficie {superf!r} inválida', campo='superficie')
    llamar(C_MED, 'post', f'{O}/{o1}/hallazgos', 400, {'numero_diente': 18, 'superficie': 'O'}, 'sin estado dental', campo='id_estado_dental')
    hallazgo(C_MED, o1, 18, 'O', 'x', 400, 'estado dental no numérico', campo='id_estado_dental')
    hallazgo(C_MED, o1, 18, 'O', 999999999, 400, 'estado dental inexistente', campo='id_estado_dental')
    hallazgo(C_MED, o1, 18, 'O', E_INACTIVO, 409, 'estado dental INACTIVO', campo='id_estado_dental', contiene='inactivo')
    hallazgo(C_MED, o1, 18, 'O', SUPER[0], 400, 'observación de 501', observacion='x' * 501, campo='observacion')
    hallazgo(C_MED, o1, 18, 'O', PIEZA[0], 400, f'«{PIEZA[1]}» es de la pieza completa: no admite la superficie O', campo='superficie', contiene='pieza completa')
    hallazgo(C_MED, o1, 18, 'T', SUPER[0], 400, f'«{SUPER[1]}» es de superficie: no admite T', campo='superficie', contiene='superficie')
    llamar(C_MED, 'post', f'{O}/999999999/hallazgos', 404, {'numero_diente': 18, 'superficie': 'O', 'id_estado_dental': SUPER[0]}, 'odontograma inexistente')
    chk('ninguna inválida se guardó', activos(o1) == [])

    print('\n=== Hallazgos: alta, duplicados y baja lógica')
    d = hallazgo(C_MED, o1, '18', 'o', SUPER[0], 201, 'caries en la 18, superficie oclusal (minúscula y piezas como texto)', observacion='  sensibilidad  ')
    h1 = d['data']['id_odontograma_detalle']
    chk('guardado normalizado (superficie en mayúscula, observación recortada)', q("SELECT superficie, observacion FROM odontograma_detalle WHERE id_odontograma_detalle=%s", (h1,))[0] == ('O', 'sensibilidad'))
    hallazgo(C_MED, o1, 18, 'O', SUPER[0], 409, 'un registro IDÉNTICO (misma pieza, superficie y estado) se rechaza', contiene='ya está registrado', campo='id_estado_dental')
    hallazgo(C_MED, o1, 18, 'O', SUPER2, 201, 'misma pieza y superficie con OTRO estado: se permite')
    hallazgo(C_MED, o1, 18, 'V', SUPER[0], 201, 'mismo estado en OTRA superficie: se permite')
    hallazgo(C_MED, o1, 11, 'T', PIEZA[0], 201, 'estado de pieza completa con la superficie T')
    hallazgo(C_MED, o1, 55, 'T', PIEZA2, 201, 'pieza temporal 55')
    chk('5 hallazgos activos', len(activos(o1)) == 5)
    d = llamar(C_MED, 'get', f'{O}/{o1}', 200, nombre='leer el odontograma con sus hallazgos')
    hs = d['data']['hallazgos']
    chk('cada hallazgo trae pieza, superficie, estado con color, símbolo y a qué se aplica', len(hs) == 5 and all({'id_odontograma_detalle', 'numero_diente', 'superficie', 'estado_descripcion', 'estado_color', 'estado_simbolo', 'aplica_a'} <= set(h) for h in hs))
    a = auditoria(o1)
    chk('cada cambio audita MODIFICACION "odontograma modificado" SIN piezas, superficies ni estados', sum(1 for x in a if x[0] == 'MODIFICACION') == 5
        and all(x[2] is None and x[3] is None and 'odontograma modificado' in x[5] and 'CON-' in x[5] for x in a if x[0] == 'MODIFICACION'))
    # quitar = baja lógica del renglón
    llamar(C_REC, 'delete', f'{O}/hallazgos/{h1}', 403, nombre='Recepción no quita hallazgos')
    llamar(C_ADM, 'delete', f'{O}/hallazgos/{h1}', 403, nombre='el Administrador no quita hallazgos')
    llamar(C_MED2, 'delete', f'{O}/hallazgos/{h1}', 403, nombre='otro médico no quita hallazgos', contiene='médico de la consulta')
    llamar(C_MED, 'delete', f'{O}/hallazgos/999999999', 404, nombre='quitar un hallazgo inexistente')
    llamar(C_MED, 'delete', f'{O}/hallazgos/{h1}', 200, nombre='el médico quita el hallazgo', contiene='quitado')
    chk('BAJA LÓGICA: el renglón sigue en la tabla con activo = false (trazabilidad)', q("SELECT activo FROM odontograma_detalle WHERE id_odontograma_detalle=%s", (h1,)) == [(False,)])
    chk('...y ya no se lee', h1 not in {h['id_odontograma_detalle'] for h in llamar(C_MED, 'get', f'{O}/{o1}', 200, nombre='releer')['data']['hallazgos']})
    llamar(C_MED, 'delete', f'{O}/hallazgos/{h1}', 404, nombre='quitar uno ya quitado')
    hallazgo(C_MED, o1, 18, 'O', SUPER[0], 201, 'el control de duplicados mira solo los ACTIVOS: se puede volver a cargar el mismo hallazgo (índice único parcial)')
    chk('quedan 2 renglones (uno inactivo y uno activo) para ese hallazgo',
        q("SELECT COUNT(*), COUNT(*) FILTER (WHERE activo) FROM odontograma_detalle WHERE id_odontograma=%s AND numero_diente=18 AND superficie='O' AND id_estado_dental=%s", (o1, SUPER[0]))[0] == (2, 1))

    print('\n=== Precarga con el último odontograma vigente del paciente de una consulta ANTERIOR')
    cA = consulta('2026-01-10')            # el que se debe copiar
    cB = consulta('2026-02-10')            # su consulta se cancela: se ignora
    cC = consulta('2026-03-10')            # su odontograma se anula: se ignora
    cX = consulta('2026-01-20', paciente=pac2)   # de OTRO paciente: se ignora
    oA = crear(C_MED, cA)['data']['id_odontograma']
    hA1 = hallazgo(C_MED, oA, 11, 'T', PIEZA[0], 201, 'A: corona/pieza 11', observacion='obs A')['data']['id_odontograma_detalle']
    hallazgo(C_MED, oA, 18, 'O', SUPER[0], 201, 'A: caries en 18 O')
    hQ = hallazgo(C_MED, oA, 17, 'V', SUPER2, 201, 'A: hallazgo que luego se quita')['data']['id_odontograma_detalle']
    llamar(C_MED, 'delete', f'{O}/hallazgos/{hQ}', 200, nombre='A: se quita ese hallazgo')
    oB = crear(C_MED, cB)['data']['id_odontograma']
    hallazgo(C_MED, oB, 21, 'T', PIEZA[0], 201, 'B: hallazgo propio')
    cu.execute("UPDATE consultas_cab SET estado='cancelada' WHERE id_consulta_cab=%s", (cB,)); cx.commit()
    oC = crear(C_MED, cC)['data']['id_odontograma']
    hallazgo(C_MED, oC, 22, 'T', PIEZA[0], 201, 'C: hallazgo propio')
    llamar(C_MED, 'delete', f'{O}/{oC}', 200, nombre='C: se anula su odontograma')
    oX = crear(cliente(fx.medico()[1]), cX, 403, 'X: otro médico no crea en la consulta de otro paciente')
    cD = consulta('2026-04-10')            # la consulta que precarga
    d = crear(C_MED, cD)
    oD = d['data']['id_odontograma']
    org = d['data']['precargado_de']
    chk(f'precargó desde la consulta A (la anterior vigente; ignoró la cancelada, la anulada y la de otro paciente): {org}',
        org and org['id_consulta_cab'] == cA and org['numero_consulta'] == f'CON-{cA:07d}' and org['copiados'] == 2 and f'CON-{cA:07d}' in d['mensaje'])
    chk('copió SOLO los hallazgos activos (2 de los 3 de A) con su observación', activos(oD) == [(11, 'T', PIEZA[0]), (18, 'O', SUPER[0])]
        and q("SELECT observacion FROM odontograma_detalle WHERE id_odontograma=%s AND numero_diente=11 AND activo", (oD,))[0][0] == 'obs A')
    a = auditoria(oD)
    chk('auditoría ALTA menciona de qué consulta se precargó (solo el N.º, sin hallazgos)', f'CON-{cA:07d}' in a[0][5] and 'Precargado desde' in a[0][3] and 'Corona' not in a[0][5])
    # lo que se cambia en D no toca A
    hallazgo(C_MED, oD, 28, 'T', PIEZA2, 201, 'D: se agrega un hallazgo propio')
    hd = q("SELECT id_odontograma_detalle FROM odontograma_detalle WHERE id_odontograma=%s AND numero_diente=11 AND activo", (oD,))[0][0]
    llamar(C_MED, 'delete', f'{O}/hallazgos/{hd}', 200, nombre='D: se quita un hallazgo precargado')
    chk('el odontograma de A quedó intacto', activos(oA) == [(11, 'T', PIEZA[0]), (18, 'O', SUPER[0])])
    # la siguiente precarga sale del último vigente (D), no de A
    cE = consulta('2026-05-10')
    d = crear(C_MED, cE)
    chk('la consulta siguiente precarga del último vigente (D), con sus cambios', d['data']['precargado_de']['id_consulta_cab'] == cD
        and activos(d['data']['id_odontograma']) == [(18, 'O', SUPER[0]), (28, 'T', PIEZA2)])
    # una consulta ANTERIOR a todas no precarga nada
    cOld = consulta('2025-01-01')
    chk('una consulta anterior a todas no precarga', crear(C_MED, cOld)['data']['precargado_de'] is None)

    print('\n=== Anular el odontograma (definitivo)')
    llamar(C_REC, 'delete', f'{O}/{oD}', 403, nombre='Recepción no anula')
    llamar(C_ADM, 'delete', f'{O}/{oD}', 403, nombre='el Administrador no anula')
    llamar(C_MED2, 'delete', f'{O}/{oD}', 403, nombre='otro médico no anula')
    llamar(C_MED, 'delete', f'{O}/999999999', 404, nombre='anular inexistente')
    llamar(C_MED, 'delete', f'{O}/{oD}', 200, nombre='el médico anula el odontograma', contiene='anulado correctamente')
    chk('queda inactivo y SUS HALLAZGOS quedan como historial', q("SELECT activo FROM odontograma WHERE id_odontograma=%s", (oD,))[0][0] is False and len(activos(oD)) == 2)
    a = auditoria(oD)
    chk('auditoría BAJA: Activo -> Anulado', a[-1][0] == 'BAJA' and a[-1][2] == {'Estado': 'Activo'} and a[-1][3] == {'Estado': 'Anulado'} and 'CON-' in a[-1][5])
    llamar(C_MED, 'delete', f'{O}/{oD}', 404, nombre='anular uno ya anulado')
    llamar(C_MED, 'get', f'{O}/{oD}', 404, nombre='un anulado ya no se lee')
    hallazgo(C_MED, oD, 12, 'T', PIEZA[0], 404, 'no se agregan hallazgos a un odontograma anulado')
    d = crear(C_MED, cD, 201, 'se puede crear OTRO odontograma para la misma consulta (único parcial por consulta activa)')
    chk('...precargado de nuevo desde A (el último vigente anterior)', d['data']['precargado_de']['id_consulta_cab'] == cA)

    print('\n=== La consulta debe estar programada o en proceso (se revalida al guardar)')
    cu.execute("UPDATE consultas_cab SET estado='en_proceso' WHERE id_consulta_cab=%s", (c1,)); cx.commit()
    hallazgo(C_MED, o1, 13, 'T', PIEZA[0], 201, 'en_proceso: se pueden agregar hallazgos')
    h_f = q("SELECT id_odontograma_detalle FROM odontograma_detalle WHERE id_odontograma=%s AND numero_diente=13 AND activo", (o1,))[0][0]
    for estado in ('finalizada', 'cancelada'):
        cu.execute("UPDATE consultas_cab SET estado=%s WHERE id_consulta_cab=%s", (estado, c1)); cx.commit()
        hallazgo(C_MED, o1, 14, 'T', PIEZA[0], 409, f'consulta {estado}: no se agregan hallazgos', contiene=estado)
        llamar(C_MED, 'delete', f'{O}/hallazgos/{h_f}', 409, nombre=f'consulta {estado}: no se quitan hallazgos', contiene=estado)
        llamar(C_MED, 'delete', f'{O}/{o1}', 409, nombre=f'consulta {estado}: no se anula el odontograma', contiene=estado)
        crear(C_MED, consulta('2026-07-01', estado), 409, f'consulta {estado}: no se crea el odontograma', contiene=estado)
    chk('nada cambió', q("SELECT activo FROM odontograma_detalle WHERE id_odontograma_detalle=%s", (h_f,))[0][0] is True)
    cu.execute("UPDATE consultas_cab SET estado='programada' WHERE id_consulta_cab=%s", (c1,)); cx.commit()
    c_anul = consulta('2026-07-02'); cu.execute("UPDATE consultas_cab SET activo=false WHERE id_consulta_cab=%s", (c_anul,)); cx.commit()
    crear(C_MED, c_anul, 404, 'consulta anulada: no se crea')

    print('\n=== Lecturas: privacidad')
    llamar(C_ADM, 'get', f'{O}/{o1}', 200, nombre='el Administrador lee')
    llamar(C_MED2, 'get', f'{O}/{o1}', 403, nombre='otro médico NO lee un odontograma ajeno')
    llamar(C_MED2, 'get', f'{O}/consulta/{c1}', 403, nombre='otro médico NO lee el de la consulta ajena')
    llamar(C_REC, 'get', f'{O}/{o1}', 403, nombre='Recepción NO lee odontogramas')
    llamar(C_CAJ, 'get', f'{O}/{o1}', 403, nombre='el Cajero NO lee odontogramas')
    d = llamar(C_MED, 'get', O + '?q=ZZ+PACIENTE&por_pagina=100', 200, nombre='listado del médico')
    chk('trae los vigentes con la cantidad de hallazgos y NO los anulados', o1 in {x['id_odontograma'] for x in d['data']} and oD not in {x['id_odontograma'] for x in d['data']}
        and all('cantidad_hallazgos' in x and 'hallazgos' not in x for x in d['data']))
    d = llamar(C_MED2, 'get', O + '?por_pagina=100', 200, nombre='otro médico lista solo lo suyo')
    chk('...no ve los de ZZ PACIENTE', o1 not in {x['id_odontograma'] for x in d['data']})
    for malo in ('?desde=2026-13-40', '?desde=2026-10-10&hasta=2026-10-01', '?pagina=x'):
        llamar(C_MED, 'get', O + malo, 400, nombre=f'filtro inválido {malo}')
    d = llamar(C_MED, 'get', f'{O}/paciente/{pac}', 200, nombre='odontogramas por paciente (solo los del médico)')
    chk('...vigentes', d['total'] >= 3)
    chk('...otro médico no ve ninguno', llamar(C_MED2, 'get', f'{O}/paciente/{pac}', 200, nombre='por paciente, otro médico')['data'] == [])
    chk('los endpoints viejos ya no existen (PATCH estado, PUT, validar-consulta, precarga)',
        C_MED.patch(f'{O}/{o1}/estado', json={'estado': 'Activo'}).status_code in (404, 405) and C_MED.put(f'{O}/{o1}', json={}).status_code in (404, 405)
        and C_MED.get(f'{O}/validar-consulta/{c1}').status_code == 404 and C_MED.get(f'{O}/precarga/{c1}').status_code == 404)

    print('\n=== Carreras')
    c9 = consulta('2026-08-01')
    res, barrera = [], threading.Barrier(2)
    cls = [cliente(u_med), cliente(u_med)]

    def crear_sinc(c):
        barrera.wait()
        res.append(c.post(O, json={'id_consulta_cab': c9}).status_code)
    hs = [threading.Thread(target=crear_sinc, args=(c,)) for c in cls]
    [h.start() for h in hs]; [h.join() for h in hs]
    chk(f'dos altas simultáneas: una gana (201) y la otra es rechazada (409): {sorted(res)}', sorted(res) == [201, 409])
    chk('...un solo odontograma activo', q("SELECT COUNT(*) FROM odontograma WHERE id_consulta_cab=%s AND activo", (c9,))[0][0] == 1)
    o9 = q("SELECT id_odontograma FROM odontograma WHERE id_consulta_cab=%s AND activo", (c9,))[0][0]
    creados.append(o9)
    res, barrera = [], threading.Barrier(2)
    cls = [cliente(u_med), cliente(u_med)]

    def hallazgo_sinc(c):
        barrera.wait()
        res.append(c.post(f'{O}/{o9}/hallazgos', json={'numero_diente': 36, 'superficie': 'D', 'id_estado_dental': SUPER[0]}).status_code)
    hs = [threading.Thread(target=hallazgo_sinc, args=(c,)) for c in cls]
    [h.start() for h in hs]; [h.join() for h in hs]
    chk(f'dos hallazgos idénticos simultáneos: uno entra (201) y el otro es rechazado (409): {sorted(res)}', sorted(res) == [201, 409])
    chk('...un solo renglón activo', q("SELECT COUNT(*) FROM odontograma_detalle WHERE id_odontograma=%s AND numero_diente=36 AND activo", (o9,))[0][0] == 1)
    # la consulta pasa a finalizada mientras se agrega un hallazgo
    cu.execute("SELECT 1 FROM consultas_cab WHERE id_consulta_cab=%s FOR UPDATE", (c9,))
    res = []
    h = threading.Thread(target=lambda: res.append(cliente(u_med).post(f'{O}/{o9}/hallazgos', json={'numero_diente': 37, 'superficie': 'T', 'id_estado_dental': PIEZA[0]}).status_code))
    h.start()
    time.sleep(0.8)
    cu.execute("UPDATE consultas_cab SET estado='finalizada' WHERE id_consulta_cab=%s", (c9,)); cx.commit(); h.join()
    chk(f'la consulta se finaliza mientras se agrega un hallazgo: se rechaza (409): {res}', res == [409])
    chk('...y no quedó el hallazgo', q("SELECT COUNT(*) FROM odontograma_detalle WHERE id_odontograma=%s AND numero_diente=37", (o9,))[0][0] == 0)

    for i in creados + [oA, oB, oC, oD, o1, o9]:
        fx.auditoria_de('odontograma', i)
    for (i,) in q("SELECT id_odontograma FROM odontograma WHERE id_paciente = ANY(%s)", ([pac, pac2],)):
        fx.auditoria_de('odontograma', i)
finally:
    cx.rollback()
    fx.limpiar()

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
