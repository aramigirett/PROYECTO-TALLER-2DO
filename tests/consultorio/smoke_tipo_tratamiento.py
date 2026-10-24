"""Tipo Tratamiento (Consultorio): precio obligatorio NUMERIC(12,0) > 0.
Cubre alta, modificación, precio inválido, datos iniciales (relajado: existen y tienen precio > 0), la migración
(idempotente, probada en una base TEMPORAL que se crea y se borra, sin tocar los datos reales) y la regresión de
Gestionar Tratamientos y de las demás pantallas que leen tipos_tratamiento."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import psycopg2
from app import app
from app.conexion.Conexion import Conexion

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SQL_PRECIO = RAIZ / 'app' / 'dao' / 'referenciales_consultorio' / 'tipo_tratamiento' / 'schema_tipo_tratamiento_precio.sql'
c = app.test_client()
fallos = []
creados = set()
MSG = 'El precio debe ser un número entero mayor a 0.'
SEEDS = ['LIMPIEZA DENTAL (PROFILAXIS)', 'SELLANTES DE FOSAS Y FISURAS', 'RESTAURACIÓN CON RESINA', 'EXTRACCIÓN SIMPLE',
         'EXTRACCIÓN DE TERCER MOLAR', 'TRATAMIENTO DE CONDUCTO', 'CORONA DE PORCELANA', 'BLANQUEAMIENTO DENTAL',
         'INSTALACIÓN DE BRACKETS', 'CONTROL DE ORTODONCIA', 'IMPLANTE DENTAL']

def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)

def api(metodo, url, esperado, json=None, nombre=None, exacto=None, contiene=None, campo=None):
    f = getattr(c, metodo)
    r = f(url, json=json) if json is not None else f(url)
    d = r.get_json(silent=True) or {}
    ok = r.status_code == esperado
    texto = d.get('error') or d.get('mensaje') or ''
    if exacto is not None:
        ok = ok and texto == exacto
    if contiene is not None:
        ok = ok and contiene in texto
    if campo is not None:
        ok = ok and d.get('campo') == campo
    chk(f"{nombre or metodo + ' ' + url} -> {r.status_code}" + ('' if ok else f' {d}'), ok)
    return d

TT = '/api/v1/tipos-tratamiento'
real = Conexion().getConexion(); cu = real.cursor()
info = real.info
tmp_db = 'odonto_tmp_tipo_trat'

def conectar(dbname):
    return psycopg2.connect(dbname=dbname, user=info.user, password=info.password, host=info.host, port=info.port)

cu.execute('SELECT COALESCE(max(id_tipo_tratamiento), 0) FROM tipos_tratamiento'); ID_INICIAL = cu.fetchone()[0]

def contar_zz():
    cu.execute("SELECT count(*) FROM tipos_tratamiento WHERE descripcion LIKE 'ZZ%'"); return cu.fetchone()[0]

try:
    # ---------- base real: columna, restricciones y datos iniciales ----------
    cu.execute("SELECT data_type, numeric_precision, numeric_scale, is_nullable FROM information_schema.columns WHERE table_name='tipos_tratamiento' AND column_name='precio'")
    chk('columna precio NUMERIC(12,0) NOT NULL', cu.fetchone() == ('numeric', 12, 0, 'NO'))
    cu.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='chk_tipos_tratamiento_precio'")
    fila = cu.fetchone(); chk('CHECK (precio > 0) existe', bool(fila) and 'precio' in fila[0] and '> (0)' in fila[0])
    cu.execute("SELECT UPPER(descripcion), precio FROM tipos_tratamiento WHERE activo = true")
    activos = {d: p for d, p in cu.fetchall()}
    for d in SEEDS:   # relajado: existe y tiene precio > 0 (los valores pueden haberse editado desde la pantalla)
        chk(f'seed existe y precio > 0: {d}', d in activos and activos[d] > 0)
    cu.execute("SELECT activo, precio FROM tipos_tratamiento WHERE UPPER(descripcion)='PRUEBA'")
    prueba = cu.fetchall()
    chk('PRUEBA (si existe) está anulada y tiene precio > 0', all(a is False and p > 0 for a, p in prueba))
    cu.execute("SELECT count(*) FROM tipos_tratamiento WHERE precio IS NULL OR precio <= 0"); chk('ninguna fila sin precio válido', cu.fetchone()[0] == 0)
    cu.execute("SELECT count(*) FROM (SELECT UPPER(descripcion) FROM tipos_tratamiento WHERE activo GROUP BY 1 HAVING count(*) > 1) x")
    chk('sin descripciones activas duplicadas', cu.fetchone()[0] == 0)

    # ---------- migración idempotente, en una base TEMPORAL ----------
    sql = SQL_PRECIO.read_text(encoding='utf-8')
    adm = conectar('postgres'); adm.autocommit = True
    adm.cursor().execute(f'DROP DATABASE IF EXISTS {tmp_db}'); adm.cursor().execute(f'CREATE DATABASE {tmp_db}')
    LEGADO = """
        CREATE TABLE tipos_tratamiento (
            id_tipo_tratamiento SERIAL PRIMARY KEY,
            descripcion VARCHAR(200) NOT NULL,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activo BOOLEAN DEFAULT true);
        CREATE UNIQUE INDEX uk_tipo_trat_descripcion ON tipos_tratamiento (descripcion) WHERE activo = true;"""
    def instantanea(cur):
        cur.execute("SELECT id_tipo_tratamiento, descripcion, precio, activo FROM tipos_tratamiento ORDER BY 1"); return cur.fetchall()
    try:
        t = conectar(tmp_db); tc = t.cursor()
        tc.execute(LEGADO); tc.execute("INSERT INTO tipos_tratamiento(descripcion) VALUES ('PRUEBA')"); t.commit()
        tc.execute(sql); t.commit()
        a = instantanea(tc)
        chk('migración (1.ª corrida): PRUEBA anulada con precio 1 + 11 seeds = 12 filas', len(a) == 12 and a[0][1:] == ('PRUEBA', 1, False))
        chk('migración: los 11 seeds con los precios pedidos', {d: p for _, d, p, ac in a if ac} == dict(zip(SEEDS, [200000, 120000, 250000, 150000, 500000, 800000, 1500000, 1200000, 3500000, 200000, 5000000])))
        tc.execute(sql); t.commit()
        b = instantanea(tc)
        chk('migración IDEMPOTENTE: la 2.ª corrida no cambia nada', a == b)
        tc.execute(sql); t.commit()
        chk('migración IDEMPOTENTE: la 3.ª corrida tampoco', instantanea(tc) == a)
        tc.execute("SELECT is_nullable FROM information_schema.columns WHERE table_name='tipos_tratamiento' AND column_name='precio'"); chk('migración: NOT NULL aplicado', tc.fetchone()[0] == 'NO')
        tc.execute("SELECT count(*) FROM pg_constraint WHERE conname='chk_tipos_tratamiento_precio'"); chk('migración: CHECK creado una sola vez', tc.fetchone()[0] == 1)
        try:
            tc.execute("INSERT INTO tipos_tratamiento(descripcion, precio) VALUES ('X', 0)"); t.commit(); chk('migración: el CHECK rechaza precio 0', False)
        except psycopg2.errors.CheckViolation:
            t.rollback(); chk('migración: el CHECK rechaza precio 0', True)
        try:
            tc.execute("INSERT INTO tipos_tratamiento(descripcion) VALUES ('Y')"); t.commit(); chk('migración: NOT NULL rechaza precio vacío', False)
        except psycopg2.errors.NotNullViolation:
            t.rollback(); chk('migración: NOT NULL rechaza precio vacío', True)
        t.close()

        # una fila sin precio que NO es PRUEBA: la migración se corta con un mensaje claro y no deja nada a medias
        adm.cursor().execute(f'DROP DATABASE {tmp_db}'); adm.cursor().execute(f'CREATE DATABASE {tmp_db}')
        t = conectar(tmp_db); tc = t.cursor()
        tc.execute(LEGADO); tc.execute("INSERT INTO tipos_tratamiento(descripcion) VALUES ('PRUEBA'), ('OTRO TRATAMIENTO')"); t.commit()
        try:
            tc.execute(sql); t.commit(); chk('migración: con una fila sin precio se corta', False)
        except psycopg2.Error as e:
            t.rollback()
            chk('migración: con una fila sin precio se corta con un mensaje claro', 'sin precio' in str(e) and 'OTRO TRATAMIENTO' in str(e))
        tc.execute("SELECT count(*) FROM information_schema.columns WHERE table_name='tipos_tratamiento' AND column_name='precio'")
        chk('migración cortada: no quedó la columna ni cambios a medias (transaccional)', tc.fetchone()[0] == 0)
        tc.execute("SELECT count(*), count(*) FILTER (WHERE activo) FROM tipos_tratamiento"); chk('migración cortada: PRUEBA sigue activa y sin seeds', tc.fetchone() == (2, 2))
        t.close()
    finally:
        try:
            adm.cursor().execute(f'DROP DATABASE IF EXISTS {tmp_db}')
        finally:
            adm.close()

    # ---------- API ----------
    api('get', TT, 401, nombre='sin sesión')
    with c.session_transaction() as s:
        s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

    d = api('get', TT, 200, nombre='lista')
    chk('la lista trae precio (entero) en todas las filas', all(isinstance(x['precio'], int) and x['precio'] > 0 for x in d['data']))
    chk('la lista trae solo activos (sin PRUEBA)', all(x['descripcion'] != 'PRUEBA' for x in d['data']))

    # alta válida
    d = api('post', TT, 201, {'descripcion': ' zz tratamiento a ', 'precio': '250000'}, 'alta con precio (texto numérico)')
    a = d['data']['id_tipo_tratamiento']; creados.add(a)
    chk('alta: descripción en mayúsculas y precio entero', d['data']['descripcion'] == 'ZZ TRATAMIENTO A' and d['data']['precio'] == 250000)
    d = api('get', f'{TT}/{a}', 200, nombre='get por id'); chk('get trae el precio guardado', d['data']['precio'] == 250000)
    cu.execute("SELECT precio FROM tipos_tratamiento WHERE id_tipo_tratamiento=%s", (a,)); chk('en la base: precio 250000', cu.fetchone()[0] == 250000)
    d = api('post', TT, 201, {'descripcion': 'zz tratamiento b', 'precio': 1}, 'alta con precio entero (mínimo, 1)'); b = d['data']['id_tipo_tratamiento']; creados.add(b)
    d = api('post', TT, 201, {'descripcion': 'zz tratamiento c', 'precio': 999999999999}, 'alta con el precio máximo (NUMERIC(12,0))'); k = d['data']['id_tipo_tratamiento']; creados.add(k)
    api('post', TT, 400, {'descripcion': 'zz tratamiento a', 'precio': 1000}, 'alta duplicada', contiene='Ya existe')

    # precio inválido: alta
    antes = contar_zz()
    for malo in [0, -5, '0', '-1', 15000.5, '15000.5', '15.000', 'abc', '', '   ', None, True, False, 10 ** 12, '1000000000000', [1], {'a': 1}]:
        api('post', TT, 400, {'descripcion': 'zz precio malo', 'precio': malo}, f'alta con precio inválido {malo!r}', exacto=MSG, campo='precio')
    api('post', TT, 400, {'descripcion': 'zz sin precio'}, 'alta sin la clave precio', exacto=MSG, campo='precio')
    chk('ninguno de los altas inválidas creó filas', contar_zz() == antes)

    # modificación
    d = api('put', f'{TT}/{a}', 200, {'descripcion': 'zz tratamiento a', 'precio': '300000'}, 'modificación: nuevo precio')
    chk('modificación: devuelve el precio nuevo', d['data']['precio'] == 300000)
    cu.execute("SELECT precio FROM tipos_tratamiento WHERE id_tipo_tratamiento=%s", (a,)); chk('en la base: precio 300000', cu.fetchone()[0] == 300000)
    api('put', f'{TT}/{a}', 200, {'descripcion': 'zz tratamiento a renombrado', 'precio': 300000}, 'modificación: cambia la descripción conservando el precio')
    for malo in [0, -1, '15000.5', 'abc', '', None, True, 10 ** 12]:
        api('put', f'{TT}/{a}', 400, {'descripcion': 'zz tratamiento a renombrado', 'precio': malo}, f'modificación con precio inválido {malo!r}', exacto=MSG, campo='precio')
    api('put', f'{TT}/{a}', 400, {'descripcion': 'zz tratamiento a renombrado'}, 'modificación sin la clave precio', exacto=MSG, campo='precio')
    cu.execute("SELECT precio, descripcion FROM tipos_tratamiento WHERE id_tipo_tratamiento=%s", (a,)); chk('las modificaciones inválidas no cambiaron nada', cu.fetchone() == (300000, 'ZZ TRATAMIENTO A RENOMBRADO'))
    api('put', f'{TT}/999999', 404, {'descripcion': 'zz x', 'precio': 1000}, 'modificación de un inexistente')
    api('put', f'{TT}/{a}', 400, {'descripcion': 'implante dental', 'precio': 1000}, 'modificación con descripción duplicada', contiene='Ya existe')

    # baja (sigue funcionando)
    api('delete', f'{TT}/{b}', 200, nombre='baja de un tipo sin tratamientos', contiene='eliminado')
    d = api('get', TT, 200, nombre='lista tras la baja'); chk('el anulado no aparece', b not in {x['id_tipo_tratamiento'] for x in d['data']})

    # ---------- la vista ----------
    r = c.get('/referenciales/tipo-tratamiento/tipo-tratamiento-index')
    chk('vista Tipo Tratamiento: campo Precio y columna Precio',
        r.status_code == 200 and b'id="txtPrecio"' in r.data and b'Precio</th>' in r.data)
    chk('vista Tipo Tratamiento: carga facturacion-validadores.js y usa formatoGs', b'facturacion-validadores.js' in r.data and b'formatoGs' in r.data and MSG.encode() in r.data)
    r = c.get('/static/js/facturacion-validadores.js'); chk('el JS compartido sigue servido (precio y formatoGs)', r.status_code == 200 and b'precio:' in r.data and b'formatoGs' in r.data)

    # ---------- regresión: Gestionar Tratamientos y demás lectores ----------
    cu.execute("""SELECT t.id_tratamiento, tt.descripcion, tt.activo FROM tratamientos t
                  JOIN paciente p ON t.id_paciente = p.id_paciente JOIN medico m ON t.id_medico = m.id_medico
                  JOIN tipos_tratamiento tt ON t.id_tipo_tratamiento = tt.id_tipo_tratamiento WHERE t.estado <> 'cancelado'""")
    esperados = cu.fetchall()
    d = api('get', '/api/v1/tratamientos', 200, nombre='Gestionar Tratamientos: listado')
    listados = {x['id_tratamiento']: x for x in d['data']}
    chk('Tratamientos: el listado trae los mismos tratamientos que la base', set(listados) == {e[0] for e in esperados})
    chk('Tratamientos: muestran el nombre de su tipo', all(listados[i]['tipo_tratamiento'] == desc for i, desc, _ in esperados))
    inactivos = [e for e in esperados if e[2] is False]
    chk(f'Tratamientos: los de un tipo ANULADO ({len(inactivos)}) siguen listándose', all(e[0] in listados for e in inactivos))
    if esperados:
        i0 = esperados[0][0]
        d = api('get', f'/api/v1/tratamientos/{i0}', 200, nombre='Gestionar Tratamientos: detalle'); chk('Tratamientos: el detalle trae el tipo', d['data'].get('tipo_tratamiento') == esperados[0][1])
    cu.execute("SELECT DISTINCT id_consulta_cab FROM tratamientos WHERE estado <> 'cancelado' LIMIT 1"); cc = cu.fetchone()
    if cc:
        api('get', f'/api/v1/tratamientos/consulta/{cc[0]}', 200, nombre='Tratamientos por consulta (lo usa Recetas)')
    r = c.get('/referenciales/tratamiento/tratamiento-index'); chk('vista Gestionar Tratamientos carga y su combo usa /api/v1/tipos-tratamiento', r.status_code == 200 and b'/api/v1/tipos-tratamiento' in r.data)
    d = api('get', TT, 200, nombre='combo de tipos (id y descripción)'); chk('combo: todas las filas con id y descripción', all('id_tipo_tratamiento' in x and x['descripcion'] for x in d['data']))

    # ---------- permisos ----------
    cu.execute("SELECT id_rol FROM roles WHERE nombre_rol <> 'Administrador' LIMIT 1"); rol = cu.fetchone()[0]
    def sin_permiso(acc):
        cu.execute("DELETE FROM permisos WHERE ventana='tipotratamiento' AND id_rol=%s AND accion=%s", (rol, acc)); real.commit()
    def con_permiso(acc):
        cu.execute("INSERT INTO permisos (id_rol, ventana, accion) VALUES (%s,'tipotratamiento',%s) ON CONFLICT DO NOTHING", (rol, acc)); real.commit()
    with c.session_transaction() as s:
        s['id_rol'] = rol; s['nombre_rol'] = 'NoAdmin'
    try:
        sin_permiso('nuevo'); api('post', TT, 403, {'descripcion': 'zz x', 'precio': 1000}, 'rol SIN "nuevo" no crea'); con_permiso('nuevo')
        sin_permiso('editar'); api('put', f'{TT}/{a}', 403, {'descripcion': 'zz x', 'precio': 1000}, 'rol SIN "editar" no modifica'); con_permiso('editar')
        api('get', TT, 200, nombre='el lookup sigue disponible con solo login')
    finally:
        for acc in ('ver', 'nuevo', 'editar', 'anular'):
            con_permiso(acc)
finally:
    if creados:
        cu.execute("DELETE FROM tipos_tratamiento WHERE id_tipo_tratamiento = ANY(%s)", (list(creados),))
    cu.execute("DELETE FROM tipos_tratamiento WHERE id_tipo_tratamiento > %s AND descripcion LIKE 'ZZ%%'", (ID_INICIAL,))
    real.commit(); cu.close(); real.close()
print('FALLOS:', fallos or 'ninguno')
