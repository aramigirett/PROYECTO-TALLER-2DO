from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.paciente.PacienteDao import PacienteDao

pacienteapi = Blueprint('pacienteapi', __name__)

# Trae todos los pacientes
@pacienteapi.route('/pacientes', methods=['GET'])
def getPacientes():
    pacientedao = PacienteDao()

    try:
        pacientes = pacientedao.getPacientes()

        return jsonify({
            'success': True,
            'data': pacientes,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener todos los pacientes: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Trae un paciente por ID
@pacienteapi.route('/pacientes/<int:paciente_id>', methods=['GET'])
def getPaciente(paciente_id):
    pacientedao = PacienteDao()

    try:
        paciente = pacientedao.getPacienteById(paciente_id)

        if paciente:
            return jsonify({
                'success': True,
                'data': paciente,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el paciente con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener paciente: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Agrega un nuevo paciente
@pacienteapi.route('/pacientes', methods=['POST'])
def addPaciente():
    data = request.get_json()
    pacientedao = PacienteDao()

    campos_requeridos = ['nombre', 'apellido', 'fechanacimiento', 'cedula', 'sexo', 'telefono', 'direccion', 'correo']

    for campo in campos_requeridos:
        if campo not in data or not data[campo]:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        nombre = data['nombre'].upper()
        apellido = data['apellido'].upper()
        fechanacimiento = data['fechanacimiento']
        cedula = data['cedula'].strip()
        sexo = data['sexo'].upper()
        telefono = data['telefono'].strip()
        direccion = data['direccion']
        correo = data['correo']

        paciente_id = pacientedao.guardarPaciente(nombre, apellido, fechanacimiento, cedula, sexo, telefono, direccion, correo)
        if paciente_id is not None:
            return jsonify({
                'success': True,
                'data': {
                    'id': paciente_id,
                    'nombre': nombre,
                    'apellido': apellido,
                    'fechanacimiento': fechanacimiento,
                    'cedula': cedula,
                    'sexo': sexo,
                    'telefono': telefono,
                    'direccion': direccion,
                    'correo': correo
                },
                'error': None
            }), 201
        else:
            return jsonify({'success': False, 'error': 'No se pudo guardar el paciente.'}), 500

    except Exception as e:
        app.logger.error(f"Error al agregar paciente: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Actualiza un paciente existente
@pacienteapi.route('/pacientes/<int:paciente_id>', methods=['PUT'])
def updatePaciente(paciente_id):
    data = request.get_json()
    pacientedao = PacienteDao()

    campos_requeridos = ['nombre', 'apellido', 'fechanacimiento', 'cedula', 'sexo', 'telefono', 'direccion', 'correo']

    for campo in campos_requeridos:
        if campo not in data or not data[campo]:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        nombre = data['nombre'].upper()
        apellido = data['apellido'].upper()
        fechanacimiento = data['fechanacimiento']
        cedula = data['cedula'].strip()
        sexo = data['sexo'].upper()
        telefono = data['telefono'].strip()
        direccion = data['direccion']
        correo = data['correo']

        if pacientedao.updatePaciente(paciente_id, nombre, apellido, fechanacimiento, cedula, sexo, telefono, direccion, correo):
            return jsonify({
                'success': True,
                'data': {
                    'id': paciente_id,
                    'nombre': nombre,
                    'apellido': apellido,
                    'fechanacimiento': fechanacimiento,
                    'cedula': cedula,
                    'sexo': sexo,
                    'telefono': telefono,
                    'direccion': direccion,
                    'correo': correo
                },
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el paciente con el ID proporcionado o no se pudo actualizar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al actualizar paciente: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Elimina un paciente
@pacienteapi.route('/pacientes/<int:paciente_id>', methods=['DELETE'])
def deletePaciente(paciente_id):
    pacientedao = PacienteDao()

    try:
        if pacientedao.deletePaciente(paciente_id):
            return jsonify({
                'success': True,
                'mensaje': f'Paciente con ID {paciente_id} eliminado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el paciente con el ID proporcionado o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar paciente: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500
