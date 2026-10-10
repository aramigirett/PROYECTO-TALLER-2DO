import os
import smtplib
import threading
from datetime import datetime
from email.mime.text import MIMEText

from flask import current_app as app

MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", MAIL_USERNAME)


def enviar_codigo_2fa(destinatario, codigo):
    """
    Envía el código de verificación 2FA por correo electrónico.
    Retorna True si el envío fue exitoso, False en caso contrario.
    """
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        app.logger.error(
            "No se pudo enviar el código 2FA: faltan las variables de entorno "
            "MAIL_USERNAME/MAIL_PASSWORD."
        )
        return False

    asunto = "Código de verificación - OdontoClinic"
    cuerpo = (
        f"Tu código de verificación es: {codigo}\n\n"
        "Este código vence en 5 minutos. Si no solicitaste este acceso, "
        "ignorá este mensaje."
    )

    mensaje = MIMEText(cuerpo, "plain", "utf-8")
    mensaje["Subject"] = asunto
    mensaje["From"] = MAIL_DEFAULT_SENDER
    mensaje["To"] = destinatario

    try:
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=10) as servidor:
            if MAIL_USE_TLS:
                servidor.starttls()
            servidor.login(MAIL_USERNAME, MAIL_PASSWORD)
            servidor.sendmail(MAIL_DEFAULT_SENDER, [destinatario], mensaje.as_string())
        return True
    except Exception as e:
        app.logger.error(f"Error al enviar código 2FA por correo: {str(e)}")
        return False


# ---------------------------------------------------------------------------
# Alertas de seguridad (intentos fallidos y bloqueo de cuenta)
# Nunca incluyen la contraseña ingresada.
# ---------------------------------------------------------------------------

def _enviar_correo(destinatarios, asunto, cuerpo):
    """
    Envía un correo de texto plano a una o varias direcciones. Retorna True si
    el envío fue exitoso. No lanza excepciones: un fallo de SMTP no debe
    romper el login.
    """
    if isinstance(destinatarios, str):
        destinatarios = [destinatarios]
    # El correo sale de la persona vinculada y puede faltar (None)
    destinatarios = [d for d in (destinatarios or []) if d]
    if not destinatarios:
        return False

    if not MAIL_USERNAME or not MAIL_PASSWORD:
        app.logger.error(
            "No se pudo enviar la alerta de seguridad: faltan las variables de "
            "entorno MAIL_USERNAME/MAIL_PASSWORD."
        )
        return False

    mensaje = MIMEText(cuerpo, "plain", "utf-8")
    mensaje["Subject"] = asunto
    mensaje["From"] = MAIL_DEFAULT_SENDER
    mensaje["To"] = ", ".join(destinatarios)

    try:
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=10) as servidor:
            if MAIL_USE_TLS:
                servidor.starttls()
            servidor.login(MAIL_USERNAME, MAIL_PASSWORD)
            servidor.sendmail(MAIL_DEFAULT_SENDER, destinatarios, mensaje.as_string())
        return True
    except Exception as e:
        app.logger.error(f"Error al enviar alerta de seguridad por correo: {str(e)}")
        return False


def _en_segundo_plano(funcion, *args):
    """
    Ejecuta el envío en un hilo aparte para que el SMTP (hasta 10 s de timeout)
    no demore la respuesta del login. Reinstala el contexto de la app porque
    el logger usa current_app.
    """
    flask_app = app._get_current_object()

    def tarea():
        with flask_app.app_context():
            funcion(*args)

    threading.Thread(target=tarea, daemon=True).start()


def _ahora():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def enviar_alerta_intento_fallido(destinatario, ci_ruc, ip, intentos, maximo):
    """Avisa al usuario que hubo un intento fallido de acceso a su cuenta."""
    restantes = maximo - intentos
    cuerpo = (
        f"Se registró un intento fallido de acceso a tu cuenta ({ci_ruc}).\n\n"
        f"Fecha y hora: {_ahora()}\n"
        f"IP: {ip or 'desconocida'}\n"
        f"Intentos fallidos consecutivos: {intentos} de {maximo}. "
        f"Si fallás {restantes} vez(es) más, la cuenta se bloqueará.\n\n"
        "Si no fuiste vos, avisá al administrador del sistema."
    )
    return _enviar_correo(destinatario, "Intento de acceso fallido - OdontoClinic", cuerpo)


def enviar_alerta_bloqueo_usuario(destinatario, ci_ruc, ip, minutos):
    """Avisa al usuario que su cuenta quedó bloqueada."""
    cuerpo = (
        f"Tu cuenta ({ci_ruc}) fue bloqueada por superar el máximo de intentos "
        "fallidos de acceso.\n\n"
        f"Fecha y hora: {_ahora()}\n"
        f"IP del último intento: {ip or 'desconocida'}\n\n"
        f"Podés volver a intentar en {minutos} minutos o pedirle al "
        "administrador que la desbloquee.\n"
        "Si no fuiste vos, avisá al administrador del sistema."
    )
    return _enviar_correo(destinatario, "Cuenta bloqueada - OdontoClinic", cuerpo)


def enviar_alerta_bloqueo_admin(destinatarios, ci_ruc, ip, minutos):
    """Avisa a los administradores que una cuenta fue bloqueada."""
    cuerpo = (
        f"La cuenta {ci_ruc} fue bloqueada por intentos fallidos de acceso.\n\n"
        f"Fecha y hora: {_ahora()}\n"
        f"IP del último intento: {ip or 'desconocida'}\n\n"
        f"Se desbloqueará sola en {minutos} minutos, o podés hacerlo desde "
        "Gestión de Usuarios."
    )
    return _enviar_correo(destinatarios, "Cuenta bloqueada por intentos fallidos - OdontoClinic", cuerpo)


def alertar_intento_fallido(destinatario, ci_ruc, ip, intentos, maximo):
    _en_segundo_plano(enviar_alerta_intento_fallido, destinatario, ci_ruc, ip, intentos, maximo)


def alertar_bloqueo(correo_usuario, correos_admin, ci_ruc, ip, minutos):
    _en_segundo_plano(enviar_alerta_bloqueo_usuario, correo_usuario, ci_ruc, ip, minutos)
    _en_segundo_plano(enviar_alerta_bloqueo_admin, correos_admin, ci_ruc, ip, minutos)


def enviar_codigo_recuperacion(destinatario, codigo, minutos):
    """Envía el código de recuperación de contraseña (en segundo plano)."""
    def enviar():
        cuerpo = (
            f"Recibimos una solicitud para recuperar la contraseña de tu cuenta.\n\n"
            f"Tu código de recuperación es: {codigo}\n\n"
            f"Vence en {minutos} minutos y solo puede usarse una vez. "
            "Si no lo solicitaste, ignorá este mensaje: tu contraseña no cambia."
        )
        _enviar_correo(destinatario, "Recuperación de contraseña - OdontoClinic", cuerpo)

    _en_segundo_plano(enviar)
