from flask import Blueprint, request, jsonify, current_app as app
import re
from app.dao.referenciales_consultorio.tipo_analisis.TipoAnalisisDao import TipoAnalisisDao

tipoanalisisapi = Blueprint('tipoanalisisapi', __name__)


# -------------------------
# Funciones auxiliares de validación
# -------------------------
def descripcion_valida(texto):
    # Permite letras (incluye ñ y acentos) y espacios
    patron = r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$'
    return re.match(patron, texto) is not None


# -------------------------
# Trae todos los tipos de análisis
# -------------------------
@tipoanalisisapi.route('/tipos-analisis', methods=['GET'])
def getTiposAnalisis():
    dao = TipoAnalisisDao()
    try:
        tipos = dao.getTiposAnalisis()
        return jsonify({'success': True, 'data': tipos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener tipos de análisis: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Trae un tipo de análisis por ID
# -------------------------
@tipoanalisisapi.route('/tipos-analisis/<int:id_tipo_analisis>', methods=['GET'])
def getTipoAnalisis(id_tipo_analisis):
    dao = TipoAnalisisDao()
    try:
        tipo = dao.getTipoAnalisisById(id_tipo_analisis)
        if tipo:
            return jsonify({'success': True, 'data': tipo, 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el tipo de análisis con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener tipo de análisis: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Agrega un nuevo tipo de análisis
# -------------------------
@tipoanalisisapi.route('/tipos-analisis', methods=['POST'])
def addTipoAnalisis():
    data = request.get_json()
    dao = TipoAnalisisDao()

    if not data or 'descripcion' not in data or not data['descripcion'].strip():
        return jsonify({'success': False, 'error': 'El campo descripción es obligatorio y no puede estar vacío.'}), 400

    descripcion = data['descripcion'].strip().upper()

    if not descripcion_valida(descripcion):
        return jsonify({'success': False, 'error': 'La descripción solo puede contener letras y espacios, sin números ni caracteres especiales.'}), 400

    try:
        if dao.existeDuplicado(descripcion):
            return jsonify({'success': False, 'error': 'Ya existe un tipo de análisis con esa descripción.'}), 400

        nuevo_id = dao.guardarTipoAnalisis(descripcion)
        if nuevo_id:
            return jsonify({
                'success': True,
                'data': {'id_tipo_analisis': nuevo_id, 'descripcion': descripcion},
                'error': None
            }), 201
        else:
            return jsonify({'success': False, 'error': 'No se pudo guardar el tipo de análisis. Consulte con el administrador.'}), 500
    except Exception as e:
        app.logger.error(f"Error al agregar tipo de análisis: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Actualiza un tipo de análisis
# -------------------------
@tipoanalisisapi.route('/tipos-analisis/<int:id_tipo_analisis>', methods=['PUT'])
def updateTipoAnalisis(id_tipo_analisis):
    data = request.get_json()
    dao = TipoAnalisisDao()

    if not data or 'descripcion' not in data or not data['descripcion'].strip():
        return jsonify({'success': False, 'error': 'El campo descripción es obligatorio y no puede estar vacío.'}), 400

    descripcion = data['descripcion'].strip().upper()

    if not descripcion_valida(descripcion):
        return jsonify({'success': False, 'error': 'La descripción solo puede contener letras y espacios, sin números ni caracteres especiales.'}), 400

    try:
        if dao.existeDuplicado(descripcion, excluir_id=id_tipo_analisis):
            return jsonify({'success': False, 'error': 'Ya existe otro tipo de análisis con esa descripción.'}), 400

        if dao.updateTipoAnalisis(id_tipo_analisis, descripcion):
            return jsonify({
                'success': True,
                'data': {'id_tipo_analisis': id_tipo_analisis, 'descripcion': descripcion},
                'error': None
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el tipo de análisis con el ID proporcionado o no se pudo actualizar.'}), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar tipo de análisis: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Elimina (baja lógica) un tipo de análisis
# -------------------------
@tipoanalisisapi.route('/tipos-analisis/<int:id_tipo_analisis>', methods=['DELETE'])
def deleteTipoAnalisis(id_tipo_analisis):
    dao = TipoAnalisisDao()
    try:
        resultado = dao.deleteTipoAnalisis(id_tipo_analisis)
        if resultado == "EN_USO":
            return jsonify({'success': False, 'error': 'No se puede eliminar: este tipo de análisis está en uso en una o más órdenes de análisis.'}), 409
        if resultado:
            return jsonify({'success': True, 'mensaje': f'Tipo de análisis con ID {id_tipo_analisis} eliminado correctamente.', 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el tipo de análisis con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar tipo de análisis: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
