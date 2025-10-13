from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_agendamiento.disponibilidad_horaria.DisponibilidadHorariaDao import DisponibilidadDao
from datetime import datetime

disponibilidadapi = Blueprint('disponibilidadapi', __name__)

# 🔹 Obtener todas las disponibilidades
@disponibilidadapi.route('/disponibilidades', methods=['GET'])
def getDisponibilidades():
    dao = DisponibilidadDao()
    try:
        disponibilidades = dao.getDisponibilidades()
        return jsonify({'success': True, 'data': disponibilidades, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener disponibilidades: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500

# disponibilidad_horaria_api.py

# 🔹 Obtener disponibilidades por médico y fecha (para agenda)
@disponibilidadapi.route('/disponibilidades/medico-fecha', methods=['GET'])
def getDisponibilidadesPorMedicoFecha():
    id_medico = request.args.get('id_medico')
    fecha = request.args.get('fecha')  # formato YYYY-MM-DD
    
    if not id_medico or not fecha:
        return jsonify({'success': False, 'error': 'Faltan parámetros id_medico o fecha'}), 400
    
    dao = DisponibilidadDao()
    try:
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
        disponibilidades = dao.getDisponibilidadesPorMedicoFecha(int(id_medico), fecha_obj)
        return jsonify({'success': True, 'data': disponibilidades, 'error': None}), 200
    except ValueError:
        return jsonify({'success': False, 'error': 'Formato de fecha inválido. Use YYYY-MM-DD'}), 400
    except Exception as e:
        app.logger.error(f"Error al obtener disponibilidades: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# 🔹 Obtener disponibilidad por ID
@disponibilidadapi.route('/disponibilidades/<int:id_disponibilidad>', methods=['GET'])
def getDisponibilidadById(id_disponibilidad):
    dao = DisponibilidadDao()
    try:
        d = dao.getDisponibilidadById(id_disponibilidad)
        if d:
            return jsonify({'success': True, 'data': d, 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se encontró la disponibilidad'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener disponibilidad: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# 🔹 Agregar nueva disponibilidad
@disponibilidadapi.route('/disponibilidades', methods=['POST'])
def addDisponibilidad():
    data = request.get_json()
    dao = DisponibilidadDao()

    campos_requeridos = [
        'id_medico', 'id_dia', 'id_turno',
        'dispo_fecha', 'dispo_hora_inicio', 'dispo_hora_fin', 'dispo_cupos'
    ]
    for campo in campos_requeridos:
        if campo not in data or not data[campo]:
            return jsonify({'success': False, 'error': f'El campo {campo} es obligatorio'}), 400

    try:
        # Normalizar formatos
        dispo_fecha = datetime.strptime(data['dispo_fecha'], "%Y-%m-%d").date()
        
        # 🔹 CORRECCIÓN: Agregar :00 si solo viene HH:MM
        hora_inicio_str = data['dispo_hora_inicio']
        hora_fin_str = data['dispo_hora_fin']
        
        # Si viene en formato HH:MM, agregar :00 para los segundos
        if len(hora_inicio_str) == 5:  # formato HH:MM
            hora_inicio_str += ':00'
        if len(hora_fin_str) == 5:  # formato HH:MM
            hora_fin_str += ':00'
        
        dispo_hora_inicio = datetime.strptime(hora_inicio_str, "%H:%M:%S").time()
        dispo_hora_fin = datetime.strptime(hora_fin_str, "%H:%M:%S").time()

        new_id = dao.guardarDisponibilidad(
            data['id_medico'],
            data['id_dia'],
            data['id_turno'],
            dispo_hora_inicio,
            dispo_hora_fin,
            dispo_fecha,
            data['dispo_cupos']
        )
        if new_id:
            return jsonify({'success': True, 'data': {'id_disponibilidad': new_id}, 'error': None}), 201
        return jsonify({'success': False, 'error': 'Ya existe una disponibilidad igual'}), 409
    except ValueError as ve:
        app.logger.error(f"Error de formato en agregar: {str(ve)}")
        return jsonify({'success': False, 'error': f'Error en formato de datos: {str(ve)}'}), 400
    except Exception as e:
        app.logger.error(f"Error al agregar disponibilidad: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# 🔹 Actualizar disponibilidad
@disponibilidadapi.route('/disponibilidades/<int:id_disponibilidad>', methods=['PUT'])
def updateDisponibilidad(id_disponibilidad):
    data = request.get_json()
    dao = DisponibilidadDao()

    campos_requeridos = [
        'id_medico', 'id_dia', 'id_turno',
        'dispo_fecha', 'dispo_hora_inicio', 'dispo_hora_fin', 'dispo_cupos'
    ]
    for campo in campos_requeridos:
        if campo not in data or not data[campo]:
            return jsonify({'success': False, 'error': f'El campo {campo} es obligatorio'}), 400

    try:
        dispo_fecha = datetime.strptime(data['dispo_fecha'], "%Y-%m-%d").date()
        
        # 🔹 CORRECCIÓN: Agregar :00 si solo viene HH:MM
        hora_inicio_str = data['dispo_hora_inicio']
        hora_fin_str = data['dispo_hora_fin']
        
        # Si viene en formato HH:MM, agregar :00 para los segundos
        if len(hora_inicio_str) == 5:  # formato HH:MM
            hora_inicio_str += ':00'
        if len(hora_fin_str) == 5:  # formato HH:MM
            hora_fin_str += ':00'
        
        dispo_hora_inicio = datetime.strptime(hora_inicio_str, "%H:%M:%S").time()
        dispo_hora_fin = datetime.strptime(hora_fin_str, "%H:%M:%S").time()

        exito = dao.updateDisponibilidad(
            id_disponibilidad,
            data['id_medico'],
            data['id_dia'],
            data['id_turno'],
            dispo_hora_inicio,
            dispo_hora_fin,
            dispo_fecha,
            data['dispo_cupos']
        )
        if exito:
            return jsonify({'success': True, 'data': {'id_disponibilidad': id_disponibilidad}, 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se pudo actualizar la disponibilidad'}), 404
    except ValueError as ve:
        app.logger.error(f"Error de formato en actualizar: {str(ve)}")
        return jsonify({'success': False, 'error': f'Error en formato de datos: {str(ve)}'}), 400
    except Exception as e:
        app.logger.error(f"Error al actualizar disponibilidad: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# 🔹 Eliminar disponibilidad
@disponibilidadapi.route('/disponibilidades/<int:id_disponibilidad>', methods=['DELETE'])
def deleteDisponibilidad(id_disponibilidad):
    dao = DisponibilidadDao()
    try:
        exito = dao.deleteDisponibilidad(id_disponibilidad)
        if exito:
            return jsonify({'success': True, 'mensaje': f'Disponibilidad {id_disponibilidad} eliminada', 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se encontró la disponibilidad o no se pudo eliminar'}), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar disponibilidad: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500