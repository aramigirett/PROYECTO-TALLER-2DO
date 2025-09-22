from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.agenda_medica.Agenda_medicaDao import Agenda_medicaDao
from datetime import datetime, time

agenda_medica_api = Blueprint('agenda_medica_api', __name__)

# Función para normalizar los datos antes de enviarlos al frontend
def procesar_agenda(agenda):
    # Fecha: el DAO ya devuelve YYYY-MM-DD, aseguramos string
    if 'fecha' in agenda and agenda['fecha']:
        agenda['fecha'] = str(agenda['fecha'])

    # Hora inicio y final
    if 'hora_inicio' in agenda and isinstance(agenda['hora_inicio'], time):
        agenda['hora_inicio'] = agenda['hora_inicio'].strftime('%H:%M:%S')
    if 'hora_final' in agenda and isinstance(agenda['hora_final'], time):
        agenda['hora_final'] = agenda['hora_final'].strftime('%H:%M:%S')

    # Estado: string → boolean
    if 'estado' in agenda:
        agenda['estado'] = (str(agenda['estado']).lower() == 'activo')

    return agenda


# Trae todas las agendas médicas
@agenda_medica_api.route('/agenda_medicas', methods=['GET'])
def getAgenda_medicas():
    dao = Agenda_medicaDao()
    try:
        agenda_medicas = dao.getAgenda_medicas()
        agenda_medicas = [procesar_agenda(ag) for ag in agenda_medicas]
        return jsonify({'success': True, 'data': agenda_medicas, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener todas las agendas médicas: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# Trae una agenda médica por ID
@agenda_medica_api.route('/agenda_medicas/<int:agenda_medica_id>', methods=['GET'])
def getAgenda_medica(agenda_medica_id):
    dao = Agenda_medicaDao()
    try:
        agenda_medica = dao.getAgenda_medicaById(agenda_medica_id)
        if agenda_medica:
            agenda_medica = procesar_agenda(agenda_medica)
            return jsonify({'success': True, 'data': agenda_medica, 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró la agenda médica con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener agenda médica: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# Función para parsear hora
def parse_time_flexible(hora_str):
    formatos = ["%H:%M:%S", "%H:%M"]
    for fmt in formatos:
        try:
            return datetime.strptime(hora_str, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Formato de hora no válido: {hora_str}")


# Agregar agenda médica
@agenda_medica_api.route('/agenda_medicas', methods=['POST'])
def addAgenda_medica():
    data = request.get_json()
    dao = Agenda_medicaDao()

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

        # Validación de horas
        hora_inicio_obj = parse_time_flexible(hora_inicio)
        hora_final_obj = parse_time_flexible(hora_final)

        # Validación de solapamiento (mismo médico)
        agendas_existentes = dao.getAgendasByFechaAndMedico(fecha, id_medico)
        for ag in agendas_existentes:
            ini = parse_time_flexible(str(ag['hora_inicio']))
            fin = parse_time_flexible(str(ag['hora_final']))
            if hora_inicio_obj < fin and hora_final_obj > ini:
                return jsonify({'success': False, 'error': 'El horario ingresado se solapa con otro horario existente para el mismo médico.'}), 400

        # Validación de solapamiento (otros médicos)
        agendas_en_fecha = dao.getAgendasByFecha(fecha)
        for ag in agendas_en_fecha:
            if ag['id_medico'] != id_medico:
                ini = parse_time_flexible(str(ag['hora_inicio']))
                fin = parse_time_flexible(str(ag['hora_final']))
                if hora_inicio_obj < fin and hora_final_obj > ini:
                    return jsonify({'success': False, 'error': 'El horario ingresado ya está ocupado por otro médico.'}), 400

        # Conversión estado: boolean → string
        if isinstance(estado, bool):
            estado = 'activo' if estado else 'inactivo'
        elif estado not in ['activo', 'inactivo']:
            return jsonify({'success': False, 'error': 'El campo estado debe ser "activo" o "inactivo".'}), 400

        agenda_id = dao.guardarAgenda_medica(id_medico, id_especialidad, fecha, id_dia, id_turno, hora_inicio, hora_final, estado)

        if agenda_id:
            return jsonify({
                'success': True,
                'data': {
                    'id_agenda_medica': agenda_id,
                    'id_medico': id_medico,
                    'id_especialidad': id_especialidad,
                    'id_dia': id_dia,
                    'id_turno': id_turno,
                    'fecha': fecha,
                    'hora_inicio': hora_inicio,
                    'hora_final': hora_final,
                    'estado': True if estado == 'activo' else False
                },
                'error': None
            }), 201
        else:
            return jsonify({'success': False, 'error': 'No se pudo guardar la agenda médica. Consulte con el administrador.'}), 500
    except Exception as e:
        app.logger.error(f"Error al agregar agenda médica: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500  


# Actualizar agenda médica
@agenda_medica_api.route('/agenda_medicas/<int:agenda_medica_id>', methods=['PUT'])
def updateAgenda_medica(agenda_medica_id):
    data = request.get_json()
    dao = Agenda_medicaDao()

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

        # Conversión estado
        if isinstance(estado, bool):
            estado = 'activo' if estado else 'inactivo'
        elif estado not in ['activo', 'inactivo']:
            return jsonify({'success': False, 'error': 'El campo estado debe ser "activo" o "inactivo".'}), 400

        actualizado = dao.updateAgenda_medica(
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
                    'estado': True if estado == 'activo' else False
                },
                'error': None
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró la agenda médica con el ID proporcionado o no se pudo actualizar.'}), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar agenda médica: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# Eliminar agenda médica
@agenda_medica_api.route('/agenda_medicas/<int:agenda_medica_id>', methods=['DELETE'])
def deleteAgenda_medica(agenda_medica_id):
    dao = Agenda_medicaDao()
    try:
        if dao.deleteAgenda_medica(agenda_medica_id):
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