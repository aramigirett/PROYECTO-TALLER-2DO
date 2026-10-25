"""Etapa 3 de la migración de Agendamiento a Tabler: Agenda y Cita (con el cupo).

Agenda: alta (funcionario de la sesión), médico / especialidad / consultorio anulados rechazados, un solo médico por día, publicar horarios (solo disponibilidades del
mismo médico y fecha), anular (bloqueado con citas) y reactivar (sin conflicto de médico y fecha), auditoría con nombres y permisos por rol.
Cita: alta con el cupo descontado en la misma transacción, hora dentro del horario, paciente anulado rechazado, cambio de estado que ajusta el cupo, cancelación que
lo devuelve, una cita cancelada no se reactiva, una cita con consulta no se toca desde Agendamiento, el cupo aguanta 12 reservas simultáneas, y los lookups que usa
Consultorio. Datos `ZZ`: se borran por ID, junto con su auditoría.
"""
import atexit
import datetime
import sys
import threading
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from app import app
from tests._conexion_pruebas import Conexion
from tests.consultorio._fixtures import Fixtures
from tests.facturacion._limpieza import borrar_auditoria

c = app.test_client()
fallos = []


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


def api(metodo, url, esperado, json=None, nombre=None, contiene=None, campo=None, cliente=None):
    f = getattr(cliente or c, metodo)
    r = f(url, json=json) if json is not None else f(url)
    d = r.get_json(silent=True) or {}
    ok = r.status_code == esperado
    if contiene is not None:
        ok = ok and contiene in (d.get('error') or d.get('mensaje') or '')
    if campo is not None:
        ok = ok and d.get('campo') == campo
    chk(f"{nombre or metodo + ' ' + url} -> {r.status_code}" + ('' if ok else f' {d}'), ok)
    return d


cx = Conexion().getConexion(); cu = cx.cursor()
fx = Fixtures(cx)


def q(sql, p=()):
    cu.execute(sql, p)
    return cu.fetchall()


def sesion(id_usuario, cliente=None):
    id_rol, nombre = q("SELECT u.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.id_usuario=%s", (id_usuario,))[0]
    with (cliente or c).session_transaction() as s:
        s.clear(); s['id_usuario'] = id_usuario; s['id_rol'] = id_rol; s['nombre_rol'] = nombre


def usuario_de(rol):
    return q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol=%s AND u.activo ORDER BY 1 LIMIT 1", (rol,))[0][0]


ADMIN, RECEP, CAJERO = usuario_de('Administrador'), usuario_de('Recepcion'), usuario_de('Cajero')
FUNC_RECEP = q("SELECT id_funcionario FROM usuarios WHERE id_usuario=%s", (RECEP,))[0][0]
SUF = int(datetime.datetime.now().strftime('%H%M%S'))
FECHA = datetime.date.today() + datetime.timedelta(days=120 + SUF % 200)
FECHA2 = FECHA + datetime.timedelta(days=1)
creados = {'agenda_cabecera': set(), 'agenda_detalle': set(), 'cita_cabecera': set(), 'cita_detalle': set(), 'disponibilidad_horaria': set()}


_limpio = []


def limpieza():
    if _limpio:
        return
    _limpio.append(1)
    try:
        cx.rollback()
        cu.execute("DELETE FROM avisos_recordatorios WHERE id_cita_detalle = ANY(%s)", (list(creados['cita_detalle']),))
        cx.commit()
        fx.borrar_consultas_de_citas(list(creados['cita_detalle']))
        for tt, _, ii in list(fx._borrar):
            if tt == 'consultas_cab':
                fx.borrar_hijos_de_consulta(ii)
                cu.execute("DELETE FROM consultas_cab WHERE id_consulta_cab = %s", (ii,))
                borrar_auditoria(cu, 'consultas_cab', [ii])
        cx.commit()
        for tabla, pk in (('cita_detalle', 'id_cita_detalle'), ('cita_cabecera', 'id_cita_cabecera'), ('agenda_detalle', 'id_agenda_detalle'),
                          ('agenda_cabecera', 'id_agenda_cabecera'), ('disponibilidad_horaria', 'id_disponibilidad')):
            if tabla == 'agenda_detalle':
                cu.execute("DELETE FROM agenda_detalle WHERE id_agenda_cabecera = ANY(%s)", (list(creados['agenda_cabecera']),))
            if tabla == 'cita_detalle':
                cu.execute("DELETE FROM cita_detalle WHERE id_cita_cabecera = ANY(%s)", (list(creados['cita_cabecera']),))
            cu.execute(f"DELETE FROM {tabla} WHERE {pk} = ANY(%s)", (list(creados[tabla]),))
            borrar_auditoria(cu, tabla, list(creados[tabla]))
        cx.commit()
        fx.limpiar()
    except Exception as e:
        cx.rollback()
        print('ERROR en la limpieza:', e)
        fallos.append('limpieza')


atexit.register(limpieza)


def ultima(entidad, i, accion):
    cu.execute("SELECT modulo, detalle, valores_anteriores, valores_nuevos, id_usuario FROM auditoria_cambios WHERE entidad=%s AND id_registro=%s AND accion=%s "
               "ORDER BY id_auditoria_cambio DESC LIMIT 1", (entidad, i, accion))
    return cu.fetchone()


def cupos(id_ad):
    return q("SELECT cupos_disponibles, estado_detalle FROM agenda_detalle WHERE id_agenda_detalle=%s", (id_ad,))[0]


def disponibilidad(id_medico, fecha, ini='08:00', fin='12:00', n=3):
    i = fx._insertar('disponibilidad_horaria', 'id_disponibilidad',
                     "INSERT INTO disponibilidad_horaria(id_medico, id_dia, id_turno, dispo_hora_inicio, dispo_hora_fin, dispo_cupos, dispo_fecha) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                     (id_medico, fx.id_dia, fx.id_turno, ini, fin, n, fecha))
    return i


# ---------------- datos ----------------
medico, _ = fx.medico(con_usuario=False)
medico2, _ = fx.medico(con_usuario=False)
consultorio = fx.consultorio()
espec_zz = fx._insertar('especialidades', 'id_especialidad', "INSERT INTO especialidades(nombre_especialidad) VALUES (%s)", (f'ZZ ESPEC A{SUF}',))
pacientes = [fx.paciente() for _ in range(14)]
AG = '/api/v1/agenda/cabeceras'
base = {'id_medico': medico, 'id_especialidad': fx.id_especialidad, 'id_consultorio': consultorio, 'fecha_agenda': FECHA.isoformat(), 'observaciones': 'ZZ'}

print('\n== Agenda')
sesion(RECEP)
chk('Agenda: vista Tabler', b'tabler' in c.get('/referenciales/agenda/agenda').data.lower())
for campo, malo, texto in (('id_medico', None, 'sin médico'), ('id_consultorio', 0, 'sin consultorio'), ('fecha_agenda', 'x', 'fecha inválida'),
                           ('fecha_agenda', '2020-01-01', 'fecha pasada')):
    api('post', AG, 400, {**base, campo: malo}, f'Agenda: rechaza {texto}')
d = api('post', AG, 201, base, 'Agenda: alta (Recepción)')
cab = d.get('data', {}).get('id_agenda_cabecera')
creados['agenda_cabecera'].add(cab)
chk('Agenda: el funcionario sale de la sesión', q("SELECT id_funcionario, estado FROM agenda_cabecera WHERE id_agenda_cabecera=%s", (cab,))[0] == (FUNC_RECEP, 'Activo'))
a = ultima('agenda_cabecera', cab, 'ALTA')
chk('Agenda: auditoría ALTA con módulo, usuario y nombres', bool(a) and a[0] == 'Módulo Agendamiento' and a[4] == RECEP and 'ZZ MEDICO' in str(a[3]) and 'Consultorio' in str(a[3]))
api('post', AG, 409, base, 'Agenda: un solo médico por día', contiene='ya tiene una agenda')
# personas y referenciales anulados
cu.execute("UPDATE medico SET activo=false WHERE id_medico=%s", (medico2,)); cx.commit()
api('post', AG, 400, {**base, 'id_medico': medico2, 'fecha_agenda': FECHA2.isoformat()}, 'Agenda: rechaza un médico anulado', contiene='anulado', campo='id_medico')
cu.execute("UPDATE especialidades SET activo=false WHERE id_especialidad=%s", (espec_zz,)); cx.commit()
api('post', AG, 400, {**base, 'id_especialidad': espec_zz, 'fecha_agenda': FECHA2.isoformat()}, 'Agenda: rechaza una especialidad anulada', contiene='anulada', campo='id_especialidad')
cons_inact = fx.consultorio(activo=False)
api('post', AG, 400, {**base, 'id_consultorio': cons_inact, 'fecha_agenda': FECHA2.isoformat()}, 'Agenda: rechaza un consultorio anulado', contiene='anulado', campo='id_consultorio')
cu.execute("UPDATE medico SET activo=true WHERE id_medico=%s", (medico2,)); cx.commit()
# horarios
dispo = disponibilidad(medico, FECHA, '08:00', '12:00', 3)
dispo_otro = disponibilidad(medico2, FECHA, '08:00', '12:00', 3)
dispo_otra_fecha = disponibilidad(medico, FECHA2, '14:00', '16:00', 3)
d = api('post', f'{AG}/{cab}/detalles', 201, {'ids_disponibilidades': [dispo]}, 'Agenda: publica un horario')
det = d['data']['ids_creados'][0]; creados['agenda_detalle'].add(det)
chk('Agenda: el horario copia día, turno, horas y cupos', q("SELECT hora_inicio::text, cupos_disponibles, cupos_maximos, estado_detalle FROM agenda_detalle WHERE id_agenda_detalle=%s", (det,))[0] == ('08:00:00', 3, 3, 'Disponible'))
api('post', f'{AG}/{cab}/detalles', 400, {'ids_disponibilidades': [dispo]}, 'Agenda: no publica dos veces el mismo horario', contiene='ya está publicado')
api('post', f'{AG}/{cab}/detalles', 400, {'ids_disponibilidades': [dispo_otro]}, 'Agenda: rechaza la disponibilidad de otro médico', contiene='no es de este médico')
api('post', f'{AG}/{cab}/detalles', 400, {'ids_disponibilidades': [dispo_otra_fecha]}, 'Agenda: rechaza la disponibilidad de otra fecha', contiene='no es de este médico')
api('post', f'{AG}/{cab}/detalles', 400, {'ids_disponibilidades': []}, 'Agenda: exige al menos una disponibilidad')
chk('Agenda: el horario publicado quedó auditado', bool(ultima('agenda_detalle', det, 'ALTA')))
chk('Agenda: la lista trae la agenda con 1 horario', any(x['id_agenda_cabecera'] == cab and x['horarios'] == 1 for x in c.get(AG).get_json()['data']))

print('\n== Cita y cupo')
CI = '/api/v1/citas'
est = fx.estado_cita
cita_body = lambda pac, hora='09:00', estado='Reservado', **x: {'id_paciente': pac, 'id_agenda_detalle': det, 'hora_cita': hora, 'motivo_consulta': 'ZZ control', 'id_estado_cita': est[estado], **x}
chk('Cita: vista Tabler', b'tabler' in c.get('/referenciales/cita/cita-index').data.lower())
api('post', CI, 400, cita_body(pacientes[0], hora='13:00'), 'Cita: la hora debe estar dentro del horario', contiene='entre 08:00 y 12:00', campo='hora_cita')
api('post', CI, 400, cita_body(pacientes[0], motivo_consulta=''), 'Cita: el motivo es obligatorio', campo='motivo_consulta')
api('post', CI, 400, cita_body(pacientes[0], estado='Cancelado'), 'Cita: no se crea Cancelada', contiene='Reservado o Confirmado', campo='id_estado_cita')
api('post', CI, 400, cita_body(pacientes[0], estado='Realizado'), 'Cita: no se crea Realizada (la marca Consultorio)', campo='id_estado_cita')
d = api('post', CI, 201, cita_body(pacientes[0]), 'Cita: alta Reservado')
cc, cd = d['data']['id_cita_cabecera'], d['data']['id_cita_detalle']
creados['cita_cabecera'].add(cc); creados['cita_detalle'].add(cd)
chk('Cita: descuenta un cupo (3 -> 2)', cupos(det) == (2, 'Disponible'))
chk('Cita: la fecha sale de la agenda y el funcionario de la sesión', q("SELECT cd.fecha_cita, cc.id_funcionario FROM cita_detalle cd JOIN cita_cabecera cc USING(id_cita_cabecera) WHERE cd.id_cita_detalle=%s", (cd,))[0] == (FECHA, FUNC_RECEP))
a = ultima('cita_detalle', cd, 'ALTA')
chk('Cita: auditoría con paciente y hora, SIN el motivo de la consulta', bool(a) and a[0] == 'Módulo Agendamiento' and 'ZZ control' not in str(a[1]) + str(a[2]) + str(a[3]) and 'ZZ PACIENTE' in str(a[3]))
chk('Cita: auditoría de la cabecera', bool(ultima('cita_cabecera', cc, 'ALTA')))
api('post', CI, 409, cita_body(pacientes[0]), 'Cita: el paciente ya tiene una cita en ese horario', contiene='ya tiene una cita')
cu.execute("UPDATE paciente SET activo=false WHERE id_paciente=%s", (pacientes[1],)); cx.commit()
api('post', CI, 400, cita_body(pacientes[1]), 'Cita: rechaza un paciente anulado', contiene='anulado', campo='id_paciente')
d2 = api('post', CI, 201, cita_body(pacientes[2], estado='Confirmado'), 'Cita: alta Confirmado'); cc2, cd2 = d2['data']['id_cita_cabecera'], d2['data']['id_cita_detalle']
creados['cita_cabecera'].add(cc2); creados['cita_detalle'].add(cd2)
d3 = api('post', CI, 201, cita_body(pacientes[3]), 'Cita: tercera reserva'); cc3, cd3 = d3['data']['id_cita_cabecera'], d3['data']['id_cita_detalle']
creados['cita_cabecera'].add(cc3); creados['cita_detalle'].add(cd3)
chk('Cita: sin cupos el horario queda Agotado', cupos(det) == (0, 'Agotado'))
api('post', CI, 409, cita_body(pacientes[4]), 'Cita: sin cupos -> 409', contiene='No hay cupos')
chk('Cita: la reserva rechazada no tocó el cupo', cupos(det) == (0, 'Agotado'))
# estados
ES = '/api/v1/citas-detalle'
api('patch', f'{ES}/{cd}/estado', 200, {'id_estado_cita': est['Confirmado']}, 'Cita: Reservado -> Confirmado')
chk('Cita: cambiar entre estados que ocupan cupo no lo mueve', cupos(det) == (0, 'Agotado'))
api('patch', f'{ES}/{cd}/estado', 200, {'id_estado_cita': est['No Asistió']}, 'Cita: Confirmado -> No Asistió (libera el cupo)')
chk('Cita: el cupo vuelve y el horario deja de estar Agotado', cupos(det) == (1, 'Disponible'))
api('patch', f'{ES}/{cd}/estado', 200, {'id_estado_cita': est['Reservado']}, 'Cita: No Asistió -> Reservado (vuelve a ocupar)')
chk('Cita: vuelve a descontar', cupos(det) == (0, 'Agotado'))
api('delete', f'{ES}/{cd3}', 200, None, 'Cita: cancelar un horario')
chk('Cita: cancelar devuelve el cupo', cupos(det) == (1, 'Disponible'))
api('patch', f'{ES}/{cd3}/estado', 409, {'id_estado_cita': est['Confirmado']}, 'Cita: una cancelada no se reactiva', contiene='no se reactiva')
api('delete', f'{ES}/{cd3}', 404, None, 'Cita: cancelar dos veces -> 404')
chk('Cita: sigue habiendo 1 cupo', cupos(det) == (1, 'Disponible'))
m = ultima('cita_detalle', cd3, 'MODIFICACION')
chk('Cita: la cancelación queda auditada con el estado anterior y el nuevo', bool(m) and 'Reservado' in str(m[2]) and 'Cancelado' in str(m[3]))
api('patch', f'{ES}/{cd}/estado', 400, {}, 'Cita: el estado es obligatorio')
# permisos
sesion(CAJERO)
for url, n in ((AG, 'Agenda'), ('/api/v1/citas-cabecera', 'Citas'), (f'/api/v1/citas/paciente/{pacientes[0]}', 'Citas de un paciente'), ('/api/v1/citas-detalle/confirmadas-sin-consulta', 'Citas confirmadas')):
    api('get', url, 403, None, f'Cajero no accede a {n}')
chk('Cajero no abre Agenda ni Citas', c.get('/referenciales/agenda/agenda').status_code == 403 and c.get('/referenciales/cita/cita-index').status_code == 403)
MEDICO = usuario_de('Medico')
sesion(MEDICO)
api('get', AG, 200, None, 'Médico ve las agendas')
api('post', AG, 403, base, 'Médico NO crea agendas')
api('post', CI, 403, cita_body(pacientes[5]), 'Médico NO crea citas')
api('patch', f'{ES}/{cd}/estado', 200, {'id_estado_cita': est['Confirmado']}, 'Médico cambia el estado de una cita (permiso estado)')
api('delete', f'{ES}/{cd}', 403, None, 'Médico NO cancela citas')
api('get', '/api/v1/citas-detalle/confirmadas-sin-consulta', 200, None, 'Médico usa el selector de Consultorio')
sesion(RECEP)

print('\n== Conexión con Consultorio')
chk('Consultorio: la cita Confirmada aparece para registrar una consulta', any(x['id_cita_detalle'] == cd2 for x in c.get('/api/v1/citas-detalle/confirmadas-sin-consulta').get_json()['data']))
fx.registrar_consulta(cd2, FUNC_RECEP)
cc_consulta = q("SELECT id_consulta_cab FROM consultas_cab WHERE id_cita=%s", (cd2,))[0][0]
chk('Consultorio: con consulta, la cita pasó a Realizado y no se ofrece de nuevo', fx.estado_de_cita(cd2) == 'Realizado'
    and all(x['id_cita_detalle'] != cd2 for x in c.get('/api/v1/citas-detalle/confirmadas-sin-consulta').get_json()['data']))
api('patch', f'{ES}/{cd2}/estado', 409, {'id_estado_cita': est['Cancelado']}, 'Cita con consulta: su estado lo maneja Consultorio', contiene='consulta registrada')
api('delete', f'{ES}/{cd2}', 409, None, 'Cita con consulta: no se cancela desde Agendamiento', contiene='consulta registrada')
api('delete', f'/api/v1/citas-cabecera/{cc2}', 409, None, 'Cita con consulta: no se anula la cita', contiene='consulta registrada')
cabecera_ok = q("SELECT cupos_disponibles FROM agenda_detalle WHERE id_agenda_detalle=%s", (det,))[0][0]
chk('Consultorio: el cupo no se movió con los intentos rechazados', cabecera_ok == cupos(det)[0])

print('\n== Anular y reactivar Agenda')
api('delete', f'{AG}/{cab}', 409, None, 'Agenda: no se anula con citas', contiene='tiene')
api('delete', f'/api/v1/agenda/detalles/{det}', 409, None, 'Horario: no se anula con citas', contiene='tiene')
chk('Agenda: sigue activa tras el 409', q("SELECT estado FROM agenda_cabecera WHERE id_agenda_cabecera=%s", (cab,))[0][0] == 'Activo')
# agenda sin citas
cab_b = api('post', AG, 201, {**base, 'fecha_agenda': FECHA2.isoformat()}, 'Agenda: segunda agenda del día siguiente')['data']['id_agenda_cabecera']; creados['agenda_cabecera'].add(cab_b)
det_b = api('post', f'{AG}/{cab_b}/detalles', 201, {'ids_disponibilidades': [dispo_otra_fecha]}, 'Agenda: publica en la segunda')['data']['ids_creados'][0]; creados['agenda_detalle'].add(det_b)
api('delete', f'{AG}/{cab_b}', 200, None, 'Agenda: anular sin citas')
chk('Agenda: anular cancela sus horarios en la misma operación', q("SELECT estado FROM agenda_cabecera WHERE id_agenda_cabecera=%s", (cab_b,))[0][0] == 'Inactivo'
    and q("SELECT estado_detalle FROM agenda_detalle WHERE id_agenda_detalle=%s", (det_b,))[0][0] == 'Cancelado')
chk('Agenda: BAJA auditada', bool(ultima('agenda_cabecera', cab_b, 'BAJA')))
chk('Agenda: la lista no trae la anulada; con ?inactivos=1 sí', all(x['id_agenda_cabecera'] != cab_b for x in c.get(AG).get_json()['data'])
    and any(x['id_agenda_cabecera'] == cab_b and not x['activo'] for x in c.get(AG + '?inactivos=1').get_json()['data']))
api('post', CI, 400, {'id_paciente': pacientes[6], 'id_agenda_detalle': det_b, 'hora_cita': '15:00', 'motivo_consulta': 'ZZ', 'id_estado_cita': est['Reservado']}, 'Cita: rechaza un horario de una agenda anulada', contiene='anulada')
cab_c = api('post', AG, 201, {**base, 'fecha_agenda': FECHA2.isoformat()}, 'Agenda: otra agenda vigente el mismo día')['data']['id_agenda_cabecera']; creados['agenda_cabecera'].add(cab_c)
api('patch', f'{AG}/{cab_b}/reactivar', 409, None, 'Agenda: reactivar con otra vigente el mismo día', contiene='ya tiene otra agenda')
api('delete', f'{AG}/{cab_c}', 200, None, 'Agenda: anula la que estorba')
cu.execute("UPDATE medico SET activo=false WHERE id_medico=%s", (medico,)); cx.commit()
api('patch', f'{AG}/{cab_b}/reactivar', 409, None, 'Agenda: reactivar con el médico anulado', contiene='médico')
cu.execute("UPDATE medico SET activo=true WHERE id_medico=%s", (medico,)); cx.commit()
api('patch', f'{AG}/{cab_b}/reactivar', 200, None, 'Agenda: reactivación')
chk('Agenda: REACTIVACION auditada y sus horarios siguen cancelados', bool(ultima('agenda_cabecera', cab_b, 'REACTIVACION'))
    and q("SELECT estado_detalle FROM agenda_detalle WHERE id_agenda_detalle=%s", (det_b,))[0][0] == 'Cancelado')
api('patch', f'{AG}/{cab_b}/reactivar', 409, None, 'Agenda: reactivar una activa', contiene='ya está activa')
sesion(MEDICO)
api('delete', f'{AG}/{cab_b}', 403, None, 'Médico NO anula agendas')
sesion(RECEP)

print('\n== Anular una cita devuelve el cupo')
antes = cupos(det)[0]
cab_cita = api('post', CI, 201, cita_body(pacientes[7], hora='10:00', id_agenda_detalle=det), 'Cita: reserva para anular')['data']; creados['cita_cabecera'].add(cab_cita['id_cita_cabecera']); creados['cita_detalle'].add(cab_cita['id_cita_detalle'])
chk('Cita: descontó', cupos(det)[0] == antes - 1)
api('delete', f"/api/v1/citas-cabecera/{cab_cita['id_cita_cabecera']}", 200, None, 'Cita: anular la cita completa')
chk('Cita: anular devolvió el cupo y canceló el horario', cupos(det)[0] == antes and fx.estado_de_cita(cab_cita['id_cita_detalle']) == 'Cancelado'
    and q("SELECT estado FROM cita_cabecera WHERE id_cita_cabecera=%s", (cab_cita['id_cita_cabecera'],))[0][0] == 'Inactivo')
chk('Cita: BAJA auditada', bool(ultima('cita_cabecera', cab_cita['id_cita_cabecera'], 'BAJA')))
api('delete', f"/api/v1/citas-cabecera/{cab_cita['id_cita_cabecera']}", 404, None, 'Cita: anular dos veces -> 404')

print('\n== Concurrencia del cupo')
dispo_c = disponibilidad(medico, FECHA, '13:00', '17:00', 3)
det_c = api('post', f'{AG}/{cab}/detalles', 201, {'ids_disponibilidades': [dispo_c]}, 'Agenda: horario de la tarde (3 cupos)')['data']['ids_creados'][0]; creados['agenda_detalle'].add(det_c)
resultados = []
ROL_RECEP = q("SELECT u.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.id_usuario=%s", (RECEP,))[0]


def reservar(i):
    cl = app.test_client()
    with cl.session_transaction() as s:
        s['id_usuario'] = RECEP; s['id_rol'] = ROL_RECEP[0]; s['nombre_rol'] = ROL_RECEP[1]
    r = cl.post(CI, json={'id_paciente': pacientes[i], 'id_agenda_detalle': det_c, 'hora_cita': '14:00', 'motivo_consulta': 'ZZ', 'id_estado_cita': est['Reservado']})
    resultados.append((r.status_code, (r.get_json() or {}).get('data')))


hilos = [threading.Thread(target=reservar, args=(i,)) for i in range(2, 14)]
[h.start() for h in hilos]; [h.join() for h in hilos]
ok = [r for r in resultados if r[0] == 201]
for _, dd in ok:
    creados['cita_cabecera'].add(dd['id_cita_cabecera']); creados['cita_detalle'].add(dd['id_cita_detalle'])
chk(f'12 reservas simultáneas sobre 3 cupos: exactamente 3 salen ({len(ok)})', len(ok) == 3 and all(r[0] in (201, 409) for r in resultados))
chk('Cupo: queda en 0 / Agotado, nunca negativo, y hay 3 citas que lo ocupan', cupos(det_c) == (0, 'Agotado') and q(
    "SELECT COUNT(*) FROM cita_detalle cd JOIN estado_cita ec USING(id_estado_cita) WHERE cd.id_agenda_detalle=%s AND ec.ocupa_cupo", (det_c,))[0][0] == 3)
chk('Cupo: las reservas rechazadas no dejaron citas huérfanas', q("SELECT COUNT(*) FROM cita_cabecera cc WHERE cc.id_paciente = ANY(%s) AND NOT EXISTS (SELECT 1 FROM cita_detalle d WHERE d.id_cita_cabecera=cc.id_cita_cabecera)",
                                                                  (pacientes,))[0][0] == 0)

limpieza()
sobras = q("SELECT (SELECT COUNT(*) FROM agenda_cabecera WHERE observaciones='ZZ') + (SELECT COUNT(*) FROM paciente WHERE nombre LIKE 'ZZ%%') + (SELECT COUNT(*) FROM especialidades WHERE nombre_especialidad LIKE 'ZZ%%')")[0][0]
chk('limpieza: no quedan datos ZZ', sobras == 0)
print('\nFALLOS:', 'ninguno' if not fallos else fallos)
