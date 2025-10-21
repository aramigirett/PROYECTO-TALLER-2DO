"""
=====================================================
API: Ficha Médica de Consulta
Descripción: Endpoints REST para fichas médicas
=====================================================
"""

from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_consultorio.consulta.FichaMedicaDao import FichaMedicaDao

# Crear Blueprint
fichamedicaapi = Blueprint('fichamedicaapi', __name__)

# =====================================================
# ENDPOINT: OBTENER FICHA MÉDICA DE UNA CONSULTA
# =====================================================
@fichamedicaapi.route('/ficha-medica/consulta/<int:consulta_id>', methods=['GET'])
def getFichaByConsulta(consulta_id):
    """
    Obtiene la ficha médica de una consulta específica
    
    URL: GET /api/v1/ficha-medica/consulta/5
    """
    fichaDao = FichaMedicaDao()

    try:
        ficha = fichaDao.getFichaByConsulta(consulta_id)

        if ficha:
            return jsonify({
                'success': True,
                'data': ficha,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró ficha médica para esta consulta.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener ficha médica: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: OBTENER FICHA MÉDICA POR ID
# =====================================================
@fichamedicaapi.route('/ficha-medica/<int:ficha_id>', methods=['GET'])
def getFicha(ficha_id):
    """
    Obtiene una ficha médica por su ID
    
    URL: GET /api/v1/ficha-medica/10
    """
    fichaDao = FichaMedicaDao()

    try:
        ficha = fichaDao.getFichaById(ficha_id)

        if ficha:
            return jsonify({
                'success': True,
                'data': ficha,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la ficha médica con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener ficha médica: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: CREAR NUEVA FICHA MÉDICA
# =====================================================
@fichamedicaapi.route('/ficha-medica', methods=['POST'])
def addFicha():
    """
    Crea una nueva ficha médica
    
    URL: POST /api/v1/ficha-medica
    
    Body JSON:
    {
        "id_consulta_cab": 5,
        "presion_arterial": "120/80",
        "temperatura": 36.5,
        "frecuencia_cardiaca": 72,
        "frecuencia_respiratoria": 16,
        "peso": 70.5,
        "talla": 175,
        "imc": 23.0,
        "examen_fisico_general": "...",
        "examen_bucal": "...",
        "observaciones_medico": "..."
    }
    """
    data = request.get_json()
    fichaDao = FichaMedicaDao()

    # Validación: id_consulta_cab es obligatorio
    if 'id_consulta_cab' not in data or data['id_consulta_cab'] is None:
        return jsonify({
            'success': False,
            'error': 'El campo id_consulta_cab es obligatorio.'
        }), 400

    try:
        # Verificar si ya existe una ficha para esta consulta
        ficha_existente = fichaDao.getFichaByConsulta(data['id_consulta_cab'])
        if ficha_existente:
            return jsonify({
                'success': False,
                'error': 'Ya existe una ficha médica para esta consulta. Use PUT para actualizar.'
            }), 400

        # Guardar nueva ficha
        ficha_id = fichaDao.guardarFicha(data)
        
        if ficha_id is not None:
            return jsonify({
                'success': True,
                'data': {
                    'id_ficha_medica': ficha_id,
                    'mensaje': 'Ficha médica creada correctamente'
                },
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo guardar la ficha médica.'
            }), 500

    except Exception as e:
        app.logger.error(f"Error al crear ficha médica: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: ACTUALIZAR FICHA MÉDICA
# =====================================================
@fichamedicaapi.route('/ficha-medica/<int:ficha_id>', methods=['PUT'])
def updateFicha(ficha_id):
    """
    Actualiza una ficha médica existente
    
    URL: PUT /api/v1/ficha-medica/10
    """
    data = request.get_json()
    fichaDao = FichaMedicaDao()

    try:
        if fichaDao.updateFicha(ficha_id, data):
            return jsonify({
                'success': True,
                'data': {
                    'id_ficha_medica': ficha_id,
                    'mensaje': 'Ficha médica actualizada correctamente'
                },
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo actualizar la ficha médica.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al actualizar ficha médica: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: ELIMINAR FICHA MÉDICA
# =====================================================
@fichamedicaapi.route('/ficha-medica/<int:ficha_id>', methods=['DELETE'])
def deleteFicha(ficha_id):
    """
    Elimina una ficha médica
    
    URL: DELETE /api/v1/ficha-medica/10
    """
    fichaDao = FichaMedicaDao()

    try:
        if fichaDao.deleteFicha(ficha_id):
            return jsonify({
                'success': True,
                'mensaje': f'Ficha médica con ID {ficha_id} eliminada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la ficha médica o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar ficha médica: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500