"""Agendamiento: el día de la Disponibilidad Horaria se calcula desde la fecha (ya no se elige), Sábado y Domingo existen en `dias`, la agenda sugiere la
próxima fecha con disponibilidad cuando no hay horarios para la suya, y Historial Médico está en el módulo Agendamiento del menú.
Datos de prueba: disponibilidades de enero de 2031 de un médico existente, borradas POR ID; el día Domingo se anula un momento y se restaura en un `finally`;
la auditoría que genera el test se borra por ID (saltando el trigger solo en su conexión)."""
import pathlib, re, sys
RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from app import app
from tests._conexion_pruebas import Conexion
from app.rutas.modulo_seguridad.menu_catalog import CATALOGO_MENU

fallos = []
c = app.test_client()
URL = '/api/v1/disponibilidades'
NOMBRES = ['LUNES', 'MARTES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'SABADO', 'DOMINGO']
FECHAS = [f'2031-01-{6 + i:02d}' for i in range(7)]       # 06/01/2031 es lunes ... 12/01/2031 es domingo


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


cx = Conexion().getConexion(); cx.autocommit = True; cu = cx.cursor()
cu.execute("SELECT COALESCE(MAX(id_auditoria_cambio), 0) FROM auditoria_cambios"); BASE = cu.fetchone()[0]
cu.execute("SELECT id_medico FROM medico WHERE activo ORDER BY id_medico LIMIT 1"); MEDICO = cu.fetchone()[0]
cu.execute("SELECT id_turno FROM turnos WHERE activo ORDER BY id_turno LIMIT 1"); TURNO = cu.fetchone()[0]
cu.execute("SELECT id_dia, activo FROM dias WHERE UPPER(descripcion) = 'DOMINGO' ORDER BY activo DESC LIMIT 1"); domingo = cu.fetchone()
creadas = []


def dia_de(id_disp):
    cu.execute("SELECT d.descripcion FROM disponibilidad_horaria h JOIN dias d USING (id_dia) WHERE h.id_disponibilidad = %s", (id_disp,))
    return cu.fetchone()[0]


def cuerpo(fecha, ini='08:00', fin='09:00', **extra):
    return {'id_medico': MEDICO, 'id_turno': TURNO, 'dispo_fecha': fecha, 'dispo_hora_inicio': ini, 'dispo_hora_fin': fin, 'dispo_cupos': '3', **extra}


try:
    with c.session_transaction() as s:
        s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

    print('== Referencial Día')
    r = c.get('/api/v1/dias')
    nombres_dias = {d['descripcion'] for d in r.get_json()['data']}
    chk('Sábado y Domingo existen y están activos en Día', {'SABADO', 'DOMINGO'} <= nombres_dias)
    chk('los 7 días de la semana están en Día', set(NOMBRES) <= nombres_dias)

    print('\n== El día se calcula desde la fecha (el servidor ignora el que mande el navegador)')
    for fecha, esperado in zip(FECHAS, NOMBRES):
        r = c.post(URL, json=cuerpo(fecha, id_dia=999999))      # un id_dia cualquiera no se usa
        d = r.get_json() or {}
        ok = r.status_code == 201
        if ok:
            creadas.append(d['data']['id_disponibilidad'])
        chk(f'{fecha} -> {esperado} (se guarda el día correcto aunque se envíe otro)', ok and dia_de(creadas[-1]) == esperado)
    r = c.post(URL, json=cuerpo('2031-01-13'))               # lunes siguiente, sin id_dia: ya no es obligatorio
    if r.status_code == 201:
        creadas.append(r.get_json()['data']['id_disponibilidad'])
    chk('sin id_dia en el cuerpo: se acepta (el día ya no es obligatorio)', r.status_code == 201 and dia_de(creadas[-1]) == 'LUNES')
    r = c.put(f'{URL}/{creadas[0]}', json=cuerpo('2031-01-08', ini='10:00', fin='11:00'))      # el lunes pasa a miércoles
    chk('editar la fecha recalcula el día (lunes -> miércoles)', r.status_code == 200 and dia_de(creadas[0]) == 'MIERCOLES')
    r = c.get(f'{URL}/{creadas[0]}')
    chk('la API devuelve el día calculado (des_dia) en el detalle', (r.get_json()['data'] or {}).get('des_dia') == 'MIERCOLES')

    print('\n== Si el día de la fecha no está en el referencial Día: error claro')
    if domingo:
        cu.execute("UPDATE dias SET activo = false WHERE id_dia = %s", (domingo[0],))
        try:
            r = c.post(URL, json=cuerpo('2031-02-02'))        # domingo
            d = r.get_json() or {}
            chk('fecha en domingo con Domingo anulado -> 400 con el motivo', r.status_code == 400 and 'Domingo' in d.get('error', '') and 'referencial Día' in d.get('error', ''))
            r = c.put(f'{URL}/{creadas[1]}', json=cuerpo('2031-02-02'))
            chk('editar a una fecha en domingo con Domingo anulado -> 400 y no cambia nada', r.status_code == 400 and dia_de(creadas[1]) == 'MARTES')
        finally:
            cu.execute("UPDATE dias SET activo = %s WHERE id_dia = %s", (domingo[1], domingo[0]))
    r = c.post(URL, json=cuerpo('2031-02-02'))
    if r.status_code == 201:
        creadas.append(r.get_json()['data']['id_disponibilidad'])
    chk('con Domingo activo la misma fecha se acepta', r.status_code == 201)
    chk('fecha inválida o vacía -> 400 en dispo_fecha', c.post(URL, json=cuerpo('')).status_code == 400 and c.post(URL, json=cuerpo('no-es-fecha')).get_json().get('campo') == 'dispo_fecha')

    print('\n== Próxima fecha con disponibilidad (mensaje de la agenda)')
    r = c.get(f'{URL}/proxima?id_medico={MEDICO}&desde=2031-01-05')
    d = r.get_json()
    chk('desde el 05/01/2031 la próxima fecha es el 07/01/2031 (martes; la del lunes pasó al miércoles al editarla) con su horario',
        r.status_code == 200 and d['success'] and {x['dispo_fecha'] for x in d['data']} == {'2031-01-07'} and d['data'][0]['des_dia'] == 'MARTES' and d['data'][0]['dispo_hora_inicio'][:5] == '08:00')
    r = c.get(f'{URL}/proxima?id_medico={MEDICO}&desde=2031-01-06')
    chk('desde el 06/01 (estricto) la próxima es la del 07/01', {x['dispo_fecha'] for x in r.get_json()['data']} == {'2031-01-07'})
    r = c.get(f'{URL}/proxima?id_medico={MEDICO}&desde=2031-12-31')
    chk('sin disponibilidades posteriores -> lista vacía', r.status_code == 200 and r.get_json()['data'] == [])
    chk('no devuelve las anuladas', (lambda: (cu.execute("UPDATE disponibilidad_horaria SET activo = false WHERE id_disponibilidad = %s", (creadas[1],)),
                                               {x['dispo_fecha'] for x in c.get(f'{URL}/proxima?id_medico={MEDICO}&desde=2031-01-06').get_json()['data']} == {'2031-01-08'})[1])())
    cu.execute("UPDATE disponibilidad_horaria SET activo = true WHERE id_disponibilidad = %s", (creadas[1],))
    chk('parámetros inválidos -> 400', c.get(f'{URL}/proxima').status_code == 400 and c.get(f'{URL}/proxima?id_medico={MEDICO}&desde=x').status_code == 400)
    with c.session_transaction() as s:
        s.clear()
    chk('sin sesión -> 401', c.get(f'{URL}/proxima?id_medico={MEDICO}&desde=2031-01-05').status_code == 401)
    with c.session_transaction() as s:
        s['id_usuario'] = 1; s['id_rol'] = 1; s['nombre_rol'] = 'Administrador'

    print('\n== Pantallas')
    html = c.get('/referenciales/disponibilidad/disponibilidad-index').get_data(as_text=True)
    chk('Disponibilidad: ya no hay selector de día; muestra el día calculado (solo lectura)', 'id="selDia"' not in html and 'id="txtDiaCalculado"' in html and 'readonly' in html
        and "'/api/v1/dias'" not in html and 'mostrarDia' in html)
    html = c.get('/referenciales/agenda/agenda').get_data(as_text=True)
    chk('Agenda: el mensaje vacío busca la próxima fecha (/disponibilidades/proxima)', 'mensajeSinDisponibilidad' in html and '/api/v1/disponibilidades/proxima' in html
        and 'La próxima es el' in html)

    print('\n== Menú: Historial Médico en Agendamiento')
    cu.execute("""SELECT p.descripcion FROM menu m JOIN menu p ON p.id_menu = m.id_menu_padre WHERE m.clave = 'historial' AND m.activo""")
    chk('tabla menu: Historial Médico cuelga de Agendamiento', cu.fetchall() == [('Agendamiento',)])
    chk('menu_catalog.py: Historial Médico es de Agendamiento', next(i['modulo'] for i in CATALOGO_MENU if i['ventana'] == 'historial') == 'Agendamiento')
    cu.execute("""SELECT r.nombre_rol, p.accion FROM permisos p JOIN roles r USING (id_rol) JOIN menu m USING (id_menu) WHERE m.clave = 'historial' ORDER BY 1, 2""")
    chk('los permisos de Historial Médico no cambiaron (Médico: ver, nuevo y anular)', cu.fetchall() == [('Medico', 'anular'), ('Medico', 'nuevo'), ('Medico', 'ver')])
    html = c.get('/referenciales/vista/vista-index').get_data(as_text=True)
    grupos = re.split(r'oc-sidebar-link oc-submenu-toggle', html)
    agend = next(g for g in grupos if 'Registrar Agenda' in g)
    consu = next(g for g in grupos if 'Registrar Consulta' in g)
    chk('menú lateral: Historial Médico aparece en Agendamiento y ya no en Consultorio', 'Historial Médico' in agend and 'Historial Médico' not in consu)
    chk('la pantalla de Historial Médico sigue cargando', c.get('/referenciales/historial/historial-index').status_code == 200)

finally:
    if creadas:
        cu.execute("DELETE FROM disponibilidad_horaria WHERE id_disponibilidad = ANY(%s)", (creadas,))
    if domingo:
        cu.execute("UPDATE dias SET activo = %s WHERE id_dia = %s", (domingo[1], domingo[0]))
    cu.execute("SELECT id_auditoria_cambio FROM auditoria_cambios WHERE id_auditoria_cambio > %s AND id_usuario = 1 AND ip = '127.0.0.1'", (BASE,))
    ids = [x[0] for x in cu.fetchall()]
    cu.execute("SET session_replication_role = replica")
    cu.execute("DELETE FROM auditoria_cambios WHERE id_auditoria_cambio = ANY(%s)", (ids,))
    cu.execute("RESET session_replication_role")
    print(f'(limpieza: {len(creadas)} disponibilidades y {len(ids)} filas de auditoría de prueba borradas por ID)')
    cu.close(); cx.close()

print('FALLOS:', 'ninguno' if not fallos else fallos)
