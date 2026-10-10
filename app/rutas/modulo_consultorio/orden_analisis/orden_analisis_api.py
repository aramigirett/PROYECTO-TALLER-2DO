"""
=====================================================
API: Orden de Análisis (Generar Orden de Análisis)
Descripción: Endpoints REST para órdenes de análisis de una Consulta
=====================================================
"""

from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_consultorio.orden_analisis.OrdenAnalisisDao import OrdenAnalisisDao
from app.rutas.modulo_seguridad.decorators import require_permiso

ordenanalisisapi = Blueprint('ordenanalisisapi', __name__)

ERRORES = {
    'CONSULTA_NO_ENCONTRADA': (404, 'No se encontró la consulta seleccionada.'),
    'CONSULTA_NO_ACTIVA': (409, 'La consulta ya no está activa (debe estar programada o en proceso).'),
    'DIAGNOSTICO_INVALIDO': (400, 'El diagnóstico seleccionado no pertenece a esta consulta.'),
    'TRATAMIENTO_INVALIDO': (400, 'El tratamiento seleccionado no pertenece a esta consulta.'),
    'ERROR_INTERNO': (500, 'Ocurrió un error interno. Consulte con el administrador.'),
}


# =====================================================
# ENDPOINT: OBTENER TODAS LAS ÓRDENES DE ANÁLISIS
# =====================================================
@ordenanalisisapi.route('/orden-analisis', methods=['GET'])
@require_permiso('ordenanalisis', 'ver')
def getOrdenes():
    dao = OrdenAnalisisDao()
    try:
        ordenes = dao.getOrdenes()
        return jsonify({'success': True, 'data': ordenes, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener órdenes de análisis: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: OBTENER UNA ORDEN DE ANÁLISIS POR ID
# =====================================================
@ordenanalisisapi.route('/orden-analisis/<int:id_orden_analisis>', methods=['GET'])
@require_permiso('ordenanalisis', 'ver')
def getOrden(id_orden_analisis):
    dao = OrdenAnalisisDao()
    try:
        orden = dao.getOrdenById(id_orden_analisis)
        if orden:
            return jsonify({'success': True, 'data': orden, 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró la orden de análisis con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener orden de análisis: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: REGISTRAR NUEVA ORDEN DE ANÁLISIS
# =====================================================
@ordenanalisisapi.route('/orden-analisis', methods=['POST'])
@require_permiso('ordenanalisis', 'nuevo')
def addOrden():
    """
    Registra una nueva orden de análisis, a partir de una Consulta activa.
    id_diagnostico e id_tratamiento son opcionales.

    Body JSON:
    {
        "id_consulta_cab": 5,
        "id_diagnostico": 3,          (opcional)
        "id_tratamiento": 2,          (opcional)
        "id_tipo_analisis": 1,
        "motivo_orden": "...",
        "indicaciones": "...",        (opcional)
        "fecha_orden": "2026-09-12"   (opcional, hoy por defecto)
    }
    """
    data = request.get_json()
    dao = OrdenAnalisisDao()

    if not data or not data.get('id_consulta_cab'):
        return jsonify({'success': False, 'error': 'El campo id_consulta_cab es obligatorio: la orden debe partir de una Consulta activa.'}), 400
    if not data.get('id_tipo_analisis'):
        return jsonify({'success': False, 'error': 'El campo Tipo de Análisis es obligatorio.'}), 400
    if not data.get('motivo_orden') or not data['motivo_orden'].strip():
        return jsonify({'success': False, 'error': 'El campo Motivo de Orden es obligatorio y no puede estar vacío.'}), 400

    try:
        resultado = dao.guardarOrden(data)

        if 'id_orden_analisis' in resultado:
            return jsonify({
                'success': True,
                'data': {
                    'id_orden_analisis': resultado['id_orden_analisis'],
                    'mensaje': 'Orden de análisis registrada correctamente'
                },
                'error': None
            }), 201

        codigo, mensaje = ERRORES.get(resultado.get('error'), ERRORES['ERROR_INTERNO'])
        return jsonify({'success': False, 'error': mensaje}), codigo

    except Exception as e:
        app.logger.error(f"Error al registrar orden de análisis: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: ACTUALIZAR ESTADO (avanza al siguiente paso)
# =====================================================
@ordenanalisisapi.route('/orden-analisis/<int:id_orden_analisis>/estado', methods=['PUT'])
@require_permiso('ordenanalisis', 'estado')
def actualizarEstado(id_orden_analisis):
    """
    Avanza la orden al siguiente estado de la secuencia estricta
    pendiente -> enviado -> en_proceso -> completado. No recibe el estado
    en el body: el sistema calcula el siguiente paso.

    URL: PUT /api/v1/orden-analisis/5/estado
    """
    dao = OrdenAnalisisDao()
    try:
        resultado = dao.actualizarEstado(id_orden_analisis)

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
                'mensaje': f'Orden de análisis actualizada a "{resultado}".',
                'error': None
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró la orden de análisis con el ID proporcionado.'}), 404

    except Exception as e:
        app.logger.error(f"Error al actualizar estado de orden de análisis: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: ANULAR ORDEN DE ANÁLISIS
# =====================================================
@ordenanalisisapi.route('/orden-analisis/<int:id_orden_analisis>', methods=['DELETE'])
@require_permiso('ordenanalisis', 'anular')
def deleteOrden(id_orden_analisis):
    dao = OrdenAnalisisDao()
    try:
        registro = dao.getOrdenById(id_orden_analisis)
        resultado = dao.anularOrden(id_orden_analisis)

        if resultado == "YA_CERRADO":
            return jsonify({
                'success': False,
                'error': 'No se puede anular: la orden ya está completada o cancelada.'
            }), 409

        if resultado:
            descripcion = f"de {registro['tipo_analisis']} del {registro['fecha_orden']} de {registro['nombre_paciente']}" if registro else 'seleccionada'
            return jsonify({
                'success': True,
                'mensaje': f'Orden de análisis {descripcion} anulada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró la orden de análisis con el ID proporcionado.'}), 404

    except Exception as e:
        app.logger.error(f"Error al anular orden de análisis: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
