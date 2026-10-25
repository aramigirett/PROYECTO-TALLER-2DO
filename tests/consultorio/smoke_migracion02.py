"""Regresión de la migración 02: permisos por id_menu, Diagnóstico y Odontograma que cuelgan de la Consulta,
funcionario obligatorio en la consulta y síntomas en diagnostico_sintoma.

Usa la base real. Reglas: datos creados por el test (consulta de la cita 11, diagnóstico, odontograma) se borran por ID y la
cita vuelve a su estado original; no se toca ninguna otra fila.
"""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from app import app
from tests._conexion_pruebas import Conexion
from tests.facturacion._limpieza import borrar_auditoria

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
# una cita real que se pueda consultar (cabecera activa y paciente, médico y consultorio activos; desde la etapa 3 el alta lo exige)
CITA = q("""SELECT cd.id_cita_detalle, cd.id_estado_cita FROM cita_detalle cd
            JOIN cita_cabecera cc ON cc.id_cita_cabecera = cd.id_cita_cabecera AND cc.estado = 'Activo'
            JOIN paciente p ON p.id_paciente = cc.id_paciente AND p.activo
            JOIN agenda_cabecera ac ON ac.id_agenda_cabecera = cc.id_agenda_cabecera
            JOIN medico m ON m.id_medico = ac.id_medico AND m.activo
            JOIN consultorio co ON co.codigo = ac.id_consultorio AND co.activo
            WHERE NOT EXISTS (SELECT 1 FROM consultas_cab c WHERE c.id_cita = cd.id_cita_detalle AND c.activo) ORDER BY 1 LIMIT 1""")[0]
ESTADO_CONFIRMADO = q("SELECT id_estado_cita FROM estado_cita WHERE descripcion='Confirmado'")[0][0]
TIPO_DX = q("SELECT id_tipo_diagnostico FROM tipo_diagnostico LIMIT 1")[0][0]
SINTOMAS = [r[0] for r in q("SELECT id_sintoma FROM sintoma ORDER BY 1 LIMIT 2")]
EST_DENTAL = q("SELECT id_estado_dental FROM estado_dental WHERE activo ORDER BY 1 LIMIT 1")[0][0]

c = app.test_client()
id_consulta = None
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
    chk('índice único parcial: un odontograma por consulta activa', bool(q("SELECT 1 FROM pg_indexes WHERE indexname='ux_odontograma_consulta_activo'")))
    chk('permisos conserva sus filas y todas con id_menu', q("SELECT count(*) FROM permisos")[0][0] >= 100 and q("SELECT count(*) FROM permisos WHERE id_menu IS NULL")[0][0] == 0)

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
    chk('usuario Médico: no registra consultas (403: Recepción las registra)', r.status_code == 403)
    chk('...y no se creó ninguna consulta', q("SELECT count(*) FROM consultas_cab WHERE id_cita=%s", (CITA[0],))[0][0] == 0)

    sesion(c, USR_FUNC[0])
    r = c.post('/api/v1/consultas', json={'id_cita': CITA[0], 'id_funcionario': 999, 'estado': 'programada'})
    chk(f'funcionario: registra la consulta (201) {r.get_json()}', r.status_code == 201)
    id_consulta = (r.get_json() or {}).get('data', {}).get('id_consulta_cab')
    chk('consultas_cab.id_funcionario sale de la sesión (se ignora el del body)',
        id_consulta is not None and q("SELECT id_funcionario FROM consultas_cab WHERE id_consulta_cab=%s", (id_consulta,))[0][0] == USR_FUNC[1])
    consulta = q("SELECT id_paciente, id_medico FROM consultas_cab WHERE id_consulta_cab=%s", (id_consulta,))[0]
    # (Los diagnósticos con síntomas y el odontograma por consulta —secciones 4 a 6 de la migración 02— tienen desde la etapa 4 sus propios tests:
    #  smoke_diagnostico.py y smoke_odontograma.py.)
finally:
    cx.rollback()
    if id_consulta:
        cu.execute("DELETE FROM consultas_cab WHERE id_consulta_cab=%s", (id_consulta,))
        borrar_auditoria(cu, 'consultas_cab', [id_consulta])   # la API de consultas audita: se borra solo lo que generó este test
    cu.execute("UPDATE cita_detalle SET id_estado_cita=%s WHERE id_cita_detalle=%s", (CITA[1], CITA[0]))
    cx.commit()
    cu.execute("SELECT count(*) FROM consultas_cab WHERE id_cita=%s", (CITA[0],))
    chk('limpieza: no quedó la consulta de prueba', cu.fetchone()[0] == 0)
    cu.execute("SELECT id_estado_cita FROM cita_detalle WHERE id_cita_detalle=%s", (CITA[0],))
    chk('limpieza: la cita volvió a su estado original', cu.fetchone()[0] == CITA[1])

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
