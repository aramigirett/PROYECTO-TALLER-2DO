"""
=====================================================
API: Consulta Detalle
Descripción: Endpoints REST para detalles clínicos
=====================================================
"""

from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_consultorio.consulta.ConsultaDetalleDao import ConsultaDetalleDao

# Crear Blueprint
consultadetalleapi = Blueprint('consultadetalleapi', __name__)

# =====================================================
# ENDPOINT: OBTENER DETALLES DE UNA CONSULTA
# =====================================================
@consultadetalleapi.route('/consultas-detalle/consulta/<int:consulta_id>', methods=['GET'])
def getDetallesByConsulta(consulta_id):
    """
    Obtiene todos los detalles clínicos de una consulta
    
    URL: GET /api/v1/consultas-detalle/consulta/5
    """
    detalleDao = ConsultaDetalleDao()

    try:
        detalles = detalleDao.getDetallesByConsulta(consulta_id)

        return jsonify({
            'success': True,
            'data': detalles,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener detalles: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: OBTENER UN DETALLE POR ID
# =====================================================
@consultadetalleapi.route('/consultas-detalle/<int:detalle_id>', methods=['GET'])
def getDetalle(detalle_id):
    """
    Obtiene un detalle específico por ID
    
    URL: GET /api/v1/consultas-detalle/15
    """
    detalleDao = ConsultaDetalleDao()

    try:
        detalle = detalleDao.getDetalleById(detalle_id)

        if detalle:
            return jsonify({
                'success': True,
                'data': detalle,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el detalle con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener detalle: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: AGREGAR NUEVO DETALLE
# =====================================================
@consultadetalleapi.route('/consultas-detalle', methods=['POST'])
def addDetalle():
    """
    Crea un nuevo detalle clínico
    
    URL: POST /api/v1/consultas-detalle
    """
    data = request.get_json()
    detalleDao = ConsultaDetalleDao()

    # Validaciones
    campos_requeridos = ['id_consulta_cab', 'id_sintoma', 'diagnostico', 'tratamiento']

    for campo in campos_requeridos:
        if campo not in data or data[campo] is None:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio.'
            }), 400

    try:
        detalle_id = detalleDao.guardarDetalle(data)
        
        if detalle_id is not None:
            return jsonify({
                'success': True,
                'data': {
                    'id_consulta_detalle': detalle_id,
                    'mensaje': 'Detalle agregado correctamente'
                },
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo guardar el detalle.'
            }), 500

    except Exception as e:
        app.logger.error(f"Error al agregar detalle: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: ACTUALIZAR DETALLE
# =====================================================
@consultadetalleapi.route('/consultas-detalle/<int:detalle_id>', methods=['PUT'])
def updateDetalle(detalle_id):
    """
    Actualiza un detalle clínico existente
    
    URL: PUT /api/v1/consultas-detalle/15
    """
    data = request.get_json()
    detalleDao = ConsultaDetalleDao()

    # Validaciones
    campos_requeridos = ['id_sintoma', 'diagnostico', 'tratamiento']

    for campo in campos_requeridos:
        if campo not in data or data[campo] is None:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio.'
            }), 400

    try:
        if detalleDao.updateDetalle(detalle_id, data):
            return jsonify({
                'success': True,
                'data': {
                    'id_consulta_detalle': detalle_id,
                    'mensaje': 'Detalle actualizado correctamente'
                },
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo actualizar el detalle.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al actualizar detalle: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: ELIMINAR DETALLE
# =====================================================
@consultadetalleapi.route('/consultas-detalle/<int:detalle_id>', methods=['DELETE'])
def deleteDetalle(detalle_id):
    """
    Elimina un detalle clínico
    
    URL: DELETE /api/v1/consultas-detalle/15
    """
    detalleDao = ConsultaDetalleDao()

    try:
        if detalleDao.deleteDetalle(detalle_id):
            return jsonify({
                'success': True,
                'mensaje': f'Detalle con ID {detalle_id} eliminado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el detalle o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar detalle: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500