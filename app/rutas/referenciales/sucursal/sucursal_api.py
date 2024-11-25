from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.sucursal.sucursal_dao import SucursalDao

sucapi = Blueprint('sucapi', __name__)

@sucapi.route('/sucursal-depositos/<int:id_sucursal>', methods=['GET'])
def get_sucursal_depositos(id_sucursal):
    dao = SucursalDao()

    try:
        pedidos = dao.get_sucursal_depositos(id_sucursal)
        return jsonify({
            'success': True,
            'data': pedidos,
            'error': False
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener los pedidos: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador'
        }), 500