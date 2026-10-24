"""Regresión de Paciente (Agendamiento) tras el cambio de deletePaciente / paciente_api.
NO había un test previo de Paciente en el proyecto: este se escribió para esta verificación."""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from app import app
from app.conexion.Conexion import Conexion

c = app.test_client()
fallos = []
pacientes = set(); clientes = set()

def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)

def api(metodo, url, esperado, json=None, nombre=None, exacto=None, contiene=None):
    f = getattr(c, metodo)
    r = f(url, json=json) if json is not None else f(url)
    d = r.get_json(silent=True) or {}
    ok = r.status_code == esperado
    texto = d.get('error') or d.get('mensaje') or ''
    if exacto is not None:
        ok = ok and texto == exacto
    if contiene is not None:
        ok = ok and contiene in texto
    chk(f"{nombre or metodo + ' ' + url} -> {r.status_code}" + ('' if ok else f' {d}'), ok)
    return d

PA = '/api/v1/pacientes'
cx = Conexion().getConexion(); cu = cx.cursor()
cu.execute("SELECT id_ciudad FROM ciudades ORDER BY 1 LIMIT 1"); CIUDAD = cu.fetchone()[0]
cu.execute("SELECT id_paciente, nombre, apellido, cedula_entidad, telefono, correo FROM paciente ORDER BY id_paciente")
antes = cu.fetchall()
MSG = 'No se puede eliminar, el paciente está registrado como cliente.'

def cuerpo(cedula, correo):
    return {'nombre': 'ZZ Regresion', 'apellido': 'ZZ Prueba', 'cedula_entidad': cedula, 'fecha_nacimiento': '1990-01-01',
            'telefono': '0981000222', 'telefono_emergencia': '0981000333', 'direccion': 'Calle de prueba 1',
            'correo': correo, 'id_ciudad': CIUDAD, 'fecha_registro': '2026-01-01'}

try:
    api('post', PA, 401, cuerpo('9980001', 'zz.a@test.invalid'), 'sin sesion')
    with c.session_transaction() as s:
        s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

    d = api('get', PA, 200, nombre='lista')
    chk('lista trae los pacientes existentes', {a[0] for a in antes} <= {x['id_paciente'] for x in d['data']})
    r = c.get('/referenciales/paciente/paciente-index'); chk('vista de paciente carga', r.status_code == 200)

    d = api('post', PA, 201, cuerpo('9980001', 'zz.a@test.invalid'), 'alta')
    p1 = d['data']['id_paciente']; pacientes.add(p1)
    api('post', PA, 409, cuerpo('9980001', 'zz.otro@test.invalid'), 'alta duplicada (cédula)')
    api('post', PA, 400, {**cuerpo('9980009', 'zz.z@test.invalid'), 'nombre': ''}, 'alta sin nombre')
    api('get', f'{PA}/{p1}', 200, nombre='get')
    api('get', f'{PA}/999999', 404, nombre='get inexistente')
    api('put', f'{PA}/{p1}', 200, {**cuerpo('9980001', 'zz.a@test.invalid'), 'direccion': 'Otra calle 2'}, 'modificación')

    # ---- DELETE ----
    api('delete', f'{PA}/999999', 404, nombre='delete inexistente (404)')
    d = api('post', PA, 201, cuerpo('9980002', 'zz.b@test.invalid'), 'segundo paciente'); p2 = d['data']['id_paciente']; pacientes.add(p2)
    api('delete', f'{PA}/{p2}', 200, nombre='delete de un paciente que NO es cliente -> 200', contiene='eliminado')
    cu.execute("SELECT count(*) FROM paciente WHERE id_paciente=%s", (p2,)); chk('SÍ se borró', cu.fetchone()[0] == 0)

    cu.execute("INSERT INTO cliente(id_paciente, nombre, ci_ruc) VALUES (%s,'ZZ CLIENTE','9980001') RETURNING id_cliente", (p1,)); clientes.add(cu.fetchone()[0]); cx.commit()
    api('delete', f'{PA}/{p1}', 409, nombre='delete de un paciente que es cliente ACTIVO -> 409', exacto=MSG)
    cu.execute("SELECT count(*) FROM paciente WHERE id_paciente=%s", (p1,)); chk('NO se borró', cu.fetchone()[0] == 1)
    cu.execute("UPDATE cliente SET activo=false WHERE id_paciente=%s", (p1,)); cx.commit()
    api('delete', f'{PA}/{p1}', 409, nombre='delete con cliente INACTIVO -> 409 (FK física)', exacto=MSG)
    if antes:
        api('delete', f'{PA}/{antes[0][0]}', 409, nombre='paciente real que es cliente: protegido', exacto=MSG)

    cu.execute("DELETE FROM cliente WHERE id_paciente=%s", (p1,)); cx.commit(); clientes.clear()
    api('delete', f'{PA}/{p1}', 200, nombre='sin cliente => se puede eliminar')

    # rol sin 'anular' -> 403 (el decorador sigue funcionando)
    cu.execute("SELECT id_rol FROM roles WHERE nombre_rol <> 'Administrador' LIMIT 1"); rol = cu.fetchone()[0]
    cu.execute("SELECT count(*) FROM permisos WHERE ventana='paciente' AND id_rol=%s AND accion='anular'", (rol,)); tenia = cu.fetchone()[0]
    cu.execute("DELETE FROM permisos WHERE ventana='paciente' AND id_rol=%s AND accion='anular'", (rol,)); cx.commit()
    try:
        with c.session_transaction() as s:
            s['id_rol'] = rol; s['nombre_rol'] = 'NoAdmin'
        api('delete', f'{PA}/999999', 403, nombre='rol sin anular -> 403')
    finally:
        if tenia:
            cu.execute("INSERT INTO permisos (id_rol, ventana, accion) VALUES (%s,'paciente','anular') ON CONFLICT DO NOTHING", (rol,)); cx.commit()
finally:
    cu.execute("DELETE FROM cliente WHERE id_paciente = ANY(%s)", (list(pacientes),))
    cu.execute("DELETE FROM paciente WHERE id_paciente = ANY(%s)", (list(pacientes),))
    cx.commit()
    cu.execute("SELECT id_paciente, nombre, apellido, cedula_entidad, telefono, correo FROM paciente ORDER BY id_paciente")
    chk('pacientes reales idénticos antes y después', antes == cu.fetchall())
    cu.close(); cx.close()
print('FALLOS:', fallos or 'ninguno')
