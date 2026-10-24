"""Mantener Cuenta Bancaria (referencial): tabla y FK nuevas, datos iniciales, estándar de referenciales (validaciones, mayúsculas, único parcial por
banco+número, Estado, "Mostrar inactivos", Reactivar con sus validaciones, baja bloqueada si está en uso, auditoría) y las conexiones con Entidad Emisora
y con la recaudación depositada. Usa datos ZZ (un banco, cuentas, caja, apertura, arqueo y recaudación) que borra POR ID."""
import sys, pathlib, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import psycopg2
from app import app
from tests._conexion_pruebas import Conexion
from app.dao.modulo_facturacion.cuenta_bancaria.CuentaBancariaDao import CuentaBancariaDao
from tests.facturacion._limpieza import borrar_auditoria

c = app.test_client()
fallos = []
CB, EM = '/api/v1/cuentas-bancarias', '/api/v1/entidades-emisoras'
stamp = str(int(time.time()))[-8:]


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


cx = Conexion().getConexion(); cx.autocommit = True; cu = cx.cursor()
cu.execute("SELECT u.id_usuario, r.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.activo ORDER BY 1")
usuarios = cu.fetchall()
ADMIN = next((u for u in usuarios if u[2] == 'Administrador'), None)
CAJERO = next((u for u in usuarios if u[2] == 'Cajero'), None)
RECEP = next((u for u in usuarios if u[2] == 'Recepcion'), None)
if not (ADMIN and CAJERO and RECEP):
    print('ABORTADO: se necesitan un Administrador, un Cajero y uno de Recepción.'); sys.exit(1)


def como(u):
    with c.session_transaction() as s:
        s['id_usuario'] = u[0]; s['id_rol'] = u[1]; s['nombre_rol'] = u[2]


ids = {'emisoras': [], 'cuentas': [], 'caja': None, 'ap': None, 'arqueo': None, 'rec': None}


def sql_en_txn(sql, params=()):
    k = Conexion().getConexion(); kc = k.cursor()
    try:
        kc.execute(sql, params); return None
    except psycopg2.Error as e:
        return getattr(getattr(e, 'diag', None), 'message_primary', None) or str(e).splitlines()[0]
    finally:
        k.rollback(); kc.close(); k.close()


try:
    # =====================================================================================================================
    # 1. ESQUEMA, DATOS INICIALES Y COMENTARIOS
    # =====================================================================================================================
    cu.execute("SELECT array_agg(column_name::text ORDER BY ordinal_position) FROM information_schema.columns WHERE table_name='cuenta_bancaria'")
    chk('cuenta_bancaria: columnas del pedido', cu.fetchone()[0] == ['id_cuenta_bancaria', 'id_entidad_emisora', 'tipo_cuenta', 'numero_cuenta', 'titular', 'activo'])
    cu.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='ck_cuenta_bancaria_tipo'")
    chk("tipo_cuenta: CHECK ('CORRIENTE','CAJA DE AHORRO')", "CORRIENTE" in cu.fetchone()[0])
    cu.execute("SELECT indexdef FROM pg_indexes WHERE indexname='ux_cuenta_bancaria_banco_numero_activo'")
    d = cu.fetchone(); chk('único PARCIAL sobre (banco, número) WHERE activo = true', d is not None and 'WHERE' in d[0] and 'activo' in d[0])
    cu.execute("SELECT is_nullable FROM information_schema.columns WHERE table_name='recaudacion_depositar' AND column_name='id_cuenta_bancaria'")
    chk('recaudacion_depositar.id_cuenta_bancaria existe (NULL) con su FK y el CHECK de DEPOSITADA',
        cu.fetchone()[0] == 'YES' and (cu.execute("SELECT count(*) FROM pg_constraint WHERE conname IN ('recaudacion_id_cuenta_bancaria_fkey','ck_recaudacion_cuenta')") or cu.fetchone()[0]) == 2)
    cu.execute("SELECT count(*) FROM pg_description WHERE objoid = 'cuenta_bancaria'::regclass AND objsubid = 0"); chk('la tabla tiene COMMENT ON', cu.fetchone()[0] == 1)
    cu.execute("""SELECT tipo_cuenta, e.descripcion, numero_cuenta, titular = (SELECT razon_social FROM empresa LIMIT 1)
                  FROM cuenta_bancaria c JOIN entidad_emisora e USING(id_entidad_emisora) WHERE numero_cuenta IN ('1020304050','2030405060') AND c.activo ORDER BY numero_cuenta""")
    chk('datos iniciales: CORRIENTE BANCO ITAÚ 1020304050 y CAJA DE AHORRO BANCO CONTINENTAL 2030405060, con la razón social como titular',
        cu.fetchall() == [('CORRIENTE', 'BANCO ITAÚ', '1020304050', True), ('CAJA DE AHORRO', 'BANCO CONTINENTAL', '2030405060', True)])
    cu.execute("SELECT array_agg(accion ORDER BY accion) FROM permisos p JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND ventana='cuentabancaria'")
    chk('el Cajero solo tiene "ver" sobre cuentabancaria', cu.fetchone()[0] == ['ver'])
    cu.execute("SELECT count(*) FROM permisos WHERE ventana='cuentabancaria' AND id_rol IN (SELECT id_rol FROM roles WHERE nombre_rol NOT IN ('Cajero','Administrador'))")
    chk('ningún otro rol recibió permisos por el seed', cu.fetchone()[0] == 0)

    # banco ZZ propio
    cu.execute("INSERT INTO entidad_emisora(descripcion, direccion, telefono, correo) VALUES ('ZZ BANCO CUENTAS', 'ZZ', '0981000000', 'zz@zz.com') RETURNING id_entidad_emisora"); BZ = cu.fetchone()[0]; ids['emisoras'].append(BZ)
    cu.execute("INSERT INTO entidad_emisora(descripcion, direccion, telefono, correo, activo) VALUES ('ZZ BANCO CUENTAS INACTIVO', 'ZZ', '0981000000', 'zz@zz.com', false) RETURNING id_entidad_emisora"); BI = cu.fetchone()[0]; ids['emisoras'].append(BI)
    NUM = '9' + stamp   # número de cuenta propio de este test

    # =====================================================================================================================
    # 2. PERMISOS
    # =====================================================================================================================
    como(RECEP)
    api('get', f'{CB}?inactivos=1', 403, nombre='Recepción: inactivos exige ver'); api('get', f'{CB}/1', 403, nombre='Recepción: detalle')
    api('post', CB, 403, {}, nombre='Recepción: alta'); api('put', f'{CB}/1', 403, {}, nombre='Recepción: editar'); api('delete', f'{CB}/1', 403, nombre='Recepción: anular')
    api('patch', f'{CB}/1/reactivar', 403, nombre='Recepción: reactivar')
    chk('vista: Recepción 403', c.get('/referenciales/cuenta-bancaria/cuenta-bancaria-index').status_code == 403)
    api('get', CB, 200, nombre='el lookup de cuentas activas queda con @require_login (alimenta combos)')
    como(CAJERO)
    api('get', f'{CB}?inactivos=1', 200, nombre='Cajero: ver (con inactivos)'); api('get', f'{CB}/1', 200, nombre='Cajero: detalle')
    api('post', CB, 403, {}, nombre='Cajero: no crea'); api('put', f'{CB}/1', 403, {}, nombre='Cajero: no edita'); api('delete', f'{CB}/1', 403, nombre='Cajero: no anula')
    api('patch', f'{CB}/1/reactivar', 403, nombre='Cajero: no reactiva')
    r = c.get('/referenciales/cuenta-bancaria/cuenta-bancaria-index'); chk('vista: Cajero 200 sin botón Agregar', r.status_code == 200 and b'id="btnAgregar"' not in r.data)

    # =====================================================================================================================
    # 3. ALTA, VALIDACIONES, DUPLICADOS
    # =====================================================================================================================
    como(ADMIN)
    r = c.get('/referenciales/cuenta-bancaria/cuenta-bancaria-index'); chk('vista: Administrador 200 con botón Agregar', r.status_code == 200 and b'id="btnAgregar"' in r.data)
    base = {'id_entidad_emisora': BZ, 'tipo_cuenta': 'corriente', 'numero_cuenta': NUM, 'titular': 'clínica zz s.a.'}
    def val(cuerpo, msg, camp, nombre, code=400):
        api('post', CB, code, cuerpo, nombre=f'validación: {nombre}', exacto=msg, campo=camp)
    def sin(k): d = dict(base); d.pop(k); return d
    val(sin('id_entidad_emisora'), 'Debe seleccionar un banco (entidad emisora).', 'id_entidad_emisora', 'sin banco')
    val({**base, 'tipo_cuenta': 'AHORRO'}, 'El tipo de cuenta debe ser Corriente o Caja de ahorro.', 'tipo_cuenta', 'tipo inválido')
    val(sin('tipo_cuenta'), 'El tipo de cuenta debe ser Corriente o Caja de ahorro.', 'tipo_cuenta', 'sin tipo')
    for malo in ('', '1234', 'abc12345', '12 345', '-12345', '1' * 31):
        val({**base, 'numero_cuenta': malo}, 'El número de cuenta debe tener entre 5 y 30 caracteres: solo números y guiones.', 'numero_cuenta', f'número {malo!r}')
    val(sin('titular'), 'El campo titular es obligatorio y no puede estar vacío.', 'titular', 'sin titular')
    val({**base, 'titular': 'a<b'}, "El campo titular solo puede contener letras, números, espacios y los símbolos . , - & ' / ( )", 'titular', 'titular con símbolos raros')
    val({**base, 'titular': 'x' * 81}, 'El campo titular no puede superar los 80 caracteres.', 'titular', 'titular largo')
    val({**base, 'id_entidad_emisora': 2147483000}, 'El banco seleccionado no existe o está anulado.', 'id_entidad_emisora', 'banco inexistente')
    val({**base, 'id_entidad_emisora': BI}, 'El banco seleccionado no existe o está anulado.', 'id_entidad_emisora', 'banco ANULADO')
    d = api('post', CB, 201, base, nombre='alta correcta'); C1 = d['data']['id_cuenta_bancaria']; ids['cuentas'].append(C1)
    chk('normaliza: tipo y titular en MAYÚSCULAS; descripción "CORRIENTE ZZ BANCO CUENTAS <n>"', (d['data']['tipo_cuenta'], d['data']['titular'], d['data']['descripcion']) == ('CORRIENTE', 'CLÍNICA ZZ S.A.', f'CORRIENTE ZZ BANCO CUENTAS {NUM}'))
    cu.execute("SELECT detalle, id_usuario FROM auditoria_cambios WHERE entidad='cuenta_bancaria' AND id_registro=%s AND accion='ALTA'", (C1,))
    f = cu.fetchone(); chk('auditoría ALTA con NOMBRES (banco) y el usuario de la sesión', f is not None and 'ZZ BANCO CUENTAS' in f[0] and NUM in f[0] and f[1] == ADMIN[0])
    val(base, 'Ya existe una cuenta activa de ese banco con ese número.', 'numero_cuenta', 'duplicado (banco + número)')
    d = api('post', CB, 201, {**base, 'id_entidad_emisora': 1, 'numero_cuenta': NUM}, nombre='el mismo número en OTRO banco sí se permite'); ids['cuentas'].append(d['data']['id_cuenta_bancaria']); C_OTRO = d['data']['id_cuenta_bancaria']

    # =====================================================================================================================
    # 4. LISTADO, EDICIÓN, BAJA Y REACTIVACIÓN
    # =====================================================================================================================
    r = api('get', CB, 200, nombre='listado por defecto')['data']
    chk('el listado trae solo activas, con el banco y el tipo', C1 in {x['id_cuenta_bancaria'] for x in r} and all(x['activo'] for x in r) and any(x['entidad_emisora'] == 'ZZ BANCO CUENTAS' for x in r))
    api('get', f'{CB}/{C1}', 200, nombre='detalle'); api('get', f'{CB}/2147483000', 404, nombre='detalle inexistente')
    d = api('put', f'{CB}/{C1}', 200, base, nombre='editar sin cambios', contiene='sin cambios')
    cu.execute("SELECT count(*) FROM auditoria_cambios WHERE entidad='cuenta_bancaria' AND id_registro=%s AND accion='MODIFICACION'", (C1,)); chk('una edición sin cambios no audita', cu.fetchone()[0] == 0)
    api('put', f'{CB}/{C1}', 200, {**base, 'titular': 'otro titular zz'}, nombre='editar el titular')
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='cuenta_bancaria' AND id_registro=%s AND accion='MODIFICACION'", (C1,))
    chk('auditoría MODIFICACION: solo lo que cambió ("Titular: A -> B")', cu.fetchone()[0] == 'Titular: CLÍNICA ZZ S.A. -> OTRO TITULAR ZZ')
    api('put', f'{CB}/{C1}', 400, {**base, 'id_entidad_emisora': 1}, nombre='editar a un duplicado (otro banco ya tiene ese número)', exacto='Ya existe una cuenta activa de ese banco con ese número.')
    api('put', f'{CB}/2147483000', 404, base, nombre='editar inexistente'); api('put', f'{CB}/{C1}', 400, {**base, 'tipo_cuenta': ''}, nombre='editar con datos inválidos')
    api('delete', f'{CB}/{C_OTRO}', 200, nombre='anular (baja lógica)', contiene='anulada correctamente')
    cu.execute("SELECT activo FROM cuenta_bancaria WHERE id_cuenta_bancaria=%s", (C_OTRO,)); chk('queda con activo = false (no se borró)', cu.fetchone()[0] is False)
    api('delete', f'{CB}/{C_OTRO}', 404, nombre='anular dos veces')
    chk('el listado por defecto la oculta', C_OTRO not in {x['id_cuenta_bancaria'] for x in api('get', CB, 200)['data']})
    chk('"inactivos=1" la muestra con Estado', any(x['id_cuenta_bancaria'] == C_OTRO and x['activo'] is False for x in api('get', f'{CB}?inactivos=1', 200)['data']))
    d = api('post', CB, 201, {**base, 'id_entidad_emisora': 1, 'numero_cuenta': NUM}, nombre='tras anular se puede crear otra igual (único parcial)'); C_NUEVA = d['data']['id_cuenta_bancaria']; ids['cuentas'].append(C_NUEVA)
    api('patch', f'{CB}/{C_OTRO}/reactivar', 409, nombre='reactivar con un duplicado activo', exacto='No se puede reactivar: ya existe una cuenta activa de ese banco con ese número.')
    api('delete', f'{CB}/{C_NUEVA}', 200, nombre='anular la nueva')
    d = api('patch', f'{CB}/{C_OTRO}/reactivar', 200, nombre='reactivar', contiene='reactivada correctamente')
    chk('queda activa', d['data']['activo'] is True)
    cu.execute("SELECT detalle FROM auditoria_cambios WHERE entidad='cuenta_bancaria' AND id_registro=%s AND accion='REACTIVACION'", (C_OTRO,)); chk('auditoría REACTIVACION', cu.fetchone() is not None)
    api('patch', f'{CB}/{C_OTRO}/reactivar', 409, nombre='reactivar una activa', exacto='La cuenta bancaria ya está activa.'); api('patch', f'{CB}/2147483000/reactivar', 404, nombre='reactivar inexistente')
    d = api('post', CB, 201, {**base, 'id_entidad_emisora': BZ, 'numero_cuenta': NUM + '1'}, nombre='cuenta para el banco inactivo'); C_B = d['data']['id_cuenta_bancaria']; ids['cuentas'].append(C_B)
    api('delete', f'{CB}/{C_B}', 200, nombre='anular'); cu.execute("UPDATE entidad_emisora SET activo = false WHERE id_entidad_emisora = %s", (BZ,))
    api('patch', f'{CB}/{C_B}/reactivar', 409, nombre='reactivar con el banco anulado', exacto='No se puede reactivar: el banco (entidad emisora) está anulado. Reactívelo primero.')
    cu.execute("UPDATE entidad_emisora SET activo = true WHERE id_entidad_emisora = %s", (BZ,))
    api('patch', f'{CB}/{C_B}/reactivar', 200, nombre='con el banco activo sí reactiva')

    # =====================================================================================================================
    # 5. CONEXIÓN CON ENTIDAD EMISORA
    # =====================================================================================================================
    api('delete', f'{EM}/{BZ}', 409, nombre='baja de un banco con cuentas bancarias activas', exacto='No se puede dar de baja, el banco tiene cuentas bancarias asociadas.')
    cu.execute("SELECT activo FROM entidad_emisora WHERE id_entidad_emisora = %s", (BZ,)); chk('el banco sigue activo', cu.fetchone()[0] is True)

    # =====================================================================================================================
    # 6. BAJA BLOQUEADA SI RECIBIÓ UN DEPÓSITO DE RECAUDACIÓN
    # =====================================================================================================================
    cu.execute("SELECT codigo FROM consultorio ORDER BY codigo LIMIT 1"); COD = cu.fetchone()[0]
    cu.execute("INSERT INTO caja(id_consultorio, descripcion) VALUES (%s, 'ZZ CAJA CUENTAS') RETURNING id_caja", (COD,)); ids['caja'] = cu.fetchone()[0]
    cu.execute("INSERT INTO apertura_cierre_caja(id_caja, id_usuario, monto_apertura, estado, fecha_cierre, total_recaudado, monto_cierre) VALUES (%s, %s, 0, 'CERRADA', now(), 0, 0) RETURNING id_apertura", (ids['caja'], RECEP[0]))
    ids['ap'] = cu.fetchone()[0]
    cu.execute("INSERT INTO arqueo_caja(id_apertura, id_usuario, total_sistema, total_contado, diferencia) VALUES (%s, %s, 0, 0, 0) RETURNING id_arqueo", (ids['ap'], ADMIN[0])); ids['arqueo'] = cu.fetchone()[0]
    cu.execute("INSERT INTO recaudacion_depositar(id_arqueo, id_usuario, monto_efectivo, monto_cheque, total) VALUES (%s, %s, 1000, 0, 1000) RETURNING id_recaudacion", (ids['arqueo'], ADMIN[0])); ids['rec'] = cu.fetchone()[0]
    chk('CHECK ck_recaudacion_cuenta: DEPOSITADA exige una cuenta bancaria',
        'ck_recaudacion_cuenta' in (sql_en_txn("UPDATE recaudacion_depositar SET estado='DEPOSITADA', fecha_deposito=CURRENT_DATE, numero_boleta='B1' WHERE id_recaudacion=%s", (ids['rec'],)) or ''))
    api('delete', f'{CB}/{C1}', 200, nombre='sin depósitos la cuenta se puede anular'); api('patch', f'{CB}/{C1}/reactivar', 200, nombre='y reactivar')
    cu.execute("UPDATE recaudacion_depositar SET estado='DEPOSITADA', id_cuenta_bancaria=%s, fecha_deposito=CURRENT_DATE, numero_boleta='ZZB1' WHERE id_recaudacion=%s", (C1, ids['rec']))
    with app.app_context():
        chk('esta_en_uso: la cuenta con una recaudación DEPOSITADA está en uso', CuentaBancariaDao().esta_en_uso(C1) == 'No se puede dar de baja, la cuenta bancaria está usada en el depósito de una recaudación.')
        chk('esta_en_uso: una cuenta sin depósitos no lo está', CuentaBancariaDao().esta_en_uso(C_OTRO) is False)
    api('delete', f'{CB}/{C1}', 409, nombre='baja de una cuenta con depósitos', exacto='No se puede dar de baja, la cuenta bancaria está usada en el depósito de una recaudación.')
    api('put', f'{CB}/{C1}', 409, {**base, 'numero_cuenta': NUM + '9'}, nombre='cambiar el número de una cuenta con depósitos', exacto='No se puede cambiar el banco, el tipo ni el número: la cuenta ya recibió depósitos de recaudación.', campo='numero_cuenta')
    api('put', f'{CB}/{C1}', 200, {**base, 'titular': 'titular nuevo zz'}, nombre='el titular sí se puede cambiar')
    cu.execute("SELECT activo FROM cuenta_bancaria WHERE id_cuenta_bancaria=%s", (C1,)); chk('la cuenta sigue activa', cu.fetchone()[0] is True)

finally:
    try:
        if ids['rec']:
            cu.execute("DELETE FROM recaudacion_depositar WHERE id_recaudacion=%s", (ids['rec'],))
        if ids['arqueo']:
            cu.execute("DELETE FROM arqueo_caja WHERE id_arqueo=%s", (ids['arqueo'],))
        if ids['ap']:
            cu.execute("DELETE FROM apertura_cierre_caja WHERE id_apertura=%s", (ids['ap'],))
        if ids['caja']:
            cu.execute("DELETE FROM caja WHERE id_caja=%s", (ids['caja'],))
        if ids['cuentas']:
            borrar_auditoria(cu, 'cuenta_bancaria', ids['cuentas'] + [C_OTRO] if 'C_OTRO' in globals() else ids['cuentas'])
            cu.execute("DELETE FROM cuenta_bancaria WHERE id_cuenta_bancaria = ANY(%s)", (ids['cuentas'],))
        if ids['emisoras']:
            borrar_auditoria(cu, 'entidad_emisora', ids['emisoras'])
            cu.execute("DELETE FROM entidad_emisora WHERE id_entidad_emisora = ANY(%s)", (ids['emisoras'],))
    except Exception as e:
        print('ERROR EN LA LIMPIEZA:', e); fallos.append('limpieza')

print()
print('FALLOS:', 'ninguno' if not fallos else fallos)
sys.exit(1 if fallos else 0)
