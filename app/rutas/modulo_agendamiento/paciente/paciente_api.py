from flask import Blueprint, jsonify, request, current_app as app
from app.dao.referenciales_agendamiento.paciente.PacienteDao import PacienteDao

pacienteapi = Blueprint('pacienteapi', __name__)

# ==============================
#   Obtener todos los pacientes
# ==============================
@pacienteapi.route('/pacientes', methods=['GET'])
def getPacientes():
    pacientedao = PacienteDao()
    try:
        pacientes = pacientedao.getPacientes()
        return jsonify({'success': True, 'data': pacientes, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener pacientes: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno al consultar los pacientes.'
        }), 500


# ==============================
#   Obtener paciente por ID
# ==============================
@pacienteapi.route('/pacientes/<int:paciente_id>', methods=['GET'])
def getPacienteById(paciente_id):
    pacientedao = PacienteDao()
    try:
        paciente = pacientedao.getPacienteById(paciente_id)
        if paciente:
            return jsonify({'success': True, 'data': paciente, 'error': None}), 200
        return jsonify({
            'success': False,
            'error': f'No se encontró el paciente con ID {paciente_id}.'
        }), 404
    except Exception as e:
        app.logger.error(f"Error al obtener paciente con ID {paciente_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno al consultar el paciente.'
        }), 500


# ==============================
#   Agregar nuevo paciente
# ==============================
@pacienteapi.route('/pacientes', methods=['POST'])
def addPaciente():
    data = request.get_json()
    pacientedao = PacienteDao()

    campos_requeridos = ['nombre', 'apellido', 'cedula_entidad', 'fecha_nacimiento',
                         'telefono', 'direccion', 'correo', 'id_ciudad', 'fecha_registro']
    for campo in campos_requeridos:
        if not data.get(campo) or (isinstance(data[campo], str) and not data[campo].strip()):
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        # Verificar duplicado
        if pacientedao.existeDuplicado(data['cedula_entidad'], data['correo']):
            return jsonify({
                'success': False,
                'error': 'Ya existe un paciente con esa cédula o correo.'
            }), 409

        paciente_id = pacientedao.guardarPaciente(
            data['nombre'], data['apellido'], data['cedula_entidad'], data['fecha_nacimiento'],
            data['telefono'], data['direccion'], data['correo'], data['id_ciudad'], data['fecha_registro']
        )

        if paciente_id:
            app.logger.info(f"Paciente creado con ID {paciente_id}.")
            return jsonify({
                'success': True,
                'data': {**data, 'id_paciente': paciente_id},
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo guardar el paciente.'
            }), 500
    except Exception as e:
        app.logger.error(f"Error al agregar paciente: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno al guardar el paciente.'
        }), 500


# ==============================
#   Actualizar paciente
# ==============================
@pacienteapi.route('/pacientes/<int:paciente_id>', methods=['PUT'])
def updatePaciente(paciente_id):
    data = request.get_json()
    pacientedao = PacienteDao()

    campos_requeridos = ['nombre', 'apellido', 'cedula_entidad', 'fecha_nacimiento',
                         'telefono', 'direccion', 'correo', 'id_ciudad', 'fecha_registro']
    for campo in campos_requeridos:
        if not data.get(campo) or (isinstance(data[campo], str) and not data[campo].strip()):
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        actualizado = pacientedao.updatePaciente(
            paciente_id, data['nombre'], data['apellido'], data['cedula_entidad'], data['fecha_nacimiento'],
            data['telefono'], data['direccion'], data['correo'], data['id_ciudad'], data['fecha_registro']
        )

        if actualizado:
            app.logger.info(f"Paciente con ID {paciente_id} actualizado correctamente.")
            return jsonify({
                'success': True,
                'data': {**data, 'id_paciente': paciente_id},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'No se encontró el paciente con ID {paciente_id} o no se pudo actualizar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar paciente con ID {paciente_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno al actualizar el paciente.'
        }), 500


# ==============================
#   Eliminar paciente
# ==============================
@pacienteapi.route('/pacientes/<int:paciente_id>', methods=['DELETE'])
def deletePaciente(paciente_id):
    pacientedao = PacienteDao()
    try:
        if pacientedao.deletePaciente(paciente_id):
            app.logger.info(f"Paciente con ID {paciente_id} eliminado.")
            return jsonify({
                'success': True,
                'mensaje': f'Paciente con ID {paciente_id} eliminado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'No se encontró el paciente con ID {paciente_id} o no se pudo eliminar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar paciente con ID {paciente_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno al eliminar el paciente.'
        }), 500