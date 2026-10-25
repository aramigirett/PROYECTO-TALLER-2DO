"""Etapa 3: Historial Médico del Paciente (datos de salud).

Reglas: Recepción y Cajero sin acceso; el Administrador solo lee; el Médico lee, registra y anula, pero solo los documentos de los pacientes que ATENDIÓ
(consulta no cancelada con él). Se registra y se anula (definitivo), no se modifica; el usuario sale de la sesión; los adjuntos se verifican por su contenido,
se guardan fuera de git y solo se bajan por la API (cada descarga se audita como EXPORTACION); la auditoría NO lleva contenido clínico.
Datos `ZZ`: se borran por ID (también los archivos subidos), junto con su auditoría.
"""
import atexit
import io
import os
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from app import app
from app.rutas.modulo_agendamiento.historial import historial_api
from tests._conexion_pruebas import Conexion
from tests.consultorio._fixtures import Fixtures
from tests.facturacion._limpieza import borrar_auditoria

c = app.test_client()
fallos = []


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


def api(metodo, url, esperado, json=None, nombre=None, contiene=None, campo=None, **kw):
    f = getattr(c, metodo)
    r = f(url, json=json, **kw) if json is not None else f(url, **kw)
    d = r.get_json(silent=True) or {}
    ok = r.status_code == esperado
    if contiene is not None:
        ok = ok and contiene in (d.get('error') or d.get('mensaje') or '')
    if campo is not None:
        ok = ok and d.get('campo') == campo
    chk(f"{nombre or metodo + ' ' + url} -> {r.status_code}" + ('' if ok else f' {d}'), ok)
    return d


cx = Conexion().getConexion(); cu = cx.cursor()
fx = Fixtures(cx)


def q(sql, p=()):
    cu.execute(sql, p)
    return cu.fetchall()


def sesion(id_usuario):
    id_rol, nombre = q("SELECT u.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.id_usuario=%s", (id_usuario,))[0]
    with c.session_transaction() as s:
        s.clear(); s['id_usuario'] = id_usuario; s['id_rol'] = id_rol; s['nombre_rol'] = nombre


def usuario_de(rol):
    return q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol=%s AND u.activo ORDER BY 1 LIMIT 1", (rol,))[0][0]


ADMIN, RECEP, CAJERO = usuario_de('Administrador'), usuario_de('Recepcion'), usuario_de('Cajero')
historiales, archivos = set(), set()
_limpio = []


def limpieza():
    if _limpio:
        return
    _limpio.append(1)
    try:
        cx.rollback()
        cu.execute("DELETE FROM historial_medico_paciente WHERE id_paciente = ANY(%s)", (list(pacientes),))
        borrar_auditoria(cu, 'historial_medico_paciente', list(historiales))
        cx.commit()
        for a in archivos:
            if os.path.exists(a):
                os.remove(a)
        fx.limpiar()
    except Exception as e:
        cx.rollback()
        print('ERROR en la limpieza:', e)
        fallos.append('limpieza')


med_a, usu_a = fx.medico(con_usuario=True)
med_b, usu_b = fx.medico(con_usuario=True)
func, _u = fx.recepcion()
consultorio = fx.consultorio()
pac_a, pac_otro = fx.paciente(), fx.paciente()
pacientes = [pac_a, pac_otro]
atexit.register(limpieza)
fx.registrar_consulta(fx.cita(med_a, pac_a, consultorio, func, 'Confirmado'), func)

HI = '/api/v1/historial-medico'
doc = lambda pac, **x: {'id_paciente': pac, 'tipo_documento': 'antecedente', 'descripcion': 'ZZ diabetes tipo 2 familiar', **x}
PDF = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n'

def bajar(url):
    """GET de un adjunto cerrando la respuesta (en Windows el archivo queda abierto hasta cerrarla). Devuelve (status, contenido, cabeceras)."""
    r = c.get(url)
    try:
        return r.status_code, r.data, r.headers
    finally:
        r.close()


print('== Acceso por rol')
chk('vista Tabler (Médico)', (sesion(usu_a), b'tabler' in c.get('/referenciales/historial/historial-index').data.lower())[1])
for rol, uid in (('Recepción', RECEP), ('Cajero', CAJERO)):
    sesion(uid)
    api('get', f'{HI}/pacientes', 403, None, f'{rol} no ve los pacientes del historial')
    api('get', f'{HI}/paciente/{pac_a}', 403, None, f'{rol} no lee el historial')
    api('post', HI, 403, doc(pac_a), f'{rol} no registra')
    chk(f'{rol} no abre la vista', c.get('/referenciales/historial/historial-index').status_code == 403)
sesion(usu_a)
d = api('get', f'{HI}/pacientes', 200, None, 'Médico: sus pacientes')
ids = [p['id_paciente'] for p in d['data']]
chk('solo trae al paciente que atendió', pac_a in ids and pac_otro not in ids)
sesion(usu_b)
chk('otro médico no ve a ese paciente en su lista', pac_a not in [p['id_paciente'] for p in c.get(f'{HI}/pacientes').get_json()['data']])
api('get', f'{HI}/paciente/{pac_a}', 403, None, 'otro médico no lee el historial de un paciente que no atendió', contiene='atendió')
api('post', HI, 403, doc(pac_a), 'otro médico no registra en ese paciente')

print('\n== Registrar, leer y anular (Médico)')
sesion(usu_a)
api('post', HI, 403, doc(pac_otro), 'no registra en un paciente que no atendió', contiene='atendió')
api('post', HI, 400, {**doc(pac_a), 'descripcion': ''}, 'la descripción es obligatoria', campo='descripcion')
api('post', HI, 400, doc(pac_a, tipo_documento='otra_cosa'), 'tipo inválido', campo='tipo_documento')
api('post', HI, 400, doc(pac_a, tipo_documento='alergia'), 'alergia sin gravedad', campo='gravedad_alergia')
api('post', HI, 400, doc(pac_a, tipo_documento='medicamento_habitual'), 'medicamento sin datos', campo='nombre_medicamento')
api('post', HI, 400, doc(pac_a, descripcion='x' * 1001), 'descripción de más de 1000 caracteres', campo='descripcion')
d = api('post', HI, 201, doc(pac_a), 'registra un antecedente')
h1 = d['data']['id_historial']; historiales.add(h1)
chk('el usuario que registra sale de la sesión', q("SELECT id_usuario_registro, estado FROM historial_medico_paciente WHERE id_historial=%s", (h1,))[0] == (usu_a, 'activo'))
d = api('post', HI, 201, doc(pac_a, tipo_documento='alergia', gravedad_alergia='Grave', tipo_alergia='Penicilina', id_usuario_registro=1), 'registra una alergia (ignora el usuario que mande el navegador)')
h2 = d['data']['id_historial']; historiales.add(h2)
chk('...el id_usuario_registro del navegador se ignora', q("SELECT id_usuario_registro FROM historial_medico_paciente WHERE id_historial=%s", (h2,))[0][0] == usu_a)
a = q("SELECT modulo, detalle, valores_nuevos, id_usuario FROM auditoria_cambios WHERE entidad='historial_medico_paciente' AND id_registro=%s AND accion='ALTA'", (h1,))
texto = str(a)
chk('auditoría ALTA con módulo, usuario, paciente y tipo, SIN contenido clínico', bool(a) and a[0][0] == 'Módulo Agendamiento' and a[0][3] == usu_a and 'Antecedente' in texto
    and 'diabetes' not in texto and 'Penicilina' not in texto)
d = api('get', f'{HI}/paciente/{pac_a}', 200, None, 'Médico lee el historial')
chk('...trae los 2 documentos sin la ruta interna del archivo', len(d['data']) == 2 and all('archivo_url' not in x and 'archivo_ruta' not in x for x in d['data']))
d = api('get', f'{HI}/paciente/{pac_a}/contadores', 200, None, 'contadores por tipo')
chk('...2 en total', d['data']['total'] == 2 and d['data']['alergia'] == 1)
d = api('get', f'{HI}/paciente/{pac_a}?tipo=alergia', 200, None, 'filtra por tipo')
chk('...solo la alergia', len(d['data']) == 1)
api('put', f'{HI}/{h1}', 405, doc(pac_a), 'el historial no se modifica (sin PUT)')
sesion(usu_b)
api('get', f'{HI}/{h1}', 403, None, 'otro médico tampoco lo lee por ID')
sesion(usu_a)
api('delete', f'{HI}/{h2}', 200, None, 'Médico anula su documento')
chk('BAJA auditada; el documento queda inactivo y no se lista', bool(q("SELECT 1 FROM auditoria_cambios WHERE entidad='historial_medico_paciente' AND id_registro=%s AND accion='BAJA'", (h2,)))
    and q("SELECT estado FROM historial_medico_paciente WHERE id_historial=%s", (h2,))[0][0] == 'inactivo' and len(c.get(f'{HI}/paciente/{pac_a}').get_json()['data']) == 1)
api('delete', f'{HI}/{h2}', 404, None, 'no se anula dos veces (anulación definitiva)')
api('patch', f'{HI}/{h2}/reactivar', 404, None, 'no existe la reactivación')
sesion(usu_b)
api('delete', f'{HI}/{h1}', 403, None, 'otro médico no anula')
cu.execute("UPDATE paciente SET activo=false WHERE id_paciente=%s", (pac_a,)); cx.commit()
sesion(usu_a)
api('post', HI, 400, doc(pac_a), 'no se registra en un paciente anulado', contiene='anulado', campo='id_paciente')
cu.execute("UPDATE paciente SET activo=true WHERE id_paciente=%s", (pac_a,)); cx.commit()

print('\n== Administrador: solo lectura')
sesion(ADMIN)
d = api('get', f'{HI}/pacientes', 200, None, 'Administrador ve todos los pacientes')
chk('...incluye al que ningún médico atendió', pac_otro in [p['id_paciente'] for p in d['data']])
api('get', f'{HI}/paciente/{pac_a}', 200, None, 'Administrador lee cualquier historial')
api('post', HI, 403, doc(pac_a), 'Administrador NO registra', contiene='solo consulta')
api('delete', f'{HI}/{h1}', 403, None, 'Administrador NO anula', contiene='solo consulta')
chk('Administrador abre la vista', c.get('/referenciales/historial/historial-index').status_code == 200)

print('\n== Archivos adjuntos')
sesion(usu_a)
chk('la carpeta de adjuntos está en uploads/ del proyecto (fuera de git)', historial_api.UPLOAD_FOLDER.endswith(os.path.join('uploads', 'historial_medico')))
r = c.post(HI, data={**{k: str(v) for k, v in doc(pac_a).items()}, 'archivo': (io.BytesIO(b'MZ\x90 esto no es un pdf'), 'informe.pdf')}, content_type='multipart/form-data')
chk('un .pdf que no es un PDF se rechaza por su contenido', r.status_code == 400 and r.get_json().get('campo') == 'archivo')
r = c.post(HI, data={**{k: str(v) for k, v in doc(pac_a).items()}, 'archivo': (io.BytesIO(PDF), 'script.exe')}, content_type='multipart/form-data')
chk('una extensión no permitida se rechaza', r.status_code == 400 and r.get_json().get('campo') == 'archivo')
r = c.post(HI, data={**{k: str(v) for k, v in doc(pac_a).items()}, 'archivo': (io.BytesIO(PDF + b'0' * (5 * 1024 * 1024)), 'grande.pdf')}, content_type='multipart/form-data')
chk('más de 5 MB se rechaza', r.status_code == 400 and 'tamaño' in r.get_json()['error'])
r = c.post(HI, data={**{k: str(v) for k, v in doc(pac_a).items()}, 'archivo': (io.BytesIO(PDF), '../../informe ZZ.pdf')}, content_type='multipart/form-data')
chk('un PDF válido se guarda (nombre saneado)', r.status_code == 201)
h3 = r.get_json()['data']['id_historial']; historiales.add(h3)
fila = q("SELECT archivo_url, archivo_nombre, archivo_tipo FROM historial_medico_paciente WHERE id_historial=%s", (h3,))[0]
ruta = os.path.join(historial_api.UPLOAD_FOLDER, fila[0]); archivos.add(ruta)
chk('...en uploads/historial_medico, con tipo pdf y sin rutas relativas en el nombre', os.path.exists(ruta) and fila[2] == 'pdf' and '..' not in fila[1] and '/' not in fila[1])
a = str(q("SELECT detalle, valores_nuevos FROM auditoria_cambios WHERE entidad='historial_medico_paciente' AND id_registro=%s AND accion='ALTA'", (h3,)))
chk('la auditoría dice "Archivo adjunto: Sí" pero no el nombre del archivo', 'Sí' in a and 'informe' not in a)
est, cuerpo_bajado, cab = bajar(f'{HI}/{h3}/archivo')
chk('el médico descarga el adjunto (el contenido es el subido)', est == 200 and cuerpo_bajado == PDF and 'attachment' in cab.get('Content-Disposition', ''))
e = q("SELECT modulo, id_usuario, detalle FROM auditoria_cambios WHERE entidad='historial_medico_paciente' AND id_registro=%s AND accion='EXPORTACION'", (h3,))
chk('la descarga queda auditada como EXPORTACION con el usuario', len(e) == 1 and e[0][1] == usu_a)
sesion(usu_b)
api('get', f'{HI}/{h3}/archivo', 403, None, 'otro médico no baja el adjunto')
sesion(RECEP)
api('get', f'{HI}/{h3}/archivo', 403, None, 'Recepción no baja el adjunto')
sesion(ADMIN)
chk('el Administrador sí puede descargarlo (solo lectura)', bajar(f'{HI}/{h3}/archivo')[0] == 200)
api('get', f'{HI}/{h1}/archivo', 404, None, 'un documento sin adjunto -> 404')
cu.execute("UPDATE historial_medico_paciente SET archivo_url=%s WHERE id_historial=%s", ('../../.env', h3)); cx.commit()
chk('una ruta con ../ guardada en la base no sale de la carpeta de adjuntos', c.get(f'{HI}/{h3}/archivo').status_code == 404)
cu.execute("UPDATE historial_medico_paciente SET estado='inactivo' WHERE id_historial=%s", (h3,)); cx.commit()
api('get', f'{HI}/{h3}/archivo', 404, None, 'un documento anulado no se descarga')

limpieza()
sobras = q("SELECT (SELECT COUNT(*) FROM historial_medico_paciente WHERE id_paciente = ANY(%s)) + (SELECT COUNT(*) FROM paciente WHERE nombre LIKE 'ZZ%%')", (pacientes,))[0][0]
chk('limpieza: no quedan datos ZZ', sobras == 0)
chk('limpieza: no quedan archivos ZZ en uploads', not any(os.path.exists(a) for a in archivos))
print('\nFALLOS:', 'ninguno' if not fallos else fallos)
