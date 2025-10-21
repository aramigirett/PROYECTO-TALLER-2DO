"""
=====================================================
API: Consulta Médica
Descripción: Endpoints REST para gestionar consultas médicas
=====================================================
"""

from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_consultorio.consulta.ConsultaDao  import ConsultaDao

# Crear Blueprint
consultaapi = Blueprint('consultaapi', __name__)

# =====================================================
# ENDPOINT: OBTENER TODAS LAS CONSULTAS
# =====================================================
@consultaapi.route('/consultas', methods=['GET'])
def getConsultas():
    """
    Obtiene todas las consultas médicas
    
    URL: GET /api/v1/consultas
    """
    consultaDao = ConsultaDao()

    try:
        consultas = consultaDao.getConsultas()

        return jsonify({
            'success': True,
            'data': consultas,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener todas las consultas: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: OBTENER UNA CONSULTA POR ID
# =====================================================
@consultaapi.route('/consultas/<int:consulta_id>', methods=['GET'])
def getConsulta(consulta_id):
    """
    Obtiene una consulta específica por ID
    
    URL: GET /api/v1/consultas/5
    """
    consultaDao = ConsultaDao()

    try:
        consulta = consultaDao.getConsultaById(consulta_id)

        if consulta:
            return jsonify({
                'success': True,
                'data': consulta,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la consulta con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener consulta: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: AGREGAR NUEVA CONSULTA
# =====================================================
@consultaapi.route('/consultas', methods=['POST'])
def addConsulta():
    """
    Crea una nueva consulta médica
    
    URL: POST /api/v1/consultas
    
    Body JSON:
    {
        "id_cita": 1,
        "id_paciente": 5,
        "id_medico": 3,
        "id_consultorio": 2,
        "id_funcionario": 1,
        "fecha_cita": "2025-10-15",
        "hora_cita": "10:30",
        "duracion_minutos": 30,
        "estado": "programada"
    }
    """
    data = request.get_json()
    consultaDao = ConsultaDao()

    # ========== VALIDACIONES ==========
    campos_requeridos = ['id_paciente', 'id_medico', 'id_consultorio', 'fecha_cita', 'hora_cita']

    for campo in campos_requeridos:
        if campo not in data or data[campo] is None:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        # Guardar consulta
        consulta_id = consultaDao.guardarConsulta(data)
        
        if consulta_id is not None:
            return jsonify({
                'success': True,
                'data': {
                    'id_consulta_cab': consulta_id,
                    'mensaje': 'Consulta registrada correctamente'
                },
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo guardar la consulta. Consulte con el administrador.'
            }), 500

    except Exception as e:
        app.logger.error(f"Error al agregar consulta: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: ACTUALIZAR CONSULTA
# =====================================================
@consultaapi.route('/consultas/<int:consulta_id>', methods=['PUT'])
def updateConsulta(consulta_id):
    """
    Actualiza una consulta existente
    
    URL: PUT /api/v1/consultas/5
    """
    data = request.get_json()
    consultaDao = ConsultaDao()

    # ========== VALIDACIONES ==========
    campos_requeridos = ['id_paciente', 'id_medico', 'id_consultorio', 'fecha_cita', 'hora_cita']

    for campo in campos_requeridos:
        if campo not in data or data[campo] is None:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        # Actualizar consulta
        if consultaDao.updateConsulta(consulta_id, data):
            return jsonify({
                'success': True,
                'data': {
                    'id_consulta_cab': consulta_id,
                    'mensaje': 'Consulta actualizada correctamente'
                },
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la consulta con el ID proporcionado o no se pudo actualizar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al actualizar consulta: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: ELIMINAR CONSULTA
# =====================================================
@consultaapi.route('/consultas/<int:consulta_id>', methods=['DELETE'])
def deleteConsulta(consulta_id):
    """
    Elimina una consulta (y sus detalles automáticamente por CASCADE)
    
    URL: DELETE /api/v1/consultas/5
    """
    consultaDao = ConsultaDao()

    try:
        if consultaDao.deleteConsulta(consulta_id):
            return jsonify({
                'success': True,
                'mensaje': f'Consulta con ID {consulta_id} eliminada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la consulta con el ID proporcionado o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar consulta: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500