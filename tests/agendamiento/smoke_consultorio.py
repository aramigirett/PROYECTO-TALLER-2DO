"""Regresión de Consultorio (Agendamiento) tras el cambio de estaEnUso / motivoEnUso y del DELETE de la API.
NO había un test previo de Consultorio en el proyecto: este se escribió para esta verificación."""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from app import app
from tests._conexion_pruebas import Conexion
from tests.facturacion._limpieza import borrar_auditoria

c = app.test_client()
fallos = []
creados = set()

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

CO = '/api/v1/consultorios'
cx = Conexion().getConexion(); cu = cx.cursor()
cu.execute("SELECT codigo, nombre_consultorio, direccion, telefono, correo FROM consultorio ORDER BY codigo")
antes = cu.fetchall()

try:
    api('get', CO, 401, nombre='sin sesion')
    with c.session_transaction() as s:
        s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

    d = api('get', CO, 200, nombre='lista')
    chk('lista trae los consultorios existentes', {r[0] for r in antes} <= {x['codigo'] for x in d['data']})
    r = c.get('/referenciales/consultorio/consultorio-index'); chk('vista de consultorio carga', r.status_code in (200,))

    base = {'nombre_consultorio': 'ZZ Consultorio Regresion', 'direccion': 'Calle de prueba 123',
            'telefono': '0981000111', 'correo': 'zz.regresion@test.invalid'}
    d = api('post', CO, 201, base, 'alta')
    k1 = d['data']['codigo']; creados.add(k1)
    chk('teléfono normalizado a 595…', d['data']['telefono'] == '595981000111')
    api('post', CO, 400, base, 'alta duplicada (nombre/correo)')
    api('post', CO, 400, {**base, 'nombre_consultorio': 'ZZ Otro', 'correo': 'x'}, 'alta con correo inválido')
    api('post', CO, 400, {**base, 'nombre_consultorio': 'ZZ Otro', 'correo': 'zz.otro@test.invalid', 'telefono': '123'}, 'alta con teléfono inválido')
    api('get', f'{CO}/{k1}', 200, nombre='get')
    api('put', f'{CO}/{k1}', 200, {**base, 'direccion': 'Calle de prueba 456'}, 'modificación')
    api('get', f'{CO}/999999', 404, nombre='get inexistente')

    # ---- DELETE: los 4 resultados posibles ----
    api('delete', f'{CO}/999999', 404, nombre='delete inexistente (404)')

    cu.execute("INSERT INTO caja(id_consultorio, descripcion) VALUES (%s,'ZZ CAJA REGRESION') RETURNING id_caja", (k1,)); cx.commit()
    api('delete', f'{CO}/{k1}', 409, nombre='delete con caja activa -> 409', contiene='No se puede anular, el consultorio tiene 1 caja(s) activa(s)')
    cu.execute("SELECT activo FROM consultorio WHERE codigo=%s", (k1,)); chk('sigue activo', cu.fetchone()[0] is True)

    # baja lógica: una caja anulada ya no impide anular el consultorio
    cu.execute("UPDATE caja SET activo=false WHERE id_consultorio=%s", (k1,)); cx.commit()
    api('delete', f'{CO}/{k1}', 200, nombre='delete con caja inactiva -> 200 (anulado)', contiene='anulado')
    cu.execute("SELECT activo FROM consultorio WHERE codigo=%s", (k1,)); chk('queda inactivo, no se borra', cu.fetchone() == (False,))
    api('delete', f'{CO}/{k1}', 404, nombre='anular uno ya anulado -> 404')

    # rol sin 'anular' -> 403 (el decorador sigue funcionando)
    cu.execute("SELECT id_rol FROM roles WHERE nombre_rol <> 'Administrador' LIMIT 1"); rol = cu.fetchone()[0]
    cu.execute("SELECT count(*) FROM permisos WHERE id_menu = (SELECT id_menu FROM menu WHERE clave='consultorio' AND activo = true) AND id_rol=%s AND accion='anular'", (rol,)); tenia = cu.fetchone()[0]
    cu.execute("DELETE FROM permisos WHERE id_menu = (SELECT id_menu FROM menu WHERE clave='consultorio' AND activo = true) AND id_rol=%s AND accion='anular'", (rol,)); cx.commit()
    try:
        with c.session_transaction() as s:
            s['id_rol'] = rol; s['nombre_rol'] = 'NoAdmin'
        api('delete', f'{CO}/999999', 403, nombre='rol sin anular -> 403')
    finally:
        if tenia:
            cu.execute("INSERT INTO permisos (id_rol, id_menu, accion) SELECT %s, id_menu, 'anular' FROM menu WHERE clave='consultorio' AND activo = true ON CONFLICT DO NOTHING", (rol,)); cx.commit()

    # esta_en_uso de un consultorio inexistente -> sin motivo
    with app.app_context():
        from app.dao.referenciales_agendamiento.consultorio.ConsultorioDao import ConsultorioDao
        chk('esta_en_uso de un consultorio inexistente -> False', ConsultorioDao().esta_en_uso(999999) is False)
finally:
    cu.execute("DELETE FROM caja WHERE id_consultorio = ANY(%s)", (list(creados),))
    cu.execute("DELETE FROM consultorio WHERE codigo = ANY(%s)", (list(creados),))
    borrar_auditoria(cu, 'consultorio', list(creados))
    cx.commit()
    cu.execute("SELECT codigo, nombre_consultorio, direccion, telefono, correo FROM consultorio ORDER BY codigo")
    despues = cu.fetchall()
    chk('consultorios reales idénticos antes y después', antes == despues)
    cu.close(); cx.close()
print('FALLOS:', fallos or 'ninguno')
