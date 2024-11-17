from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.instrumento.InstrumentoDao import InstrumentoDao

instapi = Blueprint('instapi', __name__)

# Trae todos los instrumentos
@instapi.route('/instrumentos', methods=['GET'])
def getInstrumentos():
    instrumento_dao = InstrumentoDao()

    try:
        instrumentos = instrumento_dao.getInstrumentos()

        return jsonify({
            'success': True,
            'data': instrumentos,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener todos los instrumentos: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@instapi.route('/instrumentos/<int:instrumento_id>', methods=['GET'])
def getInstrumento(instrumento_id):
    instrumento_dao = InstrumentoDao()

    try:
        instrumento = instrumento_dao.getInstrumentoById(instrumento_id)

        if instrumento:
            return jsonify({
                'success': True,
                'data': instrumento,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el instrumento con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener instrumento: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Agrega un nuevo instrumento
@instapi.route('/instrumentos', methods=['POST'])
def addInstrumento():
    data = request.get_json()
    instrumento_dao = InstrumentoDao()

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
        instrumento_id = instrumento_dao.guardarInstrumento(descripcion)
        if instrumento_id is not None:
            return jsonify({
                'success': True,
                'data': {'id': instrumento_id, 'descripcion': descripcion},
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo guardar el instrumento. Consulte con el administrador.'
            }), 500
    except Exception as e:
        app.logger.error(f"Error al agregar instrumento: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@instapi.route('/instrumentos/<int:instrumento_id>', methods=['PUT'])
def updateInstrumento(instrumento_id):
    data = request.get_json()
    instrumento_dao = InstrumentoDao()

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
        if instrumento_dao.updateInstrumento(instrumento_id, descripcion.upper()):
            return jsonify({
                'success': True,
                'data': {'id': instrumento_id, 'descripcion': descripcion},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el instrumento con el ID proporcionado o no se pudo actualizar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar instrumento: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@instapi.route('/instrumentos/<int:instrumento_id>', methods=['DELETE'])
def deleteInstrumento(instrumento_id):
    instrumento_dao = InstrumentoDao()

    try:
        # Usar el retorno de eliminarInstrumento para determinar el éxito
        if instrumento_dao.deleteInstrumento(instrumento_id):
            return jsonify({
                'success': True,
                'mensaje': f'Instrumento con ID {instrumento_id} eliminado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el instrumento con el ID proporcionado o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar instrumento: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500