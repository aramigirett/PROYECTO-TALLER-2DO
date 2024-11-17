from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.dia.DiaDao import DiaDao

diaapi = Blueprint('diaapi', __name__)

# Solo aceptar días de lunes a viernes
DIAS_VALIDOS = ['LUNES', 'MARTES', 'MIERCOLES', 'JUEVES', 'VIERNES']

# Trae todos los días
@diaapi.route('/dias', methods=['GET'])
def getDias():
    diadao = DiaDao()

    try:
        dias = diadao.getDias()

        return jsonify({
            'success': True,
            'data': dias,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener todos los dias: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@diaapi.route('/dias/<int:dia_id>', methods=['GET'])
def getDia(dia_id):
    diadao = DiaDao()

    try:
        dia = diadao.getDiaById(dia_id)

        if dia:
            return jsonify({
                'success': True,
                'data': dia,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el dia con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener dia: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Agrega un nuevo día con validación
@diaapi.route('/dias', methods=['POST'])
def addDia():
    data = request.get_json()
    diadao = DiaDao()

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

        # Validar si el día está en la lista de días válidos
        if descripcion not in DIAS_VALIDOS:
            return jsonify({
                'success': False,
                'error': 'Día inválido. Solo se permiten días de la semana.'
            }), 400

        dia_id = diadao.guardarDia(descripcion)
        if dia_id is not None:
            return jsonify({
                'success': True,
                'data': {'id': dia_id, 'descripcion': descripcion},
                'error': None
            }), 201
        else:
            return jsonify({ 'success': False, 'error': 'No se pudo guardar el día. Consulte con el administrador.' }), 500
    except Exception as e:
        app.logger.error(f"Error al agregar día: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@diaapi.route('/dias/<int:dia_id>', methods=['PUT'])
def updateDia(dia_id):
    data = request.get_json()
    diadao = DiaDao()

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
        if diadao.updateDia(dia_id, descripcion.upper()):
            return jsonify({
                'success': True,
                'data': {'id': dia_id, 'descripcion': descripcion},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el día con el ID proporcionado o no se pudo actualizar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar día: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@diaapi.route('/dias/<int:dia_id>', methods=['DELETE'])
def deleteDia(dia_id):
    diadao = DiaDao()

    try:
        # Usar el retorno de eliminarDia para determinar el éxito
        if diadao.deleteDia(dia_id):
            return jsonify({
                'success': True,
                'mensaje': f'Día con ID {dia_id} eliminado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el día con el ID proporcionado o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar día: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500