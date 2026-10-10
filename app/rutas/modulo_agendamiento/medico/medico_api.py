from flask import Blueprint, jsonify, request, session, current_app as app
from app.dao.referenciales_agendamiento.medico.MedicoDao import MedicoDao
from app.dao.modulo_seguridad.AuditoriaDao import AuditoriaDao
from app.rutas.modulo_seguridad.decorators import require_permiso, require_login

medicoapi = Blueprint('medicoapi', __name__)


def _error_cedula_repetida(donde):
    quien = 'funcionario' if donde == 'funcionario' else 'médico'
    return jsonify({
        'success': False,
        'error': f'Esa cédula ya pertenece a otro {quien}. La cédula es el CI/RUC de login y no puede repetirse.'
    }), 409


# ==============================
#   Obtener todos los médicos
# ==============================
@medicoapi.route('/medico', methods=['GET'])
@require_login  # lookup usado por formularios de otras ventanas
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
@require_login  # lookup usado por formularios de otras ventanas
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
@require_permiso('medico', 'nuevo')
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

    data['cedula'] = str(data['cedula']).strip()
    try:
        # La cédula tampoco puede existir en la tabla de funcionarios
        donde = medicodao.cedulaUsadaPorOtro(data['cedula'])
        if donde:
            return _error_cedula_repetida(donde)

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
@require_permiso('medico', 'editar')
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

    data['cedula'] = str(data['cedula']).strip()
    try:
        donde = medicodao.cedulaUsadaPorOtro(data['cedula'], excluir_medico=medico_id)
        if donde:
            return _error_cedula_repetida(donde)

        # Si la persona tiene usuario, su cédula es su login: cambiarla exige confirmación
        actual = medicodao.getMedicoById(medico_id)
        cedula_anterior = (actual['cedula'] or '').strip() if actual else None
        id_usuario = medicodao.getUsuarioVinculado(medico_id) if actual else None
        cambia_login = bool(id_usuario) and cedula_anterior != data['cedula']
        if cambia_login and not data.get('confirmar_cambio_cedula'):
            return jsonify({
                'success': False,
                'requiere_confirmacion': True,
                'cedula_anterior': cedula_anterior,
                'cedula_nueva': data['cedula'],
                'error': 'Cambiar la cédula cambia el CI/RUC con el que esta persona inicia sesión.'
            }), 409

        actualizado = medicodao.updateMedico(
            medico_id, data['nombre'], data['apellido'], data['id_especialidad'], data['num_registro'],
            data['cedula'], data['fecha_nacimiento'], data['fecha_registro'],
            data['telefono'], data['direccion'], data['correo'], data['id_ciudad']
        )

        if actualizado:
            if cambia_login:
                AuditoriaDao().registrar_cambio_cedula(
                    id_usuario, cedula_anterior, data['cedula'],
                    request.remote_addr, session.get('id_usuario'))
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
@require_permiso('medico', 'anular')
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