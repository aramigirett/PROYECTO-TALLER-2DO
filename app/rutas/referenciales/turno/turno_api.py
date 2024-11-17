from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.turno.TurnoDao import TurnoDao

turnoapi = Blueprint('turnoapi', __name__)

# Lista de turnos validos
TURNOS_VALIDOS= ['MAÑANA', 'TARDE', 'NOCHE']


# Trae todos los turnos
@turnoapi.route('/turnos', methods=['GET'])
def getTurnos():
    turnodao = TurnoDao()

    try:
        turnos = turnodao.getTurnos()

        return jsonify({
            'success': True,
            'data': turnos,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener todos los turnos: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@turnoapi.route('/turnos/<int:turno_id>', methods=['GET'])
def getTurno(turno_id):
    turnodao = TurnoDao()

    try:
        turno = turnodao.getTurnoById(turno_id)

        if turno:
            return jsonify({
                'success': True,
                'data': turno,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el turno con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener turno: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Agrega un nuevo turno
@turnoapi.route('/turnos', methods=['POST'])
def addTurno():
    data = request.get_json()
    turnodao = TurnoDao()

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
 
        # Validar si el TURNO está en la lista de TURNOS válidos
        if descripcion not in TURNOS_VALIDOS:
            return jsonify({
                'success': False,
                'error': 'Turno inválido. Solo se permiten Turnos de Mañana, Tarde y Noche.'
            }), 400


        turno_id = turnodao.guardarTurno(descripcion)
        if turno_id is not None:
            return jsonify({
                'success': True,
                'data': {'id': turno_id, 'descripcion': descripcion},
                'error': None
            }), 201
        else:
            return jsonify({ 'success': False, 'error': 'No se pudo guardar el turno. Consulte con el administrador.' }), 500
    except Exception as e:
        app.logger.error(f"Error al agregar turno: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@turnoapi.route('/turnos/<int:turno_id>', methods=['PUT'])
def updateTurno(turno_id):
    data = request.get_json()
    turnodao = TurnoDao()

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

    # Validar si el TURNO está en la lista de TURNOS válidos
    if descripcion not in TURNOS_VALIDOS:
            return jsonify({
                'success': False,
                'error': 'Turno inválido. Solo se permiten Turnos de Mañana, Tarde y Noche.'
            }), 400

    try:
        if turnodao.updateTurno(turno_id, descripcion.upper()):
            return jsonify({
                'success': True,
                'data': {'id': turno_id, 'descripcion': descripcion},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el turno con el ID proporcionado o no se pudo actualizar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar turno: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@turnoapi.route('/turnos/<int:turno_id>', methods=['DELETE'])
def deleteTurno(turno_id):
    turnodao = TurnoDao()

    try:
        # Usar el retorno de eliminarTurno para determinar el éxito
        if turnodao.deleteTurno(turno_id):
            return jsonify({
                'success': True,
                'mensaje': f'Turno con ID {turno_id} eliminado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el turno con el ID proporcionado o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar turno: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500