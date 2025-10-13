from flask import Blueprint, jsonify, request, current_app as app
from app.dao.referenciales.funcionario.FuncionarioDao import FuncionarioDao

funcionarioapi = Blueprint('funcionarioapi', __name__)

# ==============================
#   Obtener todos los funcionarios
# ==============================
@funcionarioapi.route('/funcionarios', methods=['GET'])
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

    try:
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

    try:
        actualizado = funcionariodao.updateFuncionario(
            funcionario_id, data['nombre'], data['apellido'], data['cedula'], data['fecha_nacimiento'],
            data['telefono'], data['direccion'], data['correo'], data['id_cargo'], data['fecha_registro']
        )

        if actualizado:
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