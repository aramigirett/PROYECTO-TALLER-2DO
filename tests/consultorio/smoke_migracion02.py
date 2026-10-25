"""Regresión de la migración 02: permisos por id_menu, Diagnóstico y Odontograma que cuelgan de la Consulta,
funcionario obligatorio en la consulta y síntomas en diagnostico_sintoma.

Usa la base real. Reglas: datos creados por el test (consulta de la cita 11, diagnóstico, odontograma) se borran por ID y la
cita vuelve a su estado original; no se toca ninguna otra fila.
"""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from app import app
from tests._conexion_pruebas import Conexion

fallos = []


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


def sesion(c, id_usuario):
    cu.execute("SELECT u.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.id_usuario=%s", (id_usuario,))
    id_rol, nombre = cu.fetchone()
    with c.session_transaction() as s:
        s.clear()
        s['id_usuario'] = id_usuario; s['id_rol'] = id_rol; s['nombre_rol'] = nombre


cx = Conexion().getConexion(); cu = cx.cursor()


def q(sql, p=()):
    cu.execute(sql, p)
    return cu.fetchall()


# ---------- datos de referencia (reales, no se modifican) ----------
USR_FUNC = q("SELECT u.id_usuario, u.id_funcionario FROM usuarios u WHERE u.id_funcionario IS NOT NULL AND u.activo AND u.id_rol=(SELECT id_rol FROM roles WHERE nombre_rol='Recepcion') ORDER BY 1 LIMIT 1")[0]
USR_MEDICO = q("SELECT id_usuario FROM usuarios WHERE id_medico IS NOT NULL AND activo ORDER BY 1 LIMIT 1")[0][0]
USR_ADMIN = q("SELECT id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Administrador' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
USR_CAJERO = q("SELECT id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
CITA = q("SELECT cd.id_cita_detalle, cd.id_estado_cita FROM cita_detalle cd WHERE NOT EXISTS (SELECT 1 FROM consultas_cab c WHERE c.id_cita = cd.id_cita_detalle) ORDER BY 1 LIMIT 1")[0]
ESTADO_CONFIRMADO = q("SELECT id_estado_cita FROM estado_cita WHERE descripcion='Confirmado'")[0][0]
TIPO_DX = q("SELECT id_tipo_diagnostico FROM tipo_diagnostico LIMIT 1")[0][0]
SINTOMAS = [r[0] for r in q("SELECT id_sintoma FROM sintoma ORDER BY 1 LIMIT 2")]
EST_DENTAL = q("SELECT id_estado_dental FROM estado_dental WHERE activo ORDER BY 1 LIMIT 1")[0][0]

c = app.test_client()
id_consulta = id_dx = id_dx2 = None
odontos = []
try:
    # =============================================================================================================
    # 1. Esquema
    # =============================================================================================================
    def cols(t):
        return {r[0] for r in q("SELECT column_name FROM information_schema.columns WHERE table_name=%s", (t,))}
    chk('diagnosticos: id_consulta_cab sí; id_consulta_detalle y sintomas no',
        'id_consulta_cab' in cols('diagnosticos') and not ({'id_consulta_detalle', 'sintomas'} & cols('diagnosticos')))
    chk('odontograma: id_consulta_cab sí; id_funcionario no', 'id_consulta_cab' in cols('odontograma') and 'id_funcionario' not in cols('odontograma'))
    chk('estado_dental: activo sí; estado no', 'activo' in cols('estado_dental') and 'estado' not in cols('estado_dental'))
    chk('permisos: sin columna ventana, con id_menu', 'ventana' not in cols('permisos') and 'id_menu' in cols('permisos'))
    chk('consultas_cab.id_funcionario es NOT NULL',
        q("SELECT is_nullable FROM information_schema.columns WHERE table_name='consultas_cab' AND column_name='id_funcionario'")[0][0] == 'NO')
    chk('trigger de compatibilidad de permisos eliminado', not q("SELECT 1 FROM pg_trigger WHERE tgname='trg_permisos_resolver_menu'"))
    chk('índice único parcial: un odontograma por consulta', bool(q("SELECT 1 FROM pg_indexes WHERE indexname='ux_odontograma_consulta_vigente'")))
    chk('permisos conserva sus 339+ filas y todas con id_menu', q("SELECT count(*) FROM permisos")[0][0] >= 339 and q("SELECT count(*) FROM permisos WHERE id_menu IS NULL")[0][0] == 0)

    # =============================================================================================================
    # 2. Permisos por id_menu (PermisoDao + decoradores + menú)
    # =============================================================================================================
    with app.app_context():
        from app.dao.modulo_seguridad.PermisoDao import PermisoDao
        pd = PermisoDao()
        rol_recep = q("SELECT id_rol FROM roles WHERE nombre_rol='Recepcion'")[0][0]
        ya = ('sintoma', 'anular') in pd.getPermisosDeRol(rol_recep)
        try:
            if ya:
                chk('PermisoDao.revocar', pd.revocar(rol_recep, 'sintoma', 'anular') and ('sintoma', 'anular') not in pd.getPermisosDeRol(rol_recep))
                chk('PermisoDao.otorgar', pd.otorgar(rol_recep, 'sintoma', 'anular') and ('sintoma', 'anular') in pd.getPermisosDeRol(rol_recep))
            else:
                chk('PermisoDao.otorgar', pd.otorgar(rol_recep, 'sintoma', 'anular') and ('sintoma', 'anular') in pd.getPermisosDeRol(rol_recep))
                chk('PermisoDao.revocar', pd.revocar(rol_recep, 'sintoma', 'anular') and ('sintoma', 'anular') not in pd.getPermisosDeRol(rol_recep))
        finally:
            if ya:
                pd.otorgar(rol_recep, 'sintoma', 'anular')
            else:
                pd.revocar(rol_recep, 'sintoma', 'anular')
        chk('PermisoDao.otorgar con una ventana sin menú devuelve False', pd.otorgar(rol_recep, 'zz_no_existe', 'ver') is False)

    sesion(c, USR_ADMIN)
    from app.rutas.modulo_seguridad.menu_catalog import CATALOGO_MENU
    vistas = {}
    with app.test_request_context():
        from flask import url_for
        for e in CATALOGO_MENU:
            if e.get('endpoint'):
                try:
                    vistas[e['ventana']] = url_for(e['endpoint'])
                except Exception:
                    pass
    malas = [(v, c.get(u).status_code) for v, u in vistas.items() if c.get(u).status_code != 200]
    chk(f'Administrador: abre todas las pantallas del menú ({len(vistas)}) sin 403/500: {malas}', not malas)

    sesion(c, USR_CAJERO)
    r = c.get('/referenciales/diagnosticos-medicos/diagnostico-index')
    chk('Cajero: la URL directa de Diagnósticos se rechaza (403)', r.status_code == 403)
    r = c.get('/referenciales/odontograma/odontograma-index')
    chk('Cajero: la URL directa de Odontograma se rechaza (403)', r.status_code == 403)
    r = c.get('/api/v1/diagnosticos-medicos')
    chk('Cajero: la API de Diagnósticos se rechaza (403)', r.status_code == 403)
    r = c.post('/api/v1/odontogramas', json={'id_consulta_cab': 1})
    chk('Cajero: no puede crear odontogramas (403)', r.status_code == 403)
    r = c.get('/referenciales/venta/venta-index')
    chk('Cajero: sí abre Ventas (Facturación)', r.status_code == 200)

    # =============================================================================================================
    # 3. Registrar Consulta: el funcionario sale de la sesión
    # =============================================================================================================
    cu.execute("UPDATE cita_detalle SET id_estado_cita=%s WHERE id_cita_detalle=%s", (ESTADO_CONFIRMADO, CITA[0])); cx.commit()

    sesion(c, USR_MEDICO)
    r = c.post('/api/v1/consultas', json={'id_cita': CITA[0], 'id_funcionario': 999})
    chk('usuario Médico (sin funcionario): no puede registrar la consulta (403)', r.status_code == 403)
    chk('...con el mensaje "Solo un funcionario puede registrar consultas."', (r.get_json() or {}).get('error') == 'Solo un funcionario puede registrar consultas.')
    chk('...y no se creó ninguna consulta', q("SELECT count(*) FROM consultas_cab WHERE id_cita=%s", (CITA[0],))[0][0] == 0)

    sesion(c, USR_FUNC[0])
    r = c.post('/api/v1/consultas', json={'id_cita': CITA[0], 'id_funcionario': 999, 'estado': 'programada'})
    chk(f'funcionario: registra la consulta (201) {r.get_json()}', r.status_code == 201)
    id_consulta = (r.get_json() or {}).get('data', {}).get('id_consulta_cab')
    chk('consultas_cab.id_funcionario sale de la sesión (se ignora el del body)',
        id_consulta is not None and q("SELECT id_funcionario FROM consultas_cab WHERE id_consulta_cab=%s", (id_consulta,))[0][0] == USR_FUNC[1])
    consulta = q("SELECT id_paciente, id_medico FROM consultas_cab WHERE id_consulta_cab=%s", (id_consulta,))[0]

    # =============================================================================================================
    # 4. Diagnóstico desde la Consulta, con síntomas
    # =============================================================================================================
    sesion(c, USR_ADMIN)
    base = {'id_consulta_cab': id_consulta, 'id_tipo_diagnostico': TIPO_DX, 'descripcion_diagnostico': 'ZZ CARIES DE PRUEBA',
            'fecha_diagnostico': '2026-10-24', 'pieza_dental': '18', 'sintomas': SINTOMAS,
            'id_paciente': 999999, 'id_medico': 999999}
    r = c.post('/api/v1/diagnosticos-medicos', json=base)
    chk(f'diagnóstico: alta (201) {r.get_json()}', r.status_code == 201)
    id_dx = (r.get_json() or {}).get('data', {}).get('id_diagnostico')
    fila = q("SELECT id_consulta_cab, id_paciente, id_medico, id_usuario_registro FROM diagnosticos WHERE id_diagnostico=%s", (id_dx,))[0]
    chk('paciente y médico se derivan de la consulta (se ignora lo que mande el navegador)', fila[:3] == (id_consulta, consulta[0], consulta[1]))
    chk('queda el usuario que registró', fila[3] == USR_ADMIN)
    chk('los síntomas quedan en diagnostico_sintoma', sorted(x[0] for x in q("SELECT id_sintoma FROM diagnostico_sintoma WHERE id_diagnostico=%s", (id_dx,))) == sorted(SINTOMAS))
    d = c.get(f'/api/v1/diagnosticos-medicos/{id_dx}').get_json()['data']
    chk('GET devuelve los síntomas como lista {id_sintoma, descripcion_sintoma}', sorted(s['id_sintoma'] for s in d['sintomas']) == sorted(SINTOMAS) and all(s['descripcion_sintoma'] for s in d['sintomas']))
    chk('GET devuelve id_consulta_cab y no id_consulta_detalle', d['id_consulta_cab'] == id_consulta and 'id_consulta_detalle' not in d)
    lista = c.get('/api/v1/diagnosticos-medicos').get_json()['data']
    chk('el listado trae el diagnóstico con sus síntomas', any(x['id_diagnostico'] == id_dx and len(x['sintomas']) == len(SINTOMAS) for x in lista))
    porc = c.get(f'/api/v1/diagnosticos-medicos/consulta/{id_consulta}').get_json()['data']
    chk('GET por consulta (lo usan Tratamiento, Receta, Órdenes y Justificativo) lo encuentra', any(x['id_diagnostico'] == id_dx for x in porc))
    chk('ConsultaDao.tiene_diagnostico lo ve (anular consulta con diagnóstico se bloquea)',
        c.delete(f'/api/v1/consultas/{id_consulta}').status_code == 409)

    r = c.post('/api/v1/diagnosticos-medicos', json={**base, 'sintomas': [SINTOMAS[0], 999999]})
    chk('síntoma inexistente -> 400 y no queda nada a medias', r.status_code == 400 and q("SELECT count(*) FROM diagnosticos WHERE id_consulta_cab=%s", (id_consulta,))[0][0] == 1)
    r = c.post('/api/v1/diagnosticos-medicos', json={**base, 'sintomas': 'dolor'})
    chk('síntomas que no son una lista -> 400', r.status_code == 400)
    r = c.post('/api/v1/diagnosticos-medicos', json={**base, 'id_consulta_cab': 999999})
    chk('consulta inexistente -> 404', r.status_code == 404)
    r = c.post('/api/v1/diagnosticos-medicos', json={k: v for k, v in base.items() if k != 'id_consulta_cab'})
    chk('sin consulta -> 400', r.status_code == 400)
    r = c.post('/api/v1/diagnosticos-medicos', json={**base, 'sintomas': []})
    chk('sin síntomas es válido (opcional) -> 201', r.status_code == 201)
    id_dx2 = (r.get_json() or {}).get('data', {}).get('id_diagnostico')
    chk('...y los códigos DX- son distintos', q("SELECT count(DISTINCT codigo) FROM diagnosticos WHERE id_diagnostico IN (%s,%s)", (id_dx, id_dx2))[0][0] == 2)

    from app.dao.referenciales_consultorio.sintomas.SintomasDao import SintomaDao
    with app.app_context():
        chk('Síntomas: estaEnUso ve diagnostico_sintoma (no se puede borrar un síntoma usado)', SintomaDao().estaEnUso(SINTOMAS[0]) is True)
    r = c.delete(f'/api/v1/sintomas/{SINTOMAS[0]}')
    chk('DELETE de un síntoma usado en un diagnóstico -> 409', r.status_code == 409)

    r = c.get(f'/referenciales/diagnosticos-medicos/diagnostico-index?consulta={id_consulta}&paciente={consulta[0]}&medico={consulta[1]}')
    html = r.get_data(as_text=True)
    chk('vista de Diagnósticos carga con la consulta y el selector de síntomas', r.status_code == 200 and 'id="id_consulta_cab"' in html and 'sintomasLista' in html and 'id_consulta_detalle' not in html)

    # =============================================================================================================
    # 5. Odontograma desde la Consulta (uno por consulta, con precarga)
    # =============================================================================================================
    r = c.get(f'/referenciales/odontograma/odontograma-index?consulta={id_consulta}')
    chk('vista de Odontograma carga con ?consulta=', r.status_code == 200 and 'id="id_consulta_cab"' in r.get_data(as_text=True))
    r = c.get('/api/v1/estados-dentales')
    chk('estados dentales (columna activo) -> 200 y trae activo', r.status_code == 200 and r.get_json()['data'] and 'activo' in r.get_json()['data'][0])
    r = c.post('/api/v1/odontogramas', json={'id_paciente': consulta[0], 'id_medico': consulta[1]})
    chk('sin id_consulta_cab -> 400', r.status_code == 400)
    r = c.post('/api/v1/odontogramas', json={'id_consulta_cab': 999999})
    chk('consulta inexistente -> 404', r.status_code == 404)
    r = c.post('/api/v1/odontogramas', json={'id_consulta_cab': id_consulta, 'id_paciente': 999999, 'id_medico': 999999, 'observaciones': 'ZZ',
                                              'detalles': [{'diente': 11, 'estado': EST_DENTAL, 'superficie': 'O'}, {'diente': 12, 'estado': EST_DENTAL, 'superficie': 'V'}]})
    chk(f'odontograma: alta (201) {r.get_json()}', r.status_code == 201)
    od = (r.get_json() or {}).get('data', {}).get('id_odontograma')
    odontos.append(od)
    fila = q("SELECT id_paciente, id_medico, id_consulta_cab, estado FROM odontograma WHERE id_odontograma=%s", (od,))[0]
    chk('paciente y médico se derivan de la consulta', fila == (consulta[0], consulta[1], id_consulta, 'Activo'))
    chk('se guardaron los 2 detalles', q("SELECT count(*) FROM odontograma_detalle WHERE id_odontograma=%s", (od,))[0][0] == 2)
    r = c.post('/api/v1/odontogramas', json={'id_consulta_cab': id_consulta})
    chk('un segundo odontograma para la misma consulta -> 409', r.status_code == 409)
    chk('GET /validar-consulta lo confirma', c.get(f'/api/v1/odontogramas/validar-consulta/{id_consulta}').get_json()['data']['existe_odontograma'] is True)
    lista = c.get('/api/v1/odontogramas').get_json()['data']
    chk('el listado trae id_consulta_cab (y no id_funcionario)', any(x['id_odontograma'] == od and x['id_consulta_cab'] == id_consulta and 'id_funcionario' not in x for x in lista))
    chk('GET por paciente funciona (columna corregida)', c.get(f'/api/v1/odontogramas/paciente/{consulta[0]}').status_code == 200)

    # precarga: el vigente del paciente es el de su última consulta; para otra consulta del mismo paciente se carga ese estado
    otra = q("SELECT id_consulta_cab FROM consultas_cab WHERE id_paciente=%s AND id_consulta_cab<>%s AND activo ORDER BY id_consulta_cab LIMIT 1", (consulta[0], id_consulta))
    if otra:
        r = c.get(f'/api/v1/odontogramas/precarga/{otra[0][0]}')
        dets = (r.get_json() or {}).get('data', {}).get('detalles', [])
        chk('precarga: trae el estado del odontograma anterior del paciente', r.status_code == 200 and len(dets) == 2)
    r = c.get('/api/v1/odontogramas/precarga/999999')
    chk('precarga de una consulta inexistente -> 404', r.status_code == 404)
    r = c.get(f'/api/v1/odontogramas/precarga/{id_consulta}')
    chk('precarga de la propia consulta no se incluye a sí misma', r.status_code == 200 and all(d.get('id_odontograma') != od for d in r.get_json()['data']['detalles']))

    # anular libera la consulta para uno nuevo (único parcial)
    r = c.delete(f'/api/v1/odontogramas/{od}')
    chk('anular el odontograma -> 200 (baja lógica)', r.status_code == 200 and q("SELECT estado FROM odontograma WHERE id_odontograma=%s", (od,))[0][0] == 'Inactivo')
    r = c.post('/api/v1/odontogramas', json={'id_consulta_cab': id_consulta})
    chk('anulado el anterior, se puede crear otro para la misma consulta (201)', r.status_code == 201)
    odontos.append((r.get_json() or {}).get('data', {}).get('id_odontograma'))

    # =============================================================================================================
    # 6. Consulta finalizada: no se agregan diagnósticos ni odontogramas
    # =============================================================================================================
    cu.execute("UPDATE consultas_cab SET estado='finalizada' WHERE id_consulta_cab=%s", (id_consulta,)); cx.commit()
    r = c.post('/api/v1/diagnosticos-medicos', json=base)
    chk('consulta finalizada: no admite diagnósticos (409)', r.status_code == 409)
    cu.execute("UPDATE odontograma SET estado='Inactivo', activo=false WHERE id_odontograma=%s", (odontos[-1],)); cx.commit()
    r = c.post('/api/v1/odontogramas', json={'id_consulta_cab': id_consulta})
    chk('consulta finalizada: no admite odontogramas (409)', r.status_code == 409)
finally:
    cx.rollback()
    for od in odontos:
        if od:
            cu.execute("DELETE FROM odontograma_detalle WHERE id_odontograma=%s", (od,))
            cu.execute("DELETE FROM odontograma WHERE id_odontograma=%s", (od,))
    for dx in (id_dx, id_dx2):
        if dx:
            cu.execute("DELETE FROM diagnostico_sintoma WHERE id_diagnostico=%s", (dx,))
            cu.execute("DELETE FROM diagnosticos WHERE id_diagnostico=%s", (dx,))
    if id_consulta:
        cu.execute("DELETE FROM consultas_cab WHERE id_consulta_cab=%s", (id_consulta,))
    cu.execute("UPDATE cita_detalle SET id_estado_cita=%s WHERE id_cita_detalle=%s", (CITA[1], CITA[0]))
    cx.commit()
    cu.execute("SELECT count(*) FROM consultas_cab WHERE id_cita=%s", (CITA[0],))
    chk('limpieza: no quedó la consulta de prueba', cu.fetchone()[0] == 0)
    cu.execute("SELECT id_estado_cita FROM cita_detalle WHERE id_cita_detalle=%s", (CITA[0],))
    chk('limpieza: la cita volvió a su estado original', cu.fetchone()[0] == CITA[1])

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
