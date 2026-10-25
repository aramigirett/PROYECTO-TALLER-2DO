"""Etapa 1 de la migración de Agendamiento a Tabler: los 7 referenciales (Ciudad, Cargo, Especialidad, Consultorio, Día, Turno y
Disponibilidad Horaria) contra el Estándar de referenciales.

Por cada uno: vista Tabler, validaciones, alta/modificación/duplicados sin distinguir mayúsculas, Estado / "Mostrar inactivos" / Reactivar,
baja bloqueada si está en uso (409), auditoría estructurada (módulo y JSON, con nombres) y permisos por rol (Administrador completo; Médico
y Recepción solo ven, salvo Disponibilidad: Recepción opera). Además: FK que ya no borran en cascada y Caja con un consultorio anulado.
Datos `ZZ`: se borran por ID, junto con su auditoría.
"""
import datetime
import sys
import time
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


def api(metodo, url, esperado, json=None, nombre=None, contiene=None, campo=None):
    f = getattr(c, metodo)
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


def sesion(id_usuario):
    id_rol, nombre = q("SELECT u.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.id_usuario=%s", (id_usuario,))[0]
    with c.session_transaction() as s:
        s.clear(); s['id_usuario'] = id_usuario; s['id_rol'] = id_rol; s['nombre_rol'] = nombre


def usuario_de(rol):
    return q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol=%s AND u.activo ORDER BY 1 LIMIT 1", (rol,))[0][0]


ADMIN, RECEP, MEDICO, CAJERO = usuario_de('Administrador'), usuario_de('Recepcion'), usuario_de('Medico'), usuario_de('Cajero')
SUF = datetime.datetime.now().strftime('%H%M%S')
auditorias = {}


def audita(entidad, i):
    auditorias.setdefault(entidad, set()).add(i)


def ultima_auditoria(entidad, i, accion):
    cu.execute("SELECT modulo, detalle, valores_anteriores, valores_nuevos, id_usuario, ip FROM auditoria_cambios "
               "WHERE entidad=%s AND id_registro=%s AND accion=%s ORDER BY 1 LIMIT 1", (entidad, i, accion))
    return cu.fetchone()


def n_auditorias(entidad, i):
    return q("SELECT COUNT(*) FROM auditoria_cambios WHERE entidad=%s AND id_registro=%s", (entidad, i))[0][0]


# ---------------- catálogos de un solo campo ----------------
def catalogo(nombre, ventana, url, vista, tabla, pk, clave, entidad, valido, invalidos, hijo_en_uso=None, minusculas=True):
    print(f'\n== {nombre}')
    sesion(ADMIN)
    r = c.get(vista)
    chk(f'{nombre}: vista Tabler', r.status_code == 200 and b'tabler' in r.data.lower() and b'btnAgregar' in r.data)
    for payload, texto in invalidos:
        api('post', url, 400, payload, f'{nombre}: rechaza {texto}')
    d = api('post', url, 201, {clave: valido.lower() if minusculas else valido}, f'{nombre}: alta')
    i = d.get('data', {}).get(pk)
    if not i:
        return None
    audita(entidad, i)
    chk(f'{nombre}: guardado en MAYÚSCULAS', q(f"SELECT {clave} FROM {tabla} WHERE {pk}=%s", (i,))[0][0] == valido.upper())
    api('post', url, 400, {clave: valido.title()}, f'{nombre}: duplicado sin distinguir mayúsculas', contiene='Ya existe')
    a = ultima_auditoria(entidad, i, 'ALTA')
    chk(f'{nombre}: auditoría ALTA con módulo, usuario y JSON', bool(a) and a[0] == 'Referenciales Agendamiento' and a[4] == ADMIN and a[5] and a[3])
    nuevo = valido.upper() + ' B'
    api('put', f'{url}/{i}', 200, {clave: nuevo}, f'{nombre}: modificación')
    m = ultima_auditoria(entidad, i, 'MODIFICACION')
    chk(f'{nombre}: auditoría MODIFICACION con anterior y nuevo', bool(m) and m[2] and m[3])
    antes = n_auditorias(entidad, i)
    api('put', f'{url}/{i}', 200, {clave: nuevo}, f'{nombre}: edición sin cambios', contiene='sin cambios')
    chk(f'{nombre}: edición sin cambios no audita', n_auditorias(entidad, i) == antes)
    if hijo_en_uso:
        hijo_en_uso(i)
        api('delete', f'{url}/{i}', 409, None, f'{nombre}: baja bloqueada si está en uso', contiene='No se puede anular')
        chk(f'{nombre}: sigue activo tras el 409', q(f"SELECT activo FROM {tabla} WHERE {pk}=%s", (i,))[0][0])
        hijo_en_uso(i, liberar=True)
    api('delete', f'{url}/{i}', 200, None, f'{nombre}: anulación')
    chk(f'{nombre}: BAJA auditada', bool(ultima_auditoria(entidad, i, 'BAJA')))
    chk(f'{nombre}: la lista (combos) no trae el anulado', all(f[pk] != i for f in c.get(url).get_json()['data']))
    chk(f'{nombre}: ?inactivos=1 lo trae como inactivo', any(f[pk] == i and not f['activo'] for f in c.get(url + '?inactivos=1').get_json()['data']))
    # un anulado no bloquea crear otro igual (único parcial)
    d2 = api('post', url, 201, {clave: nuevo}, f'{nombre}: alta de uno igual a un anulado')
    i2 = d2.get('data', {}).get(pk)
    if i2:
        audita(entidad, i2)
        api('patch', f'{url}/{i}/reactivar', 409, None, f'{nombre}: reactivar con otro activo igual', contiene='ya existe')
        api('delete', f'{url}/{i2}', 200, None, f'{nombre}: anula el segundo')
    api('patch', f'{url}/{i}/reactivar', 200, None, f'{nombre}: reactivación')
    chk(f'{nombre}: REACTIVACION auditada', bool(ultima_auditoria(entidad, i, 'REACTIVACION')))
    api('patch', f'{url}/{i}/reactivar', 409, None, f'{nombre}: reactivar uno ya activo', contiene='ya está activ')
    # permisos
    for rol, uid in (('Recepción', RECEP), ('Médico', MEDICO)):
        sesion(uid)
        api('get', url, 200, None, f'{nombre}: {rol} ve la lista')
        api('post', url, 403, {clave: 'ZZ NO'}, f'{nombre}: {rol} no puede agregar')
        api('put', f'{url}/{i}', 403, {clave: 'ZZ NO'}, f'{nombre}: {rol} no puede editar')
        api('delete', f'{url}/{i}', 403, None, f'{nombre}: {rol} no puede anular')
        api('patch', f'{url}/{i}/reactivar', 403, None, f'{nombre}: {rol} no puede reactivar')
        chk(f'{nombre}: {rol} abre la vista', c.get(vista).status_code == 200)
    sesion(CAJERO)
    api('get', url, 200, None, f'{nombre}: Cajero usa la lista como combo')
    api('get', url + '?inactivos=1', 403, None, f'{nombre}: Cajero sin "ver" no pide inactivos')
    chk(f'{nombre}: Cajero no abre la vista', c.get(vista).status_code == 403)
    sesion(ADMIN)
    return i


def uso_ciudad(i, liberar=False):
    if liberar:
        cu.execute("UPDATE paciente SET activo=false WHERE id_ciudad=%s AND cedula_entidad LIKE 'ZZU%%'", (i,)); cx.commit(); return
    fx._insertar('paciente', 'id_paciente', "INSERT INTO paciente(nombre, apellido, cedula_entidad, id_ciudad) VALUES ('ZZ USO','PRUEBA',%s,%s)", (f'ZZU{SUF}', i))


def uso_cargo(i, liberar=False):
    if liberar:
        cu.execute("UPDATE funcionario SET activo=false WHERE id_cargo=%s", (i,)); cx.commit(); return
    fx._insertar('funcionario', 'id_funcionario', "INSERT INTO funcionario(nombre, apellido, cedula, id_cargo) VALUES ('ZZ USO','PRUEBA',%s,%s)", (f'ZZU{SUF}', i))


def uso_especialidad(i, liberar=False):
    if liberar:
        cu.execute("UPDATE medico SET activo=false WHERE id_especialidad=%s", (i,)); cx.commit(); return
    fx._insertar('medico', 'id_medico', "INSERT INTO medico(nombre, apellido, cedula, id_especialidad, id_ciudad) VALUES ('ZZ USO','PRUEBA',%s,%s,%s)",
                 (f'ZZU{SUF}', i, fx.id_ciudad))


MEDICO_ZZ, _ = fx.medico(con_usuario=False)


def uso_dia_turno(col):
    def f(i, liberar=False):
        if liberar:
            cu.execute(f"UPDATE disponibilidad_horaria SET activo=false WHERE {col}=%s AND id_medico=%s", (i, MEDICO_ZZ)); cx.commit(); return
        dia = i if col == 'id_dia' else fx.id_dia
        turno = i if col == 'id_turno' else fx.id_turno
        fx._insertar('disponibilidad_horaria', 'id_disponibilidad',
                     "INSERT INTO disponibilidad_horaria(id_medico, id_dia, id_turno, dispo_hora_inicio, dispo_hora_fin, dispo_cupos, dispo_fecha) "
                     "VALUES (%s,%s,%s,'05:00','06:00',5,'2030-01-02')", (MEDICO_ZZ, dia, turno))
    return f


def requeridos(clave):
    return [({clave: ''}, 'vacío'), ({clave: '   '}, 'solo espacios'), ({clave: 'ZZ <b>'}, 'caracteres no permitidos'), ({}, 'sin el campo')]


ciudad = catalogo('Ciudad', 'ciudad', '/api/v1/ciudades', '/referenciales/ciudad/ciudad-index', 'ciudades', 'id_ciudad', 'descripcion', 'ciudades',
                  f'zz ciudad {SUF}', requeridos('descripcion'), uso_ciudad)
cargo = catalogo('Cargo', 'cargo', '/api/v1/cargos', '/referenciales/cargo/cargo-index', 'cargo', 'id_cargo', 'descripcion', 'cargo',
                 f'zz cargo {SUF}', requeridos('descripcion'), uso_cargo)
espec = catalogo('Especialidad', 'especialidad', '/api/v1/especialidades', '/referenciales/especialidad/especialidad-index', 'especialidades',
                 'id_especialidad', 'nombre_especialidad', 'especialidades', f'zz especialidad {SUF}', requeridos('nombre_especialidad'), uso_especialidad)
turno = catalogo('Turno', 'turno', '/api/v1/turnos', '/referenciales/turno/turno-index', 'turnos', 'id_turno', 'descripcion', 'turnos',
                 f'zz turno {SUF}', requeridos('descripcion'), uso_dia_turno('id_turno'))
chk('Turno: la base ya no limita los nombres (sin CHECK)', q("SELECT COUNT(*) FROM pg_constraint WHERE conname='chk_turnos'")[0][0] == 0)

# ---------------- Día: solo los 7 nombres de la semana ----------------
print('\n== Día')
sesion(ADMIN)
chk('Día: vista Tabler con selector de días', b'tabler' in c.get('/referenciales/dia/dia-index').data.lower())
for payload, texto in ([({'descripcion': ''}, 'vacío'), ({'descripcion': 'ENERO'}, 'un nombre que no es día'), ({'descripcion': 'LUN'}, 'abreviatura')]):
    api('post', '/api/v1/dias', 400, payload, f'Día: rechaza {texto}')
libres = [d for d in ('DOMINGO', 'SABADO', 'MIERCOLES', 'JUEVES', 'VIERNES', 'MARTES', 'LUNES')
          if not q("SELECT 1 FROM dias WHERE descripcion=%s AND activo", (d,))]
if libres:
    dia_nombre = libres[0]
    entrada = {'DOMINGO': 'domingo', 'SABADO': 'sábado', 'MIERCOLES': 'miércoles'}.get(dia_nombre, dia_nombre.lower())
    d = api('post', '/api/v1/dias', 201, {'descripcion': entrada}, f'Día: alta de un día real libre ({entrada})')
    idd = d.get('data', {}).get('id_dia')
    if idd:
        audita('dias', idd)
        chk('Día: se guarda sin tilde y en MAYÚSCULAS', q("SELECT descripcion FROM dias WHERE id_dia=%s", (idd,))[0][0] == dia_nombre)
        api('post', '/api/v1/dias', 400, {'descripcion': dia_nombre}, 'Día: no admite un día que ya existe activo', contiene='Ya existe')
        uso_dia_turno('id_dia')(idd)
        api('delete', f'/api/v1/dias/{idd}', 409, None, 'Día: baja bloqueada con disponibilidades', contiene='No se puede anular')
        uso_dia_turno('id_dia')(idd, liberar=True)
        api('delete', f'/api/v1/dias/{idd}', 200, None, 'Día: anulación')
        api('patch', f'/api/v1/dias/{idd}/reactivar', 200, None, 'Día: reactivación')
        sesion(RECEP); api('post', '/api/v1/dias', 403, {'descripcion': 'lunes'}, 'Día: Recepción no agrega'); sesion(ADMIN)
else:
    print('(los 7 días ya existen activos: se omite el alta de un día nuevo)')
    idd = None

# ---------------- Consultorio ----------------
print('\n== Consultorio')
URL = '/api/v1/consultorios'
sesion(ADMIN)
chk('Consultorio: vista Tabler', b'tabler' in c.get('/referenciales/consultorio/consultorio-index').data.lower())
base = {'nombre_consultorio': f'zz consultorio {SUF}', 'direccion': 'Calle Falsa 123', 'telefono': '0981 234 567', 'correo': f'zz{SUF}@test.invalid'}
for campo, malo, texto in (('nombre_consultorio', '', 'nombre vacío'), ('direccion', '', 'dirección vacía'), ('telefono', '123', 'teléfono no paraguayo'),
                           ('telefono', '', 'teléfono vacío'), ('correo', 'sin-arroba', 'correo inválido')):
    api('post', URL, 400, {**base, campo: malo}, f'Consultorio: rechaza {texto}', campo=campo)
d = api('post', URL, 201, base, 'Consultorio: alta')
ic = d.get('data', {}).get('codigo')
if ic:
    audita('consultorio', ic)
    fila = q("SELECT nombre_consultorio, telefono FROM consultorio WHERE codigo=%s", (ic,))[0]
    chk('Consultorio: nombre en MAYÚSCULAS y teléfono normalizado a 595…', fila == (base['nombre_consultorio'].upper(), '595981234567'))
    api('post', URL, 400, {**base, 'correo': f'otro{SUF}@test.invalid'}, 'Consultorio: nombre duplicado', contiene='ese nombre')
    api('post', URL, 400, {**base, 'nombre_consultorio': f'zz otro {SUF}'}, 'Consultorio: correo duplicado', contiene='ese correo', campo='correo')
    a = ultima_auditoria('consultorio', ic, 'ALTA')
    chk('Consultorio: auditoría ALTA con módulo y JSON', bool(a) and a[0] == 'Referenciales Agendamiento' and a[3])
    api('put', f'{URL}/{ic}', 200, {**base, 'direccion': 'Otra calle 45'}, 'Consultorio: modificación')
    # en uso por una caja activa
    id_caja = fx._insertar('caja', 'id_caja', "INSERT INTO caja(id_consultorio, descripcion) VALUES (%s,%s)", (ic, f'ZZ CAJA {SUF}'))
    api('delete', f'{URL}/{ic}', 409, None, 'Consultorio: baja bloqueada con una caja activa', contiene='caja')
    cu.execute("UPDATE caja SET activo=false WHERE id_caja=%s", (id_caja,)); cx.commit()
    api('delete', f'{URL}/{ic}', 200, None, 'Consultorio: anulación (la caja anulada no cuenta)')
    chk('Consultorio: BAJA auditada', bool(ultima_auditoria('consultorio', ic, 'BAJA')))
    api('post', URL, 201, base, 'Consultorio: alta de uno igual a un anulado')
    audita('consultorio', q("SELECT codigo FROM consultorio WHERE activo AND UPPER(nombre_consultorio)=%s", (base['nombre_consultorio'].upper(),))[0][0])
    api('patch', f'{URL}/{ic}/reactivar', 409, None, 'Consultorio: reactivar con otro activo igual', contiene='ya existe')
    # Caja: no se puede apuntar a un consultorio anulado
    sesion(ADMIN)
    api('post', '/api/v1/cajas', 400, {'id_consultorio': ic, 'descripcion': f'ZZ CAJA2 {SUF}'}, 'Caja: rechaza un consultorio anulado', contiene='anulado')
    for rol, uid in (('Recepción', RECEP), ('Médico', MEDICO)):
        sesion(uid)
        api('get', URL, 200, None, f'Consultorio: {rol} ve la lista')
        api('post', URL, 403, base, f'Consultorio: {rol} no puede agregar')
        api('delete', f'{URL}/{ic}', 403, None, f'Consultorio: {rol} no puede anular')
    sesion(ADMIN)

# ---------------- Disponibilidad Horaria ----------------
print('\n== Disponibilidad Horaria')
URL = '/api/v1/disponibilidades'
chk('Disponibilidad: vista Tabler', b'tabler' in c.get('/referenciales/disponibilidad/disponibilidad-index').data.lower())
fecha = (datetime.date.today() + datetime.timedelta(days=400)).isoformat()
base = {'id_medico': MEDICO_ZZ, 'id_dia': fx.id_dia, 'id_turno': fx.id_turno, 'dispo_fecha': fecha,
        'dispo_hora_inicio': '08:00', 'dispo_hora_fin': '12:00', 'dispo_cupos': 8}
for campo, malo, texto in (('id_medico', None, 'sin médico'), ('dispo_fecha', '2030-13-45', 'fecha inválida'), ('dispo_hora_inicio', '25:00', 'hora inválida'),
                           ('dispo_hora_fin', '07:00', 'fin anterior al inicio'), ('dispo_cupos', 0, 'cupos en cero'), ('dispo_cupos', 'x', 'cupos no numéricos')):
    api('post', URL, 400, {**base, campo: malo}, f'Disponibilidad: rechaza {texto}')
d = api('post', URL, 201, base, 'Disponibilidad: alta')
idp = d.get('data', {}).get('id_disponibilidad')
if idp:
    fx._borrar.append(('disponibilidad_horaria', 'id_disponibilidad', idp)); audita('disponibilidad_horaria', idp)
    api('post', URL, 409, {**base, 'dispo_hora_inicio': '11:00', 'dispo_hora_fin': '13:00'}, 'Disponibilidad: se superpone con otra del médico', contiene='superpone')
    d2 = api('post', URL, 201, {**base, 'dispo_hora_inicio': '12:00', 'dispo_hora_fin': '14:00'}, 'Disponibilidad: horario contiguo permitido')
    idp2 = d2.get('data', {}).get('id_disponibilidad')
    if idp2:
        fx._borrar.append(('disponibilidad_horaria', 'id_disponibilidad', idp2)); audita('disponibilidad_horaria', idp2)
    a = ultima_auditoria('disponibilidad_horaria', idp, 'ALTA')
    chk('Disponibilidad: auditoría con nombres (no IDs) y módulo', bool(a) and a[0] == 'Referenciales Agendamiento' and 'ZZ MEDICO' in str(a[3]) and 'Médico' in str(a[3]))
    api('put', f'{URL}/{idp}', 200, {**base, 'dispo_cupos': 9}, 'Disponibilidad: modificación')
    chk('Disponibilidad: MODIFICACION auditada', bool(ultima_auditoria('disponibilidad_horaria', idp, 'MODIFICACION')))
    api('delete', f'{URL}/{idp}', 200, None, 'Disponibilidad: anulación')
    chk('Disponibilidad: la lista no trae la anulada', all(f['id_disponibilidad'] != idp for f in c.get(URL).get_json()['data']))
    chk('Disponibilidad: ?inactivos=1 la trae', any(f['id_disponibilidad'] == idp for f in c.get(URL + '?inactivos=1').get_json()['data']))
    api('post', URL, 201, {**base, 'dispo_hora_inicio': '08:30', 'dispo_hora_fin': '09:30'}, 'Disponibilidad: alta sobre una anulada')
    nuevo = q("SELECT id_disponibilidad FROM disponibilidad_horaria WHERE id_medico=%s AND dispo_hora_inicio='08:30' AND activo", (MEDICO_ZZ,))[0][0]
    fx._borrar.append(('disponibilidad_horaria', 'id_disponibilidad', nuevo)); audita('disponibilidad_horaria', nuevo)
    api('patch', f'{URL}/{idp}/reactivar', 409, None, 'Disponibilidad: reactivar superpuesta a otra activa', contiene='superpone')
    api('delete', f'{URL}/{nuevo}', 200, None, 'Disponibilidad: anula la que estorba')
    api('patch', f'{URL}/{idp}/reactivar', 200, None, 'Disponibilidad: reactivación')
    # en uso: publicada en una agenda vigente -> no se anula ni se modifica
    id_func, id_u = fx.recepcion()
    cons = fx.consultorio()
    cab = fx._insertar('agenda_cabecera', 'id_agenda_cabecera',
                       "INSERT INTO agenda_cabecera(id_medico, id_especialidad, fecha_agenda, estado, id_funcionario, id_consultorio) VALUES (%s,%s,%s,'Activo',%s,%s)",
                       (MEDICO_ZZ, fx.id_especialidad, fecha, id_func, cons))
    det = fx._insertar('agenda_detalle', 'id_agenda_detalle',
                       "INSERT INTO agenda_detalle(id_agenda_cabecera, id_disponibilidad_horaria, id_dia, id_turno, hora_inicio, hora_fin, cupos_disponibles, cupos_maximos) "
                       "VALUES (%s,%s,%s,%s,'08:00','12:00',9,9)", (cab, idp, fx.id_dia, fx.id_turno))
    api('delete', f'{URL}/{idp}', 409, None, 'Disponibilidad: baja bloqueada si está en una agenda vigente', contiene='agenda')
    api('put', f'{URL}/{idp}', 409, {**base, 'dispo_cupos': 3}, 'Disponibilidad: no se modifica si está publicada', contiene='agenda')
    cu.execute("UPDATE agenda_detalle SET estado_detalle='Cancelado' WHERE id_agenda_detalle=%s", (det,)); cx.commit()
    api('put', f'{URL}/{idp}', 200, {**base, 'dispo_cupos': 3}, 'Disponibilidad: se modifica con el horario cancelado')
    # el médico, el día y el turno deben seguir activos
    fx.cu.execute("UPDATE medico SET activo=false WHERE id_medico=%s", (MEDICO_ZZ,)); cx.commit()
    api('post', URL, 400, {**base, 'dispo_hora_inicio': '15:00', 'dispo_hora_fin': '16:00'}, 'Disponibilidad: rechaza un médico anulado', contiene='anulado')
    fx.cu.execute("UPDATE medico SET activo=true WHERE id_medico=%s", (MEDICO_ZZ,)); cx.commit()
    # permisos: Recepción opera, Médico solo ve, Cajero nada
    sesion(RECEP)
    api('get', URL, 200, None, 'Disponibilidad: Recepción ve')
    api('post', URL, 201, {**base, 'dispo_hora_inicio': '17:00', 'dispo_hora_fin': '18:00'}, 'Disponibilidad: Recepción agrega')
    r_id = q("SELECT id_disponibilidad FROM disponibilidad_horaria WHERE id_medico=%s AND dispo_hora_inicio='17:00'", (MEDICO_ZZ,))[0][0]
    fx._borrar.append(('disponibilidad_horaria', 'id_disponibilidad', r_id)); audita('disponibilidad_horaria', r_id)
    api('put', f'{URL}/{r_id}', 200, {**base, 'dispo_hora_inicio': '17:00', 'dispo_hora_fin': '18:30'}, 'Disponibilidad: Recepción edita')
    api('delete', f'{URL}/{r_id}', 200, None, 'Disponibilidad: Recepción anula')
    api('patch', f'{URL}/{r_id}/reactivar', 200, None, 'Disponibilidad: Recepción reactiva')
    sesion(MEDICO)
    api('get', URL, 200, None, 'Disponibilidad: Médico ve')
    api('post', URL, 403, base, 'Disponibilidad: Médico no agrega')
    api('put', f'{URL}/{idp}', 403, base, 'Disponibilidad: Médico no edita')
    api('delete', f'{URL}/{idp}', 403, None, 'Disponibilidad: Médico no anula')
    sesion(CAJERO)
    chk('Disponibilidad: Cajero no abre la vista', c.get('/referenciales/disponibilidad/disponibilidad-index').status_code == 403)
    sesion(ADMIN)

# ---------------- FK que ya no borran en cascada ----------------
print('\n== FK (cambio del DER)')
for tabla, nombre in (('cita_cabecera', 'cita_cabecera_id_paciente_fkey'), ('cita_cabecera', 'cita_cabecera_id_agenda_cabecera_fkey'),
                      ('historial_medico_paciente', 'fk_historial_paciente'), ('medico', 'medico_id_ciudad_fkey'), ('avisos_recordatorios', 'fk_medico')):
    chk(f'{nombre}: ON DELETE RESTRICT', q("SELECT confdeltype FROM pg_constraint WHERE conname=%s AND conrelid=%s::regclass", (nombre, tabla)) == [('r',)])
pac = fx.paciente()
cons = fx.consultorio()
func, _u = fx.recepcion()
cab_a = fx._insertar('agenda_cabecera', 'id_agenda_cabecera',
                     "INSERT INTO agenda_cabecera(id_medico, id_especialidad, fecha_agenda, estado, id_funcionario, id_consultorio) VALUES (%s,%s,%s,'Activo',%s,%s)",
                     (MEDICO_ZZ, fx.id_especialidad, '2031-05-05', func, cons))
cab_c = fx._insertar('cita_cabecera', 'id_cita_cabecera',
                     "INSERT INTO cita_cabecera(id_paciente, id_agenda_cabecera, estado, id_funcionario) VALUES (%s,%s,'Activo',%s)", (pac, cab_a, func))
for sql, texto in (("DELETE FROM paciente WHERE id_paciente=%s", pac), ("DELETE FROM agenda_cabecera WHERE id_agenda_cabecera=%s", cab_a)):
    try:
        cu.execute(sql, (texto if texto == pac else cab_a,)); cx.commit(); borrado = True
    except Exception:
        cx.rollback(); borrado = False
    chk(f'borrar con citas asociadas ya no se hace en cascada ({sql.split()[2]})', not borrado)
chk('la cita sigue existiendo', q("SELECT COUNT(*) FROM cita_cabecera WHERE id_cita_cabecera=%s", (cab_c,))[0][0] == 1)

# ---------------- limpieza ----------------
sesion(ADMIN)
try:
    # los ZZ creados por la API (no pasaron por fx) se borran después de lo que cuelga de ellos
    fx.limpiar()
    for tabla, pk, entidad in (('ciudades', 'id_ciudad', 'ciudades'), ('cargo', 'id_cargo', 'cargo'), ('especialidades', 'id_especialidad', 'especialidades'),
                               ('turnos', 'id_turno', 'turnos'), ('dias', 'id_dia', 'dias'), ('consultorio', 'codigo', 'consultorio')):
        ids = list(auditorias.get(entidad, ()))
        if ids:
            cu.execute(f"DELETE FROM {tabla} WHERE {pk} = ANY(%s)", (ids,))
    for entidad, ids in auditorias.items():
        borrar_auditoria(cu, entidad, ids)
    cu.execute("SET session_replication_role = replica")
    cu.execute("DELETE FROM auditoria_cambios WHERE entidad='permisos' AND detalle LIKE '%%ZZ%%'")
    cu.execute("RESET session_replication_role")
    cx.commit()
except Exception as e:
    cx.rollback()
    print('ERROR en la limpieza:', e)
    fallos.append('limpieza')
sobras = q("SELECT (SELECT COUNT(*) FROM ciudades WHERE descripcion LIKE 'ZZ %%') + (SELECT COUNT(*) FROM cargo WHERE descripcion LIKE 'ZZ %%')"
           " + (SELECT COUNT(*) FROM especialidades WHERE nombre_especialidad LIKE 'ZZ %%') + (SELECT COUNT(*) FROM turnos WHERE descripcion LIKE 'ZZ %%')"
           " + (SELECT COUNT(*) FROM consultorio WHERE nombre_consultorio LIKE 'ZZ %%')")[0][0]
chk('limpieza: no quedan datos ZZ', sobras == 0)
print('\nFALLOS:', 'ninguno' if not fallos else fallos)
