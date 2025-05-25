from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.agenda_medica.Agenda_medicaDao import Agenda_medicaDao
from datetime import datetime, time

agenda_medica_api = Blueprint('agenda_medica_api', __name__)

# Función para convertir campos de tipo fecha y hora
def procesar_agenda(agenda):
    if 'fecha' in agenda and isinstance(agenda['fecha'], datetime):
        agenda['fecha'] = agenda['fecha'].strftime('%d/%m/%Y')
    if 'hora_inicio' in agenda and isinstance(agenda['hora_inicio'], time):
        agenda['hora_inicio'] = agenda['hora_inicio'].strftime('%H:%M:%S')
    if 'hora_final' in agenda and isinstance(agenda['hora_final'], time):
        agenda['hora_final'] = agenda['hora_final'].strftime('%H:%M:%S')
    return agenda

# Trae todas las agendas médicas
@agenda_medica_api.route('/agenda_medicas', methods=['GET'])
def getAgenda_medicas():
    agendamedicadao = Agenda_medicaDao()
    try:
        agenda_medicas = agendamedicadao.getAgenda_medicas()

        # Procesar cada registro para formatear fecha y hora
        agenda_medicas = [procesar_agenda(agenda) for agenda in agenda_medicas]

        return jsonify({'success': True, 'data': agenda_medicas, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener todas las agendas médicas: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500

# Trae una agenda médica por ID
@agenda_medica_api.route('/agenda_medicas/<int:agenda_medica_id>', methods=['GET'])
def getAgenda_medica(agenda_medica_id):
    agendamedicadao = Agenda_medicaDao()
    try:
        agenda_medica = agendamedicadao.getAgenda_medicaById(agenda_medica_id)

        # Procesar registro para formatear fecha y hora
        if agenda_medica:
            agenda_medica = procesar_agenda(agenda_medica)

            return jsonify({'success': True, 'data': agenda_medica, 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró la agenda médica con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener agenda médica: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500

# Agrega una nueva agenda médica
@agenda_medica_api.route('/agenda_medicas', methods=['POST'])
def addAgenda_medica():
    data = request.get_json()
    agendamedicadao = Agenda_medicaDao()

    campos_requeridos = ['id_medico', 'id_especialidad', 'id_dia', 'id_turno', 'fecha', 'hora_inicio', 'hora_final', 'estado']
    for campo in campos_requeridos:
        if campo not in data:
            return jsonify({'success': False, 'error': f'El campo {campo} es obligatorio.'}), 400
        if campo != 'estado' and (data[campo] is None or len(str(data[campo]).strip()) == 0):
            return jsonify({'success': False, 'error': f'El campo {campo} no puede estar vacío.'}), 400

    try:
        id_medico = data['id_medico']
        id_especialidad = data['id_especialidad']
        id_dia = data['id_dia']
        id_turno = data['id_turno']
        fecha = data['fecha']
        hora_inicio = data['hora_inicio']
        hora_final = data['hora_final']
        estado = data['estado']

        # Conversión y validación de estado
        if isinstance(estado, bool):
            estado = 'activo' if estado else 'inactivo'
        elif estado not in ['activo', 'inactivo']:
            return jsonify({'success': False, 'error': 'El campo estado debe ser "activo" o "inactivo".'}), 400

        agenda_medica_id = agendamedicadao.guardarAgenda_medica(
            id_medico, id_especialidad, fecha, id_dia, id_turno, hora_inicio, hora_final, estado
        )

        if agenda_medica_id is not None:
            return jsonify({
                'success': True,
                'data': {
                    'id_agenda_medica': agenda_medica_id,
                    'id_medico': id_medico,
                    'id_especialidad': id_especialidad,
                    'id_dia': id_dia,
                    'id_turno': id_turno,
                    'fecha': fecha,
                    'hora_inicio': hora_inicio,
                    'hora_final': hora_final,
                    'estado': estado
                },
                'error': None
            }), 201
        else:
            return jsonify({'success': False, 'error': 'No se pudo guardar la agenda médica. Consulte con el administrador.'}), 500
    except Exception as e:
        app.logger.error(f"Error al agregar agenda médica: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500

# Actualiza una agenda médica
@agenda_medica_api.route('/agenda_medicas/<int:agenda_medica_id>', methods=['PUT'])
def updateAgenda_medica(agenda_medica_id):
    data = request.get_json()
    agendamedicadao = Agenda_medicaDao()

    campos_requeridos = ['id_medico', 'id_especialidad', 'id_dia', 'id_turno', 'fecha', 'hora_inicio', 'hora_final', 'estado']
    for campo in campos_requeridos:
        if campo not in data:
            return jsonify({'success': False, 'error': f'El campo {campo} es obligatorio.'}), 400
        if campo != 'estado' and (data[campo] is None or len(str(data[campo]).strip()) == 0):
            return jsonify({'success': False, 'error': f'El campo {campo} no puede estar vacío.'}), 400

    try:
        id_medico = data['id_medico']
        id_especialidad = data['id_especialidad']
        id_dia = data['id_dia']
        id_turno = data['id_turno']
        fecha = data['fecha']
        hora_inicio = data['hora_inicio']
        hora_final = data['hora_final']
        estado = data['estado']

        # Conversión y validación de estado
        if isinstance(estado, bool):
            estado = 'activo' if estado else 'inactivo'
        elif estado not in ['activo', 'inactivo']:
            return jsonify({'success': False, 'error': 'El campo estado debe ser "activo" o "inactivo".'}), 400

        actualizado = agendamedicadao.updateAgenda_medica(
            agenda_medica_id, id_medico, id_especialidad, fecha, id_dia, id_turno, hora_inicio, hora_final, estado
        )

        if actualizado:
            return jsonify({
                'success': True,
                'data': {
                    'id_agenda_medica': agenda_medica_id,
                    'id_medico': id_medico,
                    'id_especialidad': id_especialidad,
                    'id_dia': id_dia,
                    'id_turno': id_turno,
                    'fecha': fecha,
                    'hora_inicio': hora_inicio,
                    'hora_final': hora_final,
                    'estado': estado
                },
                'error': None
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró la agenda médica con el ID proporcionado o no se pudo actualizar.'}), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar agenda médica: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500

# Elimina una agenda médica
@agenda_medica_api.route('/agenda_medicas/<int:agenda_medica_id>', methods=['DELETE'])
def deleteAgenda_medica(agenda_medica_id):
    agendamedicadao = Agenda_medicaDao()
    try:
        if agendamedicadao.deleteAgenda_medica(agenda_medica_id):
            return jsonify({
                'success': True,
                'mensaje': f'Agenda médica con ID {agenda_medica_id} eliminada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró la agenda médica con el ID proporcionado o no se pudo eliminar.'}), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar agenda médica: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
