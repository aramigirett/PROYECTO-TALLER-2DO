"""
=====================================================
API: Orden de Estudio (Generar Orden de Estudios)
Descripción: Endpoints REST para órdenes de estudio de una Consulta
=====================================================
"""

from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_consultorio.orden_estudio.OrdenEstudioDao import OrdenEstudioDao

ordenestudioapi = Blueprint('ordenestudioapi', __name__)

ERRORES = {
    'CONSULTA_NO_ENCONTRADA': (404, 'No se encontró la consulta seleccionada.'),
    'CONSULTA_NO_ACTIVA': (409, 'La consulta ya no está activa (debe estar programada o en proceso).'),
    'DIAGNOSTICO_INVALIDO': (400, 'El diagnóstico seleccionado no pertenece a esta consulta.'),
    'TRATAMIENTO_INVALIDO': (400, 'El tratamiento seleccionado no pertenece a esta consulta.'),
    'ERROR_INTERNO': (500, 'Ocurrió un error interno. Consulte con el administrador.'),
}


# =====================================================
# ENDPOINT: OBTENER TODAS LAS ÓRDENES DE ESTUDIO
# =====================================================
@ordenestudioapi.route('/orden-estudios', methods=['GET'])
def getOrdenes():
    dao = OrdenEstudioDao()
    try:
        ordenes = dao.getOrdenes()
        return jsonify({'success': True, 'data': ordenes, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener órdenes de estudio: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: OBTENER UNA ORDEN DE ESTUDIO POR ID
# =====================================================
@ordenestudioapi.route('/orden-estudios/<int:id_orden_estudio>', methods=['GET'])
def getOrden(id_orden_estudio):
    dao = OrdenEstudioDao()
    try:
        orden = dao.getOrdenById(id_orden_estudio)
        if orden:
            return jsonify({'success': True, 'data': orden, 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró la orden de estudio con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener orden de estudio: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: REGISTRAR NUEVA ORDEN DE ESTUDIO
# =====================================================
@ordenestudioapi.route('/orden-estudios', methods=['POST'])
def addOrden():
    """
    Registra una nueva orden de estudio, a partir de una Consulta activa.
    id_diagnostico e id_tratamiento son opcionales.

    Body JSON:
    {
        "id_consulta_cab": 5,
        "id_diagnostico": 3,          (opcional)
        "id_tratamiento": 2,          (opcional)
        "id_tipo_estudio": 1,
        "motivo_orden": "...",
        "indicaciones": "...",        (opcional)
        "fecha_orden": "2026-09-12"   (opcional, hoy por defecto)
    }
    """
    data = request.get_json()
    dao = OrdenEstudioDao()

    if not data or not data.get('id_consulta_cab'):
        return jsonify({'success': False, 'error': 'El campo id_consulta_cab es obligatorio: la orden debe partir de una Consulta activa.'}), 400
    if not data.get('id_tipo_estudio'):
        return jsonify({'success': False, 'error': 'El campo Tipo de Estudio es obligatorio.'}), 400
    if not data.get('motivo_orden') or not data['motivo_orden'].strip():
        return jsonify({'success': False, 'error': 'El campo Motivo de Orden es obligatorio y no puede estar vacío.'}), 400

    try:
        resultado = dao.guardarOrden(data)

        if 'id_orden_estudio' in resultado:
            return jsonify({
                'success': True,
                'data': {
                    'id_orden_estudio': resultado['id_orden_estudio'],
                    'mensaje': 'Orden de estudio registrada correctamente'
                },
                'error': None
            }), 201

        codigo, mensaje = ERRORES.get(resultado.get('error'), ERRORES['ERROR_INTERNO'])
        return jsonify({'success': False, 'error': mensaje}), codigo

    except Exception as e:
        app.logger.error(f"Error al registrar orden de estudio: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: ACTUALIZAR ESTADO (avanza al siguiente paso)
# =====================================================
@ordenestudioapi.route('/orden-estudios/<int:id_orden_estudio>/estado', methods=['PUT'])
def actualizarEstado(id_orden_estudio):
    """
    Avanza la orden al siguiente estado de la secuencia estricta
    pendiente -> enviado -> en_proceso -> completado. No recibe el estado
    en el body: el sistema calcula el siguiente paso.

    URL: PUT /api/v1/orden-estudios/5/estado
    """
    dao = OrdenEstudioDao()
    try:
        resultado = dao.actualizarEstado(id_orden_estudio)

        if resultado == "YA_COMPLETADO":
            return jsonify({
                'success': False,
                'error': 'No se puede actualizar: la orden ya está completada.'
            }), 409

        if resultado == "CANCELADO":
            return jsonify({
                'success': False,
                'error': 'No se puede actualizar: la orden está cancelada.'
            }), 409

        if resultado:
            return jsonify({
                'success': True,
                'mensaje': f'Orden de estudio actualizada a "{resultado}".',
                'error': None
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró la orden de estudio con el ID proporcionado.'}), 404

    except Exception as e:
        app.logger.error(f"Error al actualizar estado de orden de estudio: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: ANULAR ORDEN DE ESTUDIO
# =====================================================
@ordenestudioapi.route('/orden-estudios/<int:id_orden_estudio>', methods=['DELETE'])
def deleteOrden(id_orden_estudio):
    dao = OrdenEstudioDao()
    try:
        registro = dao.getOrdenById(id_orden_estudio)
        resultado = dao.anularOrden(id_orden_estudio)

        if resultado == "YA_CERRADO":
            return jsonify({
                'success': False,
                'error': 'No se puede anular: la orden ya está completada o cancelada.'
            }), 409

        if resultado:
            descripcion = f"de {registro['tipo_estudio']} del {registro['fecha_orden']} de {registro['nombre_paciente']}" if registro else 'seleccionada'
            return jsonify({
                'success': True,
                'mensaje': f'Orden de estudio {descripcion} anulada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró la orden de estudio con el ID proporcionado.'}), 404

    except Exception as e:
        app.logger.error(f"Error al anular orden de estudio: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
