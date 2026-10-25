"""Etapa 5 (commit 2): las vistas de Tratamientos y de Sesiones — acceso por rol, que sean Tabler (sin jQuery, DataTables ni SB Admin 2), quién ve los botones de
registrar / finalizar / anular, el vínculo entre las dos pantallas y la baja REAL por HTTP con el id que arma cada vista (el JSON de Flask viene con las claves
ordenadas: la vista nunca puede tomar "la primera clave" como id). Incluye el recorrido de un tratamiento de varias visitas.
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


TR = '/referenciales/tratamiento/tratamiento-index'
SE = '/referenciales/sesion-tratamiento/sesion-tratamiento-index'
try:
    f_rec, u_rec = fx.recepcion()
    med, u_med = fx.medico()
    pac, cons = fx.paciente(), fx.consultorio()
    tipo, proc, insumo = fx.tipo_tratamiento(), fx.tipo_procedimiento(), fx.insumo()
    admin = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Administrador' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    cajero = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    C_REC, C_MED, C_ADM, C_CAJ = cliente(u_rec), cliente(u_med), cliente(admin), cliente(cajero)
    c1 = fx.registrar_consulta(fx.cita(med, pac, cons, f_rec), f_rec, 'en_proceso')
    c2 = fx.registrar_consulta(fx.cita(med, pac, cons, f_rec), f_rec, 'en_proceso')

    print('\n=== Acceso')
    for url, nombre in ((TR, 'Tratamientos'), (SE, 'Sesiones')):
        chk(f'{nombre}: sin sesión redirige al login', app.test_client().get(url).status_code == 302)
        for quien, c, esp in (('Médico', C_MED, 200), ('Administrador', C_ADM, 200), ('Recepción', C_REC, 403), ('Cajero', C_CAJ, 403)):
            chk(f'{nombre}: {quien} -> {esp}', c.get(url).status_code == esp)
    chk('Tratamientos: el médico y el Administrador abren con ?consulta=', C_MED.get(f'{TR}?consulta={c1}').status_code == 200 and C_ADM.get(f'{TR}?consulta={c1}').status_code == 200)

    print('\n=== Son vistas Tabler (nada de SB Admin 2, jQuery ni DataTables)')
    paginas = {'tratamientos': C_MED.get(f'{TR}?consulta={c1}').get_data(as_text=True), 'sesiones': C_MED.get(f'{SE}?tratamiento=1&consulta={c1}').get_data(as_text=True)}
    for n, html in paginas.items():
        bajo = html.lower()
        chk(f'{n}: Tabler, sin jQuery / DataTables / Bootstrap 4 / SB Admin / CDN',
            'tabler.min.css' in bajo and 'jquery' not in bajo and 'datatables' not in bajo and 'sb-admin' not in bajo and 'stackpath.bootstrapcdn' not in bajo and 'cdn.' not in bajo)
    chk('tratamientos y sesiones declaran su clave primaria y no adivinan la primera clave',
        "const PK = 'id_tratamiento'" in paginas['tratamientos'] and "const PK = 'id_sesion'" in paginas['sesiones'] and 'Object.keys(f)' not in paginas['tratamientos'] + paginas['sesiones'])
    chk('cada pantalla enlaza a la otra con las URL reales', SE in paginas['tratamientos'] and TR in paginas['sesiones'])
    chk('"Volver a la consulta" apunta al detalle de la consulta', '/referenciales/consulta/consulta-detalle/' in paginas['tratamientos'] and 'Volver a la consulta' in paginas['sesiones'])

    print('\n=== Quién ve los botones')
    adm = {'tratamientos': C_ADM.get(f'{TR}?consulta={c1}').get_data(as_text=True), 'sesiones': C_ADM.get(f'{SE}?tratamiento=1&consulta={c1}').get_data(as_text=True)}
    chk('Tratamientos: el médico ve "Nuevo tratamiento" y su formulario; el Administrador NO (lectura clínica)',
        'id="btnNuevo"' in paginas['tratamientos'] and 'id="formTr"' in paginas['tratamientos'] and 'id="btnNuevo"' not in adm['tratamientos'] and 'id="formTr"' not in adm['tratamientos'])
    chk('Tratamientos: constantes de permiso (médico verdadero, Administrador falso)', 'PUEDE_NUEVO = true' in paginas['tratamientos'] and 'PUEDE_ANULAR = true' in paginas['tratamientos']
        and 'PUEDE_FINALIZAR = true' in paginas['tratamientos'] and 'PUEDE_NUEVO = false' in adm['tratamientos'] and 'PUEDE_ANULAR = false' in adm['tratamientos']
        and 'PUEDE_FINALIZAR = false' in adm['tratamientos'])
    chk('Sesiones: el médico ve "Nueva sesión", "Finalizar tratamiento" y el formulario; el Administrador NO',
        all(x in paginas['sesiones'] for x in ('id="btnNuevo"', 'id="btnFinalizar"', 'id="formSes"')) and not any(x in adm['sesiones'] for x in ('id="btnNuevo"', 'id="btnFinalizar"', 'id="formSes"')))
    chk('Sesiones: constantes de permiso (médico verdadero, Administrador falso)', 'PUEDE_NUEVO = true' in paginas['sesiones'] and 'PUEDE_ANULAR = true' in paginas['sesiones']
        and 'PUEDE_NUEVO = false' in adm['sesiones'] and 'PUEDE_ANULAR = false' in adm['sesiones'])

    print('\n=== Tratamiento de varias visitas, con los ids que arman las vistas')
    d = C_MED.post('/api/v1/tratamientos', json={'id_consulta_cab': c1, 'id_tipo_tratamiento': tipo, 'descripcion_tratamiento': 'ZZ vista'})
    t = d.get_json()['data']['id_tratamiento']
    fx.auditoria_de('tratamientos', t)
    lista = C_MED.get(f'/api/v1/tratamientos?consulta={c1}&por_pagina=100').get_json()['data']
    chk('la primera clave del JSON de Flask NO es el id del tratamiento y trae los campos que usa la vista',
        list(lista[0])[0] != 'id_tratamiento' and {'id_tratamiento', 'tipo_tratamiento', 'estado', 'cantidad_sesiones', 'facturado', 'estado_consulta', 'id_paciente'} <= set(lista[0]))
    resumen = C_MED.get(f'/api/v1/consultas/{c1}/resumen').get_json()['data']
    chk('el resumen de la consulta trae id_paciente (la vista lo usa para los tratamientos en curso)', resumen['consulta'].get('id_paciente') == pac)
    # visita 1: sesión en c1
    r = C_MED.post('/api/v1/sesiones-tratamiento', json={'id_tratamiento': t, 'id_consulta_cab': c1, 'procedimientos': [proc], 'descripcion_procedimiento': 'ZZ',
                                                          'insumos': [{'id_insumo': insumo, 'cantidad': 2}]})
    chk(f'visita 1: sesión en la consulta 1 -> {r.status_code}', r.status_code == 201)
    # visita 2: el tratamiento aparece "en curso" del paciente y se le registra una sesión en la consulta 2
    en_curso = C_MED.get(f'/api/v1/tratamientos?paciente={pac}&en_curso=1&por_pagina=100').get_json()['data']
    chk('visita 2: el tratamiento figura entre los en curso del paciente (de otra consulta)', any(x['id_tratamiento'] == t and str(x['id_consulta_cab']) == str(c1) for x in en_curso))
    r = C_MED.post('/api/v1/sesiones-tratamiento', json={'id_tratamiento': t, 'id_consulta_cab': c2, 'procedimientos': [proc], 'descripcion_procedimiento': 'ZZ 2'})
    chk(f'visita 2: sesión en la consulta 2 (otra consulta, mismo paciente y médico) -> {r.status_code}', r.status_code == 201)
    det = C_MED.get(f'/api/v1/tratamientos/{t}').get_json()['data']
    chk('el detalle trae las 2 sesiones, cada una con su consulta, y la primera clave no es el id',
        [s['id_consulta_cab'] for s in det['sesiones']] == [c1, c2] and list(det['sesiones'][0])[0] != 'id_sesion' and det['cantidad_sesiones'] == 2)
    s2 = det['sesiones'][1]['id_sesion']
    # anular con el id de la vista
    chk('anular la sesión 2 con el id que arma la vista -> 200', C_MED.delete(f'/api/v1/sesiones-tratamiento/{s2}').status_code == 200)
    chk('...y la 1 queda vigente', C_MED.get(f'/api/v1/tratamientos/{t}').get_json()['data']['cantidad_sesiones'] == 1)
    chk('finalizar con el id de la vista -> 200', C_MED.put(f'/api/v1/tratamientos/{t}/finalizar').status_code == 200)
    chk('la URL con un id no numérico no existe', C_MED.delete('/api/v1/tratamientos/true').status_code == 404 and C_MED.delete('/api/v1/sesiones-tratamiento/true').status_code == 404)
    t2 = C_MED.post('/api/v1/tratamientos', json={'id_consulta_cab': c1, 'id_tipo_tratamiento': tipo, 'descripcion_tratamiento': 'ZZ para anular'}).get_json()['data']['id_tratamiento']
    fx.auditoria_de('tratamientos', t2)
    chk('anular un tratamiento sin sesiones con el id que arma la vista -> 200', C_MED.delete(f'/api/v1/tratamientos/{t2}').status_code == 200)
    for (i,) in q("SELECT id_sesion FROM sesiones_tratamiento WHERE id_tratamiento = %s", (t,)):
        fx.auditoria_de('sesiones_tratamiento', i)
    for i in (c1, c2):
        fx.auditoria_de('consultas_cab', i)
finally:
    cx.rollback()
    fx.limpiar()

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
