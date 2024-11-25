from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.tratamiento.TratamientoDao import TratamientoDao

tratapi = Blueprint('tratapi', __name__)

# Trae todos los tratamientos
@tratapi.route('/tratamientos', methods=['GET'])
def getTratamientos():
    tradao = TratamientoDao()

    try:
        tratamientos = tradao.getTratamientos()

        return jsonify({
            'success': True,
            'data': tratamientos,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener todos los tratamientos: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@tratapi.route('/tratamientos/<int:tratamiento_id>', methods=['GET'])
def getTratamiento(tratamiento_id):
    tradao = TratamientoDao()

    try:
        tratamiento = tradao.getTratamientoById(tratamiento_id)

        if tratamiento:
            return jsonify({
                'success': True,
                'data': tratamiento,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el tratamiento con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener tratamiento: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Agrega un nuevo tratamiento
@tratapi.route('/tratamientos', methods=['POST'])
def addTratamiento():
    data = request.get_json()
    tradao = TratamientoDao()

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
        tratamiento_id = tradao.guardarTratamiento(descripcion)
        if tratamiento_id is not None:
            return jsonify({
                'success': True,
                'data': {'id': tratamiento_id, 'descripcion': descripcion},
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo guardar el tratamiento. Consulte con el administrador.'
            }), 500
    except Exception as e:
        app.logger.error(f"Error al agregar tratamiento: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@tratapi.route('/tratamientos/<int:tratamiento_id>', methods=['PUT'])
def updateTratamiento(tratamiento_id):
    data = request.get_json()
    tradao = TratamientoDao()

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
        if tradao.updateTratamiento(tratamiento_id, descripcion.upper()):
            return jsonify({
                'success': True,
                'data': {'id': tratamiento_id, 'descripcion': descripcion},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el tratamiento con el ID proporcionado o no se pudo actualizar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar tratamiento: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@tratapi.route('/tratamientos/<int:tratamiento_id>', methods=['DELETE'])
def deleteTratamiento(tratamiento_id):
    tradao = TratamientoDao()

    try:
        # Usar el retorno de deleteTratamiento para determinar el éxito
        if tradao.deleteTratamiento(tratamiento_id):
            return jsonify({
                'success': True,
                'mensaje': f'Tratamiento con ID {tratamiento_id} eliminado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el tratamiento con el ID proporcionado o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar tratamiento: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500
