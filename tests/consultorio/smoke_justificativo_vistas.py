"""Etapa 7 (commit 2): la vista del Justificativo Médico — acceso por rol, que sea Tabler (sin jQuery, DataTables ni SB Admin 2), quién ve los botones de registrar / generar / anular
y la generación y la baja REALES por HTTP con el id que arma la vista (el JSON de Flask viene con las claves ordenadas: la vista nunca toma "la primera clave" como id).
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


JU = '/referenciales/justificativo-medico/justificativo-medico-index'
try:
    f_rec, u_rec = fx.recepcion()
    med, u_med = fx.medico()
    pac, cons = fx.paciente(), fx.consultorio()
    admin = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Administrador' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    cajero = q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol='Cajero' AND u.activo ORDER BY 1 LIMIT 1")[0][0]
    C_REC, C_MED, C_ADM, C_CAJ = cliente(u_rec), cliente(u_med), cliente(admin), cliente(cajero)
    c1 = fx.registrar_consulta(fx.cita(med, pac, cons, f_rec), f_rec, 'en_proceso')

    print('\n=== Acceso')
    chk('sin sesión redirige al login', app.test_client().get(JU).status_code == 302)
    for quien, c, esp in (('Médico', C_MED, 200), ('Administrador', C_ADM, 200), ('Recepción', C_REC, 403), ('Cajero', C_CAJ, 403)):
        chk(f'{quien} -> {esp}', c.get(JU).status_code == esp)
    chk('el médico y el Administrador abren con ?consulta=', C_MED.get(f'{JU}?consulta={c1}').status_code == 200 and C_ADM.get(f'{JU}?consulta={c1}').status_code == 200)

    print('\n=== Es una vista Tabler (nada de SB Admin 2, jQuery ni DataTables)')
    html = C_MED.get(f'{JU}?consulta={c1}').get_data(as_text=True)
    bajo = html.lower()
    chk('Tabler, sin jQuery / DataTables / Bootstrap 4 / SB Admin / CDN',
        'tabler.min.css' in bajo and 'jquery' not in bajo and 'datatables' not in bajo and 'sb-admin' not in bajo and 'stackpath.bootstrapcdn' not in bajo and 'cdn.' not in bajo)
    chk('declara su clave primaria, vuelve a la consulta y ofrece el PDF', "const PK = 'id_justificativo'" in html and 'Object.keys(f)' not in html and 'Volver a la consulta' in html and '/pdf' in html)

    print('\n=== Quién ve los botones')
    adm = C_ADM.get(f'{JU}?consulta={c1}').get_data(as_text=True)
    chk('el médico ve "Nuevo justificativo" y el formulario; el Administrador NO (lectura clínica)',
        'id="btnNuevo"' in html and 'id="formJus"' in html and 'id="btnNuevo"' not in adm and 'id="formJus"' not in adm)
    chk('constantes de permiso (médico: nuevo, anular y generar; Administrador ninguno)',
        all(x in html for x in ('PUEDE_NUEVO = true', 'PUEDE_ANULAR = true', 'PUEDE_GENERAR = true')) and all(x in adm for x in ('PUEDE_NUEVO = false', 'PUEDE_ANULAR = false', 'PUEDE_GENERAR = false')))
    chk('"Generar" también con la consulta finalizada (la vista solo lo niega con la cancelada)', "f.estado_consulta !== 'cancelada'" in html)

    print('\n=== Los ids que arma la vista (generar, anular, PDF)')
    ids = []
    for _ in range(2):
        d = C_MED.post('/api/v1/justificativos', json={'id_consulta_cab': c1, 'dias_reposo': 2, 'recomendaciones': 'ZZ'})
        ids.append(d.get_json()['data']['id_justificativo']); fx.auditoria_de('justificativo_medico', ids[-1])
    lista = C_MED.get(f'/api/v1/justificativos?consulta={c1}').get_json()['data']
    chk('la primera clave del JSON NO es el id y trae lo que usa la vista',
        list(lista[0])[0] != 'id_justificativo' and {'id_justificativo', 'numero', 'estado', 'estado_consulta', 'dias_reposo', 'fecha_justificativo'} <= set(lista[0]))
    chk('todos nacen pendientes', {x['estado'] for x in lista} == {'pendiente'})
    a, b = lista[0]['id_justificativo'], lista[1]['id_justificativo']
    chk('generar con el id de la vista -> 200 y queda emitido', C_MED.put(f'/api/v1/justificativos/{a}/emitir').status_code == 200
        and q("SELECT estado FROM justificativo_medico WHERE id_justificativo=%s", (a,))[0][0] == 'emitido')
    chk('el PDF con el id de la vista -> 200', C_MED.get(f'/api/v1/justificativos/{a}/pdf').status_code == 200)
    cu.execute("UPDATE consultas_cab SET estado='finalizada' WHERE id_consulta_cab=%s", (c1,)); cx.commit()
    lista = C_MED.get(f'/api/v1/justificativos?consulta={c1}').get_json()['data']
    chk('con la consulta FINALIZADA el listado trae estado_consulta=finalizada y se sigue generando',
        all(x['estado_consulta'] == 'finalizada' for x in lista) and C_MED.put(f'/api/v1/justificativos/{b}/emitir').status_code == 200)
    cu.execute("UPDATE consultas_cab SET estado='en_proceso' WHERE id_consulta_cab=%s", (c1,)); cx.commit()
    chk('anular con el id de la vista -> 200', C_MED.delete(f'/api/v1/justificativos/{a}').status_code == 200)
    chk('la URL con un id no numérico no existe', C_MED.put('/api/v1/justificativos/true/emitir').status_code == 404 and C_MED.delete('/api/v1/justificativos/true').status_code == 404)
    fx.auditoria_de('consultas_cab', c1)
finally:
    cx.rollback()
    fx.limpiar()

print('\nFALLOS:', 'ninguno' if not fallos else fallos)
