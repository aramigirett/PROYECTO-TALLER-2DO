"""Etapa 6 (commit 2): las vistas de Receta, Orden de Estudios y Orden de Análisis — acceso por rol, que sean Tabler (sin jQuery, DataTables ni SB Admin 2), quién ve los
botones de registrar / avanzar / cancelar, la plantilla común de las órdenes y la baja / el avance REALES por HTTP con el id que arma cada vista (el JSON de Flask viene con
las claves ordenadas: la vista nunca puede tomar "la primera clave" como id). Incluye el avance de una orden con la consulta ya finalizada.
"""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from app import app
from tests._conexion_pruebas import Conexion
from tests.consultorio._fixtures import Fixtures

fallos = []


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


cx = Conexion().getConexion(); cu = cx.cursor()
fx = Fixtures(cx)


def q(sql, p=()):
    cu.execute(sql, p)
    return cu.fetchall()


def cliente(id_usuario):
    c = app.test_client()
    id_rol, nombre = q("SELECT u.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.id_usuario=%s", (id_usuario,))[0]
    with c.session_transaction() as s:
        s['id_usuario'] = id_usuario; s['id_rol'] = id_rol; s['nombre_rol'] = nombre
    return c


RE = '/referenciales/receta/receta-index'
OE = '/referenciales/orden-estudio/orden-estudio-index'
OA = '/referenciales/orden-analisis/orden-analisis-index'
try:
    f_rec, u_rec = fx.recepcion()
    med, u_med = fx.medico()
    pac, cons = fx.paciente(), fx.consultorio()
    m1, t_est, t_ana = fx.medicamento(), fx.tipo_estudio(), fx.tipo_analisis()
    admin = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Administrador' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    cajero = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    C_REC, C_MED, C_ADM, C_CAJ = cliente(u_rec), cliente(u_med), cliente(admin), cliente(cajero)
    c1 = fx.registrar_consulta(fx.cita(med, pac, cons, f_rec), f_rec, 'en_proceso')

    print('\n=== Acceso')
    for url, nombre in ((RE, 'Recetas'), (OE, 'Orden de Estudios'), (OA, 'Orden de Análisis')):
        chk(f'{nombre}: sin sesión redirige al login', app.test_client().get(url).status_code == 302)
        for quien, c, esp in (('Médico', C_MED, 200), ('Administrador', C_ADM, 200), ('Recepción', C_REC, 403), ('Cajero', C_CAJ, 403)):
            chk(f'{nombre}: {quien} -> {esp}', c.get(url).status_code == esp)
        chk(f'{nombre}: el médico y el Administrador abren con ?consulta=', C_MED.get(f'{url}?consulta={c1}').status_code == 200 and C_ADM.get(f'{url}?consulta={c1}').status_code == 200)

    print('\n=== Son vistas Tabler (nada de SB Admin 2, jQuery ni DataTables)')
    pag = {'receta': C_MED.get(f'{RE}?consulta={c1}').get_data(as_text=True), 'estudios': C_MED.get(f'{OE}?consulta={c1}').get_data(as_text=True),
           'análisis': C_MED.get(f'{OA}?consulta={c1}').get_data(as_text=True)}
    for n, html in pag.items():
        bajo = html.lower()
        chk(f'{n}: Tabler, sin jQuery / DataTables / Bootstrap 4 / SB Admin / CDN',
            'tabler.min.css' in bajo and 'jquery' not in bajo and 'datatables' not in bajo and 'sb-admin' not in bajo and 'stackpath.bootstrapcdn' not in bajo and 'cdn.' not in bajo)
        chk(f'{n}: "Volver a la consulta", descarga de PDF y sin adivinar la primera clave', 'Volver a la consulta' in html and '/pdf' in html and 'Object.keys(f)' not in html)
    chk('claves primarias declaradas: receta, orden de estudios y de análisis', "const PK = 'id_receta'" in pag['receta'] and "const PK = 'id_orden_estudio'" in pag['estudios']
        and "const PK = 'id_orden_analisis'" in pag['análisis'])
    chk('las dos órdenes usan la misma plantilla pero cada una con su API y su tipo',
        "const API = '/api/v1/orden-estudios'" in pag['estudios'] and "const TIPO_COL = 'id_tipo_estudio'" in pag['estudios'] and "const API_TIPOS = '/api/v1/tipos-estudio'" in pag['estudios']
        and "const API = '/api/v1/orden-analisis'" in pag['análisis'] and "const TIPO_COL = 'id_tipo_analisis'" in pag['análisis'] and "const API_TIPOS = '/api/v1/tipos-analisis'" in pag['análisis'])

    print('\n=== Quién ve los botones')
    adm = {'receta': C_ADM.get(f'{RE}?consulta={c1}').get_data(as_text=True), 'estudios': C_ADM.get(f'{OE}?consulta={c1}').get_data(as_text=True),
           'análisis': C_ADM.get(f'{OA}?consulta={c1}').get_data(as_text=True)}
    chk('Receta: el médico ve "Nueva receta" y el formulario; el Administrador NO (lectura clínica)',
        'id="btnNuevo"' in pag['receta'] and 'id="formReceta"' in pag['receta'] and 'id="btnNuevo"' not in adm['receta'] and 'id="formReceta"' not in adm['receta'])
    chk('Receta: constantes de permiso', 'PUEDE_NUEVO = true' in pag['receta'] and 'PUEDE_ANULAR = true' in pag['receta'] and 'PUEDE_NUEVO = false' in adm['receta'] and 'PUEDE_ANULAR = false' in adm['receta'])
    for n in ('estudios', 'análisis'):
        chk(f'Orden de {n}: el médico ve "Nueva" y el formulario; el Administrador NO', 'id="btnNuevo"' in pag[n] and 'id="formOrden"' in pag[n] and 'id="btnNuevo"' not in adm[n] and 'id="formOrden"' not in adm[n])
        chk(f'Orden de {n}: constantes de permiso (médico: nuevo, anular y avanzar; Administrador ninguno)',
            all(x in pag[n] for x in ('PUEDE_NUEVO = true', 'PUEDE_ANULAR = true', 'PUEDE_AVANZAR = true')) and all(x in adm[n] for x in ('PUEDE_NUEVO = false', 'PUEDE_ANULAR = false', 'PUEDE_AVANZAR = false')))
        chk(f'Orden de {n}: avanza también con la consulta finalizada (la vista solo lo niega con la cancelada)', "f.estado_consulta !== 'cancelada'" in pag[n])

    print('\n=== Los ids que arman las vistas (listado, avance, cancelación)')
    d = C_MED.post('/api/v1/recetas', json={'id_consulta_cab': c1, 'indicaciones_generales': 'ZZ', 'medicamentos': [{'id_medicamento': m1, 'dosis': '1', 'frecuencia': '2', 'duracion': '3'}]})
    id_rec = d.get_json()['data']['id_receta']; fx.auditoria_de('recetas', id_rec)
    lista = C_MED.get(f'/api/v1/recetas?consulta={c1}').get_json()['data']
    chk('receta: la primera clave del JSON NO es el id y trae lo que usa la vista', list(lista[0])[0] != 'id_receta' and {'id_receta', 'numero', 'medicamentos', 'estado_consulta', 'fecha_receta'} <= set(lista[0]))
    chk('receta: el PDF con el id de la vista -> 200', C_MED.get(f"/api/v1/recetas/{lista[0]['id_receta']}/pdf").status_code == 200)
    chk('receta: anular con el id de la vista -> 200', C_MED.delete(f"/api/v1/recetas/{lista[0]['id_receta']}").status_code == 200)
    for nombre, url, pk, tipo_col, tipo, entidad in (('estudios', '/api/v1/orden-estudios', 'id_orden_estudio', 'id_tipo_estudio', t_est, 'orden_estudios'),
                                                     ('análisis', '/api/v1/orden-analisis', 'id_orden_analisis', 'id_tipo_analisis', t_ana, 'orden_analisis')):
        ids = []
        for _ in range(2):
            d = C_MED.post(url, json={'id_consulta_cab': c1, tipo_col: tipo, 'motivo_orden': 'ZZ'})
            ids.append(d.get_json()['data'][pk]); fx.auditoria_de(entidad, ids[-1])
        lista = C_MED.get(f'{url}?consulta={c1}').get_json()['data']
        chk(f'{nombre}: la primera clave del JSON NO es el id y trae lo que usa la vista', list(lista[0])[0] != pk and {pk, 'numero', 'tipo', 'estado', 'estado_consulta', 'fecha_orden', tipo_col} <= set(lista[0]))
        o_av, o_ca = lista[0][pk], lista[1][pk]
        chk(f'{nombre}: avanzar con el id de la vista -> 200', C_MED.put(f'{url}/{o_av}/estado').status_code == 200)
        chk(f'{nombre}: cancelar con el id de la vista -> 200', C_MED.delete(f'{url}/{o_ca}').status_code == 200)
        cu.execute("UPDATE consultas_cab SET estado='finalizada' WHERE id_consulta_cab=%s", (c1,)); cx.commit()
        lista = C_MED.get(f'{url}?consulta={c1}').get_json()['data']
        chk(f'{nombre}: con la consulta FINALIZADA el listado trae estado_consulta=finalizada y se sigue avanzando', lista[0]['estado_consulta'] == 'finalizada' and C_MED.put(f'{url}/{o_av}/estado').status_code == 200)
        cu.execute("UPDATE consultas_cab SET estado='en_proceso' WHERE id_consulta_cab=%s", (c1,)); cx.commit()
        chk(f'{nombre}: la URL con un id no numérico no existe', C_MED.put(f'{url}/true/estado').status_code == 404 and C_MED.delete(f'{url}/true').status_code == 404)
    chk('receta: la URL con un id no numérico no existe', C_MED.delete('/api/v1/recetas/true').status_code == 404)
    fx.auditoria_de('consultas_cab', c1)
finally:
    cx.rollback()
    fx.limpiar()

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
