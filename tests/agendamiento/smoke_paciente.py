"""Regresión de Paciente (Agendamiento): alta, modificación, baja LÓGICA bloqueada por cliente activo (paciente -> cliente de Facturación),
reactivación, el alta de un cliente sobre un paciente anulado y el rol sin 'anular'. El detalle de la etapa 2 está en smoke_personas_agendamiento."""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from app import app
from tests._conexion_pruebas import Conexion
from tests.facturacion._limpieza import borrar_auditoria

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
cu.execute("SELECT id_ciudad FROM ciudades WHERE activo ORDER BY 1 LIMIT 1"); CIUDAD = cu.fetchone()[0]
cu.execute("SELECT id_paciente, nombre, apellido, cedula_entidad, telefono, correo, activo FROM paciente WHERE nombre NOT LIKE 'ZZ%' ORDER BY id_paciente")
antes = cu.fetchall()

def cuerpo(cedula, correo):
    return {'nombre': 'ZZ Regresion', 'apellido': 'ZZ Prueba', 'cedula_entidad': cedula, 'fecha_nacimiento': '1990-01-01',
            'telefono': '0981000222', 'telefono_emergencia': '0981000333', 'direccion': 'Calle de prueba 1',
            'correo': correo, 'id_ciudad': CIUDAD}

try:
    api('post', PA, 401, cuerpo('9980001', 'zz.a@test.invalid'), 'sin sesion')
    with c.session_transaction() as s:
        s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

    d = api('get', PA, 200, nombre='lista')
    chk('lista trae los pacientes existentes (activos)', {a[0] for a in antes if a[6]} <= {x['id_paciente'] for x in d['data']})
    r = c.get('/referenciales/paciente/paciente-index'); chk('vista de paciente carga (Tabler)', r.status_code == 200 and b'tabler' in r.data.lower())

    d = api('post', PA, 201, cuerpo('9980001', 'zz.a@test.invalid'), 'alta')
    p1 = d['data']['id_paciente']; pacientes.add(p1)
    api('post', PA, 409, cuerpo('9980001', 'zz.otro@test.invalid'), 'alta duplicada (cédula)')
    api('post', PA, 400, {**cuerpo('9980009', 'zz.z@test.invalid'), 'nombre': ''}, 'alta sin nombre')
    api('get', f'{PA}/{p1}', 200, nombre='get')
    api('get', f'{PA}/999999', 404, nombre='get inexistente')
    api('put', f'{PA}/{p1}', 200, {**cuerpo('9980001', 'zz.a@test.invalid'), 'direccion': 'Otra calle 2'}, 'modificación')

    # ---- baja lógica ----
    api('delete', f'{PA}/999999', 404, nombre='anular inexistente (404)')
    d = api('post', PA, 201, cuerpo('9980002', 'zz.b@test.invalid'), 'segundo paciente'); p2 = d['data']['id_paciente']; pacientes.add(p2)
    api('delete', f'{PA}/{p2}', 200, nombre='anular un paciente que NO es cliente -> 200', contiene='anulado')
    cu.execute("SELECT activo FROM paciente WHERE id_paciente=%s", (p2,)); chk('queda inactivo, no se borra', cu.fetchone() == (False,))
    api('post', PA, 201, cuerpo('9980002', 'zz.c@test.invalid'), 'se puede registrar de nuevo la cédula de un paciente anulado')
    cu.execute("SELECT id_paciente FROM paciente WHERE cedula_entidad='9980002' AND activo"); pacientes.add(cu.fetchone()[0])
    api('patch', f'{PA}/{p2}/reactivar', 409, nombre='no se reactiva si ya hay otro activo con esa cédula', contiene='ya existe')

    cu.execute("INSERT INTO cliente(id_paciente, nombre, ci_ruc) VALUES (%s,'ZZ CLIENTE','9980001') RETURNING id_cliente", (p1,)); clientes.add(cu.fetchone()[0]); cx.commit()
    api('delete', f'{PA}/{p1}', 409, nombre='anular un paciente que es cliente ACTIVO -> 409', contiene='registrado como cliente')
    cu.execute("SELECT activo FROM paciente WHERE id_paciente=%s", (p1,)); chk('NO se anuló', cu.fetchone() == (True,))
    cu.execute("UPDATE cliente SET activo=false WHERE id_paciente=%s", (p1,)); cx.commit()
    api('delete', f'{PA}/{p1}', 200, nombre='con el cliente INACTIVO se puede anular')
    cu.execute("SELECT 1 FROM paciente WHERE id_paciente=%s", (p1,)); chk('sigue existiendo (baja lógica)', cu.fetchone() is not None)
    if antes:
        api('delete', f'{PA}/{antes[0][0]}', 409, nombre='paciente real que es cliente: protegido', contiene='registrado como cliente')

    # rol sin 'anular' -> 403 (el decorador sigue funcionando)
    cu.execute("SELECT id_rol FROM roles WHERE nombre_rol <> 'Administrador' LIMIT 1"); rol = cu.fetchone()[0]
    with c.session_transaction() as s:
        s['id_rol'] = rol; s['nombre_rol'] = 'NoAdmin'
    api('delete', f'{PA}/999999', 403, nombre='rol sin anular -> 403')
finally:
    cx.rollback()
    cu.execute("DELETE FROM cliente WHERE id_paciente = ANY(%s)", (list(pacientes),))
    cu.execute("DELETE FROM paciente WHERE id_paciente = ANY(%s)", (list(pacientes),))
    borrar_auditoria(cu, 'paciente', list(pacientes))
    cx.commit()
    cu.execute("SELECT id_paciente, nombre, apellido, cedula_entidad, telefono, correo, activo FROM paciente WHERE nombre NOT LIKE 'ZZ%' ORDER BY id_paciente")
    chk('pacientes reales idénticos antes y después', antes == cu.fetchall())
    cu.close(); cx.close()
print('FALLOS:', fallos or 'ninguno')
