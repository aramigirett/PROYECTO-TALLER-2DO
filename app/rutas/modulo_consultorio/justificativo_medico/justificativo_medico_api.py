"""
=====================================================
API: Justificativo Médico (Generar Justificativo Médico)
Descripción: Endpoints REST para justificativos médicos de una Consulta
=====================================================
"""

from flask import Blueprint, request, jsonify, current_app as app, Response
from app.dao.referenciales_consultorio.justificativo_medico.JustificativoMedicoDao import JustificativoMedicoDao
from app.Services.justificativo_pdf_service import generarJustificativoPdf

justificativomedicoapi = Blueprint('justificativomedicoapi', __name__)

ERRORES = {
    'CONSULTA_NO_ENCONTRADA': (404, 'No se encontró la consulta seleccionada.'),
    'CONSULTA_NO_ACTIVA': (409, 'La consulta ya no está activa (debe estar programada o en proceso).'),
    'DIAGNOSTICO_INVALIDO': (400, 'El diagnóstico seleccionado no pertenece a esta consulta.'),
    'ERROR_INTERNO': (500, 'Ocurrió un error interno. Consulte con el administrador.'),
}


# =====================================================
# ENDPOINT: OBTENER TODOS LOS JUSTIFICATIVOS
# =====================================================
@justificativomedicoapi.route('/justificativos', methods=['GET'])
def getJustificativos():
    dao = JustificativoMedicoDao()
    try:
        justificativos = dao.getJustificativos()
        return jsonify({'success': True, 'data': justificativos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener justificativos médicos: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: OBTENER UN JUSTIFICATIVO POR ID
# =====================================================
@justificativomedicoapi.route('/justificativos/<int:id_justificativo>', methods=['GET'])
def getJustificativo(id_justificativo):
    dao = JustificativoMedicoDao()
    try:
        justificativo = dao.getJustificativoById(id_justificativo)
        if justificativo:
            return jsonify({'success': True, 'data': justificativo, 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el justificativo con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener justificativo médico: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: REGISTRAR NUEVO JUSTIFICATIVO
# =====================================================
@justificativomedicoapi.route('/justificativos', methods=['POST'])
def addJustificativo():
    """
    Registra un nuevo justificativo médico, a partir de una Consulta activa.
    id_diagnostico es opcional (NO hay vínculo a Tratamiento en este movimiento).

    Body JSON:
    {
        "id_consulta_cab": 5,
        "id_diagnostico": 3,             (opcional)
        "dias_reposo": 3,
        "recomendaciones": "...",        (opcional)
        "fecha_justificativo": "2026-09-12"  (opcional, hoy por defecto)
    }
    """
    data = request.get_json()
    dao = JustificativoMedicoDao()

    if not data or not data.get('id_consulta_cab'):
        return jsonify({'success': False, 'error': 'El campo id_consulta_cab es obligatorio: el justificativo debe partir de una Consulta activa.'}), 400
    dias_reposo = data.get('dias_reposo')
    if not dias_reposo or not isinstance(dias_reposo, int) or dias_reposo <= 0:
        return jsonify({'success': False, 'error': 'El campo Días de Reposo es obligatorio y debe ser mayor a cero.'}), 400

    try:
        resultado = dao.guardarJustificativo(data)

        if 'id_justificativo' in resultado:
            return jsonify({
                'success': True,
                'data': {
                    'id_justificativo': resultado['id_justificativo'],
                    'mensaje': 'Justificativo médico registrado correctamente'
                },
                'error': None
            }), 201

        codigo, mensaje = ERRORES.get(resultado.get('error'), ERRORES['ERROR_INTERNO'])
        return jsonify({'success': False, 'error': mensaje}), codigo

    except Exception as e:
        app.logger.error(f"Error al registrar justificativo médico: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: ANULAR JUSTIFICATIVO
# =====================================================
@justificativomedicoapi.route('/justificativos/<int:id_justificativo>', methods=['DELETE'])
def deleteJustificativo(id_justificativo):
    dao = JustificativoMedicoDao()
    try:
        registro = dao.getJustificativoById(id_justificativo)
        resultado = dao.anularJustificativo(id_justificativo)

        if resultado == "YA_ANULADO":
            return jsonify({
                'success': False,
                'error': 'Este justificativo ya está anulado.'
            }), 409

        if resultado:
            descripcion = f"del {registro['fecha_justificativo']} de {registro['nombre_paciente']}" if registro else 'seleccionado'
            return jsonify({
                'success': True,
                'mensaje': f'Justificativo médico {descripcion} anulado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el justificativo con el ID proporcionado.'}), 404

    except Exception as e:
        app.logger.error(f"Error al anular justificativo médico: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: DESCARGAR PDF DEL JUSTIFICATIVO
# =====================================================
@justificativomedicoapi.route('/justificativos/<int:id_justificativo>/pdf', methods=['GET'])
def descargarPdf(id_justificativo):
    """
    Genera y devuelve el PDF del justificativo al vuelo (no se guarda en
    el servidor). Si el justificativo está anulado, el PDF lo marca
    visiblemente en vez de bloquear la descarga.

    URL: GET /api/v1/justificativos/5/pdf
    """
    dao = JustificativoMedicoDao()
    try:
        justificativo = dao.getJustificativoById(id_justificativo)
        if not justificativo:
            return jsonify({'success': False, 'error': 'No se encontró el justificativo con el ID proporcionado.'}), 404

        pdf_bytes = generarJustificativoPdf(justificativo)

        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'inline; filename=justificativo_{id_justificativo}.pdf'}
        )

    except Exception as e:
        app.logger.error(f"Error al generar PDF de justificativo médico: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
