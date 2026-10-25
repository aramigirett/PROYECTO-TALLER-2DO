"""Etapa 3 (commit 3): las vistas de Registrar Consulta, Atención de la consulta y Fichas Médicas — acceso por rol y por médico, que sean Tabler
(sin jQuery, DataTables ni SB Admin 2), qué registros clínicos ofrece cada rol y la baja real por HTTP con el id que arma la vista
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


BASE = '/referenciales/consulta'
try:
    f_rec, u_rec = fx.recepcion()
    med, u_med = fx.medico()
    med2, u_med2 = fx.medico()
    pac, cons = fx.paciente(), fx.consultorio()
    admin = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Administrador' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    cajero = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    C_REC, C_MED, C_MED2, C_ADM, C_CAJ = cliente(u_rec), cliente(u_med), cliente(u_med2), cliente(admin), cliente(cajero)
    id1 = fx.registrar_consulta(fx.cita(med, pac, cons, f_rec), f_rec)
    id_anulada = fx.registrar_consulta(fx.cita(med, pac, cons, f_rec), f_rec)
    cu.execute("UPDATE consultas_cab SET activo=false WHERE id_consulta_cab=%s", (id_anulada,)); cx.commit()

    print('\n=== Acceso')
    chk('sin sesión: redirige al login', app.test_client().get(f'{BASE}/consulta-index').status_code == 302)
    for nombre, c, esperado in (('Recepción', C_REC, 200), ('Médico', C_MED, 200), ('Administrador', C_ADM, 200), ('Cajero', C_CAJ, 403)):
        chk(f'{nombre}: listado de consultas -> {esperado}', c.get(f'{BASE}/consulta-index').status_code == esperado)
    for nombre, c, esperado in (('Recepción', C_REC, 200), ('el médico de la consulta', C_MED, 200), ('Administrador', C_ADM, 200),
                                ('otro médico', C_MED2, 403), ('Cajero', C_CAJ, 403)):
        chk(f'{nombre}: atención de la consulta -> {esperado}', c.get(f'{BASE}/consulta-detalle/{id1}').status_code == esperado)
    chk('consulta inexistente -> 404', C_REC.get(f'{BASE}/consulta-detalle/999999999').status_code == 404)
    chk('consulta anulada -> 404', C_REC.get(f'{BASE}/consulta-detalle/{id_anulada}').status_code == 404)
    for nombre, c, esperado in (('Recepción', C_REC, 200), ('Médico', C_MED, 200), ('Administrador', C_ADM, 200), ('Cajero', C_CAJ, 403)):
        chk(f'{nombre}: pantalla de Fichas Médicas -> {esperado}', c.get('/referenciales/ficha-medica/ficha-medica-index').status_code == esperado)

    print('\n=== Son vistas Tabler (nada de SB Admin 2, jQuery ni DataTables)')
    paginas = {'listado': C_REC.get(f'{BASE}/consulta-index').get_data(as_text=True),
               'atención': C_MED.get(f'{BASE}/consulta-detalle/{id1}').get_data(as_text=True),
               'fichas': C_REC.get('/referenciales/ficha-medica/ficha-medica-index').get_data(as_text=True)}
    for n, html in paginas.items():
        bajo = html.lower()
        chk(f'{n}: Tabler, sin jQuery / DataTables / Bootstrap 4 / SB Admin', 'tabler.min.css' in bajo and 'jquery' not in bajo and 'datatables' not in bajo
            and 'sb-admin' not in bajo and 'stackpath.bootstrapcdn' not in bajo and 'cdn.' not in bajo)
        chk(f'{n}: declara su clave primaria y no adivina la primera clave del JSON', re.search(r"const PK(_FICHA)? = '[a-z_]+'", html) and 'Object.keys(f)' not in html)
    chk('listado: el botón Nueva Consulta lo ve Recepción y NO el Cajero/Médico',
        'id="btnNueva"' in paginas['listado'] and 'id="btnNueva"' not in C_MED.get(f'{BASE}/consulta-index').get_data(as_text=True))

    print('\n=== Registros clínicos que ofrece la pantalla central, según el rol')
    CLAVES = ['diagnosticos', 'odontogramas', 'tratamientos', 'recetas', 'ordenes_estudio', 'ordenes_analisis', 'justificativos']
    ofrecidos = lambda html: [k for k in CLAVES if f"clave: '{k}'" in html]
    chk('el Médico ve las 7 tarjetas', ofrecidos(paginas['atención']) == CLAVES)
    chk('el Administrador ve las 7 tarjetas (lectura)', ofrecidos(C_ADM.get(f'{BASE}/consulta-detalle/{id1}').get_data(as_text=True)) == CLAVES)
    html_rec = C_REC.get(f'{BASE}/consulta-detalle/{id1}').get_data(as_text=True)
    chk('Recepción no ve ninguna (no tiene `ver` de lo clínico) pero sí la tarjeta de la ficha (fichamedica ver)',
        ofrecidos(html_rec) == [] and 'id="tarjetaFicha"' in html_rec)
    chk('Recepción no puede registrar ni editar ni anular fichas (constantes de permiso en falso)',
        'PUEDE_FICHA_NUEVO = false' in html_rec and 'PUEDE_FICHA_EDITAR = false' in html_rec and 'PUEDE_FICHA_ANULAR = false' in html_rec)
    chk('el Médico sí (constantes en verdadero)', 'PUEDE_FICHA_NUEVO = true' in paginas['atención'] and 'PUEDE_FICHA_ANULAR = true' in paginas['atención'])
    chk('los enlaces a los registros clínicos son las pantallas reales (url_for)', all(u in paginas['atención'] for u in (
        '/referenciales/diagnosticos-medicos/diagnostico-index', '/referenciales/odontograma/odontograma-index', '/referenciales/tratamiento/tratamiento-index',
        '/referenciales/receta/receta-index', '/referenciales/orden-estudio/orden-estudio-index', '/referenciales/orden-analisis/orden-analisis-index',
        '/referenciales/justificativo-medico/justificativo-medico-index')))

    print('\n=== La baja REAL por HTTP con el id que arma la vista')
    V = '/api/v1/consultas'
    pk_vista = re.search(r"const PK = '([a-z_]+)'", paginas['listado']).group(1)
    lista = C_REC.get(V + '?q=ZZ+PACIENTE&por_pagina=100').get_json()['data']
    chk('la primera clave del JSON de Flask NO es el id (por eso la vista declara PK)', list(lista[0])[0] != pk_vista and pk_vista in lista[0])
    fila = next(x for x in lista if x[pk_vista] == id1)
    r = C_REC.delete(f'{V}/{fila[pk_vista]}')
    chk(f'anular la consulta con el id de la vista -> {r.status_code}', r.status_code == 200 and q("SELECT activo FROM consultas_cab WHERE id_consulta_cab=%s", (id1,))[0][0] is False)
    chk('la URL con id no numérico no existe', C_REC.delete(f'{V}/true').status_code == 404)

    id2 = fx.registrar_consulta(fx.cita(med, pac, cons, f_rec), f_rec)
    r = C_MED.post('/api/v1/ficha-medica', json={'id_consulta_cab': id2, 'temperatura': 36.5})
    fx.auditoria_de('consultas_cab', id2)
    pk_ficha = re.search(r"const PK_FICHA = '([a-z_]+)'", C_MED.get(f'{BASE}/consulta-detalle/{id2}').get_data(as_text=True)).group(1)
    ficha = C_MED.get(f'/api/v1/ficha-medica/consulta/{id2}').get_json()['data']
    fx.auditoria_de('ficha_medica_consulta', ficha[pk_ficha])
    chk('la primera clave del JSON de la ficha no es el id y la vista declara la correcta', list(ficha)[0] != pk_ficha and pk_ficha in ficha)
    r = C_MED.delete(f'/api/v1/ficha-medica/{ficha[pk_ficha]}')
    chk(f'anular la ficha con el id de la vista -> {r.status_code}', r.status_code == 200)

    fx.borrar_consultas_de_citas([x[0] for x in q("SELECT id_cita FROM consultas_cab WHERE id_consulta_cab = ANY(%s)", ([id1, id2, id_anulada],))])
finally:
    cx.rollback()
    fx.limpiar()

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
