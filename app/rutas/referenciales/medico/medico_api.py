from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.medico.MedicoDao import MedicoDao

medicoapi = Blueprint('medicoapi', __name__)

@medicoapi.route('/medicos', methods=['GET'])
def getMedicos():
    medicodao = MedicoDao()
    try:
        medicos = medicodao.getMedicos()
        return jsonify({
            'success': True,
            'data': medicos,
            'error': None
        }), 200
    except Exception as e:
        app.logger.error(f"Error al obtener todos los médicos: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@medicoapi.route('/medicos/<int:medico_id>', methods=['GET'])
def getMedico(medico_id):
    medicodao = MedicoDao()
    try:
        medico = medicodao.getMedicoById(medico_id)
        if medico:
            return jsonify({
                'success': True,
                'data': medico,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el médico con el ID proporcionado.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al obtener médico: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@medicoapi.route('/medicos', methods=['POST'])
def addMedico():
    data = request.get_json()
    medicodao = MedicoDao()

    campos_requeridos = ['nombre', 'apellido', 'telefono', 'correo', 'especialidad', 'genero']
    
    for campo in campos_requeridos:
        if campo not in data or not data[campo]:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacio.'
            }), 400

    try:
        nombre = data['nombre'].strip().upper()
        apellido = data['apellido'].strip().upper()
        telefono = data['telefono'].strip()
        correo = data['correo']
        especialidad = data['especialidad'].strip().upper()
        genero = data['genero']

        medico_id = medicodao.guardarMedico(nombre, apellido, telefono, correo, especialidad, genero)
        if medico_id is not None:
            return jsonify({
                'success': True,
                'data': {
                    'id': medico_id,
                    'nombre': nombre,
                    'apellido': apellido,
                    'telefono': telefono,
                    'correo': correo,
                    'especialidad': especialidad,
                    'genero' : genero
                },
                'error': None
            }), 201
        else:
            return jsonify({'success': False, 'error': 'No se pudo guardar el medico.'}), 500

    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Verifique que los campos numéricos sean válidos.'
        }), 400
    except Exception as e:
        app.logger.error(f"Error al agregar paciente: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@medicoapi.route('/medicos/<int:medico_id>', methods=['PUT'])
def updateMedico(medico_id):
    data = request.get_json()
    medicodao = MedicoDao()

    campos_requeridos = ['nombre', 'apellido', 'telefono', 'correo', 'especialidad', 'genero']

    for campo in campos_requeridos:
        if campo not in data or not data[campo]:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        nombre = data['nombre'].strip().upper()
        apellido = data['apellido'].strip().upper()
        telefono = data['telefono'].strip()
        correo = data['correo']
        especialidad = data['especialidad'].strip().upper()
        genero = data['genero']

        if medicodao.updateMedico(medico_id, nombre, apellido, telefono, correo, especialidad, genero):
            return jsonify({
                'success': True,
                'data': {
                    'id': medico_id,
                    'nombre': nombre,
                    'apellido': apellido,
                    'telefono': telefono,
                    'correo': correo,
                    'especialidad': especialidad,
                    'genero': genero,
                },
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el médico con el ID proporcionado o no se pudo actualizar.'
            }), 404
    
    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Verifique que los campos numéricos sean válidos.'
        }), 400

    except Exception as e:
        app.logger.error(f"Error al actualizar paciente: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@medicoapi.route('/medicos/<int:medico_id>', methods=['DELETE'])
def deleteMedico(medico_id):
    medicodao = MedicoDao()

    try:
        if medicodao.deleteMedico(medico_id):
            return jsonify({
                'success': True,
                'mensaje': f'Médico con ID {medico_id} eliminado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el médico con el ID proporcionado o no se pudo eliminar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar médico: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500