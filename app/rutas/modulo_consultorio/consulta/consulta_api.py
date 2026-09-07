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
# ENDPOINT: OBTENER CONSULTAS ACTIVAS (para Gestionar Tratamientos)
# =====================================================
@consultaapi.route('/consultas/activas', methods=['GET'])
def getConsultasActivas():
    """
    Obtiene las consultas activas (programada/en_proceso) desde las que se
    puede partir para registrar un Tratamiento.

    URL: GET /api/v1/consultas/activas
    """
    consultaDao = ConsultaDao()

    try:
        consultas = consultaDao.getConsultasActivas()
        return jsonify({
            'success': True,
            'data': consultas,
            'error': None
        }), 200
    except Exception as e:
        app.logger.error(f"Error al obtener consultas activas: {str(e)}")
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
    Crea una nueva consulta médica a partir de una Cita ya Confirmada.
    Paciente, Médico, Consultorio, Fecha y Hora se derivan de la cita en el
    backend (no se toman del body); al guardar, la cita pasa a 'Realizado'.

    URL: POST /api/v1/consultas

    Body JSON:
    {
        "id_cita": 1,
        "id_funcionario": 1,
        "duracion_minutos": 30,
        "estado": "programada"
    }
    """
    data = request.get_json()
    consultaDao = ConsultaDao()

    if not data or not data.get('id_cita'):
        return jsonify({
            'success': False,
            'error': 'El campo id_cita es obligatorio: la consulta debe partir de una Cita Confirmada.'
        }), 400

    ERRORES = {
        'CITA_NO_ENCONTRADA': (404, 'No se encontró la cita seleccionada.'),
        'CITA_NO_CONFIRMADA': (409, 'La cita no está en estado Confirmado.'),
        'CITA_YA_TIENE_CONSULTA': (409, 'Esta cita ya tiene una consulta registrada.'),
        'ERROR_INTERNO': (500, 'Ocurrió un error interno. Consulte con el administrador.'),
    }

    try:
        resultado = consultaDao.guardarConsulta(data)

        if 'id_consulta_cab' in resultado:
            return jsonify({
                'success': True,
                'data': {
                    'id_consulta_cab': resultado['id_consulta_cab'],
                    'mensaje': 'Consulta registrada correctamente'
                },
                'error': None
            }), 201

        codigo, mensaje = ERRORES.get(resultado.get('error'), ERRORES['ERROR_INTERNO'])
        return jsonify({'success': False, 'error': mensaje}), codigo

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
    Actualiza una consulta existente.
    Solo Duración y Estado (de la Consulta) son editables; Cita, Paciente,
    Médico, Consultorio, Fecha y Hora quedan fijos desde el registro inicial.

    URL: PUT /api/v1/consultas/5

    Body JSON:
    {
        "duracion_minutos": 30,
        "estado": "en_proceso"
    }
    """
    data = request.get_json()
    consultaDao = ConsultaDao()

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
    Anula (baja lógica) una consulta. Se bloquea si ya tiene Ficha Médica,
    Diagnóstico o Tratamiento asociados.

    URL: DELETE /api/v1/consultas/5
    """
    consultaDao = ConsultaDao()

    try:
        registro = consultaDao.getConsultaById(consulta_id)
        resultado = consultaDao.deleteConsulta(consulta_id)

        if resultado == "EN_USO":
            return jsonify({
                'success': False,
                'error': 'No se puede anular: esta consulta ya tiene Ficha Médica, Diagnóstico o Tratamiento registrados.'
            }), 409

        if resultado:
            descripcion = f"del {registro['fecha_cita']} de {registro['nombre_paciente']}" if registro else 'seleccionada'
            return jsonify({
                'success': True,
                'mensaje': f'Consulta {descripcion} anulada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la consulta con el ID proporcionado o no se pudo anular.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar consulta: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500