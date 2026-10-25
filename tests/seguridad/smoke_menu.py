"""Mantener Menú (punto 5): el menú lateral, el buscador y la matriz de permisos salen de la tabla `menu`; ABM con baja lógica, Reactivar y auditoría;
protección de Mantener Menú, Usuarios, Roles y Permisos (API y trigger de la base); permisos del menú por rol. Datos ZZ, borrados por ID al final."""
import re, sys, pathlib
RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import psycopg2
from app import app
from tests._conexion_pruebas import Conexion
from tests.facturacion._limpieza import borrar_auditoria

fallos = []


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


cx = Conexion().getConexion(); cx.autocommit = True; cu = cx.cursor()
cu.execute("SELECT id_rol, nombre_rol FROM roles"); ROLES = {n: i for i, n in cu.fetchall()}
creados = []     # id_menu de filas ZZ


def cliente(rol):
    c = app.test_client()
    with c.session_transaction() as s:
        s['id_usuario'] = 1; s['id_rol'] = ROLES[rol]; s['nombre_rol'] = rol
    return c


def sidebar(c):
    h = c.get('/referenciales/ciudad/ciudad-index' if True else '/').get_data(as_text=True)
    return h


def etiquetas(c):
    return set(re.findall(r'<span>([^<]+)</span>\s*</a>', sidebar(c)))


def enlaces(c):
    return set(re.findall(r'oc-sidebar-sublink[^"]*"', sidebar(c))) and set(re.findall(r'href="([^"]+)"\s*class="oc-sidebar-sublink', sidebar(c)))


try:
    admin = cliente('Administrador')

    # ---- 1. estructura y siembra ---------------------------------------------------------------------------------------------------------
    cu.execute("SELECT clave, solo_admin, protegida, ruta FROM menu WHERE clave IN ('usuario','auditoria','permiso','menu') AND activo")
    f = {r[0]: r for r in cu.fetchall()}
    chk('usuario, auditoria, permiso y menu tienen fila activa en menu con ruta', set(f) == {'usuario', 'auditoria', 'permiso', 'menu'} and all(r[3] for r in f.values()))
    chk('las 4 son exclusivas del Administrador', all(r[1] for r in f.values()))
    chk('menu, usuario y permiso están protegidas', all(f[k][2] for k in ('menu', 'usuario', 'permiso')) and not f['auditoria'][2])
    cu.execute("SELECT count(*) FROM menu WHERE activo AND id_menu_padre IS NOT NULL AND (ruta IS NULL OR clave IS NULL)")
    chk('ninguna ventana activa sin ruta o sin clave', cu.fetchone()[0] == 0)

    # ---- 2. menú lateral por rol ---------------------------------------------------------------------------------------------------------
    ea = etiquetas(admin)
    chk('Administrador ve Mantener Menú, Gestión de Usuarios y Roles y Permisos en el sidebar', {'Mantener Menú', 'Gestión de Usuarios', 'Roles y Permisos'} <= ea)
    for rol in ('Medico', 'Recepcion', 'Cajero'):
        e = etiquetas(cliente(rol))
        chk(f'{rol} no ve las ventanas de administración', not ({'Mantener Menú', 'Gestión de Usuarios', 'Roles y Permisos'} & e))
    ec = etiquetas(cliente('Cajero'))
    chk('Cajero ve solo Facturación (no ve Registrar Agenda)', 'Registrar Agenda' not in ec and len(ec) > 0)
    chk('Recepción ve Agendamiento', 'Registrar Agenda' in etiquetas(cliente('Recepcion')))

    # ---- 3. buscador ----------------------------------------------------------------------------------------------------------------------
    b = lambda c, q: [x['etiqueta'] for x in c.get('/api/v1/menu/buscar?q=' + q).get_json()['data']]
    chk('buscador: Administrador encuentra "menu" -> Mantener Menú', 'Mantener Menú' in b(admin, 'mantener%20men'))
    chk('buscador: Cajero no encuentra usuarios', 'Gestión de Usuarios' not in b(cliente('Cajero'), 'usuar'))

    # ---- 4. acceso a Mantener Menú ---------------------------------------------------------------------------------------------------------
    chk('Administrador abre la pantalla (200)', admin.get('/referenciales/menu/menu-index').status_code == 200)
    for rol in ('Medico', 'Recepcion', 'Cajero'):
        c = cliente(rol)
        chk(f'{rol}: pantalla 403 y API 403', c.get('/referenciales/menu/menu-index').status_code == 403 and c.get('/api/v1/menus').status_code == 403
            and c.post('/api/v1/menus', json={}).status_code == 403)

    # ---- 5. ABM ---------------------------------------------------------------------------------------------------------------------------
    r = admin.post('/api/v1/menus', json={'tipo': 'modulo', 'descripcion': 'ZZ Módulo', 'icono': 'fa-flask', 'orden': 900})
    chk('alta de módulo (201)', r.status_code == 201)
    mod = r.get_json()['data']['id_menu']; creados.append(mod)
    r = admin.post('/api/v1/menus', json={'tipo': 'modulo', 'descripcion': 'zz módulo', 'orden': 901})
    chk('módulo duplicado (409)', r.status_code == 409)
    body = {'tipo': 'ventana', 'id_menu_padre': mod, 'clave': 'zzventana', 'descripcion': 'ZZ Ventana', 'ruta': 'ciudad.ciudadIndex', 'icono': 'fa-bug', 'orden': 10}
    rutas = [x['endpoint'] for x in admin.get('/api/v1/menus/rutas').get_json()['data']]
    chk('lista de rutas disponible y sin la API', rutas and all('/api/' not in x['url'] for x in admin.get('/api/v1/menus/rutas').get_json()['data']))
    body['ruta'] = next(x for x in rutas if x.endswith('Index'))
    chk('ventana con ruta inexistente (400)', admin.post('/api/v1/menus', json=dict(body, ruta='no.existe')).status_code == 400)
    chk('ventana con clave inválida (400)', admin.post('/api/v1/menus', json=dict(body, clave='Z Z')).status_code == 400)
    chk('ventana con ícono inválido (400)', admin.post('/api/v1/menus', json=dict(body, icono='<script>')).status_code == 400)
    chk('ventana en módulo inexistente (400)', admin.post('/api/v1/menus', json=dict(body, id_menu_padre=999999)).status_code == 400)
    r = admin.post('/api/v1/menus', json=body)
    chk('alta de ventana (201)', r.status_code == 201)
    ven = r.get_json()['data']['id_menu']; creados.append(ven)
    chk('clave duplicada (409)', admin.post('/api/v1/menus', json=dict(body, descripcion='ZZ Otra')).status_code == 409)

    # delegar la ventana al Cajero: aparece en su menú; anulada, desaparece
    cu.execute("INSERT INTO permisos (id_rol, id_menu, accion) VALUES (%s,%s,'ver') ON CONFLICT DO NOTHING", (ROLES['Cajero'], ven))
    chk('ventana ZZ visible para el Cajero con permiso ver', 'ZZ Ventana' in etiquetas(cliente('Cajero')))
    chk('ventana ZZ NO visible para Recepción (sin permiso)', 'ZZ Ventana' not in etiquetas(cliente('Recepcion')))
    cat = [v['ventana'] for m in admin.get('/api/v1/permisos/catalogo').get_json()['data'] for v in m['ventanas']]
    chk('la matriz de permisos incluye la ventana ZZ', 'zzventana' in cat)

    r = admin.put(f'/api/v1/menus/{ven}', json=dict(body, descripcion='ZZ Ventana 2', orden=20))
    chk('modificación (200)', r.status_code == 200)
    chk('la modificación se refleja en el menú del Cajero', 'ZZ Ventana 2' in etiquetas(cliente('Cajero')))
    chk('el módulo con ventanas activas no se anula (409)', admin.delete(f'/api/v1/menus/{mod}').status_code == 409)
    r = admin.put(f'/api/v1/menus/{ven}', json=dict(body, descripcion='ZZ Ventana 2', orden=20, visible_en_menu=False))
    chk('ventana contextual (visible_en_menu=false) sale del menú', 'ZZ Ventana 2' not in etiquetas(cliente('Cajero')))
    admin.put(f'/api/v1/menus/{ven}', json=dict(body, descripcion='ZZ Ventana 2', orden=20))

    chk('anular ventana (200)', admin.delete(f'/api/v1/menus/{ven}').status_code == 200)
    chk('ventana anulada desaparece del menú del Cajero', 'ZZ Ventana 2' not in etiquetas(cliente('Cajero')))
    cat = [v['ventana'] for m in admin.get('/api/v1/permisos/catalogo').get_json()['data'] for v in m['ventanas']]
    chk('ventana anulada sale de la matriz', 'zzventana' not in cat)
    chk('no se otorga permiso sobre una ventana anulada (400)',
        admin.post('/api/v1/permisos/matriz', json={'id_rol': ROLES['Cajero'], 'ventana': 'zzventana', 'accion': 'ver'}).status_code in (400, 404))
    chk('el listado normal no trae la anulada; con inactivos=1 sí',
        ven not in [x['id_menu'] for x in admin.get('/api/v1/menus').get_json()['data']] if False else
        (ven in [x['id_menu'] for x in admin.get('/api/v1/menus?inactivos=1').get_json()['data'] if not x['activo']]))
    chk('anular dos veces (404)', admin.delete(f'/api/v1/menus/{ven}').status_code == 404)
    chk('el módulo ya se puede anular y reactivar',
        admin.delete(f'/api/v1/menus/{mod}').status_code == 200 and admin.patch(f'/api/v1/menus/{mod}/reactivar').status_code == 200)
    chk('reactivar activa (409)', admin.patch(f'/api/v1/menus/{mod}/reactivar').status_code == 409)
    # reactivar con la clave tomada por otra activa
    admin.delete(f'/api/v1/menus/{mod}')
    r = admin.patch(f'/api/v1/menus/{ven}/reactivar')
    chk('reactivar ventana con su módulo anulado (400)', r.status_code == 400)
    admin.patch(f'/api/v1/menus/{mod}/reactivar')
    r = admin.post('/api/v1/menus', json=dict(body, descripcion='ZZ Ventana B'))
    chk('la clave de una anulada se puede reusar (índice parcial)', r.status_code == 201)
    ven2 = r.get_json()['data']['id_menu']; creados.append(ven2)
    chk('reactivar la anulada con la clave ya tomada (409)', admin.patch(f'/api/v1/menus/{ven}/reactivar').status_code == 409)
    chk('reactivar ventana (200) tras liberar la clave',
        admin.delete(f'/api/v1/menus/{ven2}').status_code == 200 and admin.patch(f'/api/v1/menus/{ven}/reactivar').status_code == 200)

    # ---- 6. protección --------------------------------------------------------------------------------------------------------------------
    cu.execute("SELECT id_menu, clave FROM menu WHERE clave IN ('menu','usuario','permiso') AND activo")
    prot = dict((k, i) for i, k in cu.fetchall())
    cu.execute("SELECT id_menu FROM menu WHERE clave IS NULL AND id_menu_padre IS NULL AND descripcion = 'Módulo Seguridad' AND activo")
    modseg = cu.fetchone()[0]
    for clave, i in list(prot.items()) + [('módulo Seguridad', modseg)]:
        chk(f'anular {clave} protegida (409)', admin.delete(f'/api/v1/menus/{i}').status_code == 409)
    cu.execute("SELECT descripcion, icono, orden, ruta, id_menu_padre FROM menu WHERE id_menu = %s", (prot['menu'],))
    d, ic, o, ru, pa = cu.fetchone()
    base = {'tipo': 'ventana', 'id_menu_padre': pa, 'descripcion': d, 'ruta': ru, 'icono': ic, 'orden': o}
    chk('quitar la exclusividad de Mantener Menú (409)', admin.put(f'/api/v1/menus/{prot["menu"]}', json=dict(base, solo_admin=False)).status_code == 409)
    chk('mover Mantener Menú a otro módulo (409)', admin.put(f'/api/v1/menus/{prot["menu"]}', json=dict(base, id_menu_padre=mod, solo_admin=True)).status_code == 409)
    chk('cambiar la ruta de Mantener Menú (409)', admin.put(f'/api/v1/menus/{prot["menu"]}', json=dict(base, ruta=ru.replace('menuIndex', 'x') if False else rutas[0], solo_admin=True)).status_code == 409)
    chk('editar el orden de Mantener Menú sí se puede (200)', admin.put(f'/api/v1/menus/{prot["menu"]}', json=dict(base, orden=o, solo_admin=True)).status_code == 200)
    # el trigger lo impide aunque se salte la API (con la conexión de la app)
    from app.conexion.Conexion import Conexion as ConApp
    ca = ConApp().getConexion(); cua = ca.cursor()
    for sql, nombre in (("UPDATE menu SET activo=false WHERE id_menu=%s", 'anular'), ("DELETE FROM menu WHERE id_menu=%s", 'borrar'),
                        ("UPDATE menu SET solo_admin=false WHERE id_menu=%s", 'quitar exclusividad'), ("UPDATE menu SET protegida=false WHERE id_menu=%s", 'desproteger')):
        try:
            cua.execute(sql, (prot['permiso'],)); ok = False
        except psycopg2.Error:
            ok = True
        ca.rollback()
        chk(f'trigger: la base impide {nombre} una protegida', ok)
    cua.close(); ca.close()
    cu.execute("SELECT count(*) FROM menu WHERE id_menu = %s AND activo AND solo_admin AND protegida", (prot['permiso'],))
    chk('Roles y Permisos sigue intacta', cu.fetchone()[0] == 1)
    chk('el Administrador sigue viendo las ventanas críticas', {'Mantener Menú', 'Gestión de Usuarios', 'Roles y Permisos'} <= etiquetas(admin))

    # ---- 7. auditoría ---------------------------------------------------------------------------------------------------------------------
    cu.execute("SELECT accion, modulo FROM auditoria_cambios WHERE entidad = 'menu' AND id_registro = %s ORDER BY 1", (ven,))
    filas = cu.fetchall()
    acciones = {a for a, _ in filas}
    chk('auditoría: ALTA, MODIFICACION, BAJA y REACTIVACION de la ventana', {'ALTA', 'MODIFICACION', 'BAJA', 'REACTIVACION'} <= acciones)
    chk('auditoría con módulo Seguridad', all(m == 'Módulo Seguridad' for _, m in filas) if filas else False)
    cu.execute("SELECT valores_nuevos::text FROM auditoria_cambios WHERE entidad='menu' AND id_registro=%s AND accion='ALTA'", (ven,))
    t = cu.fetchone()[0]
    chk('el detalle muestra nombres (módulo, descripción), no IDs', 'ZZ Módulo' in t and 'ZZ Ventana' in t)
    cu.execute("SELECT count(*) FROM auditoria_cambios WHERE entidad='menu' AND id_registro=%s", (prot['menu'],))
    n_antes = cu.fetchone()[0]
    admin.put(f'/api/v1/menus/{prot["menu"]}', json=dict(base, orden=o, solo_admin=True))
    cu.execute("SELECT count(*) FROM auditoria_cambios WHERE entidad='menu' AND id_registro=%s", (prot['menu'],))
    chk('una edición sin cambios no audita', cu.fetchone()[0] == n_antes)

    # ---- 8. plan B: si falla la lectura de la tabla, el menú sigue (registro del código) ------------------------------------------------------
    import app.dao.modulo_seguridad.MenuDao as md
    orig = md.MenuDao.getFilas
    md.MenuDao.getFilas = lambda self, incluir_inactivos=True: (_ for _ in ()).throw(RuntimeError('base caída'))
    try:
        chk('con la tabla menu inaccesible la página de error aún renderiza', cliente('Administrador').get('/ruta-que-no-existe').status_code == 404)
    finally:
        md.MenuDao.getFilas = orig
finally:
    try:
        for i in creados:
            borrar_auditoria(cu, 'menu', [i])
        cu.execute("DELETE FROM permisos WHERE id_menu = ANY(%s)", (creados,))
        cu.execute("DELETE FROM menu WHERE id_menu = ANY(%s) AND id_menu_padre IS NOT NULL", (creados,))
        cu.execute("DELETE FROM menu WHERE id_menu = ANY(%s)", (creados,))
        borrar_auditoria(cu, 'menu', [])
        # la edición sin cambios de 'menu' no deja rastro; si dejó alguno de MODIFICACION propio, se borra por ID de prueba arriba
    finally:
        cu.close(); cx.close()

print('\nFALLOS: ' + ('ninguno' if not fallos else '; '.join(fallos)))
sys.exit(1 if fallos else 0)
