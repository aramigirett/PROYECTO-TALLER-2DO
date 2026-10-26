"""Roles y Permisos como matriz por rol: selector de rol + "Guardar permisos", encabezado fijo, casillas de columna y de módulo, y PUT /api/v1/permisos/matriz/<rol> que
guarda la matriz COMPLETA en una transacción (altas y bajas, con auditoría, solo Administrador). Prueba clave: un rol existente (Médico) abierto y guardado SIN cambios
conserva exactamente sus permisos (mismas filas físicas, ninguna auditoría). Restaura siempre lo que toque; la auditoría que genera se borra POR ID."""
import pathlib, sys
RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from app import app
from tests._conexion_pruebas import Conexion

fallos = []
c = app.test_client()
URL = '/api/v1/permisos/matriz'


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


cx = Conexion().getConexion(); cx.autocommit = True; cu = cx.cursor()
cu.execute("SELECT COALESCE(MAX(id_auditoria_cambio), 0) FROM auditoria_cambios"); BASE = cu.fetchone()[0]
cu.execute("SELECT id_rol FROM roles WHERE nombre_rol = 'Medico'"); MEDICO = cu.fetchone()[0]
cu.execute("SELECT id_rol FROM roles WHERE nombre_rol = 'Administrador'"); ADMIN = cu.fetchone()[0]
cu.execute("SELECT id_rol FROM roles WHERE nombre_rol = 'Cajero'"); CAJERO = cu.fetchone()[0]


def filas(rol):
    cu.execute("SELECT id_rol, id_menu, accion, ctid::text FROM permisos WHERE id_rol = %s ORDER BY id_menu, accion", (rol,))
    return cu.fetchall()


def pares(rol):
    cu.execute("SELECT m.clave, p.accion FROM permisos p JOIN menu m USING (id_menu) WHERE p.id_rol = %s AND m.activo ORDER BY 1, 2", (rol,))
    return [(a, b) for a, b in cu.fetchall()]


def como(rol, nombre):
    with c.session_transaction() as s:
        s.clear()
        if rol:
            s['id_usuario'] = 1; s['id_rol'] = rol; s['nombre_rol'] = nombre


def put(rol, permisos):
    r = c.put(f'{URL}/{rol}', json={'permisos': [{'ventana': v, 'accion': a} for v, a in permisos]})
    return r, (r.get_json(silent=True) or {})


def auditorias():
    cu.execute("SELECT detalle, accion, entidad FROM auditoria_cambios WHERE id_auditoria_cambio > %s AND entidad = 'permisos' ORDER BY 1", (BASE,))
    return cu.fetchall()


ORIGINAL = filas(MEDICO)
ORIG_PARES = pares(MEDICO)
extra_ids = []
try:
    como(ADMIN, 'Administrador')

    print('== Pantalla')
    html = c.get('/referenciales/permiso/permiso-index').get_data(as_text=True)
    chk('selector de rol, botón Guardar permisos y matriz', all(x in html for x in ('id="selRol"', 'id="btnGuardar"', 'Guardar permisos', 'id="tblMatriz"')))
    chk('encabezado fijo (sticky) con casilla por columna; módulos con casilla para marcar todo', 'position: sticky' in html and 'marca-columna' in html and 'marca-modulo' in html and 'marca-modulo-columna' in html)
    chk('guarda con un solo PUT de la matriz completa (ya no un POST/DELETE por casilla)', "method: 'PUT'" in html and 'api/v1/permisos/matriz/${rolActual}' in html and "method: otorgar ? 'POST'" not in html)
    cat = c.get('/api/v1/permisos/catalogo').get_json()['data']
    acciones = {a for m in cat for v in m['ventanas'] for a in v['acciones']}
    chk('las columnas salen de las acciones reales del catálogo (ver, nuevo, editar, anular, estado, desbloquear...)', {'ver', 'nuevo', 'editar', 'anular'} <= acciones)

    print('\n== Abrir y guardar SIN cambios: el rol Médico conserva exactamente sus permisos')
    matriz = c.get(f'{URL}/{MEDICO}').get_json()['data']
    r, d = put(MEDICO, [(p['ventana'], p['accion']) for p in matriz])
    chk('PUT con la misma matriz -> 200, 0 otorgados y 0 revocados', r.status_code == 200 and d['data'] == {'otorgados': 0, 'revocados': 0} and 'no tenían cambios' in d['mensaje'])
    chk('las filas de permisos del Médico son EXACTAMENTE las mismas (también las físicas: ninguna se borró y volvió a crear)', filas(MEDICO) == ORIGINAL and len(ORIGINAL) > 0)
    chk('sin cambios no se audita nada', auditorias() == [])

    print('\n== Alta y baja en una sola transacción, con auditoría')
    disponibles = [(v['ventana'], a) for m in cat for v in m['ventanas'] for a in v['acciones'] if (v['ventana'], a) not in ORIG_PARES]
    nuevo = disponibles[0]
    r, d = put(MEDICO, ORIG_PARES + [nuevo])
    chk('marcar uno nuevo -> 1 otorgado', r.status_code == 200 and d['data'] == {'otorgados': 1, 'revocados': 0} and nuevo in pares(MEDICO))
    quitar = ORIG_PARES[0]
    r, d = put(MEDICO, [p for p in ORIG_PARES if p != quitar] + [nuevo])
    chk('desmarcar uno existente a la vez -> 1 revocado y el nuevo se conserva', r.status_code == 200 and d['data'] == {'otorgados': 0, 'revocados': 1} and quitar not in pares(MEDICO) and nuevo in pares(MEDICO))
    r, d = put(MEDICO, ORIG_PARES)
    chk('volver a la matriz original: 1 otorgado (el que se quitó) y 1 revocado (el nuevo)', r.status_code == 200 and d['data'] == {'otorgados': 1, 'revocados': 1} and pares(MEDICO) == ORIG_PARES)
    chk('los mismos permisos que al principio (por id_menu y acción)', [(f[0], f[1], f[2]) for f in filas(MEDICO)] == [(f[0], f[1], f[2]) for f in ORIGINAL])
    aud = auditorias()
    chk('cada otorgado / revocado quedó auditado (4) con el rol, la ventana y la acción por nombre', len(aud) == 4 and all(a[1] == 'MODIFICACION' and 'Medico' in a[0] for a in aud))

    print('\n== Validaciones (nada se guarda si algo es inválido)')
    antes = filas(MEDICO)
    r, d = put(MEDICO, ORIG_PARES + [('ventana_que_no_existe', 'ver')])
    chk('un permiso que no existe -> 400 y no cambia nada (todo o nada)', r.status_code == 400 and filas(MEDICO) == antes)
    r, d = put(MEDICO, ORIG_PARES + [('usuario', 'ver')])
    chk('una ventana exclusiva del Administrador no se puede delegar -> 400', r.status_code == 400 and filas(MEDICO) == antes)
    r, d = put(MEDICO, [])
    chk('matriz vacía quita solo lo delegable (y se puede volver atrás)', r.status_code == 200 and pares(MEDICO) == [])
    put(MEDICO, ORIG_PARES)
    chk('...y restaurada queda igual', pares(MEDICO) == ORIG_PARES)
    chk('cuerpo inválido -> 400', c.put(f'{URL}/{MEDICO}', json={'permisos': 'x'}).status_code == 400 and c.put(f'{URL}/{MEDICO}', json={'permisos': [{'ventana': 1}]}).status_code == 400
        and c.put(f'{URL}/{MEDICO}', data='no json', content_type='text/plain').status_code == 400)
    chk('el Administrador no se edita -> 400', put(ADMIN, [])[0].status_code == 400)
    chk('un rol que no existe -> 400', put(999999, [])[0].status_code == 400)
    cu.execute("""INSERT INTO permisos (id_rol, id_menu, accion) SELECT %s, id_menu, 'ver' FROM menu WHERE clave = 'usuario' AND activo ON CONFLICT DO NOTHING RETURNING id_menu""", (MEDICO,))
    fuera = cu.fetchall()
    r, d = put(MEDICO, ORIG_PARES)
    cu.execute("SELECT count(*) FROM permisos p JOIN menu m USING (id_menu) WHERE p.id_rol = %s AND m.clave = 'usuario'", (MEDICO,))
    chk('lo que el rol tiene FUERA del alcance de la matriz (ventana solo Administrador) no se toca al guardar', r.status_code == 200 and cu.fetchone()[0] == (1 if fuera else 0))

    print('\n== Acceso')
    como(CAJERO, 'Cajero')
    chk('Cajero -> 403', put(MEDICO, ORIG_PARES)[0].status_code == 403)
    como(None, None)
    chk('sin sesión -> 401', put(MEDICO, ORIG_PARES)[0].status_code == 401)

finally:
    # Restaura EXACTAMENTE los permisos del Médico y borra la auditoría de prueba por ID.
    cu.execute("DELETE FROM permisos WHERE id_rol = %s AND (id_menu, accion) NOT IN (SELECT id_menu, accion FROM unnest(%s::int[], %s::text[]) AS t(id_menu, accion))",
               (MEDICO, [f[1] for f in ORIGINAL], [f[2] for f in ORIGINAL]))
    for _, id_menu, accion, _ in ORIGINAL:
        cu.execute("INSERT INTO permisos (id_rol, id_menu, accion) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", (MEDICO, id_menu, accion))
    cu.execute("SELECT id_auditoria_cambio FROM auditoria_cambios WHERE id_auditoria_cambio > %s AND id_usuario = 1 AND ip = '127.0.0.1'", (BASE,))
    ids = [x[0] for x in cu.fetchall()]
    cu.execute("SET session_replication_role = replica")
    cu.execute("DELETE FROM auditoria_cambios WHERE id_auditoria_cambio = ANY(%s)", (ids,))
    cu.execute("RESET session_replication_role")
    print(f'(limpieza: permisos del Médico restaurados y {len(ids)} filas de auditoría borradas por ID)')
    cu.close(); cx.close()

print('FALLOS:', 'ninguno' if not fallos else fallos)
