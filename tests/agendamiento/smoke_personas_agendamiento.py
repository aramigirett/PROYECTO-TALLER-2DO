"""Etapa 2 de la migración de Agendamiento a Tabler: Paciente, Médico y Funcionario con baja lógica.

Por cada una: vista Tabler, validaciones, alta (nombres en MAYÚSCULAS, fecha de alta del servidor), duplicados entre los ACTIVOS (cédula, correo, N.º de
registro; cédula cruzada médico <-> funcionario), modificación (sin cambios no audita; solo contacto audita "Datos de contacto"), referenciales anulados
rechazados al guardar y al reactivar, baja bloqueada si está en uso (409 con el motivo, "Anule primero el usuario"), reactivación, lectura mínima para
quien no tiene 'ver' (sin datos de contacto), auditoría estructurada SIN teléfono, dirección ni correo, y permisos por rol. Además: Usuarios solo se vincula a
personas activas, Cliente solo a pacientes activos, y el cambio de cédula de quien tiene usuario pide confirmación. Datos `ZZ`: se borran por ID.
"""
import datetime
import sys
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
creados = {'paciente': set(), 'medico': set(), 'funcionario': set(), 'usuarios': set(), 'cliente': set()}


def ultima(entidad, i, accion):
    cu.execute("SELECT modulo, detalle, valores_anteriores, valores_nuevos, id_usuario, ip FROM auditoria_cambios "
               "WHERE entidad=%s AND id_registro=%s AND accion=%s ORDER BY id_auditoria_cambio DESC LIMIT 1", (entidad, i, accion))
    return cu.fetchone()


def n_aud(entidad, i):
    return q("SELECT COUNT(*) FROM auditoria_cambios WHERE entidad=%s AND id_registro=%s", (entidad, i))[0][0]


usu_med = usu_f = usu2 = None
_limpio = []


def limpieza():
    """Borra lo que creó el test (también si se corta a la mitad: se registra con atexit)."""
    if _limpio:
        return
    _limpio.append(1)
    try:
        cx.rollback()
        usuarios = [u for u in (usu2, usu_med, usu_f) if u]
        cu.execute("SET session_replication_role = replica")
        cu.execute("DELETE FROM auditoria_acceso WHERE id_usuario = ANY(%s) OR id_usuario_actor = ANY(%s)", (usuarios, usuarios))
        cu.execute("RESET session_replication_role")
        for t_, pk_ in (('paciente', 'id_paciente'), ('medico', 'id_medico'), ('funcionario', 'id_funcionario')):
            borrar_auditoria(cu, t_, list(creados[t_]))
            propios = {i for tt, _, i in fx._borrar if tt == t_}
            extra = [x for x in creados[t_] if x not in propios]
            if extra:
                cu.execute(f"DELETE FROM {t_} WHERE {pk_} = ANY(%s)", (extra,))
        cx.commit()
        fx.limpiar()
    except Exception as e:
        cx.rollback()
        print('ERROR en la limpieza:', e)
        fallos.append('limpieza')


import atexit
atexit.register(limpieza)

CIUDAD = q("SELECT id_ciudad FROM ciudades WHERE activo ORDER BY 1 LIMIT 1")[0][0]
ESPEC = q("SELECT id_especialidad FROM especialidades WHERE activo ORDER BY 1 LIMIT 1")[0][0]
CARGO = q("SELECT id_cargo FROM cargo WHERE activo ORDER BY 1 LIMIT 1")[0][0]
ciudad_zz = fx._insertar('ciudades', 'id_ciudad', "INSERT INTO ciudades(descripcion) VALUES (%s)", (f'ZZ CIUDAD P{SUF}',))
espec_zz = fx._insertar('especialidades', 'id_especialidad', "INSERT INTO especialidades(nombre_especialidad) VALUES (%s)", (f'ZZ ESPEC P{SUF}',))
cargo_zz = fx._insertar('cargo', 'id_cargo', "INSERT INTO cargo(descripcion) VALUES (%s)", (f'ZZ CARGO P{SUF}',))

CONTACTO = {'telefono': '0981000222', 'direccion': 'Calle Secreta 123', 'correo': None}


def cuerpo(tipo, cedula, correo, **extra):
    base = {'nombre': 'ZZ persona', 'apellido': 'ZZ prueba', 'fecha_nacimiento': '1990-01-01', 'telefono': '0981000222',
            'direccion': 'Calle Secreta 123', 'correo': correo}
    if tipo == 'paciente':
        base.update({'cedula_entidad': cedula, 'telefono_emergencia': '0981000333', 'id_ciudad': CIUDAD})
    elif tipo == 'medico':
        base.update({'cedula': cedula, 'num_registro': f'ZZ-{cedula}', 'id_especialidad': ESPEC, 'id_ciudad': CIUDAD})
    else:
        base.update({'cedula': cedula, 'id_cargo': CARGO})
    base.update(extra)
    return base


def sin_contacto_en_auditoria(entidad, i):
    a = ultima(entidad, i, 'ALTA')
    texto = str(a[1]) + str(a[2]) + str(a[3]) if a else ''
    return bool(a) and '0981000222' not in texto and 'Calle Secreta' not in texto and '@test.invalid' not in texto and '1990-01-01' not in texto


ESPECS = [
    dict(tipo='paciente', nombre='Paciente', url='/api/v1/pacientes', vista='/referenciales/paciente/paciente-index', doc='cedula_entidad', pk='id_paciente',
         padre='id_ciudad', padre_zz=ciudad_zz, base_ced='91', col_padre='ciudad'),
    dict(tipo='medico', nombre='Médico', url='/api/v1/medico', vista='/referenciales/medico/medico-index', doc='cedula', pk='id_medico',
         padre='id_especialidad', padre_zz=espec_zz, base_ced='92', col_padre='especialidad'),
    dict(tipo='funcionario', nombre='Funcionario', url='/api/v1/funcionarios', vista='/referenciales/funcionario/funcionario-index', doc='cedula',
         pk='id_funcionario', padre='id_cargo', padre_zz=cargo_zz, base_ced='93', col_padre='cargo'),
]
ids = {}

for E in ESPECS:
    tipo, N, URL, doc, pk = E['tipo'], E['nombre'], E['url'], E['doc'], E['pk']
    ced = lambda n: f"{E['base_ced']}{SUF}{n}"[:10]
    print(f'\n== {N}')
    sesion(ADMIN)
    r = c.get(E['vista'])
    chk(f'{N}: vista Tabler', r.status_code == 200 and b'tabler' in r.data.lower() and b'btnAgregar' in r.data)
    ok = cuerpo(tipo, ced(1), f'zz{tipo}{SUF}@test.invalid')
    for campo, malo, texto in (('nombre', '', 'nombre vacío'), ('apellido', '<b>', 'apellido con símbolos'), (doc, '12', 'cédula corta'),
                               ('fecha_nacimiento', '2999-01-01', 'nacimiento futuro'), ('fecha_nacimiento', 'x', 'nacimiento inválido'),
                               ('telefono', '1', 'teléfono corto'), ('correo', 'malo', 'correo inválido'), ('direccion', '', 'dirección vacía'),
                               (E['padre'], None, 'sin referencial')):
        api('post', URL, 400, {**ok, campo: malo}, f'{N}: rechaza {texto}', campo=campo)
    d = api('post', URL, 201, ok, f'{N}: alta')
    i = d.get('data', {}).get(pk)
    if not i:
        continue
    ids[tipo] = i; creados[tipo].add(i)
    fila = q(f"SELECT nombre, apellido, fecha_registro IS NOT NULL, activo FROM {tipo} WHERE {pk}=%s", (i,))[0]
    chk(f'{N}: nombre y apellido en MAYÚSCULAS, fecha de alta del servidor', fila == ('ZZ PERSONA', 'ZZ PRUEBA', True, True))
    api('post', URL, 409, {**ok, 'correo': f'otro{tipo}{SUF}@test.invalid'} if tipo != 'medico' else {**ok, 'num_registro': 'ZZ-OTRO'}, f'{N}: cédula repetida entre activos',
        contiene='cédula', campo=doc)
    if tipo != 'medico':
        api('post', URL, 409, {**ok, doc: ced(2)}, f'{N}: correo repetido entre activos', contiene='ese correo', campo='correo')
    else:
        api('post', URL, 409, {**ok, doc: ced(2), 'correo': f'otro{SUF}@test.invalid'}, f'{N}: N.º de registro repetido entre activos', contiene='registro', campo='num_registro')
    a = ultima(tipo, i, 'ALTA')
    chk(f'{N}: auditoría ALTA con módulo, usuario e IP', bool(a) and a[0] == 'Módulo Agendamiento' and a[4] == ADMIN and a[5] and a[3])
    chk(f'{N}: la auditoría NO guarda teléfono, dirección, correo ni nacimiento', sin_contacto_en_auditoria(tipo, i))
    # modificación
    antes = n_aud(tipo, i)
    api('put', f'{URL}/{i}', 200, ok, f'{N}: edición sin cambios', contiene='sin cambios')
    chk(f'{N}: edición sin cambios no audita', n_aud(tipo, i) == antes)
    api('put', f'{URL}/{i}', 200, {**ok, 'telefono': '0981999888'}, f'{N}: edición solo de contacto')
    m = ultima(tipo, i, 'MODIFICACION')
    chk(f'{N}: solo contacto audita "Datos de contacto" sin los valores', bool(m) and 'Datos de contacto' in str(m[3]) and '0981999888' not in str(m[1]) + str(m[2]) + str(m[3]))
    api('put', f'{URL}/{i}', 200, {**ok, 'nombre': 'ZZ otro nombre'}, f'{N}: modificación del nombre')
    m = ultima(tipo, i, 'MODIFICACION')
    chk(f'{N}: MODIFICACION con anterior y nuevo', bool(m) and 'ZZ OTRO NOMBRE' in str(m[3]) and 'ZZ PERSONA' in str(m[2]))
    # referenciales anulados al guardar
    msg = {'ciudad': 'anulad', 'especialidad': 'anulad', 'cargo': 'anulad'}[E['col_padre']]
    cu.execute({'ciudad': "UPDATE ciudades SET activo=false WHERE id_ciudad=%s", 'especialidad': "UPDATE especialidades SET activo=false WHERE id_especialidad=%s",
                'cargo': "UPDATE cargo SET activo=false WHERE id_cargo=%s"}[E['col_padre']], (E['padre_zz'],)); cx.commit()
    api('post', URL, 400, cuerpo(tipo, ced(3), f'zz3{tipo}{SUF}@test.invalid', **{E['padre']: E['padre_zz']}), f'{N}: alta rechaza {E["col_padre"]} anulado', contiene=msg, campo=E['padre'])
    api('put', f'{URL}/{i}', 400, {**ok, E['padre']: E['padre_zz']}, f'{N}: modificación rechaza {E["col_padre"]} anulado', contiene=msg, campo=E['padre'])
    cu.execute({'ciudad': "UPDATE ciudades SET activo=true WHERE id_ciudad=%s", 'especialidad': "UPDATE especialidades SET activo=true WHERE id_especialidad=%s",
                'cargo': "UPDATE cargo SET activo=true WHERE id_cargo=%s"}[E['col_padre']], (E['padre_zz'],)); cx.commit()
    # lectura mínima y completa
    sesion(CAJERO)
    lista = c.get(URL).get_json()['data']
    fila_c = next((f for f in lista if f[pk] == i), None)
    chk(f'{N}: quien no tiene "ver" (Cajero) solo recibe lo mínimo, sin datos de contacto', bool(fila_c) and 'nombre' in fila_c and 'telefono' not in fila_c and 'correo' not in fila_c and 'direccion' not in fila_c)
    api('get', URL + '?inactivos=1', 403, None, f'{N}: Cajero no pide inactivos')
    chk(f'{N}: Cajero no abre la vista', c.get(E['vista']).status_code == 403)
    sesion(ADMIN)
    chk(f'{N}: Administrador recibe el detalle completo', all(('telefono' in f) for f in c.get(URL).get_json()['data']))
    # anular / reactivar
    api('delete', f'{URL}/{i}', 200, None, f'{N}: anulación')
    b = ultima(tipo, i, 'BAJA')
    chk(f'{N}: BAJA auditada', bool(b))
    chk(f'{N}: la lista no trae al anulado', all(f[pk] != i for f in c.get(URL).get_json()['data']))
    chk(f'{N}: ?inactivos=1 lo trae como inactivo', any(f[pk] == i and not f['activo'] for f in c.get(URL + '?inactivos=1').get_json()['data']))
    api('get', f'{URL}/{i}', 404, None, f'{N}: un anulado no se consulta por el buscador')
    d2 = api('post', URL, 201, {**ok, 'num_registro': f'ZZ-R{SUF}'} if tipo == 'medico' else ok, f'{N}: se puede registrar de nuevo la misma cédula')
    i2 = d2.get('data', {}).get(pk)
    if i2:
        creados[tipo].add(i2)
        api('patch', f'{URL}/{i}/reactivar', 409, None, f'{N}: reactivar con otra persona activa igual', contiene='ya existe', campo=doc)
        api('delete', f'{URL}/{i2}', 200, None, f'{N}: anula la segunda')
    # reactivar exige que los referenciales sigan activos
    tabla_p, pk_p = {'ciudad': ('ciudades', 'id_ciudad'), 'especialidad': ('especialidades', 'id_especialidad'), 'cargo': ('cargo', 'id_cargo')}[E['col_padre']]
    d3 = api('post', URL, 201, cuerpo(tipo, ced(4), f'zz4{tipo}{SUF}@test.invalid', **{E['padre']: E['padre_zz'], **({'num_registro': f'ZZ-P{SUF}'} if tipo == 'medico' else {})}), f'{N}: alta con un referencial ZZ activo')
    i3 = d3.get('data', {}).get(pk)
    if i3:
        creados[tipo].add(i3)
        api('delete', f'{URL}/{i3}', 200, None, f'{N}: anula la de prueba')
        cu.execute(f"UPDATE {tabla_p} SET activo=false WHERE {pk_p}=%s", (E['padre_zz'],)); cx.commit()
        api('patch', f'{URL}/{i3}/reactivar', 409, None, f'{N}: reactivar con {E["col_padre"]} anulado', contiene='anulad')
        cu.execute(f"UPDATE {tabla_p} SET activo=true WHERE {pk_p}=%s", (E['padre_zz'],)); cx.commit()
    api('patch', f'{URL}/{i}/reactivar', 200, None, f'{N}: reactivación')
    chk(f'{N}: REACTIVACION auditada', bool(ultima(tipo, i, 'REACTIVACION')))
    api('patch', f'{URL}/{i}/reactivar', 409, None, f'{N}: reactivar uno ya activo', contiene='ya está activ')

# ---------------- cédula cruzada médico <-> funcionario ----------------
print('\n== Cédula cruzada')
sesion(ADMIN)
ced_f = q("SELECT cedula FROM funcionario WHERE id_funcionario=%s", (ids['funcionario'],))[0][0]
api('post', '/api/v1/medico', 409, cuerpo('medico', ced_f, f'zzx{SUF}@test.invalid', num_registro=f'ZZ-X{SUF}'), 'Médico: cédula de un funcionario activo', contiene='otro funcionario')
ced_m = q("SELECT cedula FROM medico WHERE id_medico=%s", (ids['medico'],))[0][0]
api('post', '/api/v1/funcionarios', 409, cuerpo('funcionario', ced_m, f'zzy{SUF}@test.invalid'), 'Funcionario: cédula de un médico activo', contiene='otro médico')

# ---------------- baja bloqueada por trabajo en curso ----------------
print('\n== Baja bloqueada si está en uso')
pac = fx.paciente()
med_zz, usu_med = fx.medico(con_usuario=True)
f_zz, usu_f = fx.recepcion()
cons = fx.consultorio()
api('delete', f'/api/v1/medico/{med_zz}', 409, None, 'Médico con usuario activo', contiene='Anule primero el usuario')
api('delete', f'/api/v1/funcionarios/{f_zz}', 409, None, 'Funcionario con usuario activo', contiene='Anule primero el usuario')
cu.execute("UPDATE usuarios SET activo=false WHERE id_usuario = ANY(%s)", ([usu_med, usu_f],)); cx.commit()
cita = fx.cita(med_zz, pac, cons, f_zz, 'Confirmado')
api('delete', f'/api/v1/pacientes/{pac}', 409, None, 'Paciente con una cita pendiente', contiene='cita(s) pendiente(s)')
api('delete', f'/api/v1/medico/{med_zz}', 409, None, 'Médico con agenda vigente', contiene='agenda(s) vigente(s)')
cu.execute("UPDATE cita_detalle SET id_estado_cita=%s WHERE id_cita_detalle=%s", (fx.estado_cita['Cancelado'], cita)); cx.commit()
api('delete', f'/api/v1/pacientes/{pac}', 200, None, 'Paciente: con la cita cancelada se puede anular')
cu.execute("UPDATE agenda_cabecera SET estado='Inactivo' WHERE id_medico=%s", (med_zz,))
cu.execute("UPDATE disponibilidad_horaria SET activo=false WHERE id_medico=%s", (med_zz,)); cx.commit()
api('delete', f'/api/v1/medico/{med_zz}', 200, None, 'Médico: sin usuario activo ni trabajo en curso se puede anular')
api('delete', f'/api/v1/funcionarios/{f_zz}', 200, None, 'Funcionario: sin usuario activo se puede anular')
for t, i in (('paciente', pac), ('medico', med_zz), ('funcionario', f_zz)):
    creados[t].add(i)

# ---------------- Usuarios y Cliente solo con personas activas ----------------
print('\n== Usuarios y Cliente')
disp = c.get('/api/v1/usuarios/medicos-disponibles').get_json()['data']
chk('Usuarios: los médicos disponibles no incluyen anulados', all(m.get('id_medico') != med_zz for m in disp))
disp = c.get('/api/v1/usuarios/funcionarios-disponibles').get_json()['data']
chk('Usuarios: los funcionarios disponibles no incluyen anulados', all(f.get('id_funcionario') != f_zz for f in disp))
api('post', '/api/v1/usuarios', 400, {'password': 'Zz123456!x', 'id_rol': fx.rol['Medico'], 'id_medico': med_zz}, 'Usuarios: no se vincula a un médico anulado')
api('patch', f'/api/v1/usuarios/{usu_med}/reactivar', 409, None, 'Usuarios: no se reactiva el usuario de un médico anulado', contiene='anulado')
api('post', '/api/v1/clientes', 400, {'id_paciente': pac, 'nombre': 'ZZ', 'ci_ruc': '9988776', 'telefono': '0981000222', 'correo': 'zz@test.invalid'}, 'Cliente: no se crea sobre un paciente anulado', contiene='anulado')
chk('Cliente: el buscador de pacientes no trae anulados', all(p['id_paciente'] != pac for p in (c.get('/api/v1/clientes/pacientes?q=ZZ').get_json() or {}).get('data', [])))

# ---------------- cambio de cédula de quien tiene usuario ----------------
print('\n== Cédula = login')
med2, usu2 = fx.medico(con_usuario=True)
creados['medico'].add(med2)
r = api('put', f'/api/v1/medico/{med2}', 409, {**cuerpo('medico', f'94{SUF}', f'zzm{SUF}@test.invalid', num_registro=f'ZZ-M{SUF}'), 'nombre': 'ZZ MEDICO'}, 'Médico con usuario: cambiar la cédula pide confirmación')
chk('Médico con usuario: la respuesta pide confirmar', r.get('requiere_confirmacion') is True and r.get('cedula_nueva') == f'94{SUF}')
api('put', f'/api/v1/medico/{med2}', 200, {**cuerpo('medico', f'94{SUF}', f'zzm{SUF}@test.invalid', num_registro=f'ZZ-M{SUF}'), 'confirmar_cambio_cedula': True}, 'Médico con usuario: confirmado')
chk('Médico con usuario: el cambio de login queda en el tablero de accesos',
    q("SELECT COUNT(*) FROM auditoria_acceso WHERE id_usuario=%s AND ci_ruc_ingresado=%s", (usu2, f'94{SUF}'))[0][0] == 1)

# ---------------- permisos por rol ----------------
print('\n== Permisos')
sesion(RECEP)
r1 = api('post', '/api/v1/pacientes', 201, cuerpo('paciente', f'95{SUF}', f'zzr{SUF}@test.invalid'), 'Recepción agrega pacientes')
rp = r1.get('data', {}).get('id_paciente')
if rp:
    creados['paciente'].add(rp)
    api('put', f'/api/v1/pacientes/{rp}', 200, {**cuerpo('paciente', f'95{SUF}', f'zzr{SUF}@test.invalid'), 'direccion': 'Otra calle'}, 'Recepción edita pacientes')
    api('delete', f'/api/v1/pacientes/{rp}', 403, None, 'Recepción NO anula pacientes')
    api('patch', f'/api/v1/pacientes/{rp}/reactivar', 403, None, 'Recepción NO reactiva pacientes')
for url, v in (('/api/v1/medico', 'medico'), ('/api/v1/funcionarios', 'funcionario')):
    api('get', url, 200, None, f'Recepción ve {v}')
    api('post', url, 403, cuerpo(v, f'96{SUF}', f'zzq{SUF}@test.invalid'), f'Recepción NO agrega {v}')
    api('put', f'{url}/{ids[v]}', 403, cuerpo(v, f'96{SUF}', f'zzq{SUF}@test.invalid'), f'Recepción NO edita {v}')
    api('delete', f'{url}/{ids[v]}', 403, None, f'Recepción NO anula {v}')
sesion(MEDICO)
for url, v in (('/api/v1/pacientes', 'paciente'), ('/api/v1/medico', 'medico'), ('/api/v1/funcionarios', 'funcionario')):
    api('get', url, 200, None, f'Médico ve {v}')
    api('post', url, 403, cuerpo(v, f'97{SUF}', f'zzp{SUF}@test.invalid'), f'Médico NO agrega {v}')
    api('delete', f'{url}/{ids[v]}', 403, None, f'Médico NO anula {v}')
    chk(f'Médico abre la vista de {v}', c.get({'paciente': '/referenciales/paciente/paciente-index', 'medico': '/referenciales/medico/medico-index',
                                              'funcionario': '/referenciales/funcionario/funcionario-index'}[v]).status_code == 200)
sesion(ADMIN)

# ---------------- limpieza ----------------
limpieza()
sobras = q("SELECT (SELECT COUNT(*) FROM paciente WHERE nombre LIKE 'ZZ%%') + (SELECT COUNT(*) FROM medico WHERE nombre LIKE 'ZZ%%')"
           " + (SELECT COUNT(*) FROM funcionario WHERE nombre LIKE 'ZZ%%') + (SELECT COUNT(*) FROM ciudades WHERE descripcion LIKE 'ZZ%%')")[0][0]
chk('limpieza: no quedan datos ZZ', sobras == 0)
print('\nFALLOS:', 'ninguno' if not fallos else fallos)
