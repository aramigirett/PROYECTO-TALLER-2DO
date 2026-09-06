import unicodedata

from flask import Blueprint, request, jsonify, session, url_for, current_app as app

from app.dao.modulo_seguridad.PermisoDao import PermisoDao
from app.rutas.modulo_seguridad.decorators import require_login
from app.rutas.modulo_seguridad.menu_catalog import CATALOGO_MENU

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
        nombre_rol = session.get('nombre_rol')
        es_admin = nombre_rol == 'Administrador'
        permisos_rol = set() if es_admin else PermisoDao().getNombresPermisosPorRol(session.get('id_rol'))

        resultados = []
        for item in CATALOGO_MENU:
            if q not in _normalizar(item['etiqueta']):
                continue

            permiso_requerido = item['permiso_requerido']
            puede_ver = es_admin or permiso_requerido is None or permiso_requerido in permisos_rol
            if not puede_ver:
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
