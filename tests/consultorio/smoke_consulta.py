"""Etapa 3 (commit 1): Registrar Consulta — alta desde una cita Confirmado, bloqueos, estados, anulación y permisos.

Todo con datos `ZZ` creados por SQL (tests/consultorio/_fixtures.py): pacientes, médicos con su usuario, un funcionario de Recepción,
consultorios y citas propias; se borran por ID junto con la auditoría que generan. No usa a Oscar Gonzales ni a ningún usuario real.
"""
import sys
import threading
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
             "WHERE entidad='consultas_cab' AND id_registro=%s ORDER BY id_auditoria_cambio", (i,))


def consulta(i):
    return q("SELECT estado, activo, duracion_minutos, id_cita FROM consultas_cab WHERE id_consulta_cab=%s", (i,))[0]


citas_creadas = []
try:
    f_rec, u_rec = fx.recepcion()
    med, u_med = fx.medico()
    med2, u_med2 = fx.medico()
    pac = fx.paciente()
    cons = fx.consultorio()
    admin = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Administrador' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    cajero = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    C_REC, C_MED, C_MED2, C_ADM, C_CAJ = cliente(u_rec), cliente(u_med), cliente(u_med2), cliente(admin), cliente(cajero)
    URL = '/api/v1/consultas'

    def nueva_cita(estado='Confirmado', paciente=None, medico=None, consultorio=None):
        i = fx.cita(medico or med, paciente or pac, consultorio or cons, f_rec, estado)
        citas_creadas.append(i)
        return i

    print('\n=== Esquema')
    chk('id_cita: ya no es UNIQUE total (uk_consulta_cita no existe)', q("SELECT 1 FROM pg_constraint WHERE conname='uk_consulta_cita'") == [])
    chk('id_cita: único parcial uk_consulta_cita_activa WHERE activo',
        'WHERE (activo = true)' in q("SELECT indexdef FROM pg_indexes WHERE indexname='uk_consulta_cita_activa'")[0][0])
    chk('CHECK duración 1..480 en la base', 'BETWEEN 1 AND 480' in q("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='chk_consulta_duracion'")[0][0].replace('>= 1) AND (duracion_minutos <= 480', 'BETWEEN 1 AND 480'))

    print('\n=== Alta')
    c1 = nueva_cita()
    d = llamar(C_REC, 'post', URL, 201, {'id_cita': c1, 'estado': 'finalizada', 'duracion_minutos': 30, 'id_medico': med2, 'id_paciente': 999},
               'Recepción registra la consulta desde la cita')
    id1 = d['data']['id_consulta_cab']; fx.auditoria_de('consultas_cab', id1)
    chk('N.º de consulta CON-0000000 derivado del id', d['data']['numero'] == f'CON-{id1:07d}' and d['data']['numero'] in d['mensaje'])
    estado, activo, dur, cita_de = consulta(id1)
    chk('estado inicial SIEMPRE programada (el navegador no lo define) y duración guardada', estado == 'programada' and activo and dur == 30)
    chk('paciente, médico y consultorio se derivan de la cita (se ignora lo que mande el navegador)',
        q("SELECT id_paciente, id_medico, id_consultorio, id_funcionario FROM consultas_cab WHERE id_consulta_cab=%s", (id1,))[0] == (pac, med, cons, f_rec))
    chk('la cita pasa a Realizado', fx.estado_de_cita(c1) == 'Realizado')
    a = auditoria(id1)
    chk('auditoría ALTA: módulo, quién y valores nuevos (consulta, paciente con CI, médico, fecha, estado)',
        len(a) == 1 and a[0][0] == 'ALTA' and a[0][1] == 'Módulo Consultorio' and a[0][2] is None and a[0][4] == u_rec
        and {'Consulta', 'Paciente', 'Médico', 'Fecha de la cita', 'Estado'} <= set(a[0][3]) and 'CI ZZ' in a[0][3]['Paciente'])
    llamar(C_REC, 'post', URL, 409, {'id_cita': c1}, 'segunda consulta sobre la misma cita (ya Realizado)', contiene='no está en estado Confirmado')
    llamar(C_REC, 'post', URL, 400, {}, 'sin id_cita', campo='id_cita')
    llamar(C_REC, 'post', URL, 400, {'id_cita': 'abc'}, 'id_cita no numérico', campo='id_cita')
    llamar(C_REC, 'post', URL, 404, {'id_cita': 999999999}, 'cita inexistente')
    llamar(C_REC, 'post', URL, 409, {'id_cita': nueva_cita('Reservado')}, 'cita Reservado', contiene='Confirmado')
    llamar(C_REC, 'post', URL, 409, {'id_cita': nueva_cita('Cancelado')}, 'cita Cancelado')
    for malo in (0, 481, -5, 'abc', 1.5):
        llamar(C_REC, 'post', URL, 400, {'id_cita': nueva_cita(), 'duracion_minutos': malo}, f'duración inválida {malo!r}', campo='duracion_minutos')
    n_antes = q("SELECT COUNT(*) FROM consultas_cab")[0][0]
    pac_inact = fx.paciente(activo=False)
    llamar(C_REC, 'post', URL, 409, {'id_cita': nueva_cita(paciente=pac_inact)}, 'paciente inactivo', contiene='paciente')
    med_inact, _ = fx.medico(activo=False, con_usuario=False)
    llamar(C_REC, 'post', URL, 409, {'id_cita': nueva_cita(medico=med_inact)}, 'médico inactivo', contiene='médico')
    cons_inact = fx.consultorio(activo=False)
    llamar(C_REC, 'post', URL, 409, {'id_cita': nueva_cita(consultorio=cons_inact)}, 'consultorio inactivo', contiene='consultorio')
    chk('los rechazos no dejaron consultas ni cambiaron las citas', q("SELECT COUNT(*) FROM consultas_cab")[0][0] == n_antes
        and fx.estado_de_cita(citas_creadas[-1]) == 'Confirmado')
    llamar(C_MED, 'post', URL, 403, {'id_cita': nueva_cita()}, 'el médico NO registra consultas (sin permiso nuevo)')
    llamar(C_CAJ, 'post', URL, 403, {'id_cita': nueva_cita()}, 'el Cajero tampoco')
    r = app.test_client().post(URL, json={'id_cita': 1}); chk('sin sesión -> 401', r.status_code == 401)

    print('\n=== Buscador de citas disponibles')
    c_ok = nueva_cita()
    d = llamar(C_REC, 'get', URL + '/citas-disponibles?q=' + q("SELECT nombre FROM paciente WHERE id_paciente=%s", (pac,))[0][0][:12], 200, nombre='buscador')
    ids = {x['id_cita_detalle'] for x in d['data']}
    chk('trae la cita Confirmado sin consulta y no la ya consultada', c_ok in ids and c1 not in ids)
    d = llamar(C_REC, 'get', URL + '/citas-disponibles', 200, nombre='buscador sin filtro')
    chk('las citas de pacientes/médicos/consultorios inactivos no se ofrecen',
        all(x['id_paciente'] != pac_inact and x['id_medico'] != med_inact and x['id_consultorio'] != cons_inact for x in d['data']))
    llamar(C_MED, 'get', URL + '/citas-disponibles', 403, nombre='el médico no usa el buscador de alta')

    print('\n=== Estados')
    ESTADO = lambda i, c, nuevo, esp, **kw: llamar(c, 'patch', f'{URL}/{i}/estado', esp, {'estado': nuevo, **kw}, f'{nuevo} por {kw.get("quien", "")}'.strip())
    llamar(C_MED2, 'patch', f'{URL}/{id1}/estado', 403, {'estado': 'en_proceso'}, 'otro médico no inicia la atención', contiene='médico de la consulta')
    llamar(C_REC, 'patch', f'{URL}/{id1}/estado', 403, {'estado': 'en_proceso'}, 'Recepción no inicia la atención')
    llamar(C_ADM, 'patch', f'{URL}/{id1}/estado', 403, {'estado': 'en_proceso'}, 'el Administrador no inicia la atención (lectura clínica)')
    llamar(C_MED, 'patch', f'{URL}/{id1}/estado', 409, {'estado': 'finalizada'}, 'programada -> finalizada no se permite', contiene='programada')
    llamar(C_MED, 'patch', f'{URL}/{id1}/estado', 409, {'estado': 'programada'}, 'programada -> programada no se permite')
    llamar(C_MED, 'patch', f'{URL}/{id1}/estado', 400, {'estado': 'inventado'}, 'estado fuera del flujo')
    llamar(C_MED, 'patch', f'{URL}/{id1}/estado', 400, {}, 'sin estado', campo='estado')
    llamar(C_MED, 'patch', f'{URL}/{id1}/estado', 400, {'estado': 'en_proceso', 'duracion_minutos': 20}, 'la duración solo al finalizar')
    llamar(C_MED, 'patch', f'{URL}/999999999/estado', 404, {'estado': 'en_proceso'}, 'consulta inexistente')
    llamar(C_CAJ, 'patch', f'{URL}/{id1}/estado', 403, {'estado': 'en_proceso'}, 'el Cajero no cambia estados (sin permiso)')
    llamar(C_MED, 'patch', f'{URL}/{id1}/estado', 200, {'estado': 'en_proceso'}, 'el médico de la consulta inicia la atención')
    a = auditoria(id1)
    chk('auditoría MODIFICACION solo con el cambio de estado (sin nada clínico)',
        a[-1][0] == 'MODIFICACION' and a[-1][2] == {'Estado': 'Programada'} and a[-1][3] == {'Estado': 'En proceso'} and 'CON-' in a[-1][5] and 'CI ZZ' in a[-1][5])
    llamar(C_MED, 'patch', f'{URL}/{id1}/estado', 400, {'estado': 'finalizada', 'duracion_minutos': 0}, 'duración inválida al finalizar', campo='duracion_minutos')
    llamar(C_MED, 'patch', f'{URL}/{id1}/estado', 200, {'estado': 'finalizada', 'duracion_minutos': 45}, 'el médico finaliza con duración')
    chk('finalizada con la duración registrada', consulta(id1)[0] == 'finalizada' and consulta(id1)[2] == 45)
    for nuevo in ('programada', 'en_proceso', 'cancelada', 'finalizada'):
        llamar(C_MED, 'patch', f'{URL}/{id1}/estado', 409, {'estado': nuevo}, f'finalizada es final: -> {nuevo}')
    llamar(C_REC, 'delete', f'{URL}/{id1}', 409, nombre='no se anula una consulta finalizada', contiene='finalizada')

    # cancelar: Recepción desde programada; el médico desde en_proceso
    id2 = fx.registrar_consulta(nueva_cita(), f_rec)
    llamar(C_REC, 'patch', f'{URL}/{id2}/estado', 200, {'estado': 'cancelada'}, 'Recepción cancela una consulta programada')
    llamar(C_REC, 'patch', f'{URL}/{id2}/estado', 409, {'estado': 'en_proceso'}, 'cancelada es final')
    chk('cancelada queda en el historial (activa) y su cita sigue Realizado', consulta(id2)[:2] == ('cancelada', True) and fx.estado_de_cita(consulta(id2)[3]) == 'Realizado')
    id3 = fx.registrar_consulta(nueva_cita(), f_rec, 'en_proceso')
    llamar(C_MED2, 'patch', f'{URL}/{id3}/estado', 403, {'estado': 'cancelada'}, 'otro médico no cancela', contiene='Recepción o el médico')
    llamar(C_MED, 'patch', f'{URL}/{id3}/estado', 200, {'estado': 'cancelada'}, 'el médico de la consulta cancela una en proceso')
    # cancelar y anular son cosas distintas
    chk('cancelada != anulada: sigue activa', consulta(id3)[1] is True)

    print('\n=== Anular (baja por error, definitiva)')
    ca = nueva_cita()
    d = llamar(C_REC, 'post', URL, 201, {'id_cita': ca}, 'alta para anular'); ida = d['data']['id_consulta_cab']; fx.auditoria_de('consultas_cab', ida)
    llamar(C_MED, 'delete', f'{URL}/{ida}', 403, nombre='el médico no anula (sin permiso)')
    llamar(C_CAJ, 'delete', f'{URL}/{ida}', 403, nombre='el Cajero no anula')
    d = llamar(C_REC, 'delete', f'{URL}/{ida}', 200, nombre='Recepción anula una consulta sin datos clínicos', contiene='La cita volvió a Confirmado')
    chk('queda inactiva y la cita vuelve a Confirmado', consulta(ida)[1] is False and fx.estado_de_cita(ca) == 'Confirmado')
    a = auditoria(ida)
    chk('auditoría BAJA: Activo -> Anulado y la cita que vuelve a Confirmado', a[-1][0] == 'BAJA' and a[-1][2] == {'Estado': 'Activo'}
        and a[-1][3] == {'Estado': 'Anulado'} and 'vuelve a Confirmado' in a[-1][5] and 'CI ZZ' in a[-1][5])
    llamar(C_REC, 'delete', f'{URL}/{ida}', 404, nombre='anular una ya anulada')
    llamar(C_REC, 'delete', f'{URL}/999999999', 404, nombre='anular inexistente')
    llamar(C_MED, 'patch', f'{URL}/{ida}/estado', 404, {'estado': 'en_proceso'}, 'no se cambia el estado de una anulada')
    ids_c = {x['id_cita_detalle'] for x in llamar(C_REC, 'get', URL + '/citas-disponibles', 200, nombre='buscador tras anular')['data']}
    chk('la cita vuelve a ofrecerse para consultar', ca in ids_c)
    d = llamar(C_REC, 'post', URL, 201, {'id_cita': ca}, 'se puede registrar OTRA consulta sobre la misma cita (único parcial)')
    idb = d['data']['id_consulta_cab']; fx.auditoria_de('consultas_cab', idb)
    chk('hay dos filas para esa cita: una anulada y una activa', q("SELECT COUNT(*), COUNT(*) FILTER (WHERE activo) FROM consultas_cab WHERE id_cita=%s", (ca,))[0] == (2, 1))
    chk('el segundo alta es otra consulta y la cita quedó Realizado', idb != ida and fx.estado_de_cita(ca) == 'Realizado')

    # cada tipo de dato clínico vigente bloquea la anulación; uno no vigente no
    NOMBRES = {'ficha': 'Ficha Médica', 'diagnostico': 'Diagnóstico', 'odontograma': 'Odontograma', 'tratamiento': 'Tratamiento',
               'receta': 'Receta', 'orden_estudio': 'Orden de Estudios', 'orden_analisis': 'Orden de Análisis', 'justificativo': 'Justificativo Médico'}
    for tipo, nombre in NOMBRES.items():
        idc = fx.registrar_consulta(nueva_cita(), f_rec)
        t, pk, rid = fx.dato_clinico(tipo, idc)
        llamar(C_REC, 'delete', f'{URL}/{idc}', 409, nombre=f'bloquea con {nombre} vigente', contiene=nombre)
        chk(f'{nombre}: la consulta sigue activa y la cita Realizado', consulta(idc)[1] is True and fx.estado_de_cita(consulta(idc)[3]) == 'Realizado')
        fx.dejar_sin_vigencia(t, pk, rid)
        llamar(C_REC, 'delete', f'{URL}/{idc}', 200, nombre=f'con el {nombre} anulado/cancelado ya se puede anular')

    # cita que ya no está Realizado: no se pisa
    idd = fx.registrar_consulta(nueva_cita(), f_rec)
    cu.execute("UPDATE cita_detalle SET id_estado_cita=%s WHERE id_cita_detalle=%s", (fx.estado_cita['Cancelado'], consulta(idd)[3])); cx.commit()
    d = llamar(C_REC, 'delete', f'{URL}/{idd}', 200, nombre='anular cuando la cita ya no estaba Realizado')
    chk('la cita Cancelado no se pisa y se informa', fx.estado_de_cita(consulta(idd)[3]) == 'Cancelado' and d['data']['cita_revertida'] is False)

    print('\n=== Concurrencia: dos altas sobre la misma cita')
    cc = nueva_cita()
    resultados = []
    barrera = threading.Barrier(2)

    clientes = [cliente(u_rec), cliente(u_rec)]   # se preparan antes: el cursor de prueba no es seguro entre hilos

    def alta(c):
        barrera.wait()
        resultados.append(c.post(URL, json={'id_cita': cc}).status_code)
    hilos = [threading.Thread(target=alta, args=(c,)) for c in clientes]
    [h.start() for h in hilos]; [h.join() for h in hilos]
    chk(f'exactamente una gana (201) y la otra es rechazada (409): {sorted(resultados)}', sorted(resultados) == [201, 409])
    chk('una sola consulta activa para la cita', q("SELECT COUNT(*) FROM consultas_cab WHERE id_cita=%s AND activo", (cc,))[0][0] == 1)

    print('\n=== Listado, indicadores y resumen')
    d = llamar(C_REC, 'get', URL + '?q=ZZ+PACIENTE&por_pagina=100', 200, nombre='listado con filtro de texto')
    nums = {x['numero'] for x in d['data']}
    chk('trae las consultas activas del paciente y no las anuladas', f'CON-{id1:07d}' in nums and f'CON-{ida:07d}' not in nums and d['total'] >= 2)
    chk('cada fila trae número, paciente con CI, médico, estado y si tiene ficha',
        all({'numero', 'nombre_paciente', 'cedula_paciente', 'nombre_medico', 'estado', 'tiene_ficha', 'fecha_cita'} <= set(x) for x in d['data']))
    d = llamar(C_REC, 'get', URL + '?estado=finalizada&q=ZZ+PACIENTE', 200, nombre='filtro por estado')
    chk('solo finalizadas', d['data'] and all(x['estado'] == 'finalizada' for x in d['data']))
    d = llamar(C_REC, 'get', URL + '?por_pagina=1&pagina=2&q=ZZ+PACIENTE', 200, nombre='paginación en el servidor')
    chk('una fila por página y el total completo', len(d['data']) == 1 and d['total'] >= 3)
    for malo in ('?estado=raro', '?desde=2026-13-40', '?desde=2026-10-10&hasta=2026-10-01', '?pagina=x'):
        llamar(C_REC, 'get', URL + malo, 400, nombre=f'filtro inválido {malo}')
    d = llamar(C_MED2, 'get', URL + '?por_pagina=100', 200, nombre='un médico ve solo SUS consultas')
    chk('el otro médico no ve nada de ZZ PACIENTE (son del primer médico)', all(x['id_medico'] == med2 for x in d['data']))
    d = llamar(C_MED, 'get', URL + '?por_pagina=100&q=ZZ+PACIENTE', 200, nombre='el médico de las consultas las ve')
    chk('las ve todas', f'CON-{id1:07d}' in {x['numero'] for x in d['data']} and all(x['id_medico'] == med for x in d['data']))
    llamar(C_CAJ, 'get', URL, 403, nombre='el Cajero no ve consultas')
    d = llamar(C_REC, 'get', URL + '/indicadores', 200, nombre='indicadores')
    chk('indicadores con las claves de las tarjetas', {'hoy', 'programadas', 'en_proceso', 'finalizadas', 'canceladas', 'total'} <= set(d['data']))
    d = llamar(C_MED2, 'get', URL + '/indicadores', 200, nombre='indicadores del médico (solo las suyas)')
    chk('el otro médico tiene 0', d['data']['total'] == 0)

    idr = fx.registrar_consulta(nueva_cita(), f_rec)
    fx.dato_clinico('diagnostico', idr); fx.dato_clinico('diagnostico', idr); fx.dato_clinico('ficha', idr)
    d = llamar(C_MED, 'get', f'{URL}/{idr}/resumen', 200, nombre='resumen de la consulta (médico de la consulta)')
    chk('contadores: 1 ficha, 2 diagnósticos y el resto en 0 (solo cantidades)',
        d['data']['contadores'] == {'ficha': 1, 'diagnosticos': 2, 'odontogramas': 0, 'tratamientos': 0, 'recetas': 0,
                                    'ordenes_estudio': 0, 'ordenes_analisis': 0, 'justificativos': 0})
    chk('acciones del médico: puede iniciar y cargar lo clínico, no finalizar', d['data']['acciones'] == {'iniciar': True, 'finalizar': False, 'cancelar': True, 'cargar_clinico': True})
    d = llamar(C_REC, 'get', f'{URL}/{idr}/resumen', 200, nombre='resumen visto por Recepción')
    chk('acciones de Recepción: solo cancelar', d['data']['acciones'] == {'iniciar': False, 'finalizar': False, 'cancelar': True, 'cargar_clinico': False})
    d = llamar(C_ADM, 'get', f'{URL}/{idr}/resumen', 200, nombre='resumen visto por el Administrador')
    chk('el Administrador solo lee (nada de cargar clínico)', d['data']['acciones']['cargar_clinico'] is False and d['data']['acciones']['iniciar'] is False)
    llamar(C_MED2, 'get', f'{URL}/{idr}/resumen', 403, nombre='el resumen de la consulta de otro médico -> 403')
    llamar(C_REC, 'get', f'{URL}/{ida}/resumen', 404, nombre='resumen de una anulada -> 404')

    print('\n=== Lookups que usan otras pantallas')
    d = llamar(C_REC, 'get', f'{URL}/{id1}', 200, nombre='GET /consultas/<id> conserva sus claves')
    chk('claves del lookup', {'id_consulta_cab', 'id_cita', 'id_paciente', 'nombre_paciente', 'id_medico', 'nombre_medico', 'id_consultorio',
                              'nombre_consultorio', 'id_funcionario', 'fecha_cita', 'hora_cita', 'duracion_minutos', 'estado', 'numero', 'activo'} <= set(d['data']))
    d = llamar(C_REC, 'get', URL + '/activas', 200, nombre='GET /consultas/activas')
    ids_act = {x['id_consulta_cab'] for x in d['data']}
    chk('activas = programada o en_proceso, activas', idr in ids_act and id1 not in ids_act and id2 not in ids_act)
    r = C_REC.put(f'{URL}/{id1}', json={'estado': 'programada'}); chk('el PUT libre de estado ya no existe (405)', r.status_code == 405)

    fx.borrar_consultas_de_citas(citas_creadas)
finally:
    fx.borrar_consultas_de_citas(citas_creadas)
    fx.limpiar()

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
