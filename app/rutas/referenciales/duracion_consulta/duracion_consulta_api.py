from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.duracion_consulta.DuracionConsultaDao import DuracionConsultaDao

duraconsuapi = Blueprint('duraconsuapi', __name__)

# Trae todas las duraciones de consultas
@duraconsuapi.route('/duracionconsulta', methods=['GET'])
def getDuracionConsultas():
    duraconsuldao = DuracionConsultaDao()

    try:
        duracionconsultas = duraconsuldao.getDuracionConsultas()

        return jsonify({
            'success': True,
            'data': duracionconsultas,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener todas las duraciones de consultas: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@duraconsuapi.route('/duracionconsultas/<int:duracionconsulta_id>', methods=['GET'])
def getDuracionConsulta(duracionconsulta_id):
    duraconsudao = DuracionConsultaDao()

    try:
        duracionconsulta = duraconsudao.getDuracionConsultaById(duracionconsulta_id)

        if duracionconsulta:
            return jsonify({
                'success': True,
                'data': duracionconsulta,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la duración de la consulta con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener duración de la consulta: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Agrega una nueva duracion de la consulta
@duraconsuapi.route('/duracionconsultas', methods=['POST'])
def addDuracionConsulta():
    data = request.get_json()
    duraconsudao = DuracionConsultaDao()

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
        duracionconsulta_id = duraconsudao.guardarDuracionConsulta(descripcion)
        if duracionconsulta_id is not None:
            return jsonify({
                'success': True,
                'data': {'id': duracionconsulta_id, 'descripcion': descripcion},
                'error': None
            }), 201
        else:
            return jsonify({ 'success': False, 'error': 'No se pudo guardar la duración de la consulta. Consulte con el administrador.' }), 500
    except Exception as e:
        app.logger.error(f"Error al agregar Duración de la Consulta: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@duraconsuapi.route('/duracionconsultas/<int:duracionconsulta_id>', methods=['PUT'])
def updateDuracionConsulta(duracionconsulta_id):
    data = request.get_json()
    duraconsudao = DuracionConsultaDao()

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
        if duraconsudao.updateDuracionConsulta(duracionconsulta_id, descripcion.upper()):
            return jsonify({
                'success': True,
                'data': {'id': duracionconsulta_id, 'descripcion': descripcion},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la duración de la consulta con el ID proporcionado o no se pudo actualizar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar Duración de la Consulta: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@duraconsuapi.route('/duracionconsultas/<int:duracionconsulta_id>', methods=['DELETE'])
def deleteDuracionConsulta(duracionconsulta_id):
    duraconsudao = DuracionConsultaDao()

    try:
        # Usar el retorno de eliminarDuracionConsulta para determinar el éxito
        if duraconsudao.deleteDuracionConsulta(duracionconsulta_id):
            return jsonify({
                'success': True,
                'mensaje': f'DuraciónConsulta con ID {duracionconsulta_id} eliminada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la duración de la consulta con el ID proporcionado o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar Duración de la Consulta: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500