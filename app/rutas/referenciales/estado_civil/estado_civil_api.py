from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.estado_civil.EstadoCivilDao import EstadoCivilDao

estacivapi = Blueprint('estacivapi', __name__)

# Trae todos los Estados Civiles
@estacivapi.route('/estadocivil', methods=['GET'])
def getEstadosCiviles():
    estacivdao = EstadoCivilDao()

    try:
        estadosciviles = estacivdao.getEstadosCiviles()

        return jsonify({
            'success': True,
            'data': estadosciviles,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener todos los Estados Civiles: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@estacivapi.route('/estadosciviles/<int:estadocivil_id>', methods=['GET'])
def getEstadoCivil(estadocivil_id):
    estacivdao = EstadoCivilDao()

    try:
        estadocivil = estacivdao.getEstadoCivilById(estadocivil_id)

        if estadocivil:
            return jsonify({
                'success': True,
                'data': estadocivil,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el estado civil con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener estado civil: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Agrega una nuevo Estado Civil
@estacivapi.route('/estadosciviles', methods=['POST'])
def addEstadoCivil():
    data = request.get_json()
    estacivdao = EstadoCivilDao()

    # Validar que el JSON no esté vacío y tenga las propiedades necesarias
    campos_requeridos = ['descripcion']

    # Verificar si faltan campos o son vacíos
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None or len(data[campo].strip()) == 0:
            return jsonify({
                            'success': False,
                            'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
                            }), 400

    try:
        descripcion = data['descripcion'].upper()
        estadocivil_id = estacivdao.guardarEstadoCivil(descripcion)
        if estadocivil_id is not None:
            return jsonify({
                'success': True,
                'data': {'id': estadocivil_id, 'descripcion': descripcion},
                'error': None
            }), 201
        else:
            return jsonify({ 'success': False, 'error': 'No se pudo guardar el Estado Civil. Consulte con el administrador.' }), 500
    except Exception as e:
        app.logger.error(f"Error al agregar Estado Civil: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@estacivapi.route('/estadosciviles/<int:estadocivil_id>', methods=['PUT'])
def updateEstadoCivil(estadocivil_id):
    data = request.get_json()
    estacivdao = EstadoCivilDao()

    # Validar que el JSON no esté vacío y tenga las propiedades necesarias
    campos_requeridos = ['descripcion']

    # Verificar si faltan campos o son vacíos
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None or len(data[campo].strip()) == 0:
            return jsonify({
                            'success': False,
                            'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
                            }), 400
    descripcion = data['descripcion']
    try:
        if estacivdao.updateEstadoCivil(estadocivil_id, descripcion.upper()):
            return jsonify({
                'success': True,
                'data': {'id': estadocivil_id, 'descripcion': descripcion},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el estado civil con el ID proporcionado o no se pudo actualizar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar Estado Civil: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@estacivapi.route('/estadosciviles/<int:estadocivil_id>', methods=['DELETE'])
def deleteEstadoCivil(estadocivil_id):
    estacivdao = EstadoCivilDao()

    try:
        # Usar el retorno de eliminarEstadoCivil para determinar el éxito
        if estacivdao.deleteEstadoCivil(estadocivil_id):
            return jsonify({
                'success': True,
                'mensaje': f'EstadoCivil con ID {estadocivil_id} eliminada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el estado civil con el ID proporcionado o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar Estado Civil: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500