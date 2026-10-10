"""
=====================================================
API: Receta (Generar Recetas e Indicaciones)
Descripción: Endpoints REST para recetas médicas de una Consulta
=====================================================
"""

from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_consultorio.receta.RecetaDao import RecetaDao
from app.rutas.modulo_seguridad.decorators import require_permiso

recetaapi = Blueprint('recetaapi', __name__)

ERRORES = {
    'CONSULTA_NO_ENCONTRADA': (404, 'No se encontró la consulta seleccionada.'),
    'CONSULTA_NO_ACTIVA': (409, 'La consulta ya no está activa (debe estar programada o en proceso).'),
    'DIAGNOSTICO_INVALIDO': (400, 'El diagnóstico seleccionado no pertenece a esta consulta.'),
    'TRATAMIENTO_INVALIDO': (400, 'El tratamiento seleccionado no pertenece a esta consulta.'),
    'SIN_MEDICAMENTOS': (400, 'Debe registrar al menos un medicamento.'),
    'ERROR_INTERNO': (500, 'Ocurrió un error interno. Consulte con el administrador.'),
}


# =====================================================
# ENDPOINT: OBTENER TODAS LAS RECETAS
# =====================================================
@recetaapi.route('/recetas', methods=['GET'])
@require_permiso('receta', 'ver')
def getRecetas():
    dao = RecetaDao()
    try:
        recetas = dao.getRecetas()
        return jsonify({'success': True, 'data': recetas, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener recetas: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: OBTENER UNA RECETA POR ID
# =====================================================
@recetaapi.route('/recetas/<int:id_receta>', methods=['GET'])
@require_permiso('receta', 'ver')
def getReceta(id_receta):
    dao = RecetaDao()
    try:
        receta = dao.getRecetaById(id_receta)
        if receta:
            return jsonify({'success': True, 'data': receta, 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró la receta con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener receta: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: REGISTRAR NUEVA RECETA
# =====================================================
@recetaapi.route('/recetas', methods=['POST'])
@require_permiso('receta', 'nuevo')
def addReceta():
    """
    Registra una nueva receta con sus medicamentos, a partir de una
    Consulta activa. id_diagnostico e id_tratamiento son opcionales.

    Body JSON:
    {
        "id_consulta_cab": 5,
        "id_diagnostico": 3,          (opcional)
        "id_tratamiento": 2,          (opcional)
        "indicaciones_generales": "...",
        "fecha_receta": "2026-09-12", (opcional, hoy por defecto)
        "medicamentos": [{"id_medicamento": 1, "dosis": "500mg", "frecuencia": "c/8hs", "duracion": "7 días"}, ...]
    }
    """
    data = request.get_json()
    dao = RecetaDao()

    if not data or not data.get('id_consulta_cab'):
        return jsonify({'success': False, 'error': 'El campo id_consulta_cab es obligatorio: la receta debe partir de una Consulta activa.'}), 400
    if not data.get('indicaciones_generales') or not data['indicaciones_generales'].strip():
        return jsonify({'success': False, 'error': 'El campo Indicaciones Generales es obligatorio y no puede estar vacío.'}), 400
    medicamentos = data.get('medicamentos') or []
    if not medicamentos:
        return jsonify({'success': False, 'error': 'Debe registrar al menos un medicamento.'}), 400
    for med in medicamentos:
        if not med.get('id_medicamento') or not med.get('dosis') or not med.get('frecuencia') or not med.get('duracion'):
            return jsonify({'success': False, 'error': 'Cada medicamento debe tener Medicamento, Dosis, Frecuencia y Duración.'}), 400

    try:
        resultado = dao.guardarReceta(data)

        if 'id_receta' in resultado:
            return jsonify({
                'success': True,
                'data': {
                    'id_receta': resultado['id_receta'],
                    'mensaje': 'Receta registrada correctamente'
                },
                'error': None
            }), 201

        codigo, mensaje = ERRORES.get(resultado.get('error'), ERRORES['ERROR_INTERNO'])
        return jsonify({'success': False, 'error': mensaje}), codigo

    except Exception as e:
        app.logger.error(f"Error al registrar receta: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# =====================================================
# ENDPOINT: ANULAR RECETA (baja lógica)
# =====================================================
@recetaapi.route('/recetas/<int:id_receta>', methods=['DELETE'])
@require_permiso('receta', 'anular')
def deleteReceta(id_receta):
    dao = RecetaDao()
    try:
        registro = dao.getRecetaById(id_receta)
        resultado = dao.deleteReceta(id_receta)

        if resultado == "CONSULTA_FINALIZADA":
            return jsonify({
                'success': False,
                'error': 'No se puede anular: la consulta asociada ya está finalizada.'
            }), 409

        if resultado:
            descripcion = f"del {registro['fecha_receta']} de {registro['nombre_paciente']}" if registro else 'seleccionada'
            return jsonify({
                'success': True,
                'mensaje': f'Receta {descripcion} anulada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró la receta con el ID proporcionado, o ya estaba anulada.'}), 404

    except Exception as e:
        app.logger.error(f"Error al anular receta: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
