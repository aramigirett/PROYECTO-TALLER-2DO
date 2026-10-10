from flask import Blueprint, jsonify, request, session, current_app as app
from app.dao.referenciales.funcionario.FuncionarioDao import FuncionarioDao
from app.dao.modulo_seguridad.AuditoriaDao import AuditoriaDao
from app.rutas.modulo_seguridad.decorators import require_permiso, require_login

funcionarioapi = Blueprint('funcionarioapi', __name__)


def _error_cedula_repetida(donde):
    quien = 'funcionario' if donde == 'funcionario' else 'médico'
    return jsonify({
        'success': False,
        'error': f'Esa cédula ya pertenece a otro {quien}. La cédula es el CI/RUC de login y no puede repetirse.'
    }), 409

# ==============================
#   Obtener todos los funcionarios
# ==============================
@funcionarioapi.route('/funcionarios', methods=['GET'])
@require_login  # lookup usado por formularios de otras ventanas
def getFuncionarios():
    funcionariodao = FuncionarioDao()
    try:
        funcionarios = funcionariodao.getFuncionarios()
        return jsonify({'success': True, 'data': funcionarios, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener funcionarios: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno al consultar los funcionarios.'
        }), 500


# ==============================
#   Obtener funcionario por ID
# ==============================
@funcionarioapi.route('/funcionarios/<int:funcionario_id>', methods=['GET'])
@require_permiso('funcionario', 'ver')
def getFuncionarioById(funcionario_id):
    funcionariodao = FuncionarioDao()
    try:
        funcionario = funcionariodao.getFuncionarioById(funcionario_id)
        if funcionario:
            return jsonify({'success': True, 'data': funcionario, 'error': None}), 200
        return jsonify({
            'success': False,
            'error': f'No se encontró el funcionario con ID {funcionario_id}.'
        }), 404
    except Exception as e:
        app.logger.error(f"Error al obtener funcionario con ID {funcionario_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno al consultar el funcionario.'
        }), 500


# ==============================
#   Agregar nuevo funcionario
# ==============================
@funcionarioapi.route('/funcionarios', methods=['POST'])
@require_permiso('funcionario', 'nuevo')
def addFuncionario():
    data = request.get_json()
    funcionariodao = FuncionarioDao()

    campos_requeridos = ['nombre', 'apellido', 'cedula', 'fecha_nacimiento',
                         'telefono', 'direccion', 'correo', 'id_cargo', 'fecha_registro']
    for campo in campos_requeridos:
        if not data.get(campo) or (isinstance(data[campo], str) and not data[campo].strip()):
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    data['cedula'] = str(data['cedula']).strip()
    try:
        # La cédula tampoco puede existir en la tabla de médicos
        donde = funcionariodao.cedulaUsadaPorOtro(data['cedula'])
        if donde:
            return _error_cedula_repetida(donde)

        # Validar duplicado
        if funcionariodao.existeDuplicado(data['cedula'], data['correo']):
            return jsonify({
                'success': False,
                'error': 'Ya existe un funcionario con esa cédula o correo.'
            }), 409

        funcionario_id = funcionariodao.guardarFuncionario(
            data['nombre'], data['apellido'], data['cedula'], data['fecha_nacimiento'],
            data['telefono'], data['direccion'], data['correo'],
            data['id_cargo'], data['fecha_registro']
        )

        if funcionario_id:
            app.logger.info(f"Funcionario creado con ID {funcionario_id}.")
            return jsonify({
                'success': True,
                'data': {**data, 'id_funcionario': funcionario_id},
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo guardar el funcionario.'
            }), 500
    except Exception as e:
        app.logger.error(f"Error al agregar funcionario: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno al guardar el funcionario.'
        }), 500


# ==============================
#   Actualizar funcionario
# ==============================
@funcionarioapi.route('/funcionarios/<int:funcionario_id>', methods=['PUT'])
@require_permiso('funcionario', 'editar')
def updateFuncionario(funcionario_id):
    data = request.get_json()
    funcionariodao = FuncionarioDao()

    campos_requeridos = ['nombre', 'apellido', 'cedula', 'fecha_nacimiento',
                         'telefono', 'direccion', 'correo', 'id_cargo', 'fecha_registro']
    for campo in campos_requeridos:
        if not data.get(campo) or (isinstance(data[campo], str) and not data[campo].strip()):
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    data['cedula'] = str(data['cedula']).strip()
    try:
        donde = funcionariodao.cedulaUsadaPorOtro(data['cedula'], excluir_funcionario=funcionario_id)
        if donde:
            return _error_cedula_repetida(donde)

        # Si la persona tiene usuario, su cédula es su login: cambiarla exige confirmación
        actual = funcionariodao.getFuncionarioById(funcionario_id)
        cedula_anterior = (actual['cedula'] or '').strip() if actual else None
        id_usuario = funcionariodao.getUsuarioVinculado(funcionario_id) if actual else None
        cambia_login = bool(id_usuario) and cedula_anterior != data['cedula']
        if cambia_login and not data.get('confirmar_cambio_cedula'):
            return jsonify({
                'success': False,
                'requiere_confirmacion': True,
                'cedula_anterior': cedula_anterior,
                'cedula_nueva': data['cedula'],
                'error': 'Cambiar la cédula cambia el CI/RUC con el que esta persona inicia sesión.'
            }), 409

        actualizado = funcionariodao.updateFuncionario(
            funcionario_id, data['nombre'], data['apellido'], data['cedula'], data['fecha_nacimiento'],
            data['telefono'], data['direccion'], data['correo'], data['id_cargo'], data['fecha_registro']
        )

        if actualizado:
            if cambia_login:
                AuditoriaDao().registrar_cambio_cedula(
                    id_usuario, cedula_anterior, data['cedula'],
                    request.remote_addr, session.get('id_usuario'))
            app.logger.info(f"Funcionario con ID {funcionario_id} actualizado exitosamente.")
            return jsonify({
                'success': True,
                'data': {**data, 'id_funcionario': funcionario_id},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'No se encontró el funcionario con ID {funcionario_id} o no se pudo actualizar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar funcionario con ID {funcionario_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno al actualizar el funcionario.'
        }), 500


# ==============================
#   Eliminar funcionario
# ==============================
@funcionarioapi.route('/funcionarios/<int:funcionario_id>', methods=['DELETE'])
@require_permiso('funcionario', 'anular')
def deleteFuncionario(funcionario_id):
    funcionariodao = FuncionarioDao()
    try:
        if funcionariodao.deleteFuncionario(funcionario_id):
            app.logger.info(f"Funcionario con ID {funcionario_id} eliminado.")
            return jsonify({
                'success': True,
                'mensaje': f'Funcionario con ID {funcionario_id} eliminado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'No se encontró el funcionario con ID {funcionario_id} o no se pudo eliminar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar funcionario con ID {funcionario_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno al eliminar el funcionario.'
        }), 500