"""Etapa 4 (commit 1): Diagnóstico — alta con las reglas del análisis (tipo activo, al menos un síntoma activo, descripción, pieza FDI opcional),
solo el médico de la consulta con la consulta programada / en proceso (revalidado en la transacción), anulación definitiva sin tratamiento vigente,
privacidad de las lecturas, los diagnósticos viejos se siguen mostrando y auditoría sin contenido clínico.
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
             "WHERE entidad='diagnosticos' AND id_registro=%s ORDER BY id_auditoria_cambio", (i,))


URL = '/api/v1/diagnosticos-medicos'
SECRETO = 'RESERVADO-DX-5521'
registrados = []   # ids de diagnósticos creados por la API (para borrar su auditoría)

try:
    f_rec, u_rec = fx.recepcion()
    med, u_med = fx.medico()
    med2, u_med2 = fx.medico()
    pac, cons = fx.paciente(), fx.consultorio()
    tipo, tipo_inactivo = fx.tipo_diagnostico(), fx.tipo_diagnostico(activo=False)
    s1, s2, s_inactivo = fx.sintoma(), fx.sintoma(), fx.sintoma(activo=False)
    admin = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Administrador' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    cajero = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    C_REC, C_MED, C_MED2, C_ADM, C_CAJ = cliente(u_rec), cliente(u_med), cliente(u_med2), cliente(admin), cliente(cajero)

    def consulta_nueva(estado='programada', medico=None):
        return fx.registrar_consulta(fx.cita(medico or med, pac, cons, f_rec), f_rec, estado)

    c1 = consulta_nueva()
    base = {'id_consulta_cab': c1, 'id_tipo_diagnostico': tipo, 'sintomas': [s1, s2], 'descripcion_diagnostico': 'Caries profunda ' + SECRETO,
            'pieza_dental': '18', 'observaciones': 'Requiere control'}

    def alta(c, datos, esperado, nombre, **kw):
        d = llamar(c, 'post', URL, esperado, datos, nombre, **kw)
        if esperado == 201:
            registrados.append(d['data']['id_diagnostico'])
        return d

    print('\n=== Esquema')
    chk('pieza FDI en la base (CHECK) y descripción no vacía',
        {'chk_diagnostico_pieza_fdi', 'chk_diagnostico_descripcion'} <= {x[0] for x in q("SELECT conname FROM pg_constraint WHERE conrelid='diagnosticos'::regclass")})
    for sql, nombre in (("INSERT INTO diagnosticos(codigo, id_consulta_cab, id_paciente, id_medico, id_tipo_diagnostico, descripcion_diagnostico, pieza_dental, fecha_diagnostico) "
                         "VALUES ('ZXFDI', %s, %s, %s, %s, 'ZZ', '19', CURRENT_DATE)", 'pieza 19 (no existe en FDI)'),
                        ("INSERT INTO diagnosticos(codigo, id_consulta_cab, id_paciente, id_medico, id_tipo_diagnostico, descripcion_diagnostico, fecha_diagnostico) "
                         "VALUES ('ZXVAC', %s, %s, %s, %s, '   ', CURRENT_DATE)", 'descripción en blanco'),
                        ("INSERT INTO diagnosticos(codigo, id_consulta_cab, id_paciente, id_medico, id_tipo_diagnostico, descripcion_diagnostico, fecha_diagnostico) "
                         "VALUES ('ZXSIN', %s, %s, %s, %s, 'ZZ', CURRENT_DATE)", 'diagnóstico vigente sin ningún síntoma (trigger diferido)')):
        try:
            cu.execute(sql, (c1, pac, med, tipo)); cx.commit(); ok = False
        except Exception:
            cx.rollback(); ok = True
        chk(f'la base rechaza: {nombre}', ok)
    chk('...y no dejó nada', q("SELECT COUNT(*) FROM diagnosticos WHERE codigo LIKE 'ZX%%'")[0][0] == 0)
    cu.execute("INSERT INTO diagnosticos(codigo, id_consulta_cab, id_paciente, id_medico, id_tipo_diagnostico, descripcion_diagnostico, pieza_dental, fecha_diagnostico) "
               "VALUES ('ZXOK', %s, %s, %s, %s, 'ZZ', '85', CURRENT_DATE) RETURNING id_diagnostico", (c1, pac, med, tipo))
    ok_id = cu.fetchone()[0]
    cu.execute("INSERT INTO diagnostico_sintoma VALUES (%s, %s)", (ok_id, s1)); cx.commit()
    chk('(control) con un síntoma y pieza temporal 85 sí se guarda', q("SELECT COUNT(*) FROM diagnosticos WHERE codigo='ZXOK'")[0][0] == 1)
    cu.execute("DELETE FROM diagnostico_sintoma WHERE id_diagnostico=%s", (ok_id,)); cu.execute("DELETE FROM diagnosticos WHERE id_diagnostico=%s", (ok_id,)); cx.commit()

    print('\n=== Permisos y quién registra')
    chk('sin sesión -> 401', app.test_client().post(URL, json=base).status_code == 401)
    llamar(C_CAJ, 'post', URL, 403, base, 'el Cajero no registra')
    llamar(C_REC, 'post', URL, 403, base, 'Recepción no registra (ya no tiene la ventana de Diagnóstico)')
    alta(C_ADM, base, 403, 'el Administrador no registra (lectura clínica)', contiene='médico de la consulta')
    alta(C_MED2, base, 403, 'otro médico no registra en la consulta ajena', contiene='médico de la consulta')
    chk('ningún rechazo dejó un diagnóstico', q("SELECT COUNT(*) FROM diagnosticos WHERE id_consulta_cab=%s", (c1,))[0][0] == 0)

    print('\n=== Validaciones')
    sin = lambda k: {x: v for x, v in base.items() if x != k}
    alta(C_MED, sin('id_consulta_cab'), 400, 'sin id_consulta_cab', campo='id_consulta_cab')
    alta(C_MED, {**base, 'id_consulta_cab': 'x'}, 400, 'id_consulta_cab no numérico', campo='id_consulta_cab')
    alta(C_MED, {**base, 'id_consulta_cab': 999999999}, 404, 'consulta inexistente')
    alta(C_MED, sin('id_tipo_diagnostico'), 400, 'sin tipo de diagnóstico', campo='id_tipo_diagnostico')
    alta(C_MED, {**base, 'id_tipo_diagnostico': 'x'}, 400, 'tipo no numérico', campo='id_tipo_diagnostico')
    alta(C_MED, {**base, 'id_tipo_diagnostico': 999999999}, 400, 'tipo inexistente', campo='id_tipo_diagnostico')
    alta(C_MED, {**base, 'id_tipo_diagnostico': tipo_inactivo}, 409, 'tipo INACTIVO', campo='id_tipo_diagnostico', contiene='inactivo')
    for malo in (None, [], 'dolor', [True], ['a'], [0], [-1]):
        alta(C_MED, {**base, 'sintomas': malo}, 400, f'síntomas inválidos {malo!r}', campo='sintomas')
    alta(C_MED, sin('sintomas'), 400, 'sin síntomas: al menos uno', campo='sintomas', contiene='al menos un síntoma')
    alta(C_MED, {**base, 'sintomas': [s1, 999999999]}, 400, 'síntoma inexistente', campo='sintomas')
    alta(C_MED, {**base, 'sintomas': [s1, s_inactivo]}, 409, 'síntoma INACTIVO (nombra cuál)', campo='sintomas', contiene='ZZ SINTOMA')
    for malo in (None, '', '   ', 'x' * 1001, 'raro\x01'):
        alta(C_MED, {**base, 'descripcion_diagnostico': malo}, 400, f'descripción inválida {str(malo)[:12]!r}', campo='descripcion_diagnostico')
    for malo in ('19', '99', '56', '86', '10', 'abc', 0, 1.5, '1 8', True):
        alta(C_MED, {**base, 'pieza_dental': malo}, 400, f'pieza dental {malo!r} fuera de la nomenclatura FDI', campo='pieza_dental')
    alta(C_MED, {**base, 'observaciones': 'x' * 2001}, 400, 'observaciones de 2001', campo='observaciones')
    chk('ninguna inválida se guardó', q("SELECT COUNT(*) FROM diagnosticos WHERE id_consulta_cab=%s", (c1,))[0][0] == 0)

    print('\n=== Alta')
    d = alta(C_MED, {**base, 'fecha_diagnostico': '2001-01-01', 'id_paciente': 999, 'id_medico': 999, 'codigo': 'HACK-1', 'id_usuario_registro': 999},
             201, 'el médico de la consulta registra el diagnóstico (con campos de más que el servidor ignora)')
    id1 = d['data']['id_diagnostico']
    chk('código DX-NNNN generado por el servidor', d['data']['codigo'].startswith('DX-') and 'HACK' not in d['data']['codigo'])
    fila = q("SELECT codigo, id_paciente, id_medico, fecha_diagnostico = CURRENT_DATE, pieza_dental, id_usuario_registro, activo FROM diagnosticos WHERE id_diagnostico=%s", (id1,))[0]
    chk('paciente y médico se heredan de la consulta, la fecha es la de hoy (la fija el servidor) y el usuario es el de la sesión',
        fila[1:4] == (pac, med, True) and fila[5] == u_med and fila[6] is True)
    chk('pieza FDI guardada y los 2 síntomas en diagnostico_sintoma', fila[4] == '18' and sorted(x[0] for x in q("SELECT id_sintoma FROM diagnostico_sintoma WHERE id_diagnostico=%s", (id1,))) == sorted([s1, s2]))
    d2 = alta(C_MED, {k: v for k, v in base.items() if k not in ('pieza_dental', 'observaciones')}, 201, 'la pieza dental y las observaciones son opcionales')
    id2 = d2['data']['id_diagnostico']
    chk('...sin pieza queda NULL y los códigos son distintos', q("SELECT pieza_dental FROM diagnosticos WHERE id_diagnostico=%s", (id2,))[0][0] is None and d2['data']['codigo'] != d['data']['codigo'])
    alta(C_MED, {**base, 'pieza_dental': 55, 'sintomas': [s1, s1, s1]}, 201, 'pieza temporal 55 (entero) y síntomas repetidos se unifican')
    chk('...queda un solo renglón del síntoma repetido', q("SELECT COUNT(*) FROM diagnostico_sintoma WHERE id_diagnostico=%s", (registrados[-1],))[0][0] == 1)
    a = auditoria(id1)
    chk('auditoría ALTA: módulo, quién y SOLO código, consulta y paciente con CI',
        len(a) == 1 and a[0][0] == 'ALTA' and a[0][1] == 'Módulo Consultorio' and a[0][2] is None and a[0][4] == u_med
        and set(a[0][3]) == {'Diagnóstico', 'Consulta', 'Paciente'} and 'CI ZZ' in a[0][3]['Paciente'] and a[0][3]['Diagnóstico'] == d['data']['codigo'])

    print('\n=== La consulta debe estar programada o en proceso')
    cu.execute("UPDATE consultas_cab SET estado='en_proceso' WHERE id_consulta_cab=%s", (c1,)); cx.commit()
    alta(C_MED, base, 201, 'en_proceso: se puede registrar')
    for estado in ('finalizada', 'cancelada'):
        cu.execute("UPDATE consultas_cab SET estado=%s WHERE id_consulta_cab=%s", (estado, c1)); cx.commit()
        alta(C_MED, base, 409, f'consulta {estado}: no se registra', contiene=estado)
        llamar(C_MED, 'delete', f'{URL}/{id2}', 409, nombre=f'consulta {estado}: no se anula', contiene='finalizada' if estado == 'finalizada' else estado)
    cu.execute("UPDATE consultas_cab SET estado='programada' WHERE id_consulta_cab=%s", (c1,)); cx.commit()
    c_anulada = consulta_nueva(); cu.execute("UPDATE consultas_cab SET activo=false WHERE id_consulta_cab=%s", (c_anulada,)); cx.commit()
    alta(C_MED, {**base, 'id_consulta_cab': c_anulada}, 404, 'consulta anulada: no se registra')

    print('\n=== Lecturas: privacidad')
    d = llamar(C_MED, 'get', f'{URL}/{id1}', 200, nombre='el médico lee su diagnóstico')
    x = d['data']
    chk('trae tipo, síntomas {id, descripción}, descripción, pieza, código, consulta y paciente',
        x['tipo_diagnostico'] and len(x['sintomas']) == 2 and all({'id_sintoma', 'descripcion_sintoma'} <= set(s) for s in x['sintomas'])
        and SECRETO in x['descripcion_diagnostico'] and x['pieza_dental'] == '18' and x['numero_consulta'] == f'CON-{c1:07d}' and x['cedula_paciente'].startswith('ZZ'))
    llamar(C_ADM, 'get', f'{URL}/{id1}', 200, nombre='el Administrador lee')
    llamar(C_MED2, 'get', f'{URL}/{id1}', 403, nombre='otro médico NO lee un diagnóstico ajeno')
    llamar(C_REC, 'get', f'{URL}/{id1}', 403, nombre='Recepción NO lee diagnósticos')
    llamar(C_CAJ, 'get', f'{URL}/{id1}', 403, nombre='el Cajero NO lee diagnósticos')
    llamar(C_MED, 'get', f'{URL}/999999999', 404, nombre='diagnóstico inexistente')
    d = llamar(C_MED, 'get', URL + '?q=ZZ+PACIENTE&por_pagina=100', 200, nombre='listado del médico')
    chk('trae los vigentes con número de consulta, paciente y síntomas', {id1, id2} <= {x['id_diagnostico'] for x in d['data']} and d['total'] >= 3
        and all('sintomas' in x and 'numero_consulta' in x for x in d['data']))
    d = llamar(C_MED, 'get', URL + '?q=' + d['data'][0]['codigo'], 200, nombre='filtro por código')
    chk('...solo ese', len(d['data']) == 1)
    d = llamar(C_MED2, 'get', URL + '?por_pagina=100', 200, nombre='otro médico lista solo lo suyo')
    chk('...no ve los de ZZ PACIENTE', id1 not in {x['id_diagnostico'] for x in d['data']})
    d = llamar(C_MED, 'get', URL + '?por_pagina=1&pagina=2&q=ZZ+PACIENTE', 200, nombre='paginación')
    chk('una fila por página y el total completo', len(d['data']) == 1 and d['total'] >= 3)
    for malo in ('?desde=2026-13-40', '?desde=2026-10-10&hasta=2026-10-01', '?pagina=x'):
        llamar(C_MED, 'get', URL + malo, 400, nombre=f'filtro inválido {malo}')
    llamar(C_MED, 'get', f'{URL}/paciente/{pac}', 200, nombre='diagnósticos por paciente (solo los del médico)')
    d = llamar(C_MED2, 'get', f'{URL}/paciente/{pac}', 200, nombre='...otro médico no ve los ajenos')
    chk('...vacío para el otro médico', d['data'] == [])
    # el lookup que usan los combos de otras ventanas
    chk('lookup sin sesión -> 401', app.test_client().get(f'{URL}/consulta/{c1}').status_code == 401)
    d = llamar(C_MED, 'get', f'{URL}/consulta/{c1}', 200, nombre='lookup por consulta (Tratamiento, Receta, Órdenes, Justificativo)')
    chk('conserva las claves que usan esos combos', all({'id_diagnostico', 'descripcion_diagnostico', 'tipo_diagnostico', 'codigo'} <= set(x) for x in d['data']) and len(d['data']) >= 3)
    llamar(C_ADM, 'get', f'{URL}/consulta/{c1}', 200, nombre='lookup: el Administrador lee')
    llamar(C_MED2, 'get', f'{URL}/consulta/{c1}', 403, nombre='lookup: otro médico NO')
    llamar(C_REC, 'get', f'{URL}/consulta/{c1}', 403, nombre='lookup: Recepción NO')
    llamar(C_CAJ, 'get', f'{URL}/consulta/{c1}', 403, nombre='lookup: el Cajero NO (antes bastaba con tener sesión)')
    llamar(C_MED, 'get', f'{URL}/consulta/{c_anulada}', 404, nombre='lookup de una consulta anulada')

    print('\n=== Los diagnósticos viejos se siguen mostrando aunque se anulen su tipo o sus síntomas')
    cu.execute("UPDATE tipo_diagnostico SET activo=false WHERE id_tipo_diagnostico=%s", (tipo,))
    cu.execute("UPDATE sintoma SET activo=false WHERE id_sintoma=%s", (s1,)); cx.commit()
    d = llamar(C_MED, 'get', f'{URL}/{id1}', 200, nombre='con el tipo y un síntoma ya anulados, el diagnóstico se ve')
    chk('...con su tipo y sus 2 síntomas', d['data']['tipo_diagnostico'] and len(d['data']['sintomas']) == 2)
    chk('...y sigue en el listado y en el lookup', id1 in {x['id_diagnostico'] for x in llamar(C_MED, 'get', URL + '?q=ZZ+PACIENTE&por_pagina=100', 200, nombre='listado')['data']}
        and id1 in {x['id_diagnostico'] for x in llamar(C_MED, 'get', f'{URL}/consulta/{c1}', 200, nombre='lookup')['data']})
    alta(C_MED, base, 409, 'pero un diagnóstico NUEVO con ese tipo ya anulado se rechaza', campo='id_tipo_diagnostico')
    cu.execute("UPDATE tipo_diagnostico SET activo=true WHERE id_tipo_diagnostico=%s", (tipo,))
    cu.execute("UPDATE sintoma SET activo=true WHERE id_sintoma=%s", (s1,)); cx.commit()

    print('\n=== Anular (definitiva)')
    llamar(C_REC, 'delete', f'{URL}/{id1}', 403, nombre='Recepción no anula')
    llamar(C_CAJ, 'delete', f'{URL}/{id1}', 403, nombre='el Cajero no anula')
    llamar(C_ADM, 'delete', f'{URL}/{id1}', 403, nombre='el Administrador no anula', contiene='médico de la consulta')
    llamar(C_MED2, 'delete', f'{URL}/{id1}', 403, nombre='otro médico no anula', contiene='médico de la consulta')
    llamar(C_MED, 'delete', f'{URL}/999999999', 404, nombre='anular inexistente')
    # con un tratamiento vigente asociado se bloquea; cancelado, no
    cu.execute("""INSERT INTO tratamientos(codigo, id_consulta_cab, id_diagnostico, id_paciente, id_medico, id_tipo_tratamiento, descripcion_tratamiento, fecha_tratamiento, estado)
                  VALUES ('ZTDX1', %s, %s, %s, %s, (SELECT id_tipo_tratamiento FROM tipos_tratamiento WHERE activo ORDER BY 1 LIMIT 1), 'ZZ', CURRENT_DATE, 'pendiente')
                  RETURNING id_tratamiento""", (c1, id1, pac, med))
    id_trat = cu.fetchone()[0]; cx.commit()
    llamar(C_MED, 'delete', f'{URL}/{id1}', 409, nombre='con un tratamiento vigente asociado se bloquea', contiene='tratamiento asociado')
    chk('...y sigue vigente', q("SELECT activo FROM diagnosticos WHERE id_diagnostico=%s", (id1,))[0][0] is True)
    cu.execute("UPDATE tratamientos SET estado='cancelado' WHERE id_tratamiento=%s", (id_trat,)); cx.commit()
    llamar(C_MED, 'delete', f'{URL}/{id1}', 200, nombre='con el tratamiento cancelado se puede anular', contiene='anulado correctamente')
    cu.execute("DELETE FROM tratamientos WHERE id_tratamiento=%s", (id_trat,)); cx.commit()
    chk('queda inactivo', q("SELECT activo FROM diagnosticos WHERE id_diagnostico=%s", (id1,))[0][0] is False)
    a = auditoria(id1)
    chk('auditoría BAJA: Activo -> Anulado con código, consulta y paciente (sin contenido clínico)',
        a[-1][0] == 'BAJA' and a[-1][2] == {'Estado': 'Activo'} and a[-1][3] == {'Estado': 'Anulado'} and 'DX-' in a[-1][5] and 'CON-' in a[-1][5] and 'CI ZZ' in a[-1][5])
    llamar(C_MED, 'delete', f'{URL}/{id1}', 404, nombre='anular uno ya anulado')
    llamar(C_MED, 'get', f'{URL}/{id1}', 404, nombre='un diagnóstico anulado ya no se lee')
    chk('...ni está en el lookup', id1 not in {x['id_diagnostico'] for x in llamar(C_MED, 'get', f'{URL}/consulta/{c1}', 200, nombre='lookup tras anular')['data']})
    todo = ' '.join(str(x) for i in registrados for fila in auditoria(i) for x in fila)
    chk('NINGÚN dato clínico (descripción, observaciones, tipo, pieza, síntomas) aparece en la auditoría', SECRETO not in todo and 'Requiere control' not in todo
        and 'Caries' not in todo and 'ZZ TIPO DX' not in todo and 'ZZ SINTOMA' not in todo)

    print('\n=== Carreras (FOR SHARE del tipo y de los síntomas; la consulta que se cancela)')
    c2 = consulta_nueva()

    def en_hilo(c, datos, res):
        res.append(c.post(URL, json=datos).status_code)

    # a) dos altas simultáneas: ambas entran y con códigos distintos
    res, barrera = [], threading.Barrier(2)
    cls = [cliente(u_med), cliente(u_med)]

    def alta_sinc(c):
        barrera.wait()
        res.append(c.post(URL, json={**base, 'id_consulta_cab': c2}).status_code)
    hs = [threading.Thread(target=alta_sinc, args=(c,)) for c in cls]
    [h.start() for h in hs]; [h.join() for h in hs]
    chk(f'dos altas simultáneas: las dos entran: {res}', sorted(res) == [201, 201])
    chk('...con códigos distintos', q("SELECT COUNT(DISTINCT codigo), COUNT(*) FROM diagnosticos WHERE id_consulta_cab=%s", (c2,))[0] == (2, 2))
    # b) el tipo se anula mientras se guarda: el alta espera el bloqueo y después lo ve inactivo
    c3 = consulta_nueva()
    tipo2 = fx.tipo_diagnostico()
    cu.execute("SELECT 1 FROM tipo_diagnostico WHERE id_tipo_diagnostico=%s FOR UPDATE", (tipo2,))   # la baja del referencial tiene la fila
    res = []
    h = threading.Thread(target=en_hilo, args=(cliente(u_med), {**base, 'id_consulta_cab': c3, 'id_tipo_diagnostico': tipo2}, res)); h.start()
    time.sleep(0.8)
    cu.execute("UPDATE tipo_diagnostico SET activo=false WHERE id_tipo_diagnostico=%s", (tipo2,)); cx.commit(); h.join()
    chk(f'el tipo se anula mientras se guarda: el alta se rechaza (409): {res}', res == [409])
    # c) un síntoma se anula mientras se guarda
    s3 = fx.sintoma()
    cu.execute("SELECT 1 FROM sintoma WHERE id_sintoma=%s FOR UPDATE", (s3,))
    res = []
    h = threading.Thread(target=en_hilo, args=(cliente(u_med), {**base, 'id_consulta_cab': c3, 'sintomas': [s3]}, res)); h.start()
    time.sleep(0.8)
    cu.execute("UPDATE sintoma SET activo=false WHERE id_sintoma=%s", (s3,)); cx.commit(); h.join()
    chk(f'un síntoma se anula mientras se guarda: el alta se rechaza (409): {res}', res == [409])
    # d) la consulta se cancela mientras se guarda
    cu.execute("SELECT 1 FROM consultas_cab WHERE id_consulta_cab=%s FOR UPDATE", (c3,))
    res = []
    h = threading.Thread(target=en_hilo, args=(cliente(u_med), {**base, 'id_consulta_cab': c3}, res)); h.start()
    time.sleep(0.8)
    cu.execute("UPDATE consultas_cab SET estado='cancelada' WHERE id_consulta_cab=%s", (c3,)); cx.commit(); h.join()
    chk(f'la consulta se cancela mientras se guarda: el alta se rechaza (409): {res}', res == [409])
    chk('...y no quedó ningún diagnóstico en esa consulta', q("SELECT COUNT(*) FROM diagnosticos WHERE id_consulta_cab=%s", (c3,))[0][0] == 0)

    for (i,) in q("SELECT id_diagnostico FROM diagnosticos WHERE id_consulta_cab = ANY(%s)", ([c1, c2, c3],)):
        fx.auditoria_de('diagnosticos', i)
    for i in registrados:
        fx.auditoria_de('diagnosticos', i)
    for i in (c1, c2, c3, c_anulada):
        fx.auditoria_de('consultas_cab', i)
finally:
    cx.rollback()
    fx.limpiar()

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
