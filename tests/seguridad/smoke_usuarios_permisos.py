"""Etapa 3: Gestión de Usuarios y Roles y Permisos (vistas Tabler, auditoría estructurada y salvaguardas).

Usuarios: alta / modificación / baja / reactivación / desbloqueo auditados (módulo Seguridad, persona, CI/RUC y rol; NUNCA la contraseña), solo se vincula a personas
activas, no se anula el propio usuario ni el único Administrador activo. Roles y Permisos: otorgar y revocar quedan auditados (rol · ventana · acción), un cambio que no
cambia nada no audita, y se rechazan roles, ventanas y acciones inexistentes, el Administrador y las ventanas exclusivas del Administrador.
Datos `ZZ`: se borran por ID, junto con su auditoría; el permiso de prueba se restaura.
"""
import atexit
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


def api(metodo, url, esperado, json=None, nombre=None, contiene=None):
    f = getattr(c, metodo)
    r = f(url, json=json) if json is not None else f(url)
    d = r.get_json(silent=True) or {}
    ok = r.status_code == esperado
    if contiene is not None:
        ok = ok and contiene in (d.get('error') or d.get('mensaje') or '')
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


ADMIN, RECEP = usuario_de('Administrador'), usuario_de('Recepcion')
ROL = {n: i for i, n in q("SELECT id_rol, nombre_rol FROM roles")}
SUF = datetime.datetime.now().strftime('%H%M%S')
mayor_aud = q("SELECT COALESCE(MAX(id_auditoria_cambio), 0) FROM auditoria_cambios")[0][0]
usuarios_creados = set()
_limpio = []


def limpieza():
    if _limpio:
        return
    _limpio.append(1)
    try:
        cx.rollback()
        # permiso de prueba: se restaura
        cu.execute("DELETE FROM permisos WHERE id_rol=%s AND accion='ver' AND id_menu=(SELECT id_menu FROM menu WHERE clave='ciudad' AND activo)", (ROL['Cajero'],))
        # auditoría de lo que generó el test (usuarios ZZ y el permiso de prueba)
        cu.execute("SET session_replication_role = replica")
        cu.execute("DELETE FROM auditoria_cambios WHERE id_auditoria_cambio > %s AND (entidad='usuarios' AND id_registro = ANY(%s) OR (entidad='permisos' AND detalle LIKE %s))",
                   (mayor_aud, list(usuarios_creados), 'Cajero · Ciudad ·%'))
        cu.execute("DELETE FROM auditoria_acceso WHERE id_usuario = ANY(%s) OR id_usuario_actor = ANY(%s)", (list(usuarios_creados), list(usuarios_creados)))
        cu.execute("RESET session_replication_role")
        cu.execute("DELETE FROM usuarios WHERE id_usuario = ANY(%s)", (list(usuarios_creados),))
        cx.commit()
        fx.limpiar()
    except Exception as e:
        cx.rollback()
        print('ERROR en la limpieza:', e)
        fallos.append('limpieza')


atexit.register(limpieza)


def persona(correo=True, activo=True):
    return fx._insertar('funcionario', 'id_funcionario',
                        "INSERT INTO funcionario(nombre, apellido, cedula, id_cargo, correo, activo) VALUES (%s,'PRUEBA',%s,%s,%s,%s)",
                        (f'ZZ USUARIO {len(fx._borrar)}', f'9{SUF}{len(fx._borrar)}'[:10], fx.id_cargo, f'zzu{SUF}{len(fx._borrar)}@test.invalid' if correo else None, activo))


def ultima(i, accion):
    cu.execute("SELECT modulo, detalle, valores_anteriores, valores_nuevos, id_usuario FROM auditoria_cambios WHERE entidad='usuarios' AND id_registro=%s AND accion=%s "
               "ORDER BY id_auditoria_cambio DESC LIMIT 1", (i, accion))
    return cu.fetchone()


US = '/api/v1/usuarios'
PASS = 'Zz123456!x'
print('== Usuarios')
sesion(ADMIN)
chk('vista de Usuarios en Tabler', b'tabler' in c.get('/referenciales/usuario/usuario-index').data.lower() and b'btnAgregar' in c.get('/referenciales/usuario/usuario-index').data)
f1, f_sin_correo, f_anulado = persona(), persona(correo=False), persona(activo=False)
api('post', US, 400, {'password': PASS, 'id_rol': ROL['Recepcion']}, 'persona obligatoria')
api('post', US, 400, {'password': 'abc', 'id_rol': ROL['Recepcion'], 'id_funcionario': f1}, 'contraseña débil')
api('post', US, 400, {'password': PASS, 'id_rol': ROL['Recepcion'], 'id_funcionario': f_sin_correo}, 'persona sin correo', contiene='correo')
api('post', US, 400, {'password': PASS, 'id_rol': ROL['Recepcion'], 'id_funcionario': f_anulado}, 'persona anulada', contiene='anulad')
d = api('post', US, 201, {'password': PASS, 'id_rol': ROL['Recepcion'], 'id_funcionario': f1}, 'alta de un usuario')
u1 = d['data']['id_usuario']; usuarios_creados.add(u1)
a = ultima(u1, 'ALTA')
texto = str(a)
chk('auditoría ALTA: módulo Seguridad, usuario, persona, CI/RUC y rol; sin contraseña ni hash', bool(a) and a[0] == 'Módulo Seguridad' and a[4] == ADMIN and 'ZZ USUARIO' in texto and 'Recepcion' in texto
    and PASS not in texto and 'scrypt' not in texto and 'pbkdf2' not in texto)
api('post', US, 400, {'password': PASS, 'id_rol': ROL['Recepcion'], 'id_funcionario': f1}, 'la persona ya tiene usuario', contiene='ya tiene un usuario')
antes = q("SELECT COUNT(*) FROM auditoria_cambios WHERE entidad='usuarios' AND id_registro=%s", (u1,))[0][0]
api('put', f'{US}/{u1}', 200, {'id_rol': ROL['Recepcion'], 'id_funcionario': f1}, 'edición sin cambios')
chk('...no audita', q("SELECT COUNT(*) FROM auditoria_cambios WHERE entidad='usuarios' AND id_registro=%s", (u1,))[0][0] == antes)
api('put', f'{US}/{u1}', 200, {'id_rol': ROL['Cajero'], 'id_funcionario': f1, 'password': PASS + 'y'}, 'cambio de rol y de contraseña')
m = ultima(u1, 'MODIFICACION'); texto = str(m)
chk('auditoría MODIFICACION: rol anterior y nuevo y "Contraseña: modificada", sin la contraseña', 'Recepcion' in str(m[2]) and 'Cajero' in str(m[3]) and 'modificada' in str(m[3]) and PASS not in texto)
api('delete', f'{US}/{u1}', 200, None, 'baja del usuario')
chk('BAJA auditada', bool(ultima(u1, 'BAJA')))
cu.execute("UPDATE funcionario SET activo=false WHERE id_funcionario=%s", (f1,)); cx.commit()
api('patch', f'{US}/{u1}/reactivar', 409, None, 'no se reactiva si su persona está anulada', contiene='anulado')
cu.execute("UPDATE funcionario SET activo=true WHERE id_funcionario=%s", (f1,)); cx.commit()
api('patch', f'{US}/{u1}/reactivar', 200, None, 'reactivación')
chk('REACTIVACION auditada', bool(ultima(u1, 'REACTIVACION')))
cu.execute("UPDATE usuarios SET bloqueado=true, intentos_fallidos=3, fecha_bloqueo=NOW() WHERE id_usuario=%s", (u1,)); cx.commit()
api('patch', f'{US}/{u1}/desbloquear', 200, None, 'desbloqueo')
chk('el desbloqueo queda auditado en el módulo Seguridad', 'desbloqueada' in str(ultima(u1, 'MODIFICACION')[3]))
api('delete', f'{US}/{ADMIN}', 409, None, 'no se anula el propio usuario', contiene='propio usuario')
# único administrador activo
admin2 = fx._insertar('usuarios', 'id_usuario', "INSERT INTO usuarios(password_hash, id_rol, id_funcionario, activo) VALUES (%s,%s,%s,true)", ('x', ROL['Administrador'], persona()))
usuarios_creados.add(admin2)
from app.dao.modulo_seguridad.UsuarioDao import UsuarioDao
sesion(ADMIN)
chk('hay 2 administradores activos (el real y el de prueba)', UsuarioDao.contarAdministradoresActivos(UsuarioDao()) == 2)
original = UsuarioDao.contarAdministradoresActivos
UsuarioDao.contarAdministradoresActivos = lambda self: 1
try:
    api('delete', f'{US}/{admin2}', 409, None, 'no se anula al único Administrador activo', contiene='único Administrador')
finally:
    UsuarioDao.contarAdministradoresActivos = original
api('delete', f'{US}/{admin2}', 200, None, 'con otro administrador activo sí se puede anular')
sesion(RECEP)
api('get', US, 403, None, 'Recepción no ve usuarios')
chk('Recepción no abre la vista de Usuarios', c.get('/referenciales/usuario/usuario-index').status_code == 403)
sesion(ADMIN)

print('\n== Roles y Permisos')
chk('vista de Roles y Permisos en Tabler', b'tabler' in c.get('/referenciales/permiso/permiso-index').data.lower())
PM = '/api/v1/permisos/matriz'
cuerpo = lambda **x: {'id_rol': ROL['Cajero'], 'ventana': 'ciudad', 'accion': 'ver', **x}
api('post', PM, 400, cuerpo(id_rol=99999), 'rol inexistente')
api('post', PM, 400, cuerpo(id_rol=ROL['Administrador']), 'el Administrador no se edita', contiene='Administrador')
api('post', PM, 400, cuerpo(ventana='noexiste'), 'ventana inexistente')
api('post', PM, 400, cuerpo(accion='desbloquear'), 'acción que la ventana no tiene', contiene='no tiene la acción')
api('post', PM, 400, cuerpo(ventana='backup'), 'ventana exclusiva del Administrador')
chk('el Cajero arranca sin permiso sobre Ciudad', ('ciudad', 'ver') not in {(m, a) for m, a in [(r[0], r[1]) for r in q("SELECT m.clave, p.accion FROM permisos p JOIN menu m USING(id_menu) WHERE p.id_rol=%s", (ROL['Cajero'],))]})
api('post', PM, 201, cuerpo(), 'otorga ver sobre Ciudad al Cajero')
a = q("SELECT modulo, detalle, valores_anteriores, valores_nuevos, id_usuario FROM auditoria_cambios WHERE entidad='permisos' AND id_auditoria_cambio > %s AND detalle LIKE %s ORDER BY id_auditoria_cambio DESC LIMIT 1",
      (mayor_aud, 'Cajero · Ciudad ·%'))
chk('auditado: módulo Seguridad, usuario, y "Cajero · Ciudad · ver: No -> Sí" (nombres, no IDs)', bool(a) and a[0][0] == 'Módulo Seguridad' and a[0][4] == ADMIN and 'No' in str(a[0][2]) and 'Sí' in str(a[0][3]))
n = q("SELECT COUNT(*) FROM auditoria_cambios WHERE entidad='permisos' AND id_auditoria_cambio > %s", (mayor_aud,))[0][0]
api('post', PM, 201, cuerpo(), 'otorgarlo otra vez')
chk('...no genera una auditoría nueva', q("SELECT COUNT(*) FROM auditoria_cambios WHERE entidad='permisos' AND id_auditoria_cambio > %s", (mayor_aud,))[0][0] == n)
sesion(usuario_de('Cajero'))
chk('el permiso se aplica al toque: el Cajero ve Ciudad', c.get('/api/v1/ciudades?inactivos=1').status_code == 200)
sesion(ADMIN)
api('delete', PM, 200, cuerpo(), 'revoca el permiso')
chk('...auditado "Sí -> No"', 'No' in str(q("SELECT valores_nuevos FROM auditoria_cambios WHERE entidad='permisos' AND id_auditoria_cambio > %s AND detalle LIKE %s ORDER BY id_auditoria_cambio DESC LIMIT 1", (mayor_aud, 'Cajero · Ciudad ·%'))))
sesion(usuario_de('Cajero'))
chk('...y el Cajero ya no lo tiene', c.get('/api/v1/ciudades?inactivos=1').status_code == 403)
for metodo in ('post', 'delete'):
    api(metodo, PM, 403, cuerpo(), f'solo el Administrador edita la matriz ({metodo})')
chk('el Cajero no abre Roles y Permisos', c.get('/referenciales/permiso/permiso-index').status_code == 403)
sesion(ADMIN)

limpieza()
sobras = q("SELECT (SELECT COUNT(*) FROM usuarios WHERE id_usuario = ANY(%s)) + (SELECT COUNT(*) FROM funcionario WHERE nombre LIKE 'ZZ%%')", (list(usuarios_creados),))[0][0]
chk('limpieza: no quedan datos ZZ', sobras == 0)
chk('el permiso de prueba quedó restaurado (el Cajero sin Ciudad)', q("SELECT COUNT(*) FROM permisos p JOIN menu m USING(id_menu) WHERE p.id_rol=%s AND m.clave='ciudad'", (ROL['Cajero'],))[0][0] == 0)
print('\nFALLOS:', 'ninguno' if not fallos else fallos)
