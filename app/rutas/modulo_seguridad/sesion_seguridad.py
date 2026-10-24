"""Controles de sesión previos a cada request: validación de IP por país (login) y cierre por inactividad.

Se registran una sola vez con registrar_controles_de_sesion(app). Las dos reglas viven en el SERVIDOR: el JS de
inactividad.js solo avisa y redirige, nunca decide por su cuenta si la sesión sigue vigente.
"""
import os
import time

from flask import g, jsonify, redirect, request, session, url_for, current_app

from app.Services import geoip_service
from app.dao.modulo_seguridad.AuditoriaDao import AuditoriaDao

MENSAJE_IP_NO_PERMITIDA = 'No es posible acceder al sistema desde esta ubicación.'
MENSAJE_INACTIVIDAD = 'Sesión cerrada por inactividad'

# Endpoints del primer contacto con el sistema: el chequeo de IP corre antes de leer usuario o contraseña
ENDPOINTS_CON_VALIDACION_IP = {
    'seguridad.login', 'seguridad.verificar_2fa',
    'seguridad.recuperar', 'seguridad.recuperar_codigo', 'seguridad.recuperar_nueva',
}
# Consultas de estado: no cuentan como actividad del usuario (no renuevan la sesión)
RUTAS_SIN_RENOVAR = {'/sesion/estado', '/sesion/expirar'}


def minutos_inactividad():
    try:
        return max(1, int(os.environ.get('SESSION_INACTIVIDAD_MINUTOS') or 30))
    except ValueError:
        return 30


def segundos_aviso():
    try:
        return max(5, int(os.environ.get('SESSION_AVISO_SEGUNDOS') or 120))
    except ValueError:
        return 120




def limite_segundos():
    return minutos_inactividad() * 60


def segundos_restantes():
    """Segundos que le quedan a la sesión actual antes de cerrarse por inactividad (0 si ya venció o no hay actividad registrada)."""
    ultima = session.get('ultima_actividad')
    if ultima is None:
        return limite_segundos()
    return max(0, int(limite_segundos() - (time.time() - ultima)))


def ip_cliente():
    """IP del cliente para auditar: la simulada (solo en modo debug) o request.remote_addr."""
    return g.get('ip_cliente') or request.remote_addr


def _es_ruta_json():
    # /sesion/expirar es una navegación (no un fetch): responde con redirección, no con JSON
    return request.path.startswith('/api/') or request.path in ('/sesion/estado', '/sesion/extender')


def _controlar_ip():
    if request.endpoint not in ENDPOINTS_CON_VALIDACION_IP:
        return None

    g.ip_cliente = geoip_service.ip_efectiva(request.remote_addr)
    evaluacion = geoip_service.evaluar_ip(g.ip_cliente)
    g.pais_detectado = evaluacion['pais']
    g.evaluacion_ip = evaluacion
    if evaluacion['permitido'] and evaluacion['estado'] != geoip_service.ESTADO_SIN_GEOLOCALIZAR:
        return None

    # Solo los intentos (POST) dejan rastro; un GET suelto no es un intento de acceso
    if request.method == 'POST':
        ci_ruc = request.form.get('ci_ruc', '').strip()
        usuario = None
        if ci_ruc:
            from app.dao.modulo_seguridad.UsuarioDao import UsuarioDao
            usuario = UsuarioDao().get_by_ci_ruc(ci_ruc)
        resultado = 'IP_NO_PERMITIDA' if not evaluacion['permitido'] else 'IP_SIN_GEOLOCALIZAR'
        AuditoriaDao().registrar(usuario['id_usuario'] if usuario else None, ci_ruc, resultado,
                                 g.ip_cliente, 'LOGIN', pais_detectado=evaluacion['pais'])

    if not evaluacion['permitido']:
        # Mensaje genérico: no revela país, ni reglas, ni si el usuario existe
        from flask import flash, render_template
        flash(MENSAJE_IP_NO_PERMITIDA, 'danger')
        if request.endpoint == 'seguridad.login':
            return render_template('login.html', ip_bloqueada=True), 403
        return redirect(url_for('seguridad.login'))
    return None


def _controlar_inactividad():
    if not session.get('id_usuario') or request.endpoint == 'static' or request.method == 'OPTIONS':
        return None

    ahora = time.time()
    ultima = session.get('ultima_actividad')
    if ultima is not None and ahora - ultima > limite_segundos():
        id_usuario = session.get('id_usuario')
        ci_ruc = session.get('ci_ruc', '')
        try:
            AuditoriaDao().registrar(id_usuario, ci_ruc, 'CIERRE_INACTIVIDAD', request.remote_addr, 'LOGOUT')
        except Exception as e:
            # Si la base no responde, igual se cierra la sesión y se redirige: la falla solo se registra en el log
            current_app.logger.error(f"No se pudo auditar el cierre por inactividad: {str(e)}")
        session.clear()
        from flask import flash
        flash(MENSAJE_INACTIVIDAD, 'warning')
        if _es_ruta_json():
            return jsonify({'success': False, 'error': MENSAJE_INACTIVIDAD + '.', 'codigo': 'INACTIVIDAD',
                            'redirigir': url_for('seguridad.login')}), 401
        return redirect(url_for('seguridad.login'))

    # Una sesión sin marca (iniciada antes de este control) arranca ahora
    sin_renovar = request.path in RUTAS_SIN_RENOVAR or request.headers.get('X-Sin-Actividad') == '1'
    if ultima is None or not sin_renovar:
        session['ultima_actividad'] = ahora
    return None


def registrar_controles_de_sesion(app):
    @app.before_request
    def controles_de_sesion():
        respuesta = _controlar_ip()
        if respuesta is not None:
            return respuesta
        return _controlar_inactividad()

    @app.context_processor
    def inyectar_config_inactividad():
        return dict(inactividad_cfg={
            'limite': limite_segundos(),
            'aviso': min(segundos_aviso(), limite_segundos() - 1),
        })
