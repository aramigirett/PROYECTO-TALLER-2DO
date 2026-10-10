import unicodedata

from flask import Blueprint, request, jsonify, url_for, current_app as app

from app.rutas.modulo_seguridad.decorators import require_login
from app.rutas.modulo_seguridad.menu_catalog import CATALOGO_MENU
from app.rutas.modulo_seguridad.permisos_contexto import puede

menuapi = Blueprint('menuapi', __name__)


def _normalizar(texto):
    """Minúsculas y sin acentos, para comparar sin distinguir tildes."""
    texto = texto.strip().lower()
    texto = unicodedata.normalize('NFKD', texto)
    return ''.join(c for c in texto if not unicodedata.combining(c))


@menuapi.route('/menu/buscar', methods=['GET'])
@require_login
def buscarMenu():
    q = _normalizar(request.args.get('q', ''))
    if not q:
        return jsonify({'success': True, 'data': [], 'error': None}), 200

    try:
        resultados = []
        for item in CATALOGO_MENU:
            if q not in _normalizar(item['etiqueta']):
                continue

            if not puede(item['ventana'], 'ver'):
                continue

            resultados.append({
                'etiqueta': item['etiqueta'],
                'modulo': item['modulo'],
                'icono': item['icono'],
                'url': url_for(item['endpoint']),
            })

        return jsonify({'success': True, 'data': resultados, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al buscar en el menú: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
