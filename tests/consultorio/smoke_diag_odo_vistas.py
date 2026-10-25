"""Etapa 4 (commit 2): las vistas de Diagnóstico y Odontograma — acceso por rol, que sean Tabler (sin jQuery, DataTables ni SB Admin 2), quién ve los botones de
registrar / modificar / anular, el dibujo del odontograma (FDI, superficies y color por estado) y la baja REAL por HTTP con el id que arma cada vista
(el JSON de Flask viene con las claves ordenadas: la vista nunca puede tomar "la primera clave" como id).
"""
import re
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


DX = '/referenciales/diagnosticos-medicos/diagnostico-index'
OD = '/referenciales/odontograma/odontograma-index'
try:
    f_rec, u_rec = fx.recepcion()
    med, u_med = fx.medico()
    med2, u_med2 = fx.medico()
    pac, cons = fx.paciente(), fx.consultorio()
    tipo, sintoma = fx.tipo_diagnostico(), fx.sintoma()
    admin = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Administrador' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    cajero = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    C_REC, C_MED, C_MED2, C_ADM, C_CAJ = cliente(u_rec), cliente(u_med), cliente(u_med2), cliente(admin), cliente(cajero)
    c1 = fx.registrar_consulta(fx.cita(med, pac, cons, f_rec), f_rec)
    fx.auditoria_de('consultas_cab', c1)

    print('\n=== Acceso')
    for url, nombre in ((DX, 'Diagnósticos'), (OD, 'Odontograma')):
        chk(f'{nombre}: sin sesión redirige al login', app.test_client().get(url).status_code == 302)
        for quien, c, esp in (('Médico', C_MED, 200), ('Administrador', C_ADM, 200), ('Recepción', C_REC, 403), ('Cajero', C_CAJ, 403)):
            chk(f'{nombre}: {quien} -> {esp}', c.get(url).status_code == esp)
            if esp == 200:
                chk(f'{nombre}: {quien} con ?consulta= -> 200', c.get(f'{url}?consulta={c1}').status_code == 200)

    print('\n=== Son vistas Tabler (nada de SB Admin 2, jQuery ni DataTables)')
    paginas = {'diagnóstico': C_MED.get(f'{DX}?consulta={c1}').get_data(as_text=True), 'odontograma': C_MED.get(f'{OD}?consulta={c1}').get_data(as_text=True)}
    for n, html in paginas.items():
        bajo = html.lower()
        chk(f'{n}: Tabler, sin jQuery / DataTables / Bootstrap 4 / SB Admin / CDN',
            'tabler.min.css' in bajo and 'jquery' not in bajo and 'datatables' not in bajo and 'sb-admin' not in bajo
            and 'stackpath.bootstrapcdn' not in bajo and 'cdn.' not in bajo)
    chk('diagnóstico: declara su clave primaria y no adivina la primera clave', "const PK = 'id_diagnostico'" in paginas['diagnóstico'] and 'Object.keys(f)' not in paginas['diagnóstico'])
    chk('odontograma: declara las claves primarias del odontograma y del hallazgo',
        "const PK = 'id_odontograma'" in paginas['odontograma'] and "const PK_HALLAZGO = 'id_odontograma_detalle'" in paginas['odontograma'] and 'Object.keys(f)' not in paginas['odontograma'])

    print('\n=== Quién ve los botones de registrar / modificar / anular')
    adm_dx = C_ADM.get(f'{DX}?consulta={c1}').get_data(as_text=True)
    adm_od = C_ADM.get(f'{OD}?consulta={c1}').get_data(as_text=True)
    chk('Diagnóstico: el médico ve "Nuevo diagnóstico" y el formulario; el Administrador NO (lectura clínica)',
        'id="btnNuevo"' in paginas['diagnóstico'] and 'id="formDx"' in paginas['diagnóstico'] and 'id="btnNuevo"' not in adm_dx and 'id="formDx"' not in adm_dx)
    chk('Diagnóstico: constantes de permiso (médico verdadero, Administrador falso)', 'PUEDE_NUEVO = true' in paginas['diagnóstico'] and 'PUEDE_ANULAR = true' in paginas['diagnóstico']
        and 'PUEDE_NUEVO = false' in adm_dx and 'PUEDE_ANULAR = false' in adm_dx)
    chk('Odontograma: el médico ve "Crear odontograma" y "Anular odontograma"; el Administrador NO',
        'id="btnCrearOdo"' in paginas['odontograma'] and 'id="btnAnularOdo"' in paginas['odontograma'] and 'id="btnCrearOdo"' not in adm_od and 'id="btnAnularOdo"' not in adm_od)
    chk('Odontograma: constantes de permiso (médico: editar y anular verdaderos; Administrador falsos)',
        'PUEDE_EDITAR = true' in paginas['odontograma'] and 'PUEDE_ANULAR = true' in paginas['odontograma'] and 'PUEDE_EDITAR = false' in adm_od and 'PUEDE_ANULAR = false' in adm_od)
    chk('Odontograma: pieza FDI, superficies y colores salen del script (dibujarPieza / pintarOdontograma) y de las clases .odo-*',
        'function dibujarPieza' in paginas['odontograma'] and 'function pintarOdontograma' in paginas['odontograma'] and '.odo-superficie' in paginas['odontograma']
        and 'estado_color' in paginas['odontograma'])
    chk('Odontograma: las 32 piezas permanentes y las 20 temporales están en las arcadas (FDI)',
        all(str(n) in paginas['odontograma'] for n in (18, 11, 21, 28, 48, 41, 31, 38, 55, 51, 61, 65, 85, 81, 71, 75)))
    chk('Diagnóstico: el selector de piezas FDI se arma con los 8 cuadrantes', "for (let n = 1; n <= (c <= 4 ? 8 : 5); n++)" in paginas['diagnóstico'])

    print('\n=== La baja REAL por HTTP con el id que arma la vista')
    d = C_MED.post('/api/v1/diagnosticos-medicos', json={'id_consulta_cab': c1, 'id_tipo_diagnostico': tipo, 'sintomas': [sintoma], 'descripcion_diagnostico': 'ZZ vista'})
    id_dx = d.get_json()['data']['id_diagnostico']
    fx.auditoria_de('diagnosticos', id_dx)
    lista = C_MED.get('/api/v1/diagnosticos-medicos?q=ZZ+PACIENTE&por_pagina=100').get_json()['data']
    chk('la primera clave del JSON de Flask NO es el id del diagnóstico', list(lista[0])[0] != 'id_diagnostico' and 'id_diagnostico' in lista[0])
    fila = next(x for x in lista if x['id_diagnostico'] == id_dx)
    r = C_MED.delete(f"/api/v1/diagnosticos-medicos/{fila['id_diagnostico']}")
    chk(f'anular el diagnóstico con el id de la vista -> {r.status_code}', r.status_code == 200 and q("SELECT activo FROM diagnosticos WHERE id_diagnostico=%s", (id_dx,))[0][0] is False)

    d = C_MED.post('/api/v1/odontogramas', json={'id_consulta_cab': c1})
    id_odo = d.get_json()['data']['id_odontograma']
    fx.auditoria_de('odontograma', id_odo)
    estado = q("SELECT id_estado_dental FROM estado_dental WHERE aplica_a='SUPERFICIE' AND activo ORDER BY 1 LIMIT 1")[0][0]
    C_MED.post(f'/api/v1/odontogramas/{id_odo}/hallazgos', json={'numero_diente': 18, 'superficie': 'O', 'id_estado_dental': estado})
    odo = C_MED.get(f'/api/v1/odontogramas/consulta/{c1}').get_json()['data']
    chk('la primera clave del JSON del odontograma NO es el id y trae los hallazgos con color y símbolo',
        list(odo)[0] != 'id_odontograma' and 'id_odontograma' in odo and len(odo['hallazgos']) == 1
        and list(odo['hallazgos'][0])[0] != 'id_odontograma_detalle' and {'estado_color', 'estado_simbolo', 'aplica_a'} <= set(odo['hallazgos'][0]))
    h = odo['hallazgos'][0]
    r = C_MED.delete(f"/api/v1/odontogramas/hallazgos/{h['id_odontograma_detalle']}")
    chk(f'quitar el hallazgo con el id de la vista -> {r.status_code}', r.status_code == 200 and q("SELECT activo FROM odontograma_detalle WHERE id_odontograma_detalle=%s", (h['id_odontograma_detalle'],))[0][0] is False)
    r = C_MED.delete(f"/api/v1/odontogramas/{odo['id_odontograma']}")
    chk(f'anular el odontograma con el id de la vista -> {r.status_code}', r.status_code == 200 and q("SELECT activo FROM odontograma WHERE id_odontograma=%s", (id_odo,))[0][0] is False)
    chk('la URL con un id no numérico no existe', C_MED.delete('/api/v1/diagnosticos-medicos/true').status_code == 404 and C_MED.delete('/api/v1/odontogramas/hallazgos/true').status_code == 404)

    # el listado de odontogramas lleva el id de la CONSULTA para abrirlo
    od_lista = C_MED.get('/api/v1/odontogramas?por_pagina=100').get_json()['data']
    chk('el listado de odontogramas trae id_consulta_cab (la vista abre con ?consulta=) y la cantidad de hallazgos', all('id_consulta_cab' in x and 'cantidad_hallazgos' in x for x in od_lista))
finally:
    cx.rollback()
    fx.limpiar()

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
