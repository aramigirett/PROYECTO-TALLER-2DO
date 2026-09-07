"""
=====================================================
API: Tratamiento (Gestionar Tratamientos)
Descripción: Endpoints REST para el movimiento clínico de tratamientos
=====================================================
"""

from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_consultorio.tratamiento.TratamientoDao import TratamientoDao

tratamientoapi = Blueprint('tratamientoapi', __name__)

ERRORES = {
    'CONSULTA_NO_ENCONTRADA': (404, 'No se encontró la consulta seleccionada.'),
    'CONSULTA_NO_ACTIVA': (409, 'La consulta ya no está activa (debe estar programada o en proceso).'),
    'DIAGNOSTICO_INVALIDO': (400, 'El diagnóstico seleccionado no pertenece a esta consulta.'),
    'ERROR_INTERNO': (500, 'Ocurrió un error interno. Consulte con el administrador.'),
}


# =====================================================
# ENDPOINT: OBTENER TODOS LOS TRATAMIENTOS
# =====================================================
@tratamientoapi.route('/tratamientos', methods=['GET'])
def getTratamientos():
    dao = TratamientoDao()
    try:
        tratamientos = dao.getTratamientos()
        return jsonify({'success': True, 'data': tratamientos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener tratamientos: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: OBTENER UN TRATAMIENTO POR ID
# =====================================================
@tratamientoapi.route('/tratamientos/<int:id_tratamiento>', methods=['GET'])
def getTratamiento(id_tratamiento):
    dao = TratamientoDao()
    try:
        tratamiento = dao.getTratamientoById(id_tratamiento)
        if tratamiento:
            return jsonify({'success': True, 'data': tratamiento, 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el tratamiento con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener tratamiento: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: REGISTRAR NUEVO TRATAMIENTO
# =====================================================
@tratamientoapi.route('/tratamientos', methods=['POST'])
def addTratamiento():
    """
    Registra un nuevo tratamiento a partir de una Consulta activa.
    Paciente/Médico/Consultorio se derivan de la consulta en el backend.

    Body JSON:
    {
        "id_consulta_cab": 5,
        "id_diagnostico": 3,           (opcional)
        "id_tipo_tratamiento": 2,
        "descripcion_tratamiento": "...",
        "fecha_tratamiento": "2026-09-10"
    }
    """
    data = request.get_json()
    dao = TratamientoDao()

    if not data or not data.get('id_consulta_cab'):
        return jsonify({'success': False, 'error': 'El campo id_consulta_cab es obligatorio: el tratamiento debe partir de una Consulta activa.'}), 400
    if not data.get('id_tipo_tratamiento'):
        return jsonify({'success': False, 'error': 'El campo Tipo de Tratamiento es obligatorio.'}), 400
    if not data.get('descripcion_tratamiento') or not data['descripcion_tratamiento'].strip():
        return jsonify({'success': False, 'error': 'El campo Descripción es obligatorio y no puede estar vacío.'}), 400
    if not data.get('fecha_tratamiento'):
        return jsonify({'success': False, 'error': 'El campo Fecha de Tratamiento es obligatorio.'}), 400

    try:
        resultado = dao.guardarTratamiento(data)

        if 'id_tratamiento' in resultado:
            return jsonify({
                'success': True,
                'data': {
                    'id_tratamiento': resultado['id_tratamiento'],
                    'mensaje': 'Tratamiento registrado correctamente'
                },
                'error': None
            }), 201

        codigo, mensaje = ERRORES.get(resultado.get('error'), ERRORES['ERROR_INTERNO'])
        return jsonify({'success': False, 'error': mensaje}), codigo

    except Exception as e:
        app.logger.error(f"Error al agregar tratamiento: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: ANULAR TRATAMIENTO (baja lógica)
# =====================================================
@tratamientoapi.route('/tratamientos/<int:id_tratamiento>', methods=['DELETE'])
def deleteTratamiento(id_tratamiento):
    dao = TratamientoDao()
    try:
        if dao.deleteTratamiento(id_tratamiento):
            return jsonify({
                'success': True,
                'mensaje': f'Tratamiento con ID {id_tratamiento} anulado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el tratamiento con el ID proporcionado, o ya estaba anulado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al anular tratamiento: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
