"""
=====================================================
API: Sesión de Tratamiento (Gestionar Procedimientos e Insumos Utilizados)
Descripción: Endpoints REST para las sesiones clínicas de un Tratamiento
=====================================================
"""

from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_consultorio.sesion_tratamiento.SesionTratamientoDao import SesionTratamientoDao

sesiontratamientoapi = Blueprint('sesiontratamientoapi', __name__)

ERRORES = {
    'TRATAMIENTO_NO_ENCONTRADO': (404, 'No se encontró el tratamiento seleccionado.'),
    'TRATAMIENTO_NO_ACTIVO': (409, 'El tratamiento ya no está activo (debe estar pendiente o en seguimiento).'),
    'SIN_INSUMOS': (400, 'Debe registrar al menos un insumo utilizado.'),
    'ERROR_INTERNO': (500, 'Ocurrió un error interno. Consulte con el administrador.'),
}


# =====================================================
# ENDPOINT: OBTENER SESIONES DE UN TRATAMIENTO
# =====================================================
@sesiontratamientoapi.route('/sesiones-tratamiento/tratamiento/<int:id_tratamiento>', methods=['GET'])
def getSesionesByTratamiento(id_tratamiento):
    dao = SesionTratamientoDao()
    try:
        sesiones = dao.getSesionesByTratamiento(id_tratamiento)
        return jsonify({'success': True, 'data': sesiones, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener sesiones del tratamiento: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: OBTENER UNA SESIÓN POR ID
# =====================================================
@sesiontratamientoapi.route('/sesiones-tratamiento/<int:id_sesion>', methods=['GET'])
def getSesion(id_sesion):
    dao = SesionTratamientoDao()
    try:
        sesion = dao.getSesionById(id_sesion)
        if sesion:
            return jsonify({'success': True, 'data': sesion, 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró la sesión con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener sesión: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: REGISTRAR NUEVA SESIÓN
# =====================================================
@sesiontratamientoapi.route('/sesiones-tratamiento', methods=['POST'])
def addSesion():
    """
    Registra una nueva sesión de tratamiento con sus insumos.

    Body JSON:
    {
        "id_tratamiento": 5,
        "id_tipo_procedimiento": 2,
        "fecha_sesion": "2026-09-10",      (opcional, hoy por defecto)
        "descripcion_procedimiento": "...",
        "observaciones": "...",            (opcional)
        "proxima_cita": "2026-09-20",      (opcional)
        "insumos": [{"id_insumo": 1, "cantidad": 2}, ...]
    }
    """
    data = request.get_json()
    dao = SesionTratamientoDao()

    if not data or not data.get('id_tratamiento'):
        return jsonify({'success': False, 'error': 'El campo id_tratamiento es obligatorio: la sesión debe partir de un Tratamiento activo.'}), 400
    if not data.get('id_tipo_procedimiento'):
        return jsonify({'success': False, 'error': 'El campo Tipo de Procedimiento es obligatorio.'}), 400
    if not data.get('descripcion_procedimiento') or not data['descripcion_procedimiento'].strip():
        return jsonify({'success': False, 'error': 'El campo Descripción es obligatorio y no puede estar vacío.'}), 400
    insumos = data.get('insumos') or []
    if not insumos:
        return jsonify({'success': False, 'error': 'Debe registrar al menos un insumo utilizado.'}), 400
    for insumo in insumos:
        if not insumo.get('id_insumo') or not insumo.get('cantidad') or insumo.get('cantidad') <= 0:
            return jsonify({'success': False, 'error': 'Cada insumo debe tener un id_insumo válido y una cantidad mayor a cero.'}), 400

    try:
        resultado = dao.guardarSesion(data)

        if 'id_sesion' in resultado:
            return jsonify({
                'success': True,
                'data': {
                    'id_sesion': resultado['id_sesion'],
                    'mensaje': 'Sesión registrada correctamente'
                },
                'error': None
            }), 201

        codigo, mensaje = ERRORES.get(resultado.get('error'), ERRORES['ERROR_INTERNO'])
        return jsonify({'success': False, 'error': mensaje}), codigo

    except Exception as e:
        app.logger.error(f"Error al registrar sesión: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: ANULAR SESIÓN (baja lógica, solo la última)
# =====================================================
@sesiontratamientoapi.route('/sesiones-tratamiento/<int:id_sesion>', methods=['DELETE'])
def deleteSesion(id_sesion):
    dao = SesionTratamientoDao()
    try:
        registro = dao.getSesionById(id_sesion)
        resultado = dao.anularSesion(id_sesion)

        if resultado == "NO_ES_ULTIMA":
            return jsonify({
                'success': False,
                'error': 'Solo se puede anular la sesión más reciente del tratamiento.'
            }), 409

        if resultado:
            descripcion_sesion = f"N° {registro['numero_sesion']} del {registro['fecha_sesion']}" if registro else 'seleccionada'
            return jsonify({
                'success': True,
                'mensaje': f'Sesión {descripcion_sesion} anulada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró la sesión con el ID proporcionado, o ya estaba anulada.'}), 404

    except Exception as e:
        app.logger.error(f"Error al anular sesión: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
