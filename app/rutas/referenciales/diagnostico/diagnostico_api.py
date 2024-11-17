from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.diagnostico.DiagnosticoDao import DiagnosticoDao

diagapi = Blueprint('diagapi', __name__)

# Trae todos los diagnósticos
@diagapi.route('/diagnosticos', methods=['GET'])
def getDiagnosticos():
    diagdao = DiagnosticoDao()

    try:
        diagnosticos = diagdao.getDiagnosticos()

        return jsonify({
            'success': True,
            'data': diagnosticos,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener todos los diagnósticos: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@diagapi.route('/diagnosticos/<int:diagnostico_id>', methods=['GET'])
def getDiagnostico(diagnostico_id):
    diagdao = DiagnosticoDao()

    try:
        diagnostico = diagdao.getDiagnosticoById(diagnostico_id)

        if diagnostico:
            return jsonify({
                'success': True,
                'data': diagnostico,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el diagnóstico con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener diagnóstico: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Agrega un nuevo diagnóstico
@diagapi.route('/diagnosticos', methods=['POST'])
def addDiagnostico():
    data = request.get_json()
    diagdao = DiagnosticoDao()

    # Validar que el JSON no esté vacío y tenga las propiedades necesarias
    campos_requeridos = ['descripcion']

    # Verificar si faltan campos o son vacíos
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None or len(data[campo].strip()) == 0:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        descripcion = data['descripcion'].upper()
        diagnostico_id = diagdao.guardarDiagnostico(descripcion)
        if diagnostico_id is not None:
            return jsonify({
                'success': True,
                'data': {'id': diagnostico_id, 'descripcion': descripcion},
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo guardar el diagnóstico. Consulte con el administrador.'
            }), 500
    except Exception as e:
        app.logger.error(f"Error al agregar diagnóstico: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@diagapi.route('/diagnosticos/<int:diagnostico_id>', methods=['PUT'])
def updateDiagnostico(diagnostico_id):
    data = request.get_json()
    diagdao = DiagnosticoDao()

    # Validar que el JSON no esté vacío y tenga las propiedades necesarias
    campos_requeridos = ['descripcion']

    # Verificar si faltan campos o son vacíos
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None or len(data[campo].strip()) == 0:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400
    descripcion = data['descripcion']
    try:
        if diagdao.updateDiagnostico(diagnostico_id, descripcion.upper()):
            return jsonify({
                'success': True,
                'data': {'id': diagnostico_id, 'descripcion': descripcion},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el diagnóstico con el ID proporcionado o no se pudo actualizar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar diagnóstico: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@diagapi.route('/diagnosticos/<int:diagnostico_id>', methods=['DELETE'])
def deleteDiagnostico(diagnostico_id):
    diagdao = DiagnosticoDao()

    try:
        # Usar el retorno de eliminarDiagnostico para determinar el éxito
        if diagdao.deleteDiagnostico(diagnostico_id):
            return jsonify({
                'success': True,
                'mensaje': f'Diagnóstico con ID {diagnostico_id} eliminado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el diagnóstico con el ID proporcionado o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar diagnóstico: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500