from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.estado_cita.EstadoCitaDao import EstadoCitaDao

estacitapi = Blueprint('estacitapi', __name__)

# Lista de estados de la cita validos
ESTADOCITA_VALIDOS= ['RESERVADO', 'CONFIRMADO', 'REALIZADO', 'CANCELADO']


# Trae todos los Estados de la Cita
@estacitapi.route('/estadocita', methods=['GET'])
def getEstadosCita():
    estacitdao = EstadoCitaDao()

    try:
        estadoscitas = estacitdao.getEstadosCitas()

        return jsonify({
            'success': True,
            'data': estadoscitas,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener todos los Estados de la Cita: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@estacitapi.route('/estadoscitas/<int:estado_id>', methods=['GET'])
def getEstadoCita(estado_id):
    estacitdao = EstadoCitaDao()

    try:
        estadocita = estacitdao.getEstadoCitaById(estado_id)

        if estadocita:
            return jsonify({
                'success': True,
                'data': estadocita,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el estado de la cita con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener estado de la cita: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Agrega uno nuevo Estado de la cita 
@estacitapi.route('/estadoscitas', methods=['POST'])
def addEstadoCita():
    data = request.get_json()
    estacitdao = EstadoCitaDao()

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
        
        # Validar si el ESTADO está en la lista de TURNOS válidos
        if descripcion not in ESTADOCITA_VALIDOS:
            return jsonify({
                'success': False,
                'error': 'Estado de la cita inválido. Solo se permiten Estado de "Confirmado", "Reservado", "Cancelado", "Realizado".'
            }), 400
        
        estado_id = estacitdao.guardarEstadoCita(descripcion)
        if estado_id is not None:
            return jsonify({
                'success': True,
                'data': {'estado_id':estado_id, 'descripcion': descripcion},
                'error': None
            }), 201
        else:
            return jsonify({ 'success': False, 'error': 'No se pudo guardar el Estado de la Cita. Consulte con el administrador.' }), 500
    except Exception as e:
        app.logger.error(f"Error al agregar Estado de Cita: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@estacitapi.route('/estadoscitas/<int:estado_id>', methods=['PUT'])
def updateEstadoCita(estado_id):
    data = request.get_json()
    estacitdao = EstadoCitaDao()

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
    
    # Validar si el ESTADO está en la lista de TURNOS válidos
    if descripcion not in ESTADOCITA_VALIDOS:
            return jsonify({
                'success': False,
                'error': 'Estado de la cita inválido. Solo se permiten Estado de "Confirmado", "Reservado", "Cancelado", "Realizado".'
            }), 400
    try:
        if estacitdao.updateEstadoCita(estado_id, descripcion.upper()):
            return jsonify({
                'success': True,
                'data': {'estado_id': estado_id, 'descripcion': descripcion},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el estado de la cita con el ID proporcionado o no se pudo actualizar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar Estado de Cita: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@estacitapi.route('/estadoscitas/<int:estado_id>', methods=['DELETE'])
def deleteEstadoCita(estado_id):
    estacitdao = EstadoCitaDao()

    try:
        # Usar el retorno de eliminarEstadoCita para determinar el éxito
        if estacitdao.deleteEstadoCita(estado_id):
            return jsonify({
                'success': True,
                'mensaje': f'EstadoCita con ID {estado_id} eliminada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el estado de la cita con el ID proporcionado o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar Estado de la Cita: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500