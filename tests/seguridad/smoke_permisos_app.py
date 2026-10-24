"""Usuario de base de datos de la aplicación (mínimo privilegio): atributos del rol, privilegios exactos sobre tablas, vistas,
secuencias, funciones y esquema, lo que PUEDE y NO PUEDE hacer de verdad (sin UPDATE/DELETE en las auditorías, sin DDL, sin
saltarse triggers), privilegios por defecto para objetos futuros, script idempotente, contraseñas fuera del código y un
barrido por TODAS las pantallas y APIs de lectura con la aplicación conectada como odontoclinic_app (ninguna puede dar 500
por falta de permiso). La regresión de escritura la hacen los demás smoke_*.py, que ejercitan la app con ese mismo rol.
Las verificaciones privilegiadas usan postgres (TEST_DB_*); crea y borra una tabla/función de prueba."""
import os, pathlib, re, subprocess, sys
RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import psycopg2
from app import app
from app.conexion.Conexion import Conexion as ConexionApp
from tests._conexion_pruebas import Conexion as ConexionAdm
from app.rutas.modulo_seguridad.menu_catalog import CATALOGO_MENU

fallos = []
AUDITORIAS = ('auditoria_cambios', 'auditoria_acceso')


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


adm = ConexionAdm().getConexion(); adm.autocommit = True; ca = adm.cursor()
ca.execute("SELECT COALESCE(MAX(id_auditoria), 0) FROM auditoria_acceso"); ID_AUD = ca.fetchone()[0]


def como_app():
    c = ConexionApp().getConexion(); c.autocommit = True
    return c, c.cursor()


def intenta(cur, sql, params=()):
    """None si la sentencia se ejecutó; si no, el SQLSTATE del rechazo."""
    try:
        cur.execute(sql, params); return None
    except psycopg2.Error as e:
        return e.pgcode


def privilegios():
    """Matriz {(objeto, privilegio): bool} del rol de la app, para comparar antes/después de re-aplicar el script."""
    ca.execute("""SELECT c.relname, c.relkind,
                         has_table_privilege('odontoclinic_app', c.oid, 'SELECT'), has_table_privilege('odontoclinic_app', c.oid, 'INSERT'),
                         has_table_privilege('odontoclinic_app', c.oid, 'UPDATE'), has_table_privilege('odontoclinic_app', c.oid, 'DELETE'),
                         has_table_privilege('odontoclinic_app', c.oid, 'TRUNCATE'), has_table_privilege('odontoclinic_app', c.oid, 'REFERENCES'),
                         has_table_privilege('odontoclinic_app', c.oid, 'TRIGGER')
                  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                  WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm') ORDER BY 1""")
    return ca.fetchall()


try:
    # =========================================================================================================================
    # 1. ROLES
    # =========================================================================================================================
    ca.execute("SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles "
               "WHERE rolname IN ('odontoclinic_app', 'odontoclinic_backup') ORDER BY 1")
    roles = {r[0]: r[1:] for r in ca.fetchall()}
    chk('odontoclinic_app: LOGIN, sin superusuario, CREATEDB, CREATEROLE, REPLICATION ni BYPASSRLS', roles.get('odontoclinic_app') == (True, False, False, False, False, False))
    chk('odontoclinic_backup: LOGIN y sin ningún privilegio de administración', roles.get('odontoclinic_backup') == (True, False, False, False, False, False))
    ca.execute("SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.roleid JOIN pg_roles u ON u.oid = m.member "
               "WHERE u.rolname = 'odontoclinic_backup' AND r.rolname = 'pg_read_all_data'")
    chk('odontoclinic_backup es miembro de pg_read_all_data (solo lectura)', ca.fetchone()[0] == 1)
    ca.execute("SELECT count(*) FROM pg_auth_members m JOIN pg_roles u ON u.oid = m.member WHERE u.rolname = 'odontoclinic_app'")
    chk('odontoclinic_app no pertenece a ningún otro rol', ca.fetchone()[0] == 0)

    ca_app, cu = como_app()
    cu.execute("SELECT current_user, session_user"); chk('la aplicación (Conexion + .env) se conecta como odontoclinic_app', cu.fetchone() == ('odontoclinic_app', 'odontoclinic_app'))
    chk('.env: DB_USER es odontoclinic_app y las pruebas usan otro usuario (TEST_DB_USER)',
        os.environ.get('DB_USER') == 'odontoclinic_app' and os.environ.get('TEST_DB_USER') not in (None, '', 'odontoclinic_app'))

    # =========================================================================================================================
    # 2. PRIVILEGIOS EXACTOS
    # =========================================================================================================================
    p = privilegios()
    tablas = [x for x in p if x[1] in ('r', 'p')]
    vistas = [x for x in p if x[1] in ('v', 'm')]
    chk(f'hay tablas y vistas que revisar ({len(tablas)} tablas, {len(vistas)} vistas)', len(tablas) > 50 and len(vistas) >= 5)
    normales = [x for x in tablas if x[0] not in AUDITORIAS]
    chk('tablas: SELECT/INSERT/UPDATE/DELETE en todas menos las dos de auditoría', all(x[2:6] == (True,) * 4 for x in normales))
    chk('tablas: nunca TRUNCATE, REFERENCES ni TRIGGER', all(x[6:9] == (False,) * 3 for x in tablas))
    aud = {x[0]: x for x in tablas if x[0] in AUDITORIAS}
    chk('auditoria_cambios y auditoria_acceso: SOLO SELECT e INSERT (sin UPDATE ni DELETE)',
        set(aud) == set(AUDITORIAS) and all(a[2:6] == (True, True, False, False) for a in aud.values()))
    chk('vistas: solo SELECT', all(x[2:6] == (True, False, False, False) for x in vistas))
    ca.execute("""SELECT bool_and(has_sequence_privilege('odontoclinic_app', c.oid, 'USAGE') AND has_sequence_privilege('odontoclinic_app', c.oid, 'SELECT')),
                         bool_or(has_sequence_privilege('odontoclinic_app', c.oid, 'UPDATE')), count(*)
                  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relkind = 'S'""")
    f = ca.fetchone(); chk(f'secuencias: USAGE y SELECT en las {f[2]}, sin UPDATE', f[0] is True and f[1] is False and f[2] > 50)
    ca.execute("""SELECT bool_and(has_function_privilege('odontoclinic_app', p.oid, 'EXECUTE')), count(*), count(*) FILTER (WHERE p.prokind = 'p')
                  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'public'""")
    f = ca.fetchone(); chk(f'funciones y procedimientos: EXECUTE en los {f[1]} (incluye {f[2]} procedimientos)', f[0] is True and f[2] >= 2)
    ca.execute("SELECT has_schema_privilege('odontoclinic_app', 'public', 'USAGE'), has_schema_privilege('odontoclinic_app', 'public', 'CREATE'), "
               "has_database_privilege('odontoclinic_app', current_database(), 'CONNECT'), has_database_privilege('odontoclinic_app', current_database(), 'CREATE')")
    chk('esquema public: USAGE sí, CREATE no; base: CONNECT sí, CREATE no', ca.fetchone() == (True, False, True, False))

    # =========================================================================================================================
    # 3. LO QUE HACE (Y NO) DE VERDAD
    # =========================================================================================================================
    chk('SELECT sobre una tabla normal', intenta(cu, 'SELECT count(*) FROM usuarios') is None)
    chk('INSERT en auditoria_acceso permitido', intenta(cu, "INSERT INTO auditoria_acceso(ci_ruc_ingresado, resultado, ip, accion) VALUES ('0000099', 'TEST_PERMISOS_APP', '203.0.113.9', 'LOGIN')") is None)
    chk('UPDATE de auditoria_acceso rechazado (permiso denegado)', intenta(cu, "UPDATE auditoria_acceso SET ip = 'x' WHERE resultado = 'TEST_PERMISOS_APP'") == '42501')
    chk('DELETE de auditoria_acceso rechazado (permiso denegado)', intenta(cu, "DELETE FROM auditoria_acceso WHERE resultado = 'TEST_PERMISOS_APP'") == '42501')
    chk('UPDATE de auditoria_cambios rechazado', intenta(cu, 'UPDATE auditoria_cambios SET ip = ip WHERE false') == '42501')
    chk('DELETE de auditoria_cambios rechazado', intenta(cu, 'DELETE FROM auditoria_cambios WHERE false') == '42501')
    chk('TRUNCATE rechazado (tabla normal y de auditoría)', intenta(cu, 'TRUNCATE usuarios') == '42501' and intenta(cu, 'TRUNCATE auditoria_acceso') == '42501')
    chk('CREATE TABLE rechazado', intenta(cu, 'CREATE TABLE zz_no_deberia (a int)') == '42501')
    chk('ALTER TABLE rechazado', intenta(cu, 'ALTER TABLE usuarios ADD COLUMN zz int') == '42501')
    chk('DROP TABLE rechazado', intenta(cu, 'DROP TABLE paciente') == '42501')
    chk('CREATE FUNCTION rechazado', intenta(cu, "CREATE FUNCTION zz_f() RETURNS int LANGUAGE sql AS 'SELECT 1'") == '42501')
    chk('CREATE ROLE y CREATE DATABASE rechazados', intenta(cu, 'CREATE ROLE zz_rol') == '42501' and intenta(cu, 'CREATE DATABASE zz_db') == '42501')
    chk('no puede saltarse los triggers (session_replication_role requiere superusuario)', intenta(cu, "SET session_replication_role = replica") == '42501')
    chk('no puede desactivar triggers (ALTER TABLE ... DISABLE TRIGGER)', intenta(cu, 'ALTER TABLE auditoria_acceso DISABLE TRIGGER ALL') == '42501')
    cu.execute('BEGIN'); cu.execute('SELECT nextval(%s)', ('usuarios_id_usuario_seq',)); cu.execute('ROLLBACK')
    chk('usa secuencias (nextval)', True)
    # En una transacción que se deshace: el procedimiento incrementa el número de factura real si se confirmara
    cu.execute('BEGIN')
    codigo_sp = intenta(cu, 'CALL sp_siguiente_numero_factura(NULL, NULL)')
    cu.execute('ROLLBACK')
    chk('ejecuta el procedimiento sp_siguiente_numero_factura (puede fallar por negocio, nunca por permiso)', codigo_sp != '42501')
    chk('DML normal dentro de una transacción (UPDATE y DELETE sobre una tabla normal)',
        intenta(cu, "UPDATE roles SET nombre_rol = nombre_rol WHERE false") is None and intenta(cu, 'DELETE FROM token_2fa WHERE false') is None)

    # Doble protección: aun con permisos de superusuario, el trigger rechaza modificar la auditoría
    ca.execute("SELECT id_auditoria FROM auditoria_acceso WHERE resultado = 'TEST_PERMISOS_APP'"); mio = [r[0] for r in ca.fetchall()]
    chk('doble protección: el trigger también frena a postgres',
        intenta(ca, "UPDATE auditoria_acceso SET ip = 'x' WHERE id_auditoria = ANY(%s)", (mio,)) is not None)

    # =========================================================================================================================
    # 4. PRIVILEGIOS POR DEFECTO PARA OBJETOS FUTUROS
    # =========================================================================================================================
    try:
        ca.execute("CREATE TABLE zz_perm_defecto (id serial PRIMARY KEY, dato text)")
        ca.execute("CREATE FUNCTION zz_perm_defecto_f() RETURNS int LANGUAGE sql AS 'SELECT 1'")
        ca.execute("SELECT has_table_privilege('odontoclinic_app', 'zz_perm_defecto', 'SELECT,INSERT,UPDATE,DELETE'), "
                   "has_table_privilege('odontoclinic_app', 'zz_perm_defecto', 'TRUNCATE'), "
                   "has_sequence_privilege('odontoclinic_app', 'zz_perm_defecto_id_seq', 'USAGE,SELECT'), "
                   "has_function_privilege('odontoclinic_app', 'zz_perm_defecto_f()', 'EXECUTE')")
        chk('objeto futuro creado por postgres: tabla con DML, secuencia con USAGE/SELECT, función con EXECUTE y sin TRUNCATE', ca.fetchone() == (True, False, True, True))
        chk('...y la app lo usa de verdad (INSERT + nextval + función)',
            intenta(cu, "INSERT INTO zz_perm_defecto(dato) VALUES ('x')") is None and intenta(cu, 'SELECT zz_perm_defecto_f()') is None)
    finally:
        ca.execute("DROP TABLE IF EXISTS zz_perm_defecto"); ca.execute("DROP FUNCTION IF EXISTS zz_perm_defecto_f()")

    # =========================================================================================================================
    # 5. SCRIPT IDEMPOTENTE Y SIN CONTRASEÑAS
    # =========================================================================================================================
    script = (RAIZ / 'app' / 'dao' / 'modulo_seguridad' / 'schema_usuario_app.sql').read_text(encoding='utf-8')
    antes = privilegios()
    ca.execute(script); ca.execute(script)
    chk('schema_usuario_app.sql es idempotente (dos corridas más y los privilegios no cambian)', privilegios() == antes)
    chk('el script SQL no fija contraseñas (ninguna cláusula PASSWORD con literal)', re.search(r"PASSWORD\s+'", script, re.I) is None)
    claves = [os.environ.get(v) for v in ('DB_PASSWORD', 'TEST_DB_PASSWORD', 'BACKUP_DB_PASSWORD')]
    claves = [c for c in claves if c and len(c) >= 8]
    chk('hay 3 contraseñas distintas en el .env (app, pruebas y backup)', len(claves) == 3 and len(set(claves)) == 3)
    rastreados = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], capture_output=True, text=True, cwd=RAIZ).stdout.splitlines()
    filtradas = []
    for rel in rastreados:
        ruta = RAIZ / rel
        if ruta.suffix.lower() in ('.py', '.sql', '.md', '.bat', '.html', '.js', '.txt', '.example') or ruta.name == '.env.example':
            try:
                texto = ruta.read_text(encoding='utf-8', errors='ignore')
            except OSError:
                continue
            filtradas += [rel for c in claves if c in texto]
    chk('ninguna contraseña real aparece en archivos versionables' + (f' (en: {sorted(set(filtradas))})' if filtradas else ''), not filtradas)

    # =========================================================================================================================
    # 6. BARRIDO DE PANTALLAS Y APIs DE LECTURA CON LA APP COMO odontoclinic_app
    # =========================================================================================================================
    c = app.test_client()
    ca.execute("SELECT u.id_usuario, r.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.activo AND r.nombre_rol = 'Administrador' ORDER BY 1")
    admin = ca.fetchone()
    with c.session_transaction() as s:
        s['id_usuario'], s['id_rol'], s['nombre_rol'] = admin
    malas = []
    for item in CATALOGO_MENU:
        with app.test_request_context():
            from flask import url_for
            url = url_for(item['endpoint'])
        r = c.get(url)
        if r.status_code != 200:
            malas.append((url, r.status_code))
    chk(f'las {len(CATALOGO_MENU)} pantallas del menú cargan (200)' + (f' FALLAN: {malas}' if malas else ''), not malas)

    reglas = [r for r in app.url_map.iter_rules() if 'GET' in r.methods and not r.arguments and r.endpoint != 'static'
              and r.rule.startswith(('/api/v1', '/referenciales'))]
    # '/vista' (ruta suelta de app/__init__.py) renderiza vista-index.html sin 'stats': falla igual con postgres, no es de permisos
    cuerpos_500 = []
    for r in sorted(reglas, key=lambda x: x.rule):
        resp = c.get(r.rule)
        if resp.status_code >= 500:
            cuerpos_500.append((r.rule, resp.status_code, (resp.get_json(silent=True) or {}).get('error')))
    chk(f'{len(reglas)} pantallas y APIs de lectura recorridas: ninguna da error 500' + (f' -> {cuerpos_500}' if cuerpos_500 else ''), not cuerpos_500)
    cu.close(); ca_app.close()
finally:
    ca.execute("SELECT id_auditoria FROM auditoria_acceso WHERE id_auditoria > %s AND resultado = 'TEST_PERMISOS_APP'", (ID_AUD,))
    propios = [x[0] for x in ca.fetchall()]
    if propios:
        ca.execute("SET session_replication_role = replica")
        ca.execute("DELETE FROM auditoria_acceso WHERE id_auditoria = ANY(%s)", (propios,))
        ca.execute("RESET session_replication_role")
    ca.close(); adm.close()

print('FALLOS:', 'ninguno' if not fallos else fallos)
