import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from tests.facturacion._limpieza import borrar_auditoria
from app import app
from tests._conexion_pruebas import Conexion
from app.rutas.modulo_facturacion import utils

c = app.test_client()
fallos = []
clientes = set(); pacientes = set()

def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)

def api(metodo, url, esperado, json=None, nombre=None, campo=None, contiene=None, exacto=None):
    f = getattr(c, metodo)
    r = f(url, json=json) if json is not None else f(url)
    d = r.get_json(silent=True) or {}
    ok = r.status_code == esperado
    if campo is not None:
        ok = ok and d.get('campo') == campo
    texto = d.get('error') or d.get('mensaje') or ''
    if contiene is not None:
        ok = ok and contiene in texto
    if exacto is not None:
        ok = ok and texto == exacto
    chk(f"{nombre or metodo + ' ' + url} -> {r.status_code}" + ('' if ok else f' {d}'), ok)
    return d

CL = '/api/v1/clientes'
cx = Conexion().getConexion(); cu = cx.cursor()
cu.execute("SELECT id_ciudad FROM ciudades ORDER BY 1 LIMIT 1"); CIUDAD = cu.fetchone()[0]

def nuevo_paciente(nombre, apellido, cedula, tel, correo):
    cu.execute("""INSERT INTO paciente(nombre, apellido, cedula_entidad, telefono, correo, id_ciudad)
                  VALUES (%s,%s,%s,%s,%s,%s) RETURNING id_paciente""", (nombre, apellido, cedula, tel, correo, CIUDAD))
    cx.commit(); i = cu.fetchone()[0]; pacientes.add(i); return i

MSG_CI = 'Ya existe un cliente con esa CI/RUC.'
MSG_PAC = 'Ese paciente ya está registrado como cliente.'

try:
    # ---------- dígito verificador del RUC (módulo 11, base máxima 11) ----------
    chk('DV de 44444401 = 7 (consumidor final de la SET)', utils.calcular_dv_ruc('44444401') == 7)
    chk('DV de 80012345 = 0', utils.calcular_dv_ruc('80012345') == 0)
    chk('RUC con verificador CORRECTO: 44444401-7', utils.validar_ci_ruc('44444401-7') == ('44444401-7', None))
    chk('RUC con verificador CORRECTO: 80012345-0', utils.validar_ci_ruc('80012345-0') == ('80012345-0', None))
    chk('RUC con verificador INCORRECTO: 80012345-6', utils.validar_ci_ruc('80012345-6') == (None, 'El dígito verificador del RUC no es válido.'))
    chk('RUC con verificador INCORRECTO: 44444401-8', utils.validar_ci_ruc('44444401-8')[1] == 'El dígito verificador del RUC no es válido.')
    validos = [d for d in range(10) if utils.validar_ci_ruc(f'80012345-{d}')[1] is None]
    chk('de los 10 verificadores posibles solo 1 es válido', validos == [0])
    for base in ['80000001', '80069563', '1234567', '800123450', '99999999']:
        dv = utils.calcular_dv_ruc(base)
        chk(f'RUC {base}-{dv} válido y {base}-{(dv + 1) % 10} inválido',
            utils.validar_ci_ruc(f'{base}-{dv}')[1] is None and utils.validar_ci_ruc(f'{base}-{(dv + 1) % 10}')[1] is not None)
    for ced, ok_ in [('1234', False), ('12345', True), ('1234567890', True), ('12345678901', False), ('0000000', True)]:
        chk(f'cédula {ced!r} ({len(ced)} dígitos) {"válida" if ok_ else "inválida"} (sin verificador)', (utils.validar_ci_ruc(ced)[1] is None) == ok_)
    for malo in ['', '  ', 'abc', '8001-0', '80012345-', '80012345-01', '-7', '12 345', '80012345 - 0', 'ab123-4', None]:
        chk(f'CI/RUC inválido {malo!r}', utils.validar_ci_ruc(malo)[1] is not None)

    api('get', CL, 401, nombre='sin sesion')
    with c.session_transaction() as s:
        s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

    r = c.get('/referenciales/cliente/cliente-index')
    chk('vista cliente', r.status_code == 200 and b'Mostrar inactivos' in r.data and b'El cliente ya es paciente' in r.data and b'facturacion-validadores.js' in r.data)
    r = c.get('/static/js/facturacion-validadores.js')
    chk('js: ciRuc, calcularDvRuc, nombre', all(x in r.data for x in (b'ciRuc:', b'calcularDvRuc', b'nombre:', b'telefonoOpcional')))

    # ---------- seed del sistema (único dato que el test espera ya cargado; el resto lo crea el propio test con prefijo ZZ) ----------
    d = api('get', CL, 200, nombre='lista')
    por_ruc = {x['ci_ruc']: x for x in d['data']}
    cf = por_ruc.get('44444401-7')
    chk('seed SIN NOMBRE (consumidor final, sin apellido/teléfono/correo, sin paciente)',
        cf and cf['nombre'] == 'SIN NOMBRE' and not cf['apellido'] and not cf['telefono'] and not cf['correo'] and cf['id_paciente'] is None and cf['es_consumidor_final'])

    # ---------- buscador de pacientes ----------
    zp = nuevo_paciente('ZZLUCÍA', 'ZZPÉREZ', '9990001', '0981999001', 'zz.lucia@test.invalid')
    api('get', f'{CL}/pacientes?q=z', 400, nombre='buscador: 1 carácter', exacto='Ingrese al menos 2 caracteres para buscar.')
    api('get', f'{CL}/pacientes', 400, nombre='buscador: sin q')
    d = api('get', f'{CL}/pacientes?q=9990', 200, nombre='buscador por cédula (prefijo)')
    chk('encuentra al paciente de prueba, ya_es_cliente False', [x for x in d['data'] if x['id_paciente'] == zp] and not [x for x in d['data'] if x['id_paciente'] == zp][0]['ya_es_cliente'])
    d = api('get', f'{CL}/pacientes?q=zzlucía zzpé', 200, nombre='buscador por nombre y apellido (sin importar mayúsculas)')
    chk('encuentra por nombre completo', zp in {x['id_paciente'] for x in d['data']})
    d = api('get', f'{CL}/pacientes?q=9990001', 200); x = [y for y in d['data'] if y['id_paciente'] == zp][0]
    chk('trae nombre, apellido, cédula, teléfono y correo', (x['nombre'], x['apellido'], x['cedula'], x['telefono'], x['correo']) == ('ZZLUCÍA', 'ZZPÉREZ', '9990001', '0981999001', 'zz.lucia@test.invalid'))
    d = api('get', f'{CL}/pacientes?q=%25%25', 200, nombre='buscador: % no actúa como comodín'); chk('sin resultados con %%', d['data'] == [])
    d = api('get', f'{CL}/pacientes?q=' + '5' * 2 + '0', 200, nombre='buscador: otra consulta'); chk('máx. 20 resultados', len(d['data']) <= 20)

    # ---------- validaciones ----------
    base = {'nombre': ' zz  juan ', 'apellido': ' zz  pérez ', 'ci_ruc': '9991111', 'telefono': '0981 000111', 'correo': 'Juan@Test.COM'}
    api('post', CL, 400, {**base, 'nombre': ' '}, 'nombre vacío', campo='nombre')
    api('post', CL, 400, {**base, 'nombre': 'N' * 81}, 'nombre 81', campo='nombre')
    api('post', CL, 400, {**base, 'nombre': 'a<b'}, 'nombre símbolos', campo='nombre')
    api('post', CL, 400, {**base, 'apellido': 'A' * 81}, 'apellido 81', campo='apellido')
    api('post', CL, 400, {**base, 'apellido': 'a<b'}, 'apellido símbolos', campo='apellido')
    api('post', CL, 400, {**base, 'ci_ruc': ''}, 'ci_ruc vacío', campo='ci_ruc')
    api('post', CL, 400, {**base, 'ci_ruc': '1234'}, 'ci_ruc cédula corta', campo='ci_ruc')
    api('post', CL, 400, {**base, 'ci_ruc': '80012345-6'}, 'ci_ruc RUC con verificador INCORRECTO', campo='ci_ruc', exacto='El dígito verificador del RUC no es válido.')
    api('post', CL, 400, {**base, 'telefono': '12345'}, 'teléfono corto', campo='telefono')
    api('post', CL, 400, {**base, 'telefono': '+5-95-1 1'}, 'teléfono con <6 dígitos', campo='telefono')
    api('post', CL, 400, {**base, 'correo': 'malo'}, 'correo inválido', campo='correo')
    api('post', CL, 400, {**base, 'id_paciente': 'abc'}, 'id_paciente no numérico', campo='id_paciente')
    api('post', CL, 400, {**base, 'id_paciente': 999999}, 'id_paciente inexistente', campo='id_paciente', exacto='El paciente seleccionado no existe o está anulado.')
    api('post', CL, 400, None, 'sin cuerpo', campo='nombre') if False else None

    # ---------- alta manual ----------
    d = api('post', CL, 201, base, 'alta manual')
    m1 = d['data']['id_cliente']; clientes.add(m1)
    chk('mayúsculas, correo en minúsculas, sin paciente', d['data']['nombre'] == 'ZZ JUAN' and d['data']['apellido'] == 'ZZ PÉREZ' and d['data']['correo'] == 'juan@test.com' and d['data']['id_paciente'] is None and d['data']['es_paciente'] is False and d['data']['activo'] is True)
    d = api('post', CL, 201, {'nombre': 'zz empresa & hijos s.a.', 'ci_ruc': '80012345-0' if False else '80069563-1'}, 'alta con solo nombre y RUC (apellido, teléfono y correo opcionales)')
    m2 = d['data']['id_cliente']; clientes.add(m2)
    chk('opcionales quedan NULL', d['data']['apellido'] is None and d['data']['telefono'] is None and d['data']['correo'] is None and d['data']['nombre'] == 'ZZ EMPRESA & HIJOS S.A.')
    api('post', CL, 400, base, 'duplicado de CI/RUC', campo='ci_ruc', exacto=MSG_CI)
    api('post', CL, 400, {**base, 'ci_ruc': '9991111'}, 'duplicado de CI/RUC (otro nombre)', campo='ci_ruc', exacto=MSG_CI)
    api('post', CL, 400, {**base, 'ci_ruc': '44444401-7'}, 'no se puede crear otro con la CI/RUC del consumidor final', campo='ci_ruc', exacto=MSG_CI)

    # ---------- alta desde paciente ----------
    d = api('post', CL, 201, {'id_paciente': zp, 'nombre': 'zzlucía', 'apellido': 'zzpérez corregido', 'ci_ruc': '9990001', 'telefono': '0981999001', 'correo': 'zz.lucia@test.invalid'}, 'ALTA DESDE PACIENTE (con un dato corregido)')
    p1 = d['data']['id_cliente']; clientes.add(p1)
    chk('guarda id_paciente y los datos corregidos', d['data']['id_paciente'] == zp and d['data']['es_paciente'] is True and d['data']['apellido'] == 'ZZPÉREZ CORREGIDO')
    cu.execute("SELECT apellido FROM paciente WHERE id_paciente=%s", (zp,)); chk('el paciente NO se modificó (copia, no sincroniza)', cu.fetchone()[0] == 'ZZPÉREZ')
    api('post', CL, 400, {'id_paciente': zp, 'nombre': 'otro', 'ci_ruc': '9992222'}, 'DUPLICADO DE PACIENTE', campo='id_paciente', exacto=MSG_PAC)
    api('post', CL, 400, {'id_paciente': zp, 'nombre': 'otro', 'ci_ruc': '9990001'}, 'paciente y CI/RUC duplicados a la vez: gana el mensaje del paciente', campo='id_paciente', exacto=MSG_PAC)
    api('post', CL, 201, {'id_paciente': str(nuevo_paciente('ZZMARTA', 'ZZRÍOS', '9990002', None, None)), 'nombre': 'zzmarta', 'apellido': 'zzríos', 'ci_ruc': '9990002'}, 'alta desde paciente sin teléfono/correo e id_paciente como texto')
    clientes.add(max(x['id_cliente'] for x in c.get(CL).get_json()['data']))
    d = api('get', f'{CL}/pacientes?q=9990001', 200); chk('buscador: el paciente ahora figura como ya_es_cliente', [y for y in d['data'] if y['id_paciente'] == zp][0]['ya_es_cliente'] is True)

    # ---------- modificación ----------
    api('put', f'{CL}/{m1}', 200, base, 'mod sin cambios', contiene='sin cambios')
    d = api('put', f'{CL}/{m1}', 200, {**base, 'telefono': '', 'correo': '', 'apellido': '', 'nombre': 'zz juan carlos'}, 'mod: vaciar opcionales y cambiar nombre')
    chk('opcionales vaciados => NULL', d['data']['telefono'] is None and d['data']['correo'] is None and d['data']['apellido'] is None and d['data']['nombre'] == 'ZZ JUAN CARLOS')
    api('put', f'{CL}/{m1}', 400, {**base, 'ci_ruc': '80069563-1'}, 'mod con CI/RUC de otro cliente', campo='ci_ruc', exacto=MSG_CI)
    api('put', f'{CL}/{m1}', 400, {**base, 'ci_ruc': '80069563-2'}, 'mod con RUC inválido', campo='ci_ruc')
    api('put', f'{CL}/{m1}', 400, {**base, 'id_paciente': zp}, 'mod: no se puede vincular un paciente después del alta', campo='id_paciente', exacto='El paciente vinculado no se puede cambiar.')
    api('put', f'{CL}/{p1}', 400, {'nombre': 'zzlucía', 'ci_ruc': '9990001', 'id_paciente': 999999}, 'mod: no se puede cambiar el paciente vinculado', campo='id_paciente')
    d = api('put', f'{CL}/{p1}', 200, {'nombre': 'zzlucía', 'apellido': 'zzpérez', 'ci_ruc': '9990001', 'telefono': '0981999001', 'correo': 'zz.lucia@test.invalid', 'id_paciente': zp}, 'mod del cliente-paciente (mismo id_paciente permitido)')
    chk('sigue vinculado', d['data']['id_paciente'] == zp)
    api('put', f'{CL}/{cf["id_cliente"]}', 409, {'nombre': 'otro', 'ci_ruc': '44444401-7'}, 'MODIFICAR SIN NOMBRE -> bloqueado', exacto='El consumidor final no se puede modificar.')
    api('put', f'{CL}/999999', 404, base, 'mod inexistente')

    # ---------- baja ----------
    api('delete', f'{CL}/{cf["id_cliente"]}', 409, nombre='BAJA DE SIN NOMBRE -> bloqueada', exacto='El consumidor final no se puede dar de baja.')
    cu.execute("SELECT activo FROM cliente WHERE id_cliente=%s", (cf['id_cliente'],)); chk('SIN NOMBRE sigue activo', cu.fetchone()[0] is True)
    api('delete', f'{CL}/{m1}', 200, nombre='baja', contiene='anulado')
    api('delete', f'{CL}/{m1}', 404, nombre='baja repetida')
    api('get', f'{CL}/{m1}', 404, nombre='get de inactivo (solo activos)')
    d = api('get', CL, 200, nombre='lista default'); chk('default no incluye al anulado', m1 not in {x['id_cliente'] for x in d['data']})
    d = api('get', f'{CL}?inactivos=1', 200, nombre='lista con inactivos'); f = [x for x in d['data'] if x['id_cliente'] == m1]
    chk('con inactivos incluye al anulado con activo=False', len(f) == 1 and f[0]['activo'] is False)

    # ---------- reactivación ----------
    d = api('post', CL, 201, {**base, 'nombre': 'zz otro con mismo ruc'}, 'reuso de la CI/RUC tras la baja'); m3 = d['data']['id_cliente']; clientes.add(m3)
    api('patch', f'{CL}/{m1}/reactivar', 409, nombre='REACTIVAR CON CI/RUC DUPLICADA', exacto='No se puede reactivar: ya existe un cliente activo con esa CI/RUC.')
    api('delete', f'{CL}/{m3}', 200, nombre='baja del que bloqueaba')
    api('patch', f'{CL}/{m1}/reactivar', 200, nombre='reactivar OK', contiene='reactivado')
    api('patch', f'{CL}/{m1}/reactivar', 409, nombre='reactivar uno ya activo', exacto='El cliente ya está activo.')
    api('patch', f'{CL}/999999/reactivar', 404, nombre='reactivar inexistente')
    api('patch', f'{CL}/{m3}/reactivar', 409, nombre='reactivar choca con el reactivado', contiene='ya existe un cliente activo con esa CI/RUC')
    # paciente duplicado al reactivar: se anula el cliente-paciente, se vuelve a registrar al paciente con otra CI/RUC
    api('delete', f'{CL}/{p1}', 200, nombre='baja del cliente-paciente')
    d = api('post', CL, 201, {'id_paciente': zp, 'nombre': 'zzlucía', 'apellido': 'zzpérez', 'ci_ruc': '9990099'}, 'el paciente se puede registrar de nuevo tras la baja'); p2 = d['data']['id_cliente']; clientes.add(p2)
    api('patch', f'{CL}/{p1}/reactivar', 409, nombre='REACTIVAR CON PACIENTE DUPLICADO', exacto='No se puede reactivar: ese paciente ya está registrado como otro cliente activo.')
    api('delete', f'{CL}/{p2}', 200, nombre='baja del reemplazo')
    api('patch', f'{CL}/{p1}/reactivar', 200, nombre='reactivar OK (ya sin duplicado)')
    # (reactivar con paciente inexistente no es construible: la FK impide borrar un paciente que es cliente)
    cu.execute("SELECT confdeltype FROM pg_constraint WHERE conrelid='cliente'::regclass AND contype='f'"); chk('FK cliente->paciente es RESTRICT', cu.fetchone()[0] == 'r')

    # ---------- el paciente-cliente no se puede eliminar (Agendamiento) ----------
    api('delete', f'/api/v1/pacientes/{zp}', 409, nombre='anular paciente que es cliente ACTIVO', contiene='registrado como cliente')
    cu.execute("UPDATE cliente SET activo=false WHERE id_paciente=%s", (zp,)); cx.commit()
    api('delete', f'/api/v1/pacientes/{zp}', 200, nombre='anular paciente cuyo cliente está INACTIVO (baja lógica)')
    cu.execute("SELECT count(*) FROM paciente WHERE id_paciente=%s", (zp,)); chk('el paciente sigue existiendo', cu.fetchone()[0] == 1)

    # ---------- auditoría ----------
    cu.execute("SELECT id_registro, accion, id_usuario, ip, detalle FROM auditoria_cambios WHERE entidad='cliente' AND id_registro = ANY(%s) ORDER BY id_auditoria_cambio", (list(clientes),))
    aud = cu.fetchall()
    de_m1 = [x for x in aud if x[0] == m1]; print('AUD m1', [(x[1], x[4][:70]) for x in de_m1])
    chk('auditoría m1: ALTA, MOD, BAJA, REACTIVACION (sin fila para "sin cambios")', [x[1] for x in de_m1] == ['ALTA', 'MODIFICACION', 'BAJA', 'REACTIVACION'])
    chk('ALTA registra si es paciente', de_m1[0][4].endswith('Paciente: No') and any(x[0] == p1 and x[4].endswith('Paciente: Sí') for x in aud))
    chk('MOD lista solo lo que cambió (opcionales vaciados sin "None")', 'Nombre: ZZ JUAN -> ZZ JUAN CARLOS' in de_m1[1][4] and 'None' not in de_m1[1][4] and 'CI/RUC' not in de_m1[1][4])
    chk('auditoría: usuario e IP de la sesión', all(x[2] == 1 and x[3] == '127.0.0.1' for x in aud))
    cu.execute("SELECT count(*) FROM auditoria_cambios WHERE entidad='cliente' AND id_registro=%s", (cf['id_cliente'],)); chk('los intentos bloqueados sobre SIN NOMBRE no auditan', cu.fetchone()[0] == 0)

    # ---------- permisos ----------
    cu.execute("SELECT id_rol FROM roles WHERE nombre_rol <> 'Administrador' LIMIT 1"); rol = cu.fetchone()[0]
    def sin_permiso(a):
        cu.execute("DELETE FROM permisos WHERE id_menu = (SELECT id_menu FROM menu WHERE clave='cliente' AND activo = true) AND id_rol=%s AND accion=%s", (rol, a)); cx.commit()
    def con_permiso(a):
        cu.execute("INSERT INTO permisos (id_rol, id_menu, accion) SELECT %s, id_menu, %s FROM menu WHERE clave='cliente' AND activo = true ON CONFLICT DO NOTHING", (rol, a)); cx.commit()
    with c.session_transaction() as s:
        s['id_rol'] = rol; s['nombre_rol'] = 'NoAdmin'
    try:
        chk('rol sin cambios entra a la vista', c.get('/referenciales/cliente/cliente-index').status_code == 200)
        api('get', f'{CL}/pacientes?q=9990', 200, nombre='rol con "nuevo" puede buscar pacientes')
        sin_permiso('nuevo')
        api('get', f'{CL}/pacientes?q=9990', 403, nombre='rol SIN "nuevo" no puede buscar pacientes (datos personales)')
        api('post', CL, 403, base, 'rol SIN "nuevo" no puede crear')
        con_permiso('nuevo')
        sin_permiso('editar')
        api('patch', f'{CL}/{m3}/reactivar', 403, nombre='rol SIN editar no puede reactivar (mismo permiso que editar)')
        api('put', f'{CL}/{m1}', 403, base, 'rol SIN editar no puede editar')
        con_permiso('editar')
        sin_permiso('ver')
        api('get', f'{CL}?inactivos=1', 403, nombre='?inactivos=1 sin permiso ver -> 403')
        api('get', CL, 200, nombre='lista de activos sigue disponible (lookup, solo login)')
    finally:
        for a in ('ver', 'nuevo', 'editar'):
            con_permiso(a)
    with c.session_transaction() as s:
        s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'
finally:
    # limpieza acotada a lo creado por este test
    borrar_auditoria(cu, 'cliente', list(clientes)); borrar_auditoria(cu, 'paciente', list(pacientes))
    cu.execute("DELETE FROM cliente WHERE id_cliente = ANY(%s) OR id_paciente = ANY(%s)", (list(clientes), list(pacientes)))
    cu.execute("DELETE FROM paciente WHERE id_paciente = ANY(%s)", (list(pacientes),))
    cx.commit(); cu.close(); cx.close()
print('FALLOS:', fallos or 'ninguno')
