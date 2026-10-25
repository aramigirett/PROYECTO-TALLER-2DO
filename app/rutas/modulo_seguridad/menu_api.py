from flask import Blueprint, request, jsonify, url_for, current_app as app

from app.rutas.modulo_seguridad.decorators import require_login
from app.rutas.modulo_seguridad import menu_servicio

menuapi = Blueprint('menuapi', __name__)


@menuapi.route('/menu/buscar', methods=['GET'])
@require_login
def buscarMenu():
    """Buscador general: las entradas ACTIVAS de la tabla menu sobre las que el rol tiene permiso "ver"."""
    try:
        resultados = [{'etiqueta': e['etiqueta'], 'modulo': e['modulo'], 'icono': e['icono'], 'url': url_for(e['endpoint'])}
                      for e in menu_servicio.buscar(request.args.get('q', ''))]
        return jsonify({'success': True, 'data': resultados, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al buscar en el menú: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
