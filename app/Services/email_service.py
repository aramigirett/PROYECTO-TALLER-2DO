import os
import smtplib
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
