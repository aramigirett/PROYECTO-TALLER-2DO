from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.ocupacion.OcupacionDao import OcupacionDao

ocupapi = Blueprint('ocupapi', __name__)

# Trae todas las ocupaciones
@ocupapi.route('/ocupaciones', methods=['GET'])
def getOcupaciones():
    ocupaciondao = OcupacionDao()

    try:
        ocupaciones = ocupaciondao.getOcupaciones()

        return jsonify({
            'success': True,
            'data': ocupaciones,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener todas las ocupaciones: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@ocupapi.route('/ocupaciones/<int:ocupacion_id>', methods=['GET'])
def getOcupacion(ocupacion_id):
    ocupaciondao = OcupacionDao()

    try:
        ocupacion = ocupaciondao.getOcupacionById(ocupacion_id)

        if ocupacion:
            return jsonify({
                'success': True,
                'data': ocupacion,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la ocupación con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener ocupación: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Agrega una nueva ocupación
@ocupapi.route('/ocupaciones', methods=['POST'])
def addOcupacion():
    data = request.get_json()
    ocupaciondao = OcupacionDao()

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
        ocupacion_id = ocupaciondao.guardarOcupacion(descripcion)
        if ocupacion_id is not None:
            return jsonify({
                'success': True,
                'data': {'id': ocupacion_id, 'descripcion': descripcion},
                'error': None
            }), 201
        else:
            return jsonify({ 'success': False, 'error': 'No se pudo guardar la ocupacion. Consulte con el administrador.' }), 500
    except Exception as e:
        app.logger.error(f"Error al agregar ocupacion: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@ocupapi.route('/ocupaciones/<int:ocupacion_id>', methods=['PUT'])
def updateOcupacion(ocupacion_id):
    data = request.get_json()
    ocupaciondao = OcupacionDao()

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
        if ocupaciondao.updateOcupacion(ocupacion_id, descripcion.upper()):
            return jsonify({
                'success': True,
                'data': {'id': ocupacion_id, 'descripcion': descripcion},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la ocupación con el ID proporcionado o no se pudo actualizar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar ocupación: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@ocupapi.route('/ocupaciones/<int:ocupacion_id>', methods=['DELETE'])
def deleteOcupacion(ocupacion_id):
    ocupaciondao = OcupacionDao()

    try:
        # Usar el retorno de eliminarOcupación para determinar el éxito
        if ocupaciondao.deleteOcupacion(ocupacion_id):
            return jsonify({
                'success': True,
                'mensaje': f'Ocupacion con ID {ocupacion_id} eliminada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la ocupación con el ID proporcionado o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar ocupación: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500