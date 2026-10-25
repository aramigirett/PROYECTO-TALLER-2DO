"""
=====================================================
Servicio: envío de avisos y recordatorios (WhatsApp Web con respaldo por correo)
Descripción:
  - WhatsAppSesion: UNA sesión de WhatsApp Web por servidor. Selenium abre el navegador con un PERFIL persistente dentro del proyecto
    (`whatsapp_session/`, fuera de git), así el QR se escanea una sola vez. Sabe decir si la sesión está vinculada,
    abrir la pantalla del QR para vincular y enviar un mensaje a un número.
  - construir_mensaje(): el recordatorio sale solo de una plantilla con paciente, médico, fecha, hora y consultorio de la cita.
  - enviar_recordatorio(): orquesta el envío de UN aviso: WhatsApp y, si no está vinculado o falla, el mismo recordatorio por correo
    (el Gmail SMTP del 2FA). Devuelve por qué canal salió y el motivo de cualquier fallo; no toca la base (lo registra la API).
No se prueba contra WhatsApp real en los tests: el navegador y el correo se inyectan.
=====================================================
"""
import os
import re
import threading
import time
import urllib.parse
from datetime import datetime

from flask import current_app as app

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PERFIL_POR_DEFECTO = os.path.join(RAIZ, 'whatsapp_session')   # ya está en .gitignore (whatsapp_session*); el perfil viejo (whatsapp_session_persistente) se puede borrar
URL_WHATSAPP = 'https://web.whatsapp.com/'

VINCULADO = 'VINCULADO'
NO_VINCULADO = 'NO_VINCULADO'
SIN_VERIFICAR = 'SIN_VERIFICAR'
CARGANDO = 'CARGANDO'

# Selectores (WhatsApp Web cambia: se prueban varios, en español e inglés)
SEL_VINCULADO = ['//div[@id="pane-side"]', '//div[@aria-label="Lista de chats"]', '//div[@aria-label="Chat list"]',
                 '//span[@data-icon="chats-filled"]', '//span[@data-icon="chat"]']
SEL_QR = ['//canvas[@aria-label]', '//div[@data-ref]', '//canvas']
SEL_CAJA = ['//footer//div[@contenteditable="true"]', '//div[@contenteditable="true"][@data-tab="10"]']
SEL_ENVIAR = ['//button[@aria-label="Enviar"]', '//button[@aria-label="Send"]', '//span[@data-icon="send"]/ancestor::button',
              '//span[@data-icon="wds-ic-send-filled"]/ancestor::button', '//div[@role="button"][@aria-label="Enviar"]']
SEL_INVALIDO = ['//*[contains(text(), "inválido")]', '//*[contains(text(), "no es válido")]', '//*[contains(text(), "invalid")]',
                '//*[contains(text(), "no está en WhatsApp")]', '//*[contains(text(), "not on WhatsApp")]']
SEL_RELOJ = ['//span[@data-icon="msg-time"]']


# ---------------------------------------------------------------------------
# Plantilla del mensaje
# ---------------------------------------------------------------------------
PLANTILLA = (
    "Hola {paciente}, le saluda {clinica}.\n\n"
    "Le recordamos su cita:\n"
    "📅 Fecha: {fecha}\n"
    "🕐 Hora: {hora}\n"
    "👨‍⚕️ Médico: {medico}\n"
    "🏥 Consultorio: {consultorio}\n\n"
    "Por favor confirme su asistencia respondiendo este mensaje. Si necesita reprogramar, avísenos con anticipación.\n\n"
    "Gracias."
)
NOMBRE_CLINICA = os.environ.get('NOMBRE_CLINICA', 'OdontoClinic')


def _fecha_legible(fecha):
    try:
        return datetime.strptime(str(fecha)[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
    except ValueError:
        return str(fecha)


def construir_mensaje(aviso):
    """El recordatorio, armado con los datos de la cita del aviso (paciente, médico, fecha, hora y consultorio)."""
    return PLANTILLA.format(
        paciente=(aviso.get('paciente') or 'paciente').title(), clinica=NOMBRE_CLINICA, fecha=_fecha_legible(aviso.get('fecha_cita')),
        hora=str(aviso.get('hora_cita') or '')[:5], medico=aviso.get('medico') or 'Por asignar',
        consultorio=aviso.get('nombre_consultorio') or 'nuestras instalaciones')


def asunto_correo(aviso):
    return f"Recordatorio de su cita del {_fecha_legible(aviso.get('fecha_cita'))} - {NOMBRE_CLINICA}"


def normalizar_telefono(telefono):
    """Número para WhatsApp (Paraguay): 0981 123 456 -> 595981123456. Devuelve None si no parece un celular o fijo paraguayo."""
    digitos = re.sub(r'\D', '', str(telefono or ''))
    if not digitos:
        return None
    if digitos.startswith('0'):
        digitos = '595' + digitos[1:]
    elif not digitos.startswith('595'):
        digitos = '595' + digitos
    return digitos if re.fullmatch(r'595\d{8,9}', digitos) else None


# ---------------------------------------------------------------------------
# Sesión de WhatsApp Web
# ---------------------------------------------------------------------------
def _crear_navegador(perfil):
    """Abre Chrome (o Edge si no hay Chrome) con el perfil persistente. Selenium Manager baja el driver si hace falta."""
    from selenium import webdriver
    chrome = [p for p in (r'C:\Program Files\Google\Chrome\Application\chrome.exe', r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                          os.path.join(os.environ.get('LOCALAPPDATA', ''), r'Google\Chrome\Application\chrome.exe')) if os.path.exists(p)]
    usar_edge = os.environ.get('WHATSAPP_BROWSER', '').lower() == 'edge' or (not chrome and os.environ.get('WHATSAPP_BROWSER', '').lower() != 'chrome')
    opciones = webdriver.EdgeOptions() if usar_edge else webdriver.ChromeOptions()
    opciones.add_argument(f'--user-data-dir={perfil}' if not usar_edge else f'--user-data-dir={perfil}_edge')
    opciones.add_argument('--profile-directory=Default')
    opciones.add_argument('--disable-blink-features=AutomationControlled')
    opciones.add_argument('--no-first-run')
    opciones.add_argument('--window-size=1100,800')
    opciones.add_experimental_option('excludeSwitches', ['enable-automation'])
    return webdriver.Edge(options=opciones) if usar_edge else webdriver.Chrome(options=opciones)


MSG_NO_ABRE = ('No se pudo abrir el navegador de WhatsApp. Si quedó abierta otra ventana de Chrome de WhatsApp (de antes), ciérrela e intente de nuevo; '
               'el navegador no puede abrirse dos veces con el mismo perfil.')


def _motivo_navegador(e):
    """Texto para el usuario cuando Selenium no logra abrir o conducir el navegador (típico: el perfil ya lo usa otra ventana)."""
    nombre = type(e).__name__
    if nombre in ('SessionNotCreatedException', 'WebDriverException', 'NoSuchDriverException'):
        return MSG_NO_ABRE
    return 'Falló el navegador de WhatsApp Web.'


class WhatsAppSesion:
    """
    La sesión de WhatsApp Web del servidor. Un solo navegador a la vez (un lock serializa todo). `driver_factory` permite inyectar un navegador
    falso en los tests. Los estados: SIN_VERIFICAR (todavía no se abrió el navegador), CARGANDO, VINCULADO, NO_VINCULADO (hay que escanear el QR).
    """

    def __init__(self, driver_factory=None, perfil=None, pausa=0.5):
        self._factory = driver_factory or _crear_navegador
        self.perfil = perfil or os.environ.get('WHATSAPP_PROFILE_DIR') or PERFIL_POR_DEFECTO
        self._driver = None
        self._lock = threading.RLock()
        self._pausa = pausa

    # ---- navegador ----
    def _abrir(self):
        if self._driver is not None:
            try:
                self._driver.current_url   # ¿sigue vivo? (el usuario pudo cerrar la ventana)
                return
            except Exception:
                self._driver = None
        self._driver = self._factory(self.perfil)
        self._driver.get(URL_WHATSAPP)

    def cerrar(self):
        with self._lock:
            if self._driver is not None:
                try:
                    self._driver.quit()
                except Exception:
                    pass
                self._driver = None

    def _hay(self, selectores):
        for s in selectores:
            try:
                if self._driver.find_elements('xpath', s):
                    return True
            except Exception:
                pass
        return False

    def _leer_estado(self):
        if self._hay(SEL_VINCULADO):
            return VINCULADO
        if self._hay(SEL_QR):
            return NO_VINCULADO
        return CARGANDO

    def _esperar_estado(self, timeout):
        fin = time.time() + timeout
        estado = self._leer_estado()
        while estado == CARGANDO and time.time() < fin:
            time.sleep(self._pausa)
            estado = self._leer_estado()
        return estado

    # ---- API pública ----
    def estado(self, abrir=False, timeout=25):
        """
        {'estado': ..., 'detalle': ...}. Con abrir=False no lanza el navegador (SIN_VERIFICAR si todavía no está abierto); con abrir=True lo abre,
        espera a que cargue y dice si la sesión sigue vinculada.
        """
        with self._lock:
            if self._driver is None and not abrir:
                return {'estado': SIN_VERIFICAR, 'detalle': 'Todavía no se verificó la sesión de WhatsApp en este servidor.'}
            try:
                self._abrir()
                estado = self._esperar_estado(timeout)
                detalle = {VINCULADO: 'WhatsApp Web está vinculado.', NO_VINCULADO: 'Escanee el código QR con el celular de la clínica.',
                           CARGANDO: 'WhatsApp Web todavía está cargando.'}[estado]
                return {'estado': estado, 'detalle': detalle}
            except Exception as e:
                app.logger.error(f"Error al verificar la sesión de WhatsApp: {str(e)}")
                self.cerrar()
                return {'estado': SIN_VERIFICAR, 'detalle': _motivo_navegador(e)}

    def vincular(self):
        """Abre WhatsApp Web (con el navegador a la vista) para escanear el QR. Es no bloqueante: la pantalla consulta estado() hasta VINCULADO."""
        return self.estado(abrir=True, timeout=10)

    def enviar(self, telefono, mensaje, timeout=40):
        """Envía `mensaje` al número. Devuelve (True, None) o (False, motivo)."""
        numero = normalizar_telefono(telefono)
        if not numero:
            return False, 'El paciente no tiene un teléfono válido.'
        with self._lock:
            try:
                self._abrir()
                estado = self._esperar_estado(timeout)
                if estado != VINCULADO:
                    return False, ('WhatsApp no está vinculado (hay que escanear el código QR).' if estado == NO_VINCULADO
                                   else 'WhatsApp Web no terminó de cargar.')
                self._driver.get(f"{URL_WHATSAPP}send?phone={numero}&text={urllib.parse.quote(mensaje)}")
                fin = time.time() + timeout
                while time.time() < fin:
                    if self._hay(SEL_INVALIDO) and not self._hay(SEL_CAJA):
                        return False, 'El número no es válido o no tiene WhatsApp.'
                    if self._hay(SEL_CAJA):
                        break
                    time.sleep(self._pausa)
                else:
                    return False, 'No cargó el chat de WhatsApp a tiempo.'
                time.sleep(self._pausa)
                if not self._click_enviar():
                    return False, 'No se encontró el botón de enviar de WhatsApp Web.'
                # esperar a que el reloj de "enviando" desaparezca (el mensaje salió)
                fin = time.time() + 15
                time.sleep(self._pausa)
                while self._hay(SEL_RELOJ) and time.time() < fin:
                    time.sleep(self._pausa)
                return True, None
            except Exception as e:
                app.logger.error(f"Error al enviar por WhatsApp: {str(e)}")
                self.cerrar()
                return False, _motivo_navegador(e)

    def _click_enviar(self):
        for s in SEL_ENVIAR:
            try:
                elementos = self._driver.find_elements('xpath', s)
                if elementos:
                    elementos[0].click()
                    return True
            except Exception:
                continue
        try:   # último recurso: Enter en la caja de texto
            for s in SEL_CAJA:
                cajas = self._driver.find_elements('xpath', s)
                if cajas:
                    from selenium.webdriver.common.keys import Keys
                    cajas[0].send_keys(Keys.ENTER)
                    return True
        except Exception:
            pass
        return False


_sesion = WhatsAppSesion()


def sesion_whatsapp():
    """La sesión única del servidor."""
    return _sesion


# ---------------------------------------------------------------------------
# Envío de un aviso (WhatsApp con respaldo por correo)
# ---------------------------------------------------------------------------
def enviar_recordatorio(aviso, mensaje=None, sesion=None, correo=None):
    """
    Envía el recordatorio de UN aviso (dict de AvisoRecordatorioDao.getAvisoById) por el canal elegido, con respaldo por correo.
      mensaje  texto final (si la pantalla lo editó); si no, se arma desde la plantilla con los datos de la cita
      sesion   WhatsAppSesion (por defecto la del servidor)   ·   correo  función(destinatario, asunto, cuerpo) -> (ok, motivo)
    Devuelve {'ok', 'canal' ('WhatsApp' | 'Correo' | None), 'motivo' (por qué falló WhatsApp o por qué se usó el correo), 'mensaje'}.
    """
    from app.Services.email_service import enviar_recordatorio_correo
    sesion = sesion or sesion_whatsapp()
    correo = correo or enviar_recordatorio_correo
    texto = (mensaje or '').strip() or construir_mensaje(aviso)
    motivos = []

    if aviso.get('forma_envio') == 'WhatsApp':
        ok, motivo = sesion.enviar(aviso.get('telefono_paciente'), texto)
        if ok:
            return {'ok': True, 'canal': 'WhatsApp', 'motivo': None, 'mensaje': texto}
        motivos.append(f'WhatsApp: {motivo}')
    elif aviso.get('forma_envio') == 'SMS':
        motivos.append('SMS: no está disponible en este sistema')

    destino = (aviso.get('correo_paciente') or '').strip()
    if not destino:
        motivos.append('Correo: el paciente no tiene correo registrado')
        return {'ok': False, 'canal': None, 'motivo': '. '.join(motivos)[:200], 'mensaje': texto}
    ok, motivo = correo(destino, asunto_correo(aviso), texto)
    if ok:
        return {'ok': True, 'canal': 'Correo', 'motivo': ('. '.join(motivos)[:200] or None), 'mensaje': texto}
    motivos.append(f'Correo: {motivo}')
    return {'ok': False, 'canal': None, 'motivo': '. '.join(motivos)[:200], 'mensaje': texto}
