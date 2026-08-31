from flask import Blueprint, request, jsonify, current_app as app

from app.dao.modulo_seguridad.AuditoriaDao import AuditoriaDao
from app.rutas.modulo_seguridad.decorators import require_admin

auditoriaapi = Blueprint('auditoriaapi', __name__)


@auditoriaapi.route('/auditoria/intentos', methods=['GET'])
@require_admin
def getUltimosIntentos():
    limite = request.args.get('limite', default=200, type=int)
    try:
        intentos = AuditoriaDao().get_ultimos_intentos(limite)
        return jsonify({'success': True, 'data': intentos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener intentos de acceso: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
