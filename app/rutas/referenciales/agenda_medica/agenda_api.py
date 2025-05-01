from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.agenda.AgendaDao import AgendaDao

agendaapi = Blueprint('agendaapi', __name__)

# Obtener todas las agendas médicas
@agendaapi.route('/agendas', methods=['GET'])
def getAgendas():
    agendadao = AgendaDao()

    try:
        agendas = agendadao.getAgendas()
        return jsonify({
            'success': True, 
            'data': agendas,
            'error': None
        }), 200
    except Exception as e:
        app.logger.error(f"Error al obtener todas las agendas: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Obtener una agenda médica por ID
@agendaapi.route('/agendas/<int:agenda_id>', methods=['GET'])
def getAgenda(agenda_id):
    agendadao = AgendaDao()

    try:
        agenda = agendadao.getAgendaById(agenda_id)
        if agenda:
            return jsonify({
                'success': True, 
                'data': agenda,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la agenda con el ID proporcionado.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al obtener la agenda: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Agregar una nueva agenda médica
@agendaapi.route('/agendas', methods=['POST'])
def addAgenda():
    data = request.get_json()
    agendadao = AgendaDao()

    campos_requeridos = ['id_medico', 'fecha_agenda', 'hora_inicio', 'hora_final', 'duracion']
    
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        id_medico = data['id_medico']
        fecha_agenda = data['fecha_agenda']
        hora_inicio = data['hora_inicio']
        hora_final = data['hora_final']
        duracion = data['duracion']

        agenda_id = agendadao.guardarAgenda(id_medico, fecha_agenda, hora_inicio, hora_final, duracion)
        if agenda_id is not None:
           return jsonify({
               'success': True,
               'data': { 'id_agenda_medica': agenda_id, 'id_medico': id_medico, 'fecha_agenda': fecha_agenda, 'hora_inicio': hora_inicio, 'hora_final': hora_final},
               'error': None
           }),201
        else:
            return jsonify({'success': False, 'error': 'No se pudo guardar la agenda. Consulte con el administradod.'}),500
    
    except Exception as e:
        app.logger.error(f"Error al agregar agenda: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrio un error interno, Consulte con el administrador.'
        }),500

# Actualizar una agenda médica
@agendaapi.route('/agendas/<int:agenda_id>', methods=['PUT'])
def updateAgenda(agenda_id):
    data = request.get_json()
    agendadao = AgendaDao()

    campos_requeridos = ['id_medico', 'fecha_agenda', 'hora_inicio', 'hora_final', 'duracion']
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        id_medico = data['id_medico']
        fecha_agenda = data['fecha_agenda']
        hora_inicio = data['hora_inicio']
        hora_final = data['hora_final']
        duracion = data['duracion']

        if agendadao.updateAgenda(agenda_id, id_medico, fecha_agenda, hora_inicio, hora_final, duracion):
            return jsonify({
                'success': True,
                'data': { 
                    'id_medico': id_medico, 
                    'fecha_agenda': fecha_agenda, 
                    'hora_inicio': hora_inicio, 
                    'hora_final': hora_final, 
                    'duracion': duracion
                },
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la agenda con el ID proporcionado o no se pudo actualizar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar agenda: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Eliminar una agenda médica
@agendaapi.route('/agendas/<int:agenda_id>', methods=['DELETE'])
def deleteAgenda(agenda_id):
    agendadao = AgendaDao()

    try:
        if agendadao.deleteAgenda(agenda_id):
            return jsonify({
                'success': True,
                'mensaje': f'Agenda con ID {agenda_id} eliminada correctamente',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la agenda con el ID proporcionado o no se pudo eliminar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar agenda: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500