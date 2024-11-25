from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.dia.DiaDao import DiaDao

diaapi = Blueprint('diaapi', __name__)

# Lista de días válidos
DIAS_VALIDOS = {'LUNES', 'MARTES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'SABADO', 'DOMINGO'}

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
        app.logger.error(f"Error al obtener todos los días: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Agrega un nuevo día
@diaapi.route('/dias', methods=['POST'])
def addDia():
    data = request.get_json()
    diadao = DiaDao()
    
    # Validar que la propiedad 'descripcion' esté en el JSON y no esté vacía
    if 'descripcion' not in data or not data['descripcion'].strip():
        return jsonify({
            'success': False,
            'error': 'El campo descripcion es obligatorio y no puede estar vacío.'
        }), 400

    descripcion = data['descripcion'].strip().upper()
    
    # Verificar que el día sea válido
    if descripcion not in DIAS_VALIDOS:
        return jsonify({
            'success': False,
            'error': f'El día proporcionado ({descripcion}) no es válido. Debe ser dias de la semana: {", ".join(DIAS_VALIDOS)}.'
        }), 400

    try:
        dia_id = diadao.guardarDia(descripcion)
        if dia_id is not None:
            return jsonify({
                'success': True,
                'data': {'id': dia_id, 'descripcion': descripcion},
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo guardar el día. Consulte con el administrador.'
            }), 500
    except Exception as e:
        app.logger.error(f"Error al agregar día: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Actualiza un día
@diaapi.route('/dias/<int:dia_id>', methods=['PUT'])
def updateDia(dia_id):
    data = request.get_json()
    diadao = DiaDao()

    if 'descripcion' not in data or not data['descripcion'].strip():
        return jsonify({
            'success': False,
            'error': 'El campo descripcion es obligatorio y no puede estar vacío.'
        }), 400

    descripcion = data['descripcion'].strip().upper()

    if descripcion not in DIAS_VALIDOS:
        return jsonify({
            'success': False,
            'error': f'El día proporcionado ({descripcion}) no es válido. Debe ser uno de los siguientes: {", ".join(DIAS_VALIDOS)}.'
        }), 400

    try:
        if diadao.updateDia(dia_id, descripcion):
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