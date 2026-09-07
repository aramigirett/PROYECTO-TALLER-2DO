from flask import Blueprint, request, jsonify, current_app as app
import re
from app.dao.referenciales_consultorio.tipo_estudio.TipoEstudioDao import TipoEstudioDao

tipoestudioapi = Blueprint('tipoestudioapi', __name__)


# -------------------------
# Funciones auxiliares de validación
# -------------------------
def descripcion_valida(texto):
    # Permite letras (incluye ñ y acentos) y espacios
    patron = r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$'
    return re.match(patron, texto) is not None


# -------------------------
# Trae todos los tipos de estudio
# -------------------------
@tipoestudioapi.route('/tipos-estudio', methods=['GET'])
def getTiposEstudio():
    dao = TipoEstudioDao()
    try:
        tipos = dao.getTiposEstudio()
        return jsonify({'success': True, 'data': tipos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener tipos de estudio: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Trae un tipo de estudio por ID
# -------------------------
@tipoestudioapi.route('/tipos-estudio/<int:id_tipo_estudio>', methods=['GET'])
def getTipoEstudio(id_tipo_estudio):
    dao = TipoEstudioDao()
    try:
        tipo = dao.getTipoEstudioById(id_tipo_estudio)
        if tipo:
            return jsonify({'success': True, 'data': tipo, 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el tipo de estudio con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener tipo de estudio: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Agrega un nuevo tipo de estudio
# -------------------------
@tipoestudioapi.route('/tipos-estudio', methods=['POST'])
def addTipoEstudio():
    data = request.get_json()
    dao = TipoEstudioDao()

    if not data or 'descripcion' not in data or not data['descripcion'].strip():
        return jsonify({'success': False, 'error': 'El campo descripción es obligatorio y no puede estar vacío.'}), 400

    descripcion = data['descripcion'].strip().upper()

    if not descripcion_valida(descripcion):
        return jsonify({'success': False, 'error': 'La descripción solo puede contener letras y espacios, sin números ni caracteres especiales.'}), 400

    try:
        if dao.existeDuplicado(descripcion):
            return jsonify({'success': False, 'error': 'Ya existe un tipo de estudio con esa descripción.'}), 400

        nuevo_id = dao.guardarTipoEstudio(descripcion)
        if nuevo_id:
            return jsonify({
                'success': True,
                'data': {'id_tipo_estudio': nuevo_id, 'descripcion': descripcion},
                'error': None
            }), 201
        else:
            return jsonify({'success': False, 'error': 'No se pudo guardar el tipo de estudio. Consulte con el administrador.'}), 500
    except Exception as e:
        app.logger.error(f"Error al agregar tipo de estudio: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Actualiza un tipo de estudio
# -------------------------
@tipoestudioapi.route('/tipos-estudio/<int:id_tipo_estudio>', methods=['PUT'])
def updateTipoEstudio(id_tipo_estudio):
    data = request.get_json()
    dao = TipoEstudioDao()

    if not data or 'descripcion' not in data or not data['descripcion'].strip():
        return jsonify({'success': False, 'error': 'El campo descripción es obligatorio y no puede estar vacío.'}), 400

    descripcion = data['descripcion'].strip().upper()

    if not descripcion_valida(descripcion):
        return jsonify({'success': False, 'error': 'La descripción solo puede contener letras y espacios, sin números ni caracteres especiales.'}), 400

    try:
        if dao.existeDuplicado(descripcion, excluir_id=id_tipo_estudio):
            return jsonify({'success': False, 'error': 'Ya existe otro tipo de estudio con esa descripción.'}), 400

        if dao.updateTipoEstudio(id_tipo_estudio, descripcion):
            return jsonify({
                'success': True,
                'data': {'id_tipo_estudio': id_tipo_estudio, 'descripcion': descripcion},
                'error': None
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el tipo de estudio con el ID proporcionado o no se pudo actualizar.'}), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar tipo de estudio: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Elimina (baja lógica) un tipo de estudio
# -------------------------
@tipoestudioapi.route('/tipos-estudio/<int:id_tipo_estudio>', methods=['DELETE'])
def deleteTipoEstudio(id_tipo_estudio):
    dao = TipoEstudioDao()
    try:
        resultado = dao.deleteTipoEstudio(id_tipo_estudio)
        if resultado == "EN_USO":
            return jsonify({'success': False, 'error': 'No se puede eliminar: este tipo de estudio está en uso en una o más órdenes de estudio.'}), 409
        if resultado:
            return jsonify({'success': True, 'mensaje': f'Tipo de estudio con ID {id_tipo_estudio} eliminado correctamente.', 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el tipo de estudio con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar tipo de estudio: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
