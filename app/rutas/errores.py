from flask import g, jsonify, render_template, request, session, url_for, current_app as app

from app.rutas.modulo_seguridad.menu_servicio import etiqueta_ventana


def _es_api():
    return request.path.startswith('/api/')


def _etiqueta_ventana():
    """Nombre legible de la ventana que require_permiso dejó en g (si la conoce)."""
    ventana = g.get('ventana_denegada')
    return etiqueta_ventana(ventana) if ventana else None


def _responder(codigo, titulo, mensaje, icono, **extra):
    """Página HTML (con sidebar si hay sesión) o JSON si la ruta es /api/."""
    if _es_api():
        return jsonify({'success': False, 'error': mensaje}), codigo

    con_sesion = bool(session.get('id_usuario'))
    destino_inicio = url_for('vista.vistaIndex') if con_sesion else url_for('seguridad.login')
    contexto = dict(
        codigo=codigo, titulo=titulo, mensaje=mensaje, icono=icono,
        con_sesion=con_sesion, url_inicio=destino_inicio,
        texto_inicio='Volver al inicio' if con_sesion else 'Ir a iniciar sesión',
        **extra,
    )
    if con_sesion:
        try:
            return render_template('errores/error.html', layout='base_tabler.html', **contexto), codigo
        except Exception:
            # Si el layout completo falla (p. ej. base de datos caída), no encadenar otro error.
            app.logger.exception('No se pudo renderizar la página de error con base_tabler.html')
    try:
        return render_template('errores/error.html', layout='errores/_standalone.html', **contexto), codigo
    except Exception:
        # Último recurso: HTML mínimo, para que un error nunca encadene otro error.
        app.logger.exception('No se pudo renderizar la página de error')
        html = ('<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>%s</title></head>'
                '<body style="font-family:sans-serif;text-align:center;margin-top:15%%">'
                '<h1>%s</h1><p>%s</p><p><a href="%s">%s</a></p></body></html>'
                % (codigo, codigo, mensaje, destino_inicio, contexto['texto_inicio']))
        return html, codigo


def registrar_manejadores_de_error(app):
    @app.errorhandler(403)
    def sin_permiso(e):
        return _responder(
            403, 'Sin permiso',
            'No tenés permiso para acceder a esta ventana. Si lo necesitás, pedíselo al administrador.',
            'fa-lock', ventana=None if _es_api() else _etiqueta_ventana(), mostrar_atras=True)

    @app.errorhandler(404)
    def no_encontrada(e):
        return _responder(
            404, 'Página no encontrada',
            'La página que buscás no existe.' if not _es_api() else 'El recurso solicitado no existe.',
            'fa-search', ventana=None, mostrar_atras=True)

    @app.errorhandler(500)
    def error_interno(e):
        return _responder(
            500, 'Error interno',
            'Ocurrió un error interno. Intentá de nuevo en unos minutos; si el problema continúa, avisale al administrador.',
            'fa-exclamation-triangle', ventana=None, mostrar_atras=False)
