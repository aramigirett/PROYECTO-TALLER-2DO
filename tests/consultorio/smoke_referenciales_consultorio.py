"""Etapas 1 y 2 de la migración de Consultorio a Tabler: los 8 referenciales con baja lógica (Tipo Tratamiento, Tipo Insumo, Tipo
Procedimiento Médico, Medicamentos, Tipo Estudio, Tipo Análisis, Tipo Diagnóstico y Síntomas) contra el Estándar de referenciales.

Por cada uno: vista Tabler, validaciones (modo ampliado de descripción), alta/modificación/duplicados sin distinguir mayúsculas,
Estado / "Mostrar inactivos" / Reactivar, baja bloqueada si está en uso (409; los cancelados no cuentan), auditoría estructurada
en `auditoria_cambios` (módulo y JSON) y permisos. Datos `ZZ`: se borran por ID, junto con su auditoría.
"""
import re
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from app import app
from tests._conexion_pruebas import Conexion
from tests.facturacion._limpieza import borrar_auditoria

c = app.test_client()
fallos = []


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


def api(metodo, url, esperado, json=None, nombre=None, campo=None, contiene=None):
    f = getattr(c, metodo)
    r = f(url, json=json) if json is not None else f(url)
    d = r.get_json(silent=True) or {}
    ok = r.status_code == esperado
    if campo is not None:
        ok = ok and d.get('campo') == campo
    if contiene is not None:
        ok = ok and contiene in (d.get('error') or d.get('mensaje') or '')
    chk(f"{nombre or metodo + ' ' + url} -> {r.status_code}" + ('' if ok else f' {d}'), ok)
    return d


cx = Conexion().getConexion(); cu = cx.cursor()


def q(sql, p=()):
    cu.execute(sql, p)
    return cu.fetchall()


def sesion(id_usuario):
    id_rol, nombre = q("SELECT u.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.id_usuario=%s", (id_usuario,))[0]
    with c.session_transaction() as s:
        s.clear(); s['id_usuario'] = id_usuario; s['id_rol'] = id_rol; s['nombre_rol'] = nombre


ADMIN = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Administrador' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
CAJERO = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND u.activo ORDER BY 1 LIMIT 1")[0][0]

# datos reales en los que se cuelgan los registros "en uso" de prueba (no se modifican; los hijos ZZ se borran por ID)
TRAT = q("SELECT id_consulta_cab, id_paciente, id_medico, fecha_tratamiento FROM tratamientos ORDER BY 1 LIMIT 1")[0]
SESION = q("SELECT id_sesion, id_tratamiento FROM sesiones_tratamiento WHERE activo ORDER BY 1 LIMIT 1")[0]
RECETA = q("SELECT id_receta FROM recetas ORDER BY 1 LIMIT 1")[0][0]
CONSULTA = q("SELECT id_consulta_cab FROM consultas_cab WHERE activo ORDER BY 1 LIMIT 1")[0][0]
TIPO_TRAT_REAL = q("SELECT id_tipo_tratamiento FROM tipos_tratamiento WHERE activo ORDER BY 1 LIMIT 1")[0][0]
TIPO_DX_REAL = q("SELECT id_tipo_diagnostico FROM tipo_diagnostico WHERE activo ORDER BY 1 LIMIT 1")[0][0]
TIPO_PROC_REAL = q("SELECT id_tipo_procedimiento FROM tipo_procedimiento_medico ORDER BY 1 LIMIT 1")[0][0]

hijos = []   # (tabla, columna_pk, id) a borrar al final, en orden inverso


def hijo(tabla, pk, sql, params):
    cu.execute(sql + f" RETURNING {pk}", params)
    i = cu.fetchone()[0]; cx.commit(); hijos.append((tabla, pk, i)); return i


def usar_tratamiento(i, estado='pendiente'):
    return hijo('tratamientos', 'id_tratamiento',
                "INSERT INTO tratamientos(codigo, id_consulta_cab, id_paciente, id_medico, id_tipo_tratamiento, descripcion_tratamiento, "
                "fecha_tratamiento, estado) VALUES (%s,%s,%s,%s,%s,'ZZ',%s,%s)",
                (f'ZZ-{len(hijos)}', TRAT[0], TRAT[1], TRAT[2], i, TRAT[3], estado))


def usar_sesion_insumo(i):
    return hijo('sesion_insumos', 'id_sesion_insumo', "INSERT INTO sesion_insumos(id_sesion, id_insumo, cantidad) VALUES (%s,%s,1)", (SESION[0], i))


def usar_sesion(i):
    n = q("SELECT COALESCE(MAX(numero_sesion),0)+1 FROM sesiones_tratamiento WHERE id_tratamiento=%s", (SESION[1],))[0][0]
    return hijo('sesiones_tratamiento', 'id_sesion',
                "INSERT INTO sesiones_tratamiento(id_tratamiento, numero_sesion, id_tipo_procedimiento, fecha_sesion, descripcion_procedimiento) "
                "VALUES (%s,%s,%s,CURRENT_DATE,'ZZ')", (SESION[1], n, i))


def usar_receta(i):
    return hijo('receta_medicamento', 'id_receta_medicamento',
                "INSERT INTO receta_medicamento(id_receta, id_medicamento, dosis, frecuencia, duracion) VALUES (%s,%s,'ZZ','ZZ','ZZ')", (RECETA, i))


def usar_orden(tabla, pk, col):
    def f(i, estado='pendiente'):
        return hijo(tabla, pk, f"INSERT INTO {tabla}(id_consulta_cab, {col}, motivo_orden, fecha_orden, estado) VALUES (%s,%s,'ZZ',CURRENT_DATE,%s)",
                    (CONSULTA, i, estado))
    return f


def _crear_dx(id_tipo, id_sintoma):
    """Un diagnóstico vigente exige al menos un síntoma (trigger diferido): se inserta todo antes de confirmar."""
    cu.execute("WITH dx AS (INSERT INTO diagnosticos(codigo, id_consulta_cab, id_paciente, id_medico, id_tipo_diagnostico, descripcion_diagnostico, fecha_diagnostico) "
               "SELECT %s, id_consulta_cab, id_paciente, id_medico, %s, 'ZZ', CURRENT_DATE FROM consultas_cab WHERE id_consulta_cab=%s RETURNING id_diagnostico), "
               "sx AS (INSERT INTO diagnostico_sintoma(id_diagnostico, id_sintoma) SELECT id_diagnostico, %s FROM dx) SELECT id_diagnostico FROM dx",
               (f'ZZ-DX-{len(hijos)}', id_tipo, CONSULTA, id_sintoma))
    i = cu.fetchone()[0]; cx.commit(); hijos.append(('diagnosticos', 'id_diagnostico', i))
    return i


def usar_diagnostico(i):
    return _crear_dx(i, q("SELECT id_sintoma FROM sintoma WHERE activo ORDER BY 1 LIMIT 1")[0][0])


def usar_diagnostico_sintoma(i):
    return _crear_dx(TIPO_DX_REAL, i)


def anular_diagnostico_sintoma(i):
    anular_hijo('diagnosticos', 'id_diagnostico', hijos[-1][2])


def cancelar(tabla, pk, i):
    cu.execute(f"UPDATE {tabla} SET estado='cancelado' WHERE {pk}=%s", (i,)); cx.commit()


def anular_hijo(tabla, pk, i):
    cu.execute(f"UPDATE {tabla} SET activo=false WHERE {pk}=%s", (i,)); cx.commit()


ESPECS = [
    dict(nombre='Tipo Tratamiento', ventana='tipotratamiento', url='/api/v1/tipos-tratamiento', vista='/referenciales/tipo-tratamiento/tipo-tratamiento-index',
         tabla='tipos_tratamiento', pk='id_tipo_tratamiento', clave='descripcion', extras={'precio': 150000, 'iva': 10},
         extras2={'precio': 175000, 'iva': 5}, usar=usar_tratamiento,
         en_uso_ok=lambda i: cancelar('tratamientos', 'id_tratamiento', hijos[-1][2])),
    dict(nombre='Tipo Insumo', ventana='tipoinsumo', url='/api/v1/tipos-insumo', vista='/referenciales/tipo-insumo/tipo-insumo-index',
         tabla='insumos', pk='id_insumo', clave='descripcion', extras={'presentacion': 'caja x 10'}, extras2={'presentacion': 'FRASCO 50 ML'},
         usar=usar_sesion_insumo, en_uso_ok=lambda i: anular_hijo('sesion_insumos', 'id_sesion_insumo', hijos[-1][2])),
    dict(nombre='Tipo Procedimiento Médico', ventana='tipoprocedimientomedico', url='/api/v1/tipos-procedimiento-medico',
         vista='/referenciales/tipo-procedimiento-medico/tipo-procedimiento-medico-index', tabla='tipo_procedimiento_medico',
         pk='id_tipo_procedimiento', clave='descripcion', extras={}, extras2={}, usar=usar_sesion,
         en_uso_ok=lambda i: anular_hijo('sesiones_tratamiento', 'id_sesion', hijos[-1][2])),
    dict(nombre='Medicamentos', ventana='medicamento', url='/api/v1/medicamentos', vista='/referenciales/medicamento/medicamento-index',
         tabla='medicamentos', pk='id_medicamento', clave='nombre_comercial', extras={'presentacion': 'caja x 20 comprimidos'},
         extras2={'presentacion': None}, usar=usar_receta, en_uso_ok=lambda i: anular_hijo('receta_medicamento', 'id_receta_medicamento', hijos[-1][2])),
    dict(nombre='Tipo Estudio', ventana='tipoestudio', url='/api/v1/tipos-estudio', vista='/referenciales/tipo-estudio/tipo-estudio-index',
         tabla='tipo_estudio', pk='id_tipo_estudio', clave='descripcion', extras={}, extras2={},
         usar=usar_orden('orden_estudios', 'id_orden_estudio', 'id_tipo_estudio'),
         en_uso_ok=lambda i: cancelar('orden_estudios', 'id_orden_estudio', hijos[-1][2])),
    dict(nombre='Tipo Análisis', ventana='tipoanalisis', url='/api/v1/tipos-analisis', vista='/referenciales/tipo-analisis/tipo-analisis-index',
         tabla='tipo_analisis', pk='id_tipo_analisis', clave='descripcion', extras={}, extras2={},
         usar=usar_orden('orden_analisis', 'id_orden_analisis', 'id_tipo_analisis'),
         en_uso_ok=lambda i: cancelar('orden_analisis', 'id_orden_analisis', hijos[-1][2])),
    dict(nombre='Tipo Diagnóstico', ventana='tipodiagnostico', url='/api/v1/diagnosticos', vista='/referenciales/tipo-diagnostico/tipo-diagnostico-index',
         tabla='tipo_diagnostico', pk='id_tipo_diagnostico', clave='descripcion_diagnostico', extras={'tipo_diagnostico': 'patología dental'},
         extras2={'tipo_diagnostico': 'ZZ OTRA CATEGORÍA'}, usar=usar_diagnostico,
         en_uso_ok=lambda i: anular_hijo('diagnosticos', 'id_diagnostico', hijos[-1][2])),
    dict(nombre='Síntomas', ventana='sintoma', url='/api/v1/sintomas', vista='/referenciales/sintoma/sintoma-index',
         tabla='sintoma', pk='id_sintoma', clave='descripcion_sintoma', extras={}, extras2={}, usar=usar_diagnostico_sintoma,
         en_uso_ok=anular_diagnostico_sintoma),
]

creados = {}   # tabla -> ids ZZ (para borrar y limpiar la auditoría)


def auditoria(tabla, i):
    return q("SELECT accion, modulo, valores_anteriores, valores_nuevos, id_usuario, ip, detalle FROM auditoria_cambios "
             "WHERE entidad=%s AND id_registro=%s ORDER BY id_auditoria_cambio", (tabla, i))


try:
    sesion(ADMIN)
    for e in ESPECS:
        n, url, K, PK, T = e['nombre'], e['url'], e['clave'], e['pk'], e['tabla']
        print(f'\n=== {n}')
        creados[T] = set()
        base = {K: 'zz prueba (ñandú) 5% / ampliado', **e['extras']}

        # ---- vista Tabler ----
        r = c.get(e['vista'])
        txt = r.data.decode('utf-8', 'replace')
        chk(f'{n}: vista en Tabler con Estado, Mostrar inactivos y validadores compartidos',
            r.status_code == 200 and 'tabler' in txt.lower() and 'Mostrar inactivos' in txt and 'facturacion-listado.js' in txt
            and 'facturacion-validadores.js' in txt and 'Estado</th>' in txt and 'SB Admin' not in txt)
        chk(f'{n}: sin columna Código visible', 'Código' not in txt)

        # ---- validaciones ----
        api('post', url, 400, {**base, K: ''}, f'{n}: vacío', campo=K)
        api('post', url, 400, {**base, K: 'x' * 101}, f'{n}: 101 caracteres', campo=K)
        api('post', url, 400, {**base, K: 'a<b>'}, f'{n}: símbolo no permitido', campo=K)
        api('post', url, 400, {**base, K: '(EMPIEZA CON PARÉNTESIS)'}, f'{n}: debe empezar con letra o número', campo=K)
        api('post', url, 400, {**base, K: 'ZZ ; DROP'}, f'{n}: punto y coma no permitido', campo=K)
        if 'presentacion' in e['extras']:
            api('post', url, 400, {**base, 'presentacion': 'x' * 101}, f'{n}: presentación de 101', campo='presentacion')
            api('post', url, 400, {**base, 'presentacion': 'a<b'}, f'{n}: presentación con símbolo no permitido', campo='presentacion')
        if 'tipo_diagnostico' in e['extras']:
            for malo in ('', '   ', None, 'a<b', 'x' * 101):
                api('post', url, 400, {**base, 'tipo_diagnostico': malo}, f'{n}: tipo de diagnóstico inválido {malo!r:.20}', campo='tipo_diagnostico')
            api('post', url, 400, {k: v for k, v in base.items() if k != 'tipo_diagnostico'}, f'{n}: sin tipo de diagnóstico', campo='tipo_diagnostico')
        if 'precio' in e['extras']:
            for malo in (None, '', 0, -5, 'abc', 1.5, 10 ** 12):
                api('post', url, 400, {**base, 'precio': malo}, f'{n}: precio inválido {malo!r}', campo='precio',
                    contiene='El precio debe ser un número entero mayor a 0.')
            api('post', url, 400, {**base, 'iva': 7}, f'{n}: IVA 7', campo='iva')
            api('post', url, 400, {k: v for k, v in base.items() if k != 'iva'}, f'{n}: sin IVA', campo='iva')

        # ---- alta ----
        d = api('post', url, 201, base, f'{n}: alta')
        i = d['data'][PK]; creados[T].add(i)
        chk(f'{n}: guarda en MAYÚSCULAS y acepta tildes, Ñ, %, / y paréntesis', d['data'][K] == 'ZZ PRUEBA (ÑANDÚ) 5% / AMPLIADO')
        chk(f'{n}: el mensaje nombra el registro', 'ZZ PRUEBA (ÑANDÚ) 5% / AMPLIADO' in d['mensaje'] and 'agregado' in d['mensaje'])
        api('post', url, 400, {**base, K: ' zz  PRUEBA (ñandú) 5% /   ampliado '}, f'{n}: duplicado (otra capitalización y espacios)', campo=K)
        a = auditoria(T, i)
        chk(f'{n}: auditoría ALTA con módulo y valores nuevos (JSON)',
            len(a) == 1 and a[0][0] == 'ALTA' and a[0][1] == 'Referenciales Consultorio' and a[0][2] is None and a[0][3] and a[0][4] == ADMIN and a[0][5])
        d2 = api('get', f'{url}/{i}', 200, nombre=f'{n}: obtener')
        chk(f'{n}: el registro trae id, texto, activo y fecha', d2['data'][PK] == i and d2['data']['activo'] is True and ('fecha_registro' in d2['data']) == (T not in ('tipo_diagnostico', 'sintoma')))

        # ---- sin cambios / modificación ----
        api('put', f'{url}/{i}', 200, {**base}, f'{n}: sin cambios', contiene='sin cambios')
        chk(f'{n}: sin cambios no audita', len(auditoria(T, i)) == 1)
        nuevo = {K: 'zz prueba 2', **e['extras2']} if e['extras2'] else {K: 'zz prueba 2', **e['extras']}
        d3 = api('put', f'{url}/{i}', 200, nuevo, f'{n}: modificación')
        a = auditoria(T, i)
        chk(f'{n}: auditoría MODIFICACION con anterior y nuevo (solo lo que cambió)',
            len(a) == 2 and a[1][0] == 'MODIFICACION' and a[1][2] and a[1][3] and 'ZZ PRUEBA (ÑANDÚ) 5% / AMPLIADO' in str(a[1][2]) and 'ZZ PRUEBA 2' in str(a[1][3]))
        api('put', f'{url}/999999', 404, nuevo, f'{n}: modificar inexistente')
        d4 = api('post', url, 201, {**nuevo, K: 'zz otro'}, f'{n}: segundo registro'); j = d4['data'][PK]; creados[T].add(j)
        api('put', f'{url}/{j}', 400, {**nuevo, K: 'ZZ PRUEBA 2'}, f'{n}: modificar a un texto que ya existe', campo=K)

        # ---- listados: activos, inactivos, estado ----
        lista = api('get', url, 200, nombre=f'{n}: lista')['data']
        chk(f'{n}: la lista por defecto trae solo activos', all(x['activo'] for x in lista) and any(x[PK] == i for x in lista))

        # ---- baja y reactivación ----
        api('delete', f'{url}/{j}', 200, nombre=f'{n}: anular', contiene='anulado')
        a = auditoria(T, j)
        chk(f'{n}: auditoría BAJA con estado Inactivo', a[-1][0] == 'BAJA' and 'Inactivo' in str(a[-1][3]) and 'Activo' in str(a[-1][2]))
        chk(f'{n}: anulado sale de la lista por defecto', all(x[PK] != j for x in api('get', url, 200, nombre=f'{n}: lista 2')['data']))
        con = api('get', url + '?inactivos=1', 200, nombre=f'{n}: lista con inactivos')['data']
        fila = [x for x in con if x[PK] == j]
        chk(f'{n}: con inactivos trae el anulado con activo=false', len(fila) == 1 and fila[0]['activo'] is False)
        api('delete', f'{url}/{j}', 404, nombre=f'{n}: anular uno ya anulado')
        api('get', f'{url}/{j}', 404, nombre=f'{n}: obtener un anulado')
        api('put', f'{url}/{j}', 404, nuevo, f'{n}: modificar un anulado')
        # un registro anulado no bloquea crear otro igual (único parcial) y entonces no se puede reactivar
        d5 = api('post', url, 201, {**nuevo, K: 'zz otro'}, f'{n}: crear uno igual a un anulado'); k = d5['data'][PK]; creados[T].add(k)
        api('patch', f'{url}/{j}/reactivar', 409, nombre=f'{n}: reactivar con otro activo igual', contiene='ya existe')
        api('delete', f'{url}/{k}', 200, nombre=f'{n}: anular el duplicado')
        d6 = api('patch', f'{url}/{j}/reactivar', 200, nombre=f'{n}: reactivar', contiene='reactivado')
        chk(f'{n}: reactivado vuelve activo', d6['data']['activo'] is True)
        a = auditoria(T, j)
        chk(f'{n}: auditoría REACTIVACION con estado Activo', a[-1][0] == 'REACTIVACION' and 'Activo' in str(a[-1][3]) and 'Inactivo' in str(a[-1][2]))
        api('patch', f'{url}/{j}/reactivar', 409, nombre=f'{n}: reactivar uno ya activo', contiene='ya está activo')
        api('patch', f'{url}/999999/reactivar', 404, nombre=f'{n}: reactivar inexistente')

        # ---- en uso ----
        hid = e['usar'](i)
        d = api('delete', f'{url}/{i}', 409, nombre=f'{n}: baja bloqueada si está en uso', contiene='No se puede dar de baja')
        chk(f'{n}: el bloqueado sigue activo y sin BAJA auditada',
            q(f"SELECT activo FROM {T} WHERE {PK}=%s", (i,))[0][0] is True and all(x[0] != 'BAJA' for x in auditoria(T, i)))
        e['en_uso_ok'](i)
        api('delete', f'{url}/{i}', 200, nombre=f'{n}: anular cuando el uso ya no está vigente')

        # ---- como lo hace la vista: el id sale de la clave primaria declarada, y la baja/reactivación reales van por HTTP ----
        # (Flask devuelve el JSON con las claves ORDENADAS: la primera es 'activo'. Una vista que tome "la primera clave" pide /<recurso>/true -> 404.)
        pk_vista = re.search(r"const PK = '([a-z_]+)'", txt).group(1)
        api_vista = re.search(r"const API = '([^']+)'", txt).group(1)
        chk(f'{n}: la vista declara la clave primaria real ({PK}) y no adivina la primera clave del JSON', pk_vista == PK and 'Object.keys(f)' not in txt and 'Object.keys(registro)' not in txt)
        chk(f'{n}: la vista llama a la API registrada ({url})', api_vista == url)
        lista_real = api('get', url + '?inactivos=1', 200, nombre=f'{n}: lista real para armar las URL como la vista')['data']
        chk(f'{n}: la primera clave del JSON NO es la clave primaria (la trampa existe) y la clave primaria está en cada fila',
            list(lista_real[0])[0] != PK and all(PK in x for x in lista_real))
        adaptador = app.url_map.bind('localhost')

        def resuelve(metodo, ruta):
            try:
                adaptador.match(ruta, method=metodo)
                return True
            except Exception:
                return False
        chk(f'{n}: TODAS las filas reales (también los datos iniciales) resuelven GET/PUT/DELETE/PATCH-reactivar en url_map',
            all(resuelve(m, f'{api_vista}/{x[pk_vista]}' + ('/reactivar' if m == 'PATCH' else ''))
                for x in lista_real for m in ('GET', 'PUT', 'DELETE', 'PATCH')))
        chk(f'{n}: la URL con una clave no numérica ("true") NO existe (es lo que producía el 404)', not resuelve('DELETE', f'{api_vista}/true'))
        dv = api('post', url, 201, {**base, K: 'zz via vista'}, f'{n}: alta para la prueba de la vista')
        creados[T].add(dv['data'][PK])
        fila_vista = next(x for x in api('get', url, 200, nombre=f'{n}: lista')['data'] if x[K] == 'ZZ VIA VISTA')
        vid = fila_vista[pk_vista]
        api('get', f'{api_vista}/{vid}', 200, nombre=f'{n}: editar (GET por id de la vista)')
        api('delete', f'{api_vista}/{vid}', 200, nombre=f'{n}: ANULAR por HTTP con el id de la vista', contiene='anulado')
        chk(f'{n}: quedó inactivo en la base', q(f"SELECT activo FROM {T} WHERE {PK}=%s", (vid,))[0][0] is False)
        api('patch', f'{api_vista}/{vid}/reactivar', 200, nombre=f'{n}: REACTIVAR por HTTP con el id de la vista', contiene='reactivado')
        chk(f'{n}: quedó activo en la base', q(f"SELECT activo FROM {T} WHERE {PK}=%s", (vid,))[0][0] is True)

        # ---- permisos ----
        sesion(CAJERO)
        api('get', url, 200, nombre=f'{n}: Cajero: la lista (lookup) sigue disponible')
        api('get', url + '?inactivos=1', 403, nombre=f'{n}: Cajero: inactivos exige ver')
        api('get', f'{url}/{i}', 403, nombre=f'{n}: Cajero: obtener')
        api('post', url, 403, base, f'{n}: Cajero: alta')
        api('put', f'{url}/{i}', 403, nuevo, f'{n}: Cajero: modificar')
        api('delete', f'{url}/{k}', 403, nombre=f'{n}: Cajero: anular')
        api('patch', f'{url}/{i}/reactivar', 403, nombre=f'{n}: Cajero: reactivar')
        chk(f'{n}: Cajero: la vista da 403', c.get(e['vista']).status_code == 403)
        sesion(ADMIN)

    # ---------- específicos ----------
    print('\n=== específicos')
    d = api('post', '/api/v1/medicamentos', 201, {'nombre_comercial': 'zz amoxicilina/clavulánico 875/125 mg'}, 'Medicamentos: nombre de la consigna')
    creados['medicamentos'].add(d['data']['id_medicamento'])
    chk('Medicamentos: AMOXICILINA/CLAVULÁNICO 875/125 MG se guarda', d['data']['nombre_comercial'] == 'ZZ AMOXICILINA/CLAVULÁNICO 875/125 MG' and d['data']['presentacion'] is None)
    api('post', '/api/v1/medicamentos', 400, {'nombre_comercial': ''}, 'Medicamentos: mensaje con "nombre comercial"', campo='nombre_comercial', contiene='El campo nombre comercial es obligatorio')
    # el tipo cancelado no cuenta como uso, y una descripción con (PROFILAXIS) es válida
    d = api('post', '/api/v1/tipos-tratamiento', 201, {'descripcion': 'zz limpieza dental (profilaxis)', 'precio': 1, 'iva': 0}, 'Tipo Tratamiento: con paréntesis y IVA exenta')
    creados['tipos_tratamiento'].add(d['data']['id_tipo_tratamiento'])
    chk('Tipo Tratamiento: IVA 0 (Exenta) y precio 1 se guardan', d['data']['iva'] == 0 and d['data']['precio'] == 1)
    ids_trat = q("SELECT id_tipo_tratamiento, precio, iva FROM tipos_tratamiento WHERE descripcion='ZZ LIMPIEZA DENTAL (PROFILAXIS)'")
    chk('Tipo Tratamiento: el listado devuelve precio entero e iva', all(isinstance(x['precio'], int) and 'iva' in x for x in api('get', '/api/v1/tipos-tratamiento', 200, nombre='Tipo Tratamiento: lista')['data']))
    # Tipo Diagnóstico también se bloquea por un tratamiento no cancelado que lo use (aparte de los diagnósticos)
    d = api('post', '/api/v1/diagnosticos', 201, {'descripcion_diagnostico': 'zz dx para tratamiento', 'tipo_diagnostico': 'zz'}, 'Tipo Diagnóstico: alta para el tratamiento')
    td = d['data']['id_tipo_diagnostico']; creados['tipo_diagnostico'].add(td)
    tid = hijo('tratamientos', 'id_tratamiento',
               "INSERT INTO tratamientos(codigo, id_consulta_cab, id_paciente, id_medico, id_tipo_tratamiento, id_tipo_diagnostico, descripcion_tratamiento, "
               "fecha_tratamiento, estado) VALUES (%s,%s,%s,%s,%s,%s,'ZZ',%s,'pendiente')",
               (f'ZZ-TD-{len(hijos)}', TRAT[0], TRAT[1], TRAT[2], TIPO_TRAT_REAL, td, TRAT[3]))
    api('delete', f'/api/v1/diagnosticos/{td}', 409, nombre='Tipo Diagnóstico: baja bloqueada por un tratamiento', contiene='tratamientos')
    cancelar('tratamientos', 'id_tratamiento', tid)
    api('delete', f'/api/v1/diagnosticos/{td}', 200, nombre='Tipo Diagnóstico: con el tratamiento cancelado se puede anular')
    # los registros existentes quedaron en MAYÚSCULAS y los combos de otras pantallas siguen trayendo solo activos
    chk('Tipo Diagnóstico y Síntomas: todo lo cargado está en MAYÚSCULAS',
        q("SELECT count(*) FROM tipo_diagnostico WHERE descripcion_diagnostico <> UPPER(descripcion_diagnostico) OR tipo_diagnostico <> UPPER(tipo_diagnostico)")[0][0] == 0
        and q("SELECT count(*) FROM sintoma WHERE descripcion_sintoma <> UPPER(descripcion_sintoma)")[0][0] == 0)
    # los lookups de otras pantallas conservan sus claves
    lk = {'/api/v1/tipos-insumo': 'id_insumo', '/api/v1/tipos-procedimiento-medico': 'id_tipo_procedimiento', '/api/v1/medicamentos': 'id_medicamento',
          '/api/v1/tipos-estudio': 'id_tipo_estudio', '/api/v1/tipos-analisis': 'id_tipo_analisis', '/api/v1/tipos-tratamiento': 'id_tipo_tratamiento',
          '/api/v1/diagnosticos': 'id_tipo_diagnostico', '/api/v1/sintomas': 'id_sintoma'}
    for u_, pk_ in lk.items():
        datos = api('get', u_, 200, nombre=f'lookup {u_}')['data']
        chk(f'lookup {u_}: conserva la clave {pk_} y trae solo activos', all(pk_ in x and x['activo'] for x in datos))

finally:
    cx.rollback()
    for tabla, pk, i in reversed(hijos):
        if tabla == 'diagnosticos':
            cu.execute("DELETE FROM diagnostico_sintoma WHERE id_diagnostico=%s", (i,))
        cu.execute(f"DELETE FROM {tabla} WHERE {pk}=%s", (i,))
    for tabla, ids in creados.items():
        pk = {'tipo_diagnostico': 'id_tipo_diagnostico', 'sintoma': 'id_sintoma', 'tipos_tratamiento': 'id_tipo_tratamiento', 'insumos': 'id_insumo', 'tipo_procedimiento_medico': 'id_tipo_procedimiento',
              'medicamentos': 'id_medicamento', 'tipo_estudio': 'id_tipo_estudio', 'tipo_analisis': 'id_tipo_analisis'}[tabla]
        cu.execute(f"DELETE FROM {tabla} WHERE {pk} = ANY(%s)", (list(ids),))
        borrar_auditoria(cu, tabla, ids)
    cx.commit()

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
