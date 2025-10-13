from flask import Blueprint, jsonify, request, current_app as app
from app.dao.referenciales_agendamiento.medico.MedicoDao import MedicoDao

medicoapi = Blueprint('medicoapi', __name__) 


# ==============================
#   Obtener todos los médicos
# ==============================
@medicoapi.route('/medico', methods=['GET'])
def getMedicos():
    medicodao = MedicoDao()
    try:
        medicos = medicodao.getMedicos()
        return jsonify({'success': True, 'data': medicos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener todos los médicos: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno al consultar los médicos. Consulte con el administrador.'
        }), 500


# ==============================
#   Obtener médico por ID
# ==============================
@medicoapi.route('/medico/<int:medico_id>', methods=['GET'])
def getMedico(medico_id):
    medicodao = MedicoDao()
    try:
        medico = medicodao.getMedicoById(medico_id)
        if medico:
            return jsonify({'success': True, 'data': medico, 'error': None}), 200
        return jsonify({
            'success': False,
            'error': f'No se encontró el médico con el ID {medico_id}.'
        }), 404
    except Exception as e:
        app.logger.error(f"Error al obtener médico con ID {medico_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno al consultar el médico. Consulte con el administrador.'
        }), 500


# ==============================
#   Agregar nuevo médico
# ==============================
@medicoapi.route('/medico', methods=['POST'])
def addMedico():
    data = request.get_json()
    medicodao = MedicoDao()

    # Validar campos requeridos
    campos_requeridos = ['nombre', 'apellido', 'id_especialidad', 'num_registro', 
                         'cedula', 'fecha_nacimiento', 'fecha_registro', 
                         'telefono', 'direccion', 'correo', 'id_ciudad']
    for campo in campos_requeridos:
        if not data.get(campo) or (isinstance(data[campo], str) and not data[campo].strip()):
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        # Validación de duplicados
        if medicodao.existeDuplicado(data['cedula'], data['num_registro']):
            return jsonify({
                'success': False,
                'error': 'El médico ya está registrado.'
            }), 409

        medico_id = medicodao.guardarMedico(
            data['nombre'], data['apellido'], data['id_especialidad'], data['num_registro'],
            data['cedula'], data['fecha_nacimiento'], data['fecha_registro'],
            data['telefono'], data['direccion'], data['correo'], data['id_ciudad']
        )

        if medico_id:
            app.logger.info(f"Médico creado con ID {medico_id}.")
            return jsonify({
                'success': True,
                'data': {**data, 'id_medico': medico_id},
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo guardar el médico. Consulte con el administrador.'
            }), 500

    except Exception as e:
        app.logger.error(f"Error al agregar médico: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno al guardar el médico. Consulte con el administrador.'
        }), 500


# ==============================
#   Actualizar médico existente
# ==============================
@medicoapi.route('/medico/<int:medico_id>', methods=['PUT'])
def updateMedico(medico_id):
    data = request.get_json()
    medicodao = MedicoDao()

    # Validar campos requeridos
    campos_requeridos = ['nombre', 'apellido', 'id_especialidad', 'num_registro', 
                         'cedula', 'fecha_nacimiento', 'fecha_registro', 
                         'telefono', 'direccion', 'correo', 'id_ciudad']
    for campo in campos_requeridos:
        if not data.get(campo) or (isinstance(data[campo], str) and not data[campo].strip()):
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        actualizado = medicodao.updateMedico(
            medico_id, data['nombre'], data['apellido'], data['id_especialidad'], data['num_registro'],
            data['cedula'], data['fecha_nacimiento'], data['fecha_registro'],
            data['telefono'], data['direccion'], data['correo'], data['id_ciudad']
        )

        if actualizado:
            app.logger.info(f"Médico con ID {medico_id} actualizado exitosamente.")
            return jsonify({
                'success': True,
                'data': {**data, 'id_medico': medico_id},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'No se encontró el médico con el ID {medico_id} o no se pudo actualizar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al actualizar médico con ID {medico_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno al actualizar el médico. Consulte con el administrador.'
        }), 500


# ==============================
#   Eliminar médico
# ==============================
@medicoapi.route('/medico/<int:medico_id>', methods=['DELETE'])
def deleteMedico(medico_id):
    medicodao = MedicoDao()
    try:
        if medicodao.deleteMedico(medico_id):
            app.logger.info(f"Médico con ID {medico_id} eliminado.")
            return jsonify({
                'success': True,
                'mensaje': f'Médico con ID {medico_id} eliminado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'No se encontró el médico con el ID {medico_id} o no se pudo eliminar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar médico con ID {medico_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno al eliminar el médico. Consulte con el administrador.'
        }), 500