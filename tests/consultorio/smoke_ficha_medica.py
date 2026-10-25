"""Etapa 3 (commit 2): Ficha Médica — una por consulta, validaciones y rangos clínicos, IMC del servidor, médico de la consulta, consulta abierta
(programada / en_proceso) revalidada al guardar, privacidad de las lecturas y auditoría sin valores clínicos.

Datos `ZZ` de tests/consultorio/_fixtures.py (médicos con su usuario, Recepción, pacientes, consultas); se borran por ID con su auditoría.
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
             "WHERE entidad='ficha_medica_consulta' AND id_registro=%s ORDER BY id_auditoria_cambio", (i,))


def fila_ficha(i):
    fila = q("SELECT presion_arterial, temperatura, frecuencia_cardiaca, frecuencia_respiratoria, peso, talla, imc, activo "
             "FROM ficha_medica_consulta WHERE id_ficha_medica=%s", (i,))[0]
    return tuple(float(x) if hasattr(x, 'as_tuple') else x for x in fila)


F = '/api/v1/ficha-medica'
SECRETO = 'UNICORNIO-RESERVADO-7731'

try:
    f_rec, u_rec = fx.recepcion()
    med, u_med = fx.medico()
    med2, u_med2 = fx.medico()
    pac = fx.paciente()
    cons = fx.consultorio()
    admin = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Administrador' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    cajero = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    C_REC, C_MED, C_MED2, C_ADM, C_CAJ = cliente(u_rec), cliente(u_med), cliente(u_med2), cliente(admin), cliente(cajero)

    def consulta_nueva(estado='programada', medico=None, paciente=None):
        cita = fx.cita(medico or med, paciente or pac, cons, f_rec)
        return fx.registrar_consulta(cita, f_rec, estado)

    print('\n=== Esquema')
    cu.execute("SELECT conname, convalidated FROM pg_constraint WHERE conrelid='ficha_medica_consulta'::regclass")
    estado_chk = dict(cu.fetchall())
    chk('CHECK de rangos, de presión y de al menos un dato existen', {'chk_ficha_rangos', 'chk_ficha_presion', 'chk_ficha_con_datos'} <= set(estado_chk))
    chk('chk_ficha_con_datos es NOT VALID (aprobado: no toca la ficha vacía anterior), los otros validados',
        estado_chk['chk_ficha_con_datos'] is False and estado_chk['chk_ficha_rangos'] and estado_chk['chk_ficha_presion'])
    chk('fk_ficha_consulta es RESTRICT (nada se borra en cascada)', 'ON DELETE RESTRICT' in q("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='fk_ficha_consulta'")[0][0])
    c0 = consulta_nueva()
    for sql, nombre in (("INSERT INTO ficha_medica_consulta(id_consulta_cab, temperatura) VALUES (%s, 99)", 'temperatura 99 °C'),
                        ("INSERT INTO ficha_medica_consulta(id_consulta_cab, peso) VALUES (%s, 0)", 'peso 0'),
                        ("INSERT INTO ficha_medica_consulta(id_consulta_cab, presion_arterial) VALUES (%s, '80/120')", 'presión sistólica < diastólica'),
                        ("INSERT INTO ficha_medica_consulta(id_consulta_cab, presion_arterial) VALUES (%s, 'abc')", 'presión con formato inválido'),
                        ("INSERT INTO ficha_medica_consulta(id_consulta_cab) VALUES (%s)", 'ficha sin ningún dato')):
        try:
            cu.execute(sql, (c0,)); cx.commit(); ok = False
        except Exception:
            cx.rollback(); ok = True
        chk(f'la base rechaza: {nombre}', ok)
    try:
        cu.execute("DELETE FROM consultas_cab WHERE id_consulta_cab=%s", (c0,)); cx.commit(); ok = True
    except Exception:
        cx.rollback(); ok = False
    chk('(control) una consulta sin ficha sí se borra', ok)

    print('\n=== Permisos y quién carga la ficha')
    c1 = consulta_nueva()
    URL1 = f'{F}/consulta/{c1}'
    r = app.test_client().get(URL1); chk('sin sesión -> 401', r.status_code == 401)
    llamar(C_CAJ, 'get', URL1, 403, nombre='el Cajero NO lee fichas (antes bastaba con tener sesión)')
    llamar(C_CAJ, 'get', f'{F}', 403, nombre='el Cajero no lista fichas')
    llamar(C_REC, 'get', URL1, 404, nombre='Recepción puede leer (aún no hay ficha -> 404 de "no hay ficha")', contiene='No se encontró ficha')
    llamar(C_REC, 'post', F, 403, {'id_consulta_cab': c1, 'temperatura': 36.5}, 'Recepción NO crea fichas (solo ver)')
    llamar(C_ADM, 'post', F, 403, {'id_consulta_cab': c1, 'temperatura': 36.5}, 'el Administrador NO crea fichas (lectura clínica)', contiene='médico de la consulta')
    llamar(C_MED2, 'post', F, 403, {'id_consulta_cab': c1, 'temperatura': 36.5}, 'otro médico NO crea la ficha de la consulta ajena', contiene='médico de la consulta')
    llamar(C_MED2, 'get', URL1, 403, nombre='otro médico NO lee la ficha de una consulta ajena')
    llamar(C_MED, 'post', F, 400, {'temperatura': 36.5}, 'sin id_consulta_cab', campo='id_consulta_cab')
    llamar(C_MED, 'post', F, 400, {'id_consulta_cab': 'x', 'temperatura': 36.5}, 'id_consulta_cab no numérico', campo='id_consulta_cab')
    llamar(C_MED, 'post', F, 404, {'id_consulta_cab': 999999999, 'temperatura': 36.5}, 'consulta inexistente')
    n = q("SELECT COUNT(*) FROM ficha_medica_consulta")[0][0]
    chk('ninguno de los rechazos dejó una ficha', n == q("SELECT COUNT(*) FROM ficha_medica_consulta")[0][0] and
        q("SELECT COUNT(*) FROM ficha_medica_consulta WHERE id_consulta_cab=%s", (c1,))[0][0] == 0)

    print('\n=== Validaciones y rangos clínicos (servidor)')
    base = {'id_consulta_cab': c1}
    llamar(C_MED, 'post', F, 400, base, 'ficha sin ningún dato', campo='ficha', contiene='al menos un dato')
    llamar(C_MED, 'post', F, 400, {**base, 'temperatura': '', 'peso': '  ', 'examen_bucal': ' '}, 'solo vacíos', campo='ficha')
    INVALIDOS = [
        ('presion_arterial', '80/120'), ('presion_arterial', '100/100'), ('presion_arterial', '49/30'), ('presion_arterial', '301/100'),
        ('presion_arterial', '120/29'), ('presion_arterial', '120/201'), ('presion_arterial', 'abc'), ('presion_arterial', '120'),
        ('temperatura', 29.99), ('temperatura', 45.01), ('temperatura', 99), ('temperatura', 'x'), ('temperatura', 36.555), ('temperatura', -36),
        ('frecuencia_cardiaca', 19), ('frecuencia_cardiaca', 251), ('frecuencia_cardiaca', 72.5), ('frecuencia_cardiaca', 'a'),
        ('frecuencia_respiratoria', 4), ('frecuencia_respiratoria', 81), ('frecuencia_respiratoria', 16.5),
        ('peso', 0.99), ('peso', 500.01), ('peso', -70), ('peso', 'x'), ('talla', 29.9), ('talla', 250.1), ('talla', 'x'),
        ('examen_bucal', 'a' * 2001), ('examen_fisico_general', 'raro\x01'), ('observaciones_medico', 123),
    ]
    for campo, valor in INVALIDOS:
        llamar(C_MED, 'post', F, 400, {**base, 'temperatura': 36.5, campo: valor}, f'{campo} = {str(valor)[:20]!r} inválido', campo=campo)
    chk('ninguna inválida se guardó', q("SELECT COUNT(*) FROM ficha_medica_consulta WHERE id_consulta_cab=%s", (c1,))[0][0] == 0)

    print('\n=== Alta, IMC y una por consulta')
    d = llamar(C_MED, 'post', F, 201, {**base, 'presion_arterial': '120 / 80', 'temperatura': '36,5', 'frecuencia_cardiaca': '72', 'frecuencia_respiratoria': 16,
                                        'peso': 70, 'talla': 175, 'imc': 999, 'examen_fisico_general': SECRETO, 'examen_bucal': 'sin hallazgos'},
               'el médico de la consulta crea la ficha (IMC del navegador = 999)')
    id1 = d['data']['id_ficha_medica']
    chk('el servidor calculó el IMC (22,86) e ignoró el 999 del navegador', d['data']['imc'] == 22.86 and fila_ficha(id1)[6] == 22.86)
    chk('la presión se guarda normalizada y los números con su valor', fila_ficha(id1)[:6] == ('120/80', 36.5, 72, 16, 70, 175))
    llamar(C_MED, 'post', F, 409, {**base, 'temperatura': 37}, 'segunda ficha activa para la misma consulta', contiene='Ya existe una ficha')
    a = auditoria(id1)
    chk('auditoría ALTA: módulo, quién, N.º de consulta y paciente con CI',
        len(a) == 1 and a[0][0] == 'ALTA' and a[0][1] == 'Módulo Consultorio' and a[0][2] is None and a[0][4] == u_med
        and set(a[0][3]) == {'Consulta', 'Paciente'} and 'CI ZZ' in a[0][3]['Paciente'])
    d = llamar(C_MED, 'get', f'{F}/{id1}', 200, nombre='leer la ficha por id')
    chk('devuelve los valores clínicos (solo a quien tiene fichamedica ver)', d['data']['examen_fisico_general'] == SECRETO and d['data']['imc'] == 22.86)
    llamar(C_MED, 'get', URL1, 200, nombre='leer la ficha por consulta')
    llamar(C_REC, 'get', URL1, 200, nombre='Recepción lee la ficha (fichamedica ver)')
    llamar(C_ADM, 'get', f'{F}/{id1}', 200, nombre='el Administrador lee la ficha')
    llamar(C_MED2, 'get', f'{F}/{id1}', 403, nombre='otro médico NO lee la ficha por id')
    llamar(C_MED, 'get', f'{F}/999999999', 404, nombre='ficha inexistente')

    print('\n=== Modificación (excepción del CUS)')
    llamar(C_MED, 'put', f'{F}/{id1}', 400, {}, 'editar dejándola vacía', campo='ficha')
    llamar(C_MED, 'put', f'{F}/{id1}', 400, {'temperatura': 50}, 'editar con un rango inválido', campo='temperatura')
    llamar(C_MED, 'put', f'{F}/{id1}', 200, {'presion_arterial': '120/80', 'temperatura': 36.5, 'frecuencia_cardiaca': 72, 'frecuencia_respiratoria': 16,
                                              'peso': 70, 'talla': 175, 'examen_fisico_general': SECRETO, 'examen_bucal': 'sin hallazgos'},
           'editar sin cambios', contiene='no tiene cambios')
    chk('sin cambios no audita', len(auditoria(id1)) == 1)
    llamar(C_MED, 'put', f'{F}/{id1}', 200, {'presion_arterial': '130/85', 'temperatura': 38.75, 'peso': 80, 'talla': 180,
                                              'observaciones_medico': SECRETO}, 'editar con cambios')
    chk('el IMC se recalculó en el servidor (24,69) y lo no enviado quedó vacío', fila_ficha(id1)[6] == 24.69 and fila_ficha(id1)[2] is None)
    a = auditoria(id1)
    chk('auditoría MODIFICACION sin NINGÚN valor (ni anterior ni nuevo)', len(a) == 2 and a[1][0] == 'MODIFICACION' and a[1][2] is None and a[1][3] is None
        and 'ficha modificada' in a[1][5] and 'CON-' in a[1][5])
    llamar(C_REC, 'put', f'{F}/{id1}', 403, {'temperatura': 37}, 'Recepción NO edita (sin permiso editar)')
    llamar(C_ADM, 'put', f'{F}/{id1}', 403, {'temperatura': 37}, 'el Administrador NO edita', contiene='médico de la consulta')
    llamar(C_MED2, 'put', f'{F}/{id1}', 403, {'temperatura': 37}, 'otro médico NO edita', contiene='médico de la consulta')
    llamar(C_MED, 'put', f'{F}/999999999', 404, {'temperatura': 37}, 'editar inexistente')

    print('\n=== La consulta debe estar programada o en proceso (se revalida al guardar)')
    cu.execute("UPDATE consultas_cab SET estado='en_proceso' WHERE id_consulta_cab=%s", (c1,)); cx.commit()
    llamar(C_MED, 'put', f'{F}/{id1}', 200, {'temperatura': 37.2, 'peso': 80, 'talla': 180}, 'en_proceso: se puede editar')
    for estado in ('finalizada', 'cancelada'):
        cu.execute("UPDATE consultas_cab SET estado=%s WHERE id_consulta_cab=%s", (estado, c1)); cx.commit()
        llamar(C_MED, 'put', f'{F}/{id1}', 409, {'temperatura': 36.9}, f'consulta {estado}: no se edita', contiene=estado)
        llamar(C_MED, 'delete', f'{F}/{id1}', 409, nombre=f'consulta {estado}: no se anula la ficha', contiene='finalizada' if estado == 'finalizada' else estado)
        c_nueva = consulta_nueva(estado)
        llamar(C_MED, 'post', F, 409, {'id_consulta_cab': c_nueva, 'temperatura': 36.5}, f'consulta {estado}: no se crea ficha', contiene=estado)
    chk('la ficha quedó intacta', fila_ficha(id1)[1] == 37.2 and fila_ficha(id1)[7] is True)
    cu.execute("UPDATE consultas_cab SET estado='programada' WHERE id_consulta_cab=%s", (c1,)); cx.commit()
    c_anulada = consulta_nueva(); cu.execute("UPDATE consultas_cab SET activo=false WHERE id_consulta_cab=%s", (c_anulada,)); cx.commit()
    llamar(C_MED, 'post', F, 404, {'id_consulta_cab': c_anulada, 'temperatura': 36.5}, 'consulta anulada: no se crea ficha')

    print('\n=== Anular y volver a crear')
    llamar(C_REC, 'delete', f'{F}/{id1}', 403, nombre='Recepción NO anula la ficha')
    llamar(C_ADM, 'delete', f'{F}/{id1}', 403, nombre='el Administrador NO anula la ficha')
    llamar(C_MED2, 'delete', f'{F}/{id1}', 403, nombre='otro médico NO anula la ficha')
    llamar(C_MED, 'delete', f'{F}/{id1}', 200, nombre='el médico de la consulta anula la ficha', contiene='anulada correctamente')
    a = auditoria(id1)
    chk('auditoría BAJA: Activo -> Anulado', a[-1][0] == 'BAJA' and a[-1][2] == {'Estado': 'Activo'} and a[-1][3] == {'Estado': 'Anulado'} and 'CON-' in a[-1][5])
    llamar(C_MED, 'delete', f'{F}/{id1}', 404, nombre='anular una ya anulada')
    llamar(C_MED, 'put', f'{F}/{id1}', 404, {'temperatura': 37}, 'editar una anulada')
    llamar(C_MED, 'get', f'{F}/{id1}', 404, nombre='leer una anulada')
    d = llamar(C_MED, 'post', F, 201, {**base, 'temperatura': 36.1}, 'se puede crear otra ficha (único parcial)')
    id2 = d['data']['id_ficha_medica']
    chk('hay dos fichas para la consulta: una anulada y una activa', q("SELECT COUNT(*), COUNT(*) FILTER (WHERE activo) FROM ficha_medica_consulta WHERE id_consulta_cab=%s", (c1,))[0] == (2, 1))
    chk('sin peso o sin talla el IMC queda vacío', fila_ficha(id2)[6] is None)
    todo = ' '.join(str(x) for i in (id1, id2) for fila in auditoria(i) for x in fila)
    chk('NINGÚN valor clínico (ni el dato reservado ni 38.75, 130/85, 80) aparece en la auditoría de la ficha',
        SECRETO not in todo and '38.75' not in todo and '130/85' not in todo and '36.1' not in todo)

    print('\n=== Listado (sin valores clínicos) y filtros')
    d = llamar(C_REC, 'get', F + '?q=ZZ+PACIENTE&por_pagina=100', 200, nombre='listado de fichas')
    fila = next(x for x in d['data'] if x['id_ficha_medica'] == id2)
    chk('identifica la ficha: consulta, paciente con CI, médico, fecha, estado y cuántos datos tiene',
        {'numero_consulta', 'nombre_paciente', 'cedula_paciente', 'nombre_medico', 'fecha_consulta', 'estado_consulta', 'datos_cargados'} <= set(fila)
        and fila['datos_cargados'] == 1 and fila['numero_consulta'] == f'CON-{c1:07d}')
    prohibidas = {'temperatura', 'peso', 'talla', 'imc', 'presion_arterial', 'frecuencia_cardiaca', 'frecuencia_respiratoria',
                  'examen_fisico_general', 'examen_bucal', 'observaciones_medico'}
    chk('NO trae ningún valor clínico', all(not (prohibidas & set(x)) for x in d['data']))
    chk('no lista las anuladas', id1 not in {x['id_ficha_medica'] for x in d['data']})
    d = llamar(C_MED2, 'get', F + '?por_pagina=100', 200, nombre='un médico lista solo SUS fichas')
    chk('el otro médico no ve las de ZZ PACIENTE', id2 not in {x['id_ficha_medica'] for x in d['data']})
    d = llamar(C_MED, 'get', F + '?por_pagina=100&q=ZZ+PACIENTE', 200, nombre='el médico de la consulta la ve')
    chk('...en su listado', id2 in {x['id_ficha_medica'] for x in d['data']})
    for malo in ('?desde=2026-13-01', '?desde=2026-10-10&hasta=2026-10-01', '?pagina=x'):
        llamar(C_REC, 'get', F + malo, 400, nombre=f'filtro inválido {malo}')
    r = C_REC.get('/fichas-todas'); chk('el endpoint viejo /fichas-todas (que devolvía todos los valores) ya no existe', r.status_code == 404)

    print('\n=== Concurrencia: dos altas de la ficha de la misma consulta')
    c2 = consulta_nueva()
    resultados, barrera = [], threading.Barrier(2)
    clientes = [cliente(u_med), cliente(u_med)]

    def alta(c):
        barrera.wait()
        resultados.append(c.post(F, json={'id_consulta_cab': c2, 'temperatura': 36.8}).status_code)
    hilos = [threading.Thread(target=alta, args=(c,)) for c in clientes]
    [h.start() for h in hilos]; [h.join() for h in hilos]
    chk(f'una gana (201) y la otra es rechazada (409): {sorted(resultados)}', sorted(resultados) == [201, 409])
    chk('una sola ficha activa', q("SELECT COUNT(*) FROM ficha_medica_consulta WHERE id_consulta_cab=%s AND activo", (c2,))[0][0] == 1)

    print('\n=== Carrera: la consulta pasa a cancelada mientras se guarda')
    c3 = consulta_nueva()
    cu.execute("SELECT 1 FROM consultas_cab WHERE id_consulta_cab=%s FOR UPDATE", (c3,))   # otra transacción tiene la consulta
    res = []
    cl = cliente(u_med)
    h = threading.Thread(target=lambda: res.append(cl.post(F, json={'id_consulta_cab': c3, 'temperatura': 36.8}).status_code))
    h.start()
    time.sleep(0.8)   # que la API llegue al bloqueo y espere
    cu.execute("UPDATE consultas_cab SET estado='cancelada' WHERE id_consulta_cab=%s", (c3,)); cx.commit()   # la cancelan y libera el bloqueo
    h.join()
    chk(f'la ficha que esperaba el bloqueo se rechaza (409) porque la consulta ya está cancelada: {res}', res == [409])
    chk('no quedó ficha', q("SELECT COUNT(*) FROM ficha_medica_consulta WHERE id_consulta_cab=%s", (c3,))[0][0] == 0)

    for i in (c1, c2, c3):
        fx.auditoria_de('consultas_cab', i)
    for (i,) in q("SELECT id_ficha_medica FROM ficha_medica_consulta WHERE id_consulta_cab = ANY(%s)", ([c1, c2, c3],)):
        fx.auditoria_de('ficha_medica_consulta', i)
    for i in (id1, id2):
        fx.auditoria_de('ficha_medica_consulta', i)
finally:
    cx.rollback()
    fx.limpiar()

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
