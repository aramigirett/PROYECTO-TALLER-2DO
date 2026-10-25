"""Etapa 6 (commit 1): Órdenes de Estudios y de Análisis (idénticas: se prueban las dos con el mismo código) — alta con las reglas del análisis (tipo activo, motivo,
vínculos con un diagnóstico vigente y un tratamiento no cancelado de la MISMA consulta), solo el médico de la consulta con la consulta programada / en proceso,
avance de estado de UN paso por vez (solo el médico de la orden, también con la consulta FINALIZADA, no con la cancelada), anular (no completada, no con la consulta
finalizada), privacidad de las lecturas y auditoría sin contenido clínico. Datos `ZZ` de tests/consultorio/_fixtures.py (se borran por ID con su auditoría).
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


HOY = datetime.date.today()
SECRETO = 'RESERVADO-OR-4409'
ORDENES = [
    dict(nombre='ESTUDIOS', url='/api/v1/orden-estudios', tabla='orden_estudios', pk='id_orden_estudio', tipo_col='id_tipo_estudio', tipo_fx='tipo_estudio', prefijo='OES',
         entidad='orden_estudios', artefacto='orden de estudios'),
    dict(nombre='ANÁLISIS', url='/api/v1/orden-analisis', tabla='orden_analisis', pk='id_orden_analisis', tipo_col='id_tipo_analisis', tipo_fx='tipo_analisis', prefijo='OAN',
         entidad='orden_analisis', artefacto='orden de análisis'),
]

try:
    f_rec, u_rec = fx.recepcion()
    med, u_med = fx.medico()
    med2, u_med2 = fx.medico()
    pac, cons = fx.paciente(), fx.consultorio()
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

    for O in ORDENES:
        URL, PK, TIPO = O['url'], O['pk'], O['tipo_col']
        print(f"\n################ ORDEN DE {O['nombre']}")
        tipo, tipo_inactivo = getattr(fx, O['tipo_fx'])(), getattr(fx, O['tipo_fx'])(activo=False)
        c1 = consulta_nueva()
        base = {'id_consulta_cab': c1, TIPO: tipo, 'motivo_orden': 'Control radiográfico ' + SECRETO, 'indicaciones': 'En ayunas ' + SECRETO}
        registradas = []

        def alta(c, datos, esperado, nombre, **kw):
            d = llamar(c, 'post', URL, esperado, datos, nombre, **kw)
            if esperado == 201:
                registradas.append(d['data'][PK])
            return d

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
        llamar(C_MED, 'post', URL, 400, {**base, TIPO: None}, 'sin tipo', campo=TIPO)
        llamar(C_MED, 'post', URL, 400, {**base, TIPO: 'x'}, 'tipo no numérico', campo=TIPO)
        llamar(C_MED, 'post', URL, 400, {**base, TIPO: 99999999}, 'tipo inexistente', campo=TIPO)
        llamar(C_MED, 'post', URL, 409, {**base, TIPO: tipo_inactivo}, 'tipo inactivo', contiene='inactivo', campo=TIPO)
        llamar(C_MED, 'post', URL, 400, {**base, 'motivo_orden': '  '}, 'motivo en blanco', campo='motivo_orden')
        llamar(C_MED, 'post', URL, 400, {**base, 'motivo_orden': 'a' * 1001}, 'motivo de 1001', campo='motivo_orden')
        llamar(C_MED, 'post', URL, 400, {**base, 'indicaciones': 'b' * 2001}, 'indicaciones de 2001', campo='indicaciones')
        c_otra = consulta_nueva()
        dx_ajeno, dx_anulado, dx_ok = diagnostico(c_otra), diagnostico(c1, activo=False), diagnostico(c1)
        t_ajeno, t_cancelado, t_ok = tratamiento(c_otra), tratamiento(c1, 'cancelado'), tratamiento(c1)
        llamar(C_MED, 'post', URL, 400, {**base, 'id_diagnostico': dx_ajeno}, 'diagnóstico de OTRA consulta', campo='id_diagnostico')
        llamar(C_MED, 'post', URL, 400, {**base, 'id_diagnostico': dx_anulado}, 'diagnóstico anulado', campo='id_diagnostico')
        llamar(C_MED, 'post', URL, 400, {**base, 'id_tratamiento': t_ajeno}, 'tratamiento de OTRA consulta', campo='id_tratamiento')
        llamar(C_MED, 'post', URL, 400, {**base, 'id_tratamiento': t_cancelado}, 'tratamiento cancelado', campo='id_tratamiento')
        chk('...ningún rechazo dejó una orden', q(f"SELECT COUNT(*) FROM {O['tabla']} WHERE id_consulta_cab IN (%s,%s)", (c1, c_otra))[0][0] == 0)

        print('\n=== Alta correcta')
        d = alta(C_MED, {**base, 'id_diagnostico': dx_ok, 'id_tratamiento': t_ok, 'estado': 'completado', 'fecha_orden': '2020-01-01', 'id_paciente': 1}, 201,
                 'el médico registra (con campos que el servidor ignora)')
        o1 = d['data'][PK]
        chk('...N.º derivado del id', d['data']['numero'] == f"{O['prefijo']}-{o1:07d}" and d['data']['numero'] in d['mensaje'])
        f = q(f"SELECT estado, fecha_orden, id_diagnostico, id_tratamiento FROM {O['tabla']} WHERE {PK}=%s", (o1,))[0]
        chk('...estado pendiente, fecha de hoy y vínculos', f == ('pendiente', HOY, dx_ok, t_ok))
        o_ind = alta(C_MED, {k: v for k, v in base.items() if k != 'indicaciones'}, 201, 'sin indicaciones (opcionales)')['data'][PK]
        c_prog = consulta_nueva('programada')
        alta(C_MED, {**base, 'id_consulta_cab': c_prog}, 201, 'consulta programada también admite')
        for estado in ('finalizada', 'cancelada'):
            alta(C_MED, {**base, 'id_consulta_cab': consulta_nueva(estado)}, 409, f'consulta {estado}', contiene=estado)

        print('\n=== Lecturas: privacidad')
        lista = llamar(C_MED, 'get', f'{URL}?consulta={c1}', 200, None, 'el médico lista las de su consulta')
        chk('...2 órdenes con paciente, tipo, estado y N.º', lista['total'] == 2 and {'numero', 'nombre_paciente', 'tipo', 'estado', 'motivo_orden', TIPO} <= set(lista['data'][0]))
        chk('un médico ajeno no ve ninguna', llamar(C_MED2, 'get', f'{URL}?consulta={c1}', 200, None, 'otro médico lista')['total'] == 0)
        chk('el Administrador ve todas', llamar(C_ADM, 'get', f'{URL}?consulta={c1}', 200, None, 'el Administrador lista')['total'] == 2)
        llamar(C_MED, 'get', f'{URL}/{o1}', 200, None, 'el médico abre el detalle')
        llamar(C_MED2, 'get', f'{URL}/{o1}', 403, None, 'otro médico NO abre el detalle')
        llamar(C_ADM, 'get', f'{URL}/{o1}', 200, None, 'el Administrador abre el detalle')
        llamar(C_MED, 'get', f'{URL}?estado=raro', 400, None, 'estado inválido en el filtro')
        llamar(C_MED, 'get', f'{URL}?desde=x', 400, None, 'fecha inválida en el filtro')
        chk('el filtro por estado funciona', llamar(C_MED, 'get', f'{URL}?consulta={c1}&estado=enviado', 200, None, 'estado=enviado')['total'] == 0)

        print('\n=== Avanzar el estado (un paso por vez)')
        llamar(C_REC, 'put', f'{URL}/{o1}/estado', 403, None, 'Recepción no avanza')
        llamar(C_MED2, 'put', f'{URL}/{o1}/estado', 403, None, 'otro médico no avanza')
        llamar(C_ADM, 'put', f'{URL}/{o1}/estado', 403, None, 'el Administrador no avanza')
        llamar(C_CAJ, 'put', f'{URL}/{o1}/estado', 403, None, 'el Cajero no avanza')
        for esperado in ('enviado', 'en_proceso'):
            llamar(C_MED, 'put', f'{URL}/{o1}/estado', 200, {'estado': 'completado'}, f'avanza a {esperado} (el cuerpo no elige el estado)')
            chk(f'...queda {esperado}', q(f"SELECT estado FROM {O['tabla']} WHERE {PK}=%s", (o1,))[0][0] == esperado)
        # la consulta se FINALIZA: el médico igual completa la orden (el paciente trae el resultado días después)
        cu.execute("UPDATE consultas_cab SET estado='finalizada' WHERE id_consulta_cab=%s", (c1,)); cx.commit()
        llamar(C_MED, 'put', f'{URL}/{o1}/estado', 200, None, 'con la consulta FINALIZADA el médico completa la orden')
        chk('...queda completado', q(f"SELECT estado FROM {O['tabla']} WHERE {PK}=%s", (o1,))[0][0] == 'completado')
        llamar(C_MED, 'put', f'{URL}/{o1}/estado', 409, None, 'completada: no avanza más', contiene='completada')
        llamar(C_MED, 'delete', f'{URL}/{o1}', 409, None, 'completada y con la consulta finalizada: no se cancela')
        llamar(C_MED, 'put', f'{URL}/99999999/estado', 404, None, 'orden inexistente')
        # consulta cancelada: no se avanza
        c_can = consulta_nueva()
        o_can = alta(C_MED, {**base, 'id_consulta_cab': c_can}, 201, 'orden para la consulta que se cancela')['data'][PK]
        cu.execute("UPDATE consultas_cab SET estado='cancelada' WHERE id_consulta_cab=%s", (c_can,)); cx.commit()
        llamar(C_MED, 'put', f'{URL}/{o_can}/estado', 409, None, 'con la consulta CANCELADA no avanza', contiene='cancelada')
        # consulta anulada
        c_anu = consulta_nueva()
        o_anu = alta(C_MED, {**base, 'id_consulta_cab': c_anu}, 201, 'orden para la consulta que se anula')['data'][PK]
        cu.execute("UPDATE consultas_cab SET activo=false WHERE id_consulta_cab=%s", (c_anu,)); cx.commit()
        llamar(C_MED, 'put', f'{URL}/{o_anu}/estado', 404, None, 'con la consulta ANULADA no avanza')
        cu.execute("UPDATE consultas_cab SET activo=true WHERE id_consulta_cab=%s", (c_anu,)); cx.commit()

        print('\n=== Anular (cancelar, definitivo)')
        llamar(C_REC, 'delete', f'{URL}/{o_ind}', 403, None, 'Recepción no anula')
        llamar(C_MED2, 'delete', f'{URL}/{o_ind}', 403, None, 'otro médico no anula')
        llamar(C_ADM, 'delete', f'{URL}/{o_ind}', 403, None, 'el Administrador no anula')
        cu.execute("UPDATE consultas_cab SET estado='en_proceso' WHERE id_consulta_cab=%s", (c1,)); cx.commit()
        llamar(C_MED, 'put', f'{URL}/{o_ind}/estado', 200, None, 'se avanza una pendiente a enviado')
        llamar(C_MED, 'delete', f'{URL}/{o_ind}', 200, None, 'el médico cancela una orden ya enviada', contiene='anulada')
        chk('...queda cancelada', q(f"SELECT estado FROM {O['tabla']} WHERE {PK}=%s", (o_ind,))[0][0] == 'cancelado')
        llamar(C_MED, 'delete', f'{URL}/{o_ind}', 404, None, 'cancelar dos veces')
        llamar(C_MED, 'put', f'{URL}/{o_ind}/estado', 404, None, 'una cancelada no avanza')
        chk('...ya no figura en el listado', llamar(C_MED, 'get', f'{URL}?consulta={c1}', 200, None, 'lista')['total'] == 1)
        c_comp = consulta_nueva()
        o_comp = alta(C_MED, {**base, 'id_consulta_cab': c_comp}, 201, 'orden que se completa con la consulta abierta')['data'][PK]
        for _ in range(3):
            C_MED.put(f'{URL}/{o_comp}/estado')
        llamar(C_MED, 'delete', f'{URL}/{o_comp}', 409, None, 'completada con la consulta abierta: no se cancela', contiene='completada')
        c_fin = consulta_nueva('en_proceso')
        o_fin = alta(C_MED, {**base, 'id_consulta_cab': c_fin}, 201, 'orden en una consulta que luego se finaliza')['data'][PK]
        cu.execute("UPDATE consultas_cab SET estado='finalizada' WHERE id_consulta_cab=%s", (c_fin,)); cx.commit()
        llamar(C_MED, 'delete', f'{URL}/{o_fin}', 409, None, 'con la consulta finalizada no se cancela', contiene='finalizada')

        print('\n=== Auditoría sin contenido clínico')
        for i in registradas:
            fx.auditoria_de(O['entidad'], i)
        filas = q("SELECT accion, modulo, valores_anteriores, valores_nuevos, id_usuario, detalle FROM auditoria_cambios WHERE entidad=%s AND id_registro=%s ORDER BY id_auditoria_cambio", (O['entidad'], o1))
        chk('o1: ALTA y 3 cambios de estado con módulo Consultorio y el usuario', [f[0] for f in filas] == ['ALTA', 'MODIFICACION', 'MODIFICACION', 'MODIFICACION']
            and all(f[1] == 'Módulo Consultorio' and f[4] == u_med for f in filas))
        chk('...el ALTA lleva N.º, consulta y paciente con CI', all(x in filas[0][5] for x in (f"{O['prefijo']}-{o1:07d}", 'Consulta: CON-', 'ZZ PACIENTE', 'CI ')))
        chk('...los cambios guardan solo el estado', [(f[2], f[3]) for f in filas[1:]] == [({'Estado': 'Pendiente'}, {'Estado': 'Enviado'}), ({'Estado': 'Enviado'}, {'Estado': 'En proceso'}),
                                                                                                ({'Estado': 'En proceso'}, {'Estado': 'Completado'})])
        chk('...la cancelación dice Anulado', q("SELECT valores_nuevos FROM auditoria_cambios WHERE entidad=%s AND id_registro=%s AND accion='BAJA'", (O['entidad'], o_ind))[0][0] == {'Estado': 'Anulado'})
        todo = q("SELECT detalle, valores_anteriores::text, valores_nuevos::text FROM auditoria_cambios WHERE entidad=%s AND id_registro = ANY(%s)", (O['entidad'], registradas))
        chk('NINGUNA fila de auditoría contiene el motivo, las indicaciones ni el tipo', not any(SECRETO in (x or '') or 'ZZ ESTUDIO' in (x or '') or 'ZZ ANALISIS' in (x or '') for fila in todo for x in fila))

        print('\n=== Carreras')
        c3 = consulta_nueva()
        tipo2 = getattr(fx, O['tipo_fx'])()
        cu.execute(f"SELECT 1 FROM {O['tipo_fx']} WHERE {TIPO}=%s FOR UPDATE", (tipo2,))   # la baja del referencial tiene la fila
        res = []
        h = threading.Thread(target=lambda: res.append(C_MED.post(URL, json={**base, 'id_consulta_cab': c3, TIPO: tipo2}).status_code)); h.start()
        time.sleep(0.8)
        cu.execute(f"UPDATE {O['tipo_fx']} SET activo=false WHERE {TIPO}=%s", (tipo2,)); cx.commit(); h.join()
        chk(f'el tipo se anula mientras se guarda: se rechaza (409): {res}', res == [409])
        cu.execute("SELECT 1 FROM consultas_cab WHERE id_consulta_cab=%s FOR UPDATE", (c3,))
        res = []
        h = threading.Thread(target=lambda: res.append(C_MED.post(URL, json={**base, 'id_consulta_cab': c3}).status_code)); h.start()
        time.sleep(0.8)
        cu.execute("UPDATE consultas_cab SET estado='cancelada' WHERE id_consulta_cab=%s", (c3,)); cx.commit(); h.join()
        chk(f'la consulta se cancela mientras se guarda: se rechaza (409): {res}', res == [409])
        c4 = consulta_nueva()
        o_r = alta(C_MED, {**base, 'id_consulta_cab': c4}, 201, 'orden para la carrera avanzar / cancelar')['data'][PK]
        res, barrera = {}, threading.Barrier(2)
        cl = [cliente(u_med), cliente(u_med)]

        def en_hilo(clave, f):
            barrera.wait(); res[clave] = f().status_code
        hs = [threading.Thread(target=en_hilo, args=('avanzar', lambda: cl[0].put(f'{URL}/{o_r}/estado'))), threading.Thread(target=en_hilo, args=('cancelar', lambda: cl[1].delete(f'{URL}/{o_r}')))]
        [x.start() for x in hs]; [x.join() for x in hs]
        estado = q(f"SELECT estado FROM {O['tabla']} WHERE {PK}=%s", (o_r,))[0][0]
        chk(f'avanzar y cancelar a la vez: el resultado es coherente ({res}, {estado})',
            (estado == 'cancelado' and res['cancelar'] == 200 and res['avanzar'] in (200, 404)) or (estado == 'cancelado' and res['avanzar'] == 200 and res['cancelar'] == 200))
        for (i,) in q(f"SELECT {PK} FROM {O['tabla']} WHERE id_consulta_cab IN (SELECT id_consulta_cab FROM consultas_cab WHERE id_paciente=%s)", (pac,)):
            fx.auditoria_de(O['entidad'], i)
        for (i,) in q("SELECT id_consulta_cab FROM consultas_cab WHERE id_paciente=%s", (pac,)):
            fx.auditoria_de('consultas_cab', i)
finally:
    cx.rollback()
    fx.limpiar()

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
