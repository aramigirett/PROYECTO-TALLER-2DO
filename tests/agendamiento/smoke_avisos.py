"""Etapa 3: Avisos y Recordatorios con envío automático (WhatsApp con sesión persistente y respaldo por correo).

NO usa WhatsApp ni Gmail reales: el navegador (Selenium) y el correo son dobles de prueba. Cubre:
  - WhatsAppSesion: estado (vinculado / QR / sin verificar), envío, número inválido, no vinculado, navegador cerrado; teléfono normalizado y plantilla del mensaje.
  - enviar_recordatorio: WhatsApp, respaldo por correo (con el motivo), ambos fallan, forma Gmail, SMS heredado, paciente sin correo.
  - API: aviso de una cita (datos salen de la cita) o de un paciente, anulados rechazados, un aviso vigente por cita, enviar (ENVIADO / ERROR con canal y motivo),
    reenvío, auditoría SIN el texto del mensaje, confirmación, anular / reactivar, sin teléfono ni correo en las listas, y permisos por rol.
Datos `ZZ`: se borran por ID, junto con su auditoría.
"""
import atexit
import datetime
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from app import app
from app.Services import email_service, whatsapp_service as ws
from tests._conexion_pruebas import Conexion
from tests.consultorio._fixtures import Fixtures
from tests.facturacion._limpieza import borrar_auditoria

c = app.test_client()
fallos = []


def chk(nombre, cond):
    print(('OK  ' if cond else 'FAIL'), nombre)
    if not cond:
        fallos.append(nombre)


def api(metodo, url, esperado, json=None, nombre=None, contiene=None, campo=None):
    f = getattr(c, metodo)
    r = f(url, json=json) if json is not None else f(url)
    d = r.get_json(silent=True) or {}
    ok = r.status_code == esperado
    if contiene is not None:
        ok = ok and contiene in (d.get('error') or d.get('mensaje') or '')
    if campo is not None:
        ok = ok and d.get('campo') == campo
    chk(f"{nombre or metodo + ' ' + url} -> {r.status_code}" + ('' if ok else f' {d}'), ok)
    return d


# ---------------- dobles de prueba ----------------
class Elemento:
    def __init__(self, driver, accion=None):
        self.driver, self.accion = driver, accion

    def click(self):
        if self.accion:
            self.accion()

    def send_keys(self, *_):
        if self.accion:
            self.accion()


class NavegadorFalso:
    """Un WhatsApp Web mínimo: `presentes` = fragmentos de XPath que existen en la página actual."""
    def __init__(self, presentes, falla_click=False):
        self.presentes, self.urls, self.cerrado, self.falla_click = list(presentes), [], False, falla_click
        self.enviados = 0
        self._url = 'https://web.whatsapp.com/'

    @property
    def current_url(self):
        if self.cerrado:
            raise RuntimeError('ventana cerrada')
        return self._url

    def get(self, url):
        self.urls.append(url); self._url = url

    def find_elements(self, _by, xpath):
        if self.cerrado:
            raise RuntimeError('ventana cerrada')
        if any(p in xpath for p in self.presentes):
            if 'Enviar' in xpath or 'data-icon="send"' in xpath:
                return [Elemento(self, self._enviar)]
            return [Elemento(self)]
        return []

    def _enviar(self):
        if self.falla_click:
            raise RuntimeError('boom')
        self.enviados += 1

    def quit(self):
        self.cerrado = True


VINCULADA = ['pane-side', 'footer', 'aria-label="Enviar"']
SIN_VINCULAR = ['canvas']


def sesion_con(*navegadores):
    cola = list(navegadores)
    return ws.WhatsAppSesion(driver_factory=lambda perfil: cola.pop(0), perfil='zz', pausa=0.01)


print('== Teléfono y plantilla')
# Solo los celulares guardados en formato nacional (09XX): se quita el 0 y se antepone 595. Línea baja o cualquier otra cosa -> None (sin WhatsApp).
for entrada, esperado in (('0981123456', '595981123456'), ('0981 123 456', '595981123456'), ('0981 123-456', '595981123456'), ('0991717821', '595991717821'),
                          ('021 339 8423', None), ('021 234 567', None), ('+595 981 123456', None), ('595981123456', None), ('981123456', None),
                          ('12', None), ('', None), (None, None), ('abc', None)):
    chk(f'normalizar_telefono({entrada!r}) -> {esperado}', ws.normalizar_telefono(entrada) == esperado)
aviso_ej = {'paciente': 'ANA PEREZ', 'fecha_cita': '2030-05-04', 'hora_cita': '09:30', 'medico': 'LUIS GOMEZ', 'nombre_consultorio': 'CENTRAL'}
m = ws.construir_mensaje(aviso_ej)
chk('la plantilla trae paciente, fecha, hora, médico y consultorio', all(x in m for x in ('Ana Perez', '04/05/2030', '09:30', 'LUIS GOMEZ', 'CENTRAL')))
chk('la plantilla funciona sin médico ni consultorio', 'Por asignar' in ws.construir_mensaje({**aviso_ej, 'medico': None, 'nombre_consultorio': None}))

print('\n== Sesión de WhatsApp (navegador falso)')
s = sesion_con(NavegadorFalso(VINCULADA))
chk('sin abrir el navegador: SIN_VERIFICAR', s.estado()['estado'] == ws.SIN_VERIFICAR)
chk('al verificar con la sesión guardada: VINCULADO', s.estado(abrir=True, timeout=1)['estado'] == ws.VINCULADO)
ok, motivo = s.enviar('0981 123456', 'Hola')
nav = s._driver
chk('enviar: sale por el chat del número normalizado con el texto codificado', ok and motivo is None and any('send?phone=595981123456&text=Hola' in u for u in nav.urls) and nav.enviados == 1)
ok, motivo = s.enviar('xx', 'Hola')
chk('enviar: teléfono inválido -> motivo claro, no abre el chat', not ok and 'celular' in motivo and nav.enviados == 1)
ok, motivo = s.enviar('021 339 8423', 'Hola')
chk('enviar a una línea baja: no se manda por WhatsApp (motivo claro, el chat no se abre)', not ok and 'celular' in motivo and 'líneas bajas' in motivo and nav.enviados == 1
    and not any('phone=' in u and '0213398423' in u for u in nav.urls))
s.cerrar()
s = sesion_con(NavegadorFalso(SIN_VINCULAR))
ok, motivo = s.enviar('0981123456', 'Hola')
chk('enviar sin vincular: (False, "no está vinculado") y no manda nada', not ok and 'no está vinculado' in motivo and s._driver.enviados == 0)
chk('vincular: abre WhatsApp Web y dice NO_VINCULADO (hay que escanear el QR)', s.vincular()['estado'] == ws.NO_VINCULADO)
s.cerrar()
s = sesion_con(NavegadorFalso(VINCULADA + ['inválido'], falla_click=False))
s._abrir()
s._driver.presentes = ['pane-side', 'inválido']      # el chat no carga y aparece el cartel de número inválido
ok, motivo = s.enviar('0981123456', 'Hola', timeout=2)
chk('enviar a un número que no tiene WhatsApp -> motivo', not ok and 'no es válido' in motivo)
s.cerrar()
nav1, nav2 = NavegadorFalso(VINCULADA), NavegadorFalso(VINCULADA)
s = sesion_con(nav1, nav2)
s.estado(abrir=True, timeout=1)
nav1.cerrado = True                                    # el usuario cierra la ventana
ok, _ = s.enviar('0981123456', 'Hola')
chk('si cierran la ventana, el servicio abre otro navegador y envía', ok and nav2.enviados == 1)
s.cerrar()
s = sesion_con(NavegadorFalso(VINCULADA, falla_click=True))
ok, motivo = s.enviar('0981123456', 'Hola')
chk('si el botón de enviar no responde, prueba con Enter en la caja de texto', ok)
s.cerrar()
s = sesion_con(NavegadorFalso(['pane-side', 'footer']))
s._abrir(); s._driver.find_elements = lambda *_a: (_ for _ in ()).throw(RuntimeError('se cayó el navegador'))
ok, motivo = s.enviar('0981123456', 'Hola', timeout=1)
chk('si el navegador se cae a mitad del envío: (False, motivo) sin excepción', not ok and bool(motivo))

print('\n== Orquestación: WhatsApp con respaldo por correo')
aviso = {**aviso_ej, 'forma_envio': 'WhatsApp', 'telefono_paciente': '0981123456', 'correo_paciente': 'ana@test.invalid'}
correos = []
correo_ok = lambda dest, asunto, cuerpo: (correos.append((dest, asunto, cuerpo)) or (True, None))
correo_mal = lambda dest, asunto, cuerpo: (False, 'no se pudo conectar con el servidor de correo')


class SesionFalsa:
    def __init__(self, resultado): self.resultado, self.mensajes = resultado, []
    def enviar(self, tel, texto):
        self.mensajes.append((tel, texto)); return self.resultado


with app.app_context():
    r = ws.enviar_recordatorio(aviso, None, SesionFalsa((True, None)), correo_ok)
    chk('WhatsApp ok -> canal WhatsApp, sin motivo, sin correo', r['ok'] and r['canal'] == 'WhatsApp' and r['motivo'] is None and not correos and 'Ana Perez' in r['mensaje'])
    r = ws.enviar_recordatorio(aviso, 'Texto editado', SesionFalsa((True, None)), correo_ok)
    chk('el texto editado en pantalla es el que sale', r['mensaje'] == 'Texto editado')
    r = ws.enviar_recordatorio(aviso, None, SesionFalsa((False, 'WhatsApp no está vinculado (hay que escanear el código QR).')), correo_ok)
    chk('WhatsApp falla -> sale por correo y queda el motivo', r['ok'] and r['canal'] == 'Correo' and 'no está vinculado' in r['motivo'] and correos[-1][0] == 'ana@test.invalid'
        and 'Recordatorio de su cita' in correos[-1][1])
    sesion_real = sesion_con(NavegadorFalso(VINCULADA))
    n = len(correos)
    r = ws.enviar_recordatorio({**aviso, 'telefono_paciente': '021 339 8423'}, None, sesion_real, correo_ok)
    chk('línea baja con forma WhatsApp: no se envía por WhatsApp y sale por el correo de respaldo', r['ok'] and r['canal'] == 'Correo' and 'celular' in r['motivo']
        and len(correos) == n + 1 and (sesion_real._driver is None or sesion_real._driver.enviados == 0))
    sesion_real.cerrar()
    r = ws.enviar_recordatorio(aviso, None, SesionFalsa((False, 'no cargó')), correo_mal)
    chk('WhatsApp y correo fallan -> ERROR con los dos motivos', not r['ok'] and r['canal'] is None and 'WhatsApp: no cargó' in r['motivo'] and 'Correo: no se pudo conectar' in r['motivo'])
    r = ws.enviar_recordatorio({**aviso, 'correo_paciente': ''}, None, SesionFalsa((False, 'no cargó')), correo_ok)
    chk('sin correo registrado: ERROR que lo dice', not r['ok'] and 'no tiene correo' in r['motivo'])
    n = len(correos)
    sf = SesionFalsa((True, None))
    r = ws.enviar_recordatorio({**aviso, 'forma_envio': 'Gmail'}, None, sf, correo_ok)
    chk('forma Gmail: va directo por correo (WhatsApp no se toca)', r['ok'] and r['canal'] == 'Correo' and not sf.mensajes and len(correos) == n + 1 and r['motivo'] is None)
    r = ws.enviar_recordatorio({**aviso, 'forma_envio': 'SMS'}, None, sf, correo_ok)
    chk('forma SMS (heredada): sale por correo y lo explica', r['ok'] and r['canal'] == 'Correo' and 'SMS' in r['motivo'])
    chk('el motivo no supera los 200 caracteres de la columna', len(ws.enviar_recordatorio(aviso, None, SesionFalsa((False, 'x' * 300)), correo_mal)['motivo']) <= 200)
    chk('correo del sistema sin configurar: (False, motivo) sin romper', email_service.enviar_recordatorio_correo('a@b.com', 'a', 'b')[0] in (True, False))

print('\n== API de Avisos')
cx = Conexion().getConexion(); cu = cx.cursor()
fx = Fixtures(cx)


def q(sql, p=()):
    cu.execute(sql, p)
    return cu.fetchall()


def sesion(id_usuario):
    id_rol, nombre = q("SELECT u.id_rol, r.nombre_rol FROM usuarios u JOIN roles r USING(id_rol) WHERE u.id_usuario=%s", (id_usuario,))[0]
    with c.session_transaction() as s_:
        s_.clear(); s_['id_usuario'] = id_usuario; s_['id_rol'] = id_rol; s_['nombre_rol'] = nombre


def usuario_de(rol):
    return q("SELECT u.id_usuario FROM usuarios u JOIN roles r USING(id_rol) WHERE r.nombre_rol=%s AND u.activo ORDER BY 1 LIMIT 1", (rol,))[0][0]


ADMIN, RECEP, MEDICO, CAJERO = usuario_de('Administrador'), usuario_de('Recepcion'), usuario_de('Medico'), usuario_de('Cajero')
FUNC_RECEP = q("SELECT id_funcionario FROM usuarios WHERE id_usuario=%s", (RECEP,))[0][0]
SUF = int(datetime.datetime.now().strftime('%H%M%S'))
FECHA = datetime.date.today() + datetime.timedelta(days=400 + SUF % 200)
avisos_ids, citas_ids = set(), set()
_limpio = []


def limpieza():
    if _limpio:
        return
    _limpio.append(1)
    try:
        cx.rollback()
        cu.execute("DELETE FROM avisos_recordatorios WHERE id_paciente = ANY(%s)", (list(pacientes),))
        cu.execute("DELETE FROM cita_detalle WHERE id_cita_detalle = ANY(%s)", (list(citas_ids),))
        borrar_auditoria(cu, 'avisos_recordatorios', list(avisos_ids))
        cx.commit()
        fx.limpiar()
    except Exception as e:
        cx.rollback()
        print('ERROR en la limpieza:', e)
        fallos.append('limpieza')


medico, _ = fx.medico(con_usuario=False)
consultorio = fx.consultorio()
pacientes = [fx.paciente() for _ in range(4)]
cu.execute("UPDATE paciente SET telefono='0981123456', correo=%s WHERE id_paciente = ANY(%s)", ('zz@test.invalid', pacientes)); cx.commit()
atexit.register(limpieza)
cita = fx.cita(medico, pacientes[0], consultorio, FUNC_RECEP, 'Confirmado')
cita_cancelada = fx.cita(medico, pacientes[1], consultorio, FUNC_RECEP, 'Cancelado')
citas_ids.update({cita, cita_cancelada})
AV = '/api/v1/avisos'

# dobles en el servidor: ni WhatsApp ni Gmail reales
ws._sesion = type('S', (), {'estado': lambda self, abrir=False, timeout=25: {'estado': 'VINCULADO' if abrir else 'SIN_VERIFICAR', 'detalle': 'x'},
                            'vincular': lambda self: {'estado': 'NO_VINCULADO', 'detalle': 'QR'},
                            'enviar': lambda self, tel, texto: ws_resultado[0]})()
ws_resultado = [(True, None)]
mails = []
email_service.enviar_recordatorio_correo = lambda dest, asunto, cuerpo: (mails.append((dest, asunto, cuerpo)) or mail_resultado[0])
mail_resultado = [(True, None)]

sesion(RECEP)
chk('vista Tabler', b'tabler' in c.get('/referenciales/avisos-recordatorios/avisos-recordatorios').data.lower())
api('post', AV, 400, {'forma_envio': 'Telegram', 'id_cita_detalle': cita}, 'forma de envío inválida', campo='forma_envio')
api('post', AV, 400, {'forma_envio': 'WhatsApp'}, 'sin paciente ni cita', campo='id_paciente')
api('post', AV, 400, {'forma_envio': 'WhatsApp', 'id_paciente': pacientes[2], 'fecha_cita': 'x', 'hora_cita': '09:00'}, 'fecha inválida', campo='fecha_cita')
api('post', AV, 400, {'forma_envio': 'WhatsApp', 'id_cita_detalle': cita_cancelada}, 'una cita Cancelada no se recuerda', contiene='pendiente', campo='id_cita_detalle')
d = api('post', AV, 201, {'forma_envio': 'WhatsApp', 'id_cita_detalle': cita, 'id_paciente': pacientes[3], 'fecha_cita': '2020-01-01', 'hora_cita': '03:00'}, 'aviso de una cita (los datos del navegador se ignoran)')
av1 = d['data']['id_aviso']; avisos_ids.add(av1)
fila = q("SELECT id_paciente, id_funcionario, id_medico, codigo, fecha_cita, hora_cita::text, id_cita_detalle, estado_envio FROM avisos_recordatorios WHERE id_aviso=%s", (av1,))[0]
chk('aviso de una cita: paciente, médico, consultorio, fecha y hora salen de la cita; el funcionario, de la sesión',
    fila[0] == pacientes[0] and fila[1] == FUNC_RECEP and fila[2] == medico and fila[3] == consultorio and fila[4] == q("SELECT fecha_cita FROM cita_detalle WHERE id_cita_detalle=%s", (cita,))[0][0] and fila[6] == cita and fila[7] == 'Pendiente')
a = q("SELECT modulo, detalle, valores_nuevos, id_usuario FROM auditoria_cambios WHERE entidad='avisos_recordatorios' AND id_registro=%s AND accion='ALTA'", (av1,))
chk('auditoría ALTA con módulo y nombres', bool(a) and a[0][0] == 'Módulo Agendamiento' and a[0][3] == RECEP and 'ZZ PACIENTE' in str(a[0][2]))
api('post', AV, 409, {'forma_envio': 'WhatsApp', 'id_cita_detalle': cita}, 'un solo aviso vigente por cita', contiene='ya tiene un aviso')
d = api('post', AV, 201, {'forma_envio': 'Gmail', 'id_paciente': pacientes[2], 'fecha_cita': FECHA.isoformat(), 'hora_cita': '10:15', 'mensaje': 'Texto propio'}, 'aviso de un paciente (sin cita)')
av2 = d['data']['id_aviso']; avisos_ids.add(av2)
cu.execute("UPDATE paciente SET activo=false WHERE id_paciente=%s", (pacientes[3],)); cx.commit()
api('post', AV, 400, {'forma_envio': 'WhatsApp', 'id_paciente': pacientes[3], 'fecha_cita': FECHA.isoformat(), 'hora_cita': '10:00'}, 'rechaza un paciente anulado', contiene='anulado', campo='id_paciente')
cu.execute("UPDATE medico SET activo=false WHERE id_medico=%s", (medico,)); cx.commit()
api('post', AV, 400, {'forma_envio': 'WhatsApp', 'id_paciente': pacientes[2], 'id_medico': medico, 'fecha_cita': FECHA.isoformat(), 'hora_cita': '11:00'}, 'rechaza un médico anulado', contiene='anulado', campo='id_medico')
cu.execute("UPDATE medico SET activo=true WHERE id_medico=%s", (medico,)); cx.commit()
cons_inact = fx.consultorio(activo=False)
api('post', AV, 400, {'forma_envio': 'WhatsApp', 'id_paciente': pacientes[2], 'codigo': cons_inact, 'fecha_cita': FECHA.isoformat(), 'hora_cita': '11:00'}, 'rechaza un consultorio anulado', contiene='anulado', campo='codigo')
lista = c.get(AV).get_json()['data']
chk('la lista no trae el teléfono ni el correo del paciente', all('telefono_paciente' not in x and 'correo_paciente' not in x for x in lista) and any(x['id_aviso'] == av1 and x['tiene_telefono'] for x in lista))
d = api('get', f'{AV}/{av1}/mensaje-preview', 200, nombre='vista previa del mensaje')
chk('la vista previa trae la plantilla con los datos de la cita', 'ZZ PACIENTE' in d['mensaje'].upper() and '🏥 Consultorio' in d['mensaje'])
d = api('get', f'{AV}/{av2}/mensaje-preview', 200, nombre='vista previa de un aviso con texto propio')
chk('...y respeta el texto propio cargado al crear', d['mensaje'] == 'Texto propio')

print('\n== Enviar')
ws_resultado[0] = (True, None)
d = api('post', f'{AV}/{av1}/enviar', 200, {'mensaje': 'Hola, recordatorio ZZ editado'}, 'enviar por WhatsApp')
fila = q("SELECT estado_envio, canal_enviado, motivo_error, fecha_envio IS NOT NULL, mensaje FROM avisos_recordatorios WHERE id_aviso=%s", (av1,))[0]
chk('queda ENVIADO por WhatsApp, con fecha y el texto que salió', fila == ('Enviado', 'WhatsApp', None, True, 'Hola, recordatorio ZZ editado'))
m = q("SELECT detalle, valores_anteriores, valores_nuevos FROM auditoria_cambios WHERE entidad='avisos_recordatorios' AND id_registro=%s AND accion='MODIFICACION' ORDER BY id_auditoria_cambio DESC LIMIT 1", (av1,))[0]
chk('la auditoría del envío NO guarda el texto del mensaje', 'recordatorio ZZ' not in str(m) and 'Enviado' in str(m[2]) and 'WhatsApp' in str(m[2]))
api('post', f'{AV}/{av1}/enviar', 409, {}, 'un aviso enviado no se reenvía', contiene='ya fue enviado')
ws_resultado[0] = (False, 'WhatsApp no está vinculado (hay que escanear el código QR).')
mail_resultado[0] = (True, None)
d = api('post', f'{AV}/{av2}/enviar', 200, {}, 'enviar por Gmail')
fila = q("SELECT estado_envio, canal_enviado, motivo_error FROM avisos_recordatorios WHERE id_aviso=%s", (av2,))[0]
chk('forma Gmail: ENVIADO por Correo, sin tocar WhatsApp, con el texto propio', fila == ('Enviado', 'Correo', None) and mails[-1][2] == 'Texto propio' and mails[-1][0] == 'zz@test.invalid')
# respaldo y error
cita2 = fx.cita(medico, pacientes[2], consultorio, FUNC_RECEP, 'Reservado'); citas_ids.add(cita2)
av3 = api('post', AV, 201, {'forma_envio': 'WhatsApp', 'id_cita_detalle': cita2}, 'aviso para probar el respaldo')['data']['id_aviso']; avisos_ids.add(av3)
d = api('post', f'{AV}/{av3}/enviar', 200, {}, 'WhatsApp no vinculado -> sale por correo')
chk('mensaje al usuario dice que salió por Correo y por qué', 'Correo' in d['mensaje'] and 'no está vinculado' in d['mensaje'])
fila = q("SELECT estado_envio, canal_enviado, motivo_error FROM avisos_recordatorios WHERE id_aviso=%s", (av3,))[0]
chk('queda ENVIADO por Correo con el motivo del respaldo', fila[0] == 'Enviado' and fila[1] == 'Correo' and 'no está vinculado' in fila[2])
cita3 = fx.cita(medico, pacientes[0], consultorio, FUNC_RECEP, 'Reservado'); citas_ids.add(cita3)
av4 = api('post', AV, 201, {'forma_envio': 'WhatsApp', 'id_cita_detalle': cita3}, 'aviso para probar el error')['data']['id_aviso']; avisos_ids.add(av4)
mail_resultado[0] = (False, 'la dirección de correo del paciente fue rechazada')
api('post', f'{AV}/{av4}/enviar', 502, {}, 'WhatsApp y correo fallan -> 502 con el motivo', contiene='rechazada')
fila = q("SELECT estado_envio, canal_enviado, motivo_error, fecha_envio FROM avisos_recordatorios WHERE id_aviso=%s", (av4,))[0]
chk('queda ERROR sin canal, con los dos motivos y sin fecha de envío', fila[0] == 'Error' and fila[1] is None and 'WhatsApp:' in fila[2] and 'Correo:' in fila[2] and fila[3] is None)
mail_resultado[0] = (True, None); ws_resultado[0] = (True, None)
api('post', f'{AV}/{av4}/enviar', 200, {}, 'un aviso en ERROR se puede reenviar')
chk('...y queda ENVIADO por WhatsApp sin el motivo viejo', q("SELECT estado_envio, canal_enviado, motivo_error FROM avisos_recordatorios WHERE id_aviso=%s", (av4,))[0] == ('Enviado', 'WhatsApp', None))
api('post', f'{AV}/{av4}/enviar', 400, {'mensaje': 'x' * 1001}, 'mensaje de más de 1000 caracteres', campo='mensaje')
api('post', f'{AV}/999999/enviar', 404, {}, 'enviar un aviso inexistente')
api('put', f'{AV}/{av1}', 403, {'forma_envio': 'Gmail', 'id_cita_detalle': cita}, 'Recepción NO edita avisos (solo el Administrador)')

print('\n== Confirmación, anular, reactivar y WhatsApp')
api('patch', f'{AV}/{av1}/estado', 200, {'estado_confirmacion': 'Confirmado'}, 'confirmación del paciente')
api('patch', f'{AV}/{av1}/estado', 400, {'estado_confirmacion': 'Quizás'}, 'confirmación inválida', campo='estado_confirmacion')
chk('la confirmación quedó auditada', 'Confirmado' in str(q("SELECT valores_nuevos FROM auditoria_cambios WHERE entidad='avisos_recordatorios' AND id_registro=%s AND accion='MODIFICACION' ORDER BY id_auditoria_cambio DESC LIMIT 1", (av1,))))
api('delete', f'{AV}/{av1}', 200, None, 'anular un aviso')
chk('BAJA auditada y la lista ya no lo trae', bool(q("SELECT 1 FROM auditoria_cambios WHERE entidad='avisos_recordatorios' AND id_registro=%s AND accion='BAJA'", (av1,))) and all(x['id_aviso'] != av1 for x in c.get(AV).get_json()['data']))
chk('?inactivos=1 lo trae como anulado', any(x['id_aviso'] == av1 and not x['activo'] for x in c.get(AV + '?inactivos=1').get_json()['data']))
d = api('post', AV, 201, {'forma_envio': 'WhatsApp', 'id_cita_detalle': cita}, 'se puede crear otro aviso para la cita del anulado'); avisos_ids.add(d['data']['id_aviso'])
api('patch', f'{AV}/{av1}/reactivar', 409, None, 'reactivar con otro aviso vigente para la cita', contiene='ya tiene un aviso vigente')
api('delete', f'{AV}/{d["data"]["id_aviso"]}', 200, None, 'anula el segundo')
api('patch', f'{AV}/{av1}/reactivar', 200, None, 'reactivación')
chk('REACTIVACION auditada', bool(q("SELECT 1 FROM auditoria_cambios WHERE entidad='avisos_recordatorios' AND id_registro=%s AND accion='REACTIVACION'", (av1,))))
d = api('get', '/api/v1/avisos/whatsapp/estado', 200, nombre='estado de WhatsApp (sin abrir el navegador)')
chk('...SIN_VERIFICAR hasta que alguien verifique', d['data']['estado'] == 'SIN_VERIFICAR')
d = api('get', '/api/v1/avisos/whatsapp/estado?verificar=1', 200, nombre='verificar la sesión')
chk('...VINCULADO', d['data']['estado'] == 'VINCULADO')
d = api('post', '/api/v1/avisos/whatsapp/vincular', 200, {}, 'vincular')
chk('...pide escanear el QR', d['data']['estado'] == 'NO_VINCULADO')

print('\n== Permisos')
sesion(MEDICO)
api('get', AV, 200, None, 'Médico ve los avisos')
for metodo, url, cuerpo, n in (('post', AV, {'forma_envio': 'WhatsApp', 'id_cita_detalle': cita}, 'crea'), ('post', f'{AV}/{av3}/enviar', {}, 'envía'), ('delete', f'{AV}/{av3}', None, 'anula'),
                               ('patch', f'{AV}/{av3}/estado', {'estado_confirmacion': 'Confirmado'}, 'confirma'), ('post', '/api/v1/avisos/whatsapp/vincular', {}, 'vincula WhatsApp')):
    api(metodo, url, 403, cuerpo, f'Médico NO {n}')
api('get', '/api/v1/avisos/whatsapp/estado?verificar=1', 403, None, 'Médico NO verifica la sesión')
api('get', '/api/v1/avisos/whatsapp/estado', 200, None, 'Médico ve el estado de WhatsApp')
sesion(CAJERO)
api('get', AV, 403, None, 'Cajero no ve avisos')
chk('Cajero no abre la vista', c.get('/referenciales/avisos-recordatorios/avisos-recordatorios').status_code == 403)
sesion(ADMIN)

limpieza()
sobras = q("SELECT (SELECT COUNT(*) FROM avisos_recordatorios WHERE id_paciente = ANY(%s)) + (SELECT COUNT(*) FROM paciente WHERE nombre LIKE 'ZZ%%')", (pacientes,))[0][0]
chk('limpieza: no quedan datos ZZ', sobras == 0)
print('\nFALLOS:', 'ninguno' if not fallos else fallos)
