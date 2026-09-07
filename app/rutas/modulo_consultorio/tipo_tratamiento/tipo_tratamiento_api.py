from flask import Blueprint, request, jsonify, current_app as app
import re
from app.dao.referenciales_consultorio.tipo_tratamiento.TipoTratamientoDao import TipoTratamientoDao

tipotratamientoapi = Blueprint('tipotratamientoapi', __name__)


# -------------------------
# Funciones auxiliares de validación
# -------------------------
def descripcion_valida(texto):
    # Permite letras (incluye ñ y acentos) y espacios
    patron = r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$'
    return re.match(patron, texto) is not None


def codigo_valido(texto):
    # Letras y números, sin espacios ni caracteres especiales, hasta 10 caracteres
    patron = r'^[A-Za-z0-9]{1,10}$'
    return re.match(patron, texto) is not None


# -------------------------
# Trae todos los tipos de tratamiento
# -------------------------
@tipotratamientoapi.route('/tipos-tratamiento', methods=['GET'])
def getTiposTratamiento():
    dao = TipoTratamientoDao()
    try:
        tipos = dao.getTiposTratamiento()
        return jsonify({'success': True, 'data': tipos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener tipos de tratamiento: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Trae un tipo de tratamiento por ID
# -------------------------
@tipotratamientoapi.route('/tipos-tratamiento/<int:id_tipo_tratamiento>', methods=['GET'])
def getTipoTratamiento(id_tipo_tratamiento):
    dao = TipoTratamientoDao()
    try:
        tipo = dao.getTipoTratamientoById(id_tipo_tratamiento)
        if tipo:
            return jsonify({'success': True, 'data': tipo, 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el tipo de tratamiento con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener tipo de tratamiento: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Agrega un nuevo tipo de tratamiento
# -------------------------
@tipotratamientoapi.route('/tipos-tratamiento', methods=['POST'])
def addTipoTratamiento():
    data = request.get_json()
    dao = TipoTratamientoDao()

    if not data or 'codigo' not in data or not data['codigo'].strip():
        return jsonify({'success': False, 'error': 'El campo código es obligatorio y no puede estar vacío.'}), 400
    if 'descripcion' not in data or not data['descripcion'].strip():
        return jsonify({'success': False, 'error': 'El campo descripción es obligatorio y no puede estar vacío.'}), 400

    codigo = data['codigo'].strip().upper()
    descripcion = data['descripcion'].strip().upper()

    if not codigo_valido(codigo):
        return jsonify({'success': False, 'error': 'El código solo puede contener letras y números, sin espacios, hasta 10 caracteres.'}), 400
    if not descripcion_valida(descripcion):
        return jsonify({'success': False, 'error': 'La descripción solo puede contener letras y espacios, sin números ni caracteres especiales.'}), 400

    try:
        if dao.existeDuplicado(descripcion, codigo):
            return jsonify({'success': False, 'error': 'Ya existe un tipo de tratamiento con ese código o descripción.'}), 400

        nuevo_id = dao.guardarTipoTratamiento(codigo, descripcion)
        if nuevo_id:
            return jsonify({
                'success': True,
                'data': {'id_tipo_tratamiento': nuevo_id, 'codigo': codigo, 'descripcion': descripcion},
                'error': None
            }), 201
        else:
            return jsonify({'success': False, 'error': 'No se pudo guardar el tipo de tratamiento. Consulte con el administrador.'}), 500
    except Exception as e:
        app.logger.error(f"Error al agregar tipo de tratamiento: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Actualiza un tipo de tratamiento
# -------------------------
@tipotratamientoapi.route('/tipos-tratamiento/<int:id_tipo_tratamiento>', methods=['PUT'])
def updateTipoTratamiento(id_tipo_tratamiento):
    data = request.get_json()
    dao = TipoTratamientoDao()

    if not data or 'codigo' not in data or not data['codigo'].strip():
        return jsonify({'success': False, 'error': 'El campo código es obligatorio y no puede estar vacío.'}), 400
    if 'descripcion' not in data or not data['descripcion'].strip():
        return jsonify({'success': False, 'error': 'El campo descripción es obligatorio y no puede estar vacío.'}), 400

    codigo = data['codigo'].strip().upper()
    descripcion = data['descripcion'].strip().upper()

    if not codigo_valido(codigo):
        return jsonify({'success': False, 'error': 'El código solo puede contener letras y números, sin espacios, hasta 10 caracteres.'}), 400
    if not descripcion_valida(descripcion):
        return jsonify({'success': False, 'error': 'La descripción solo puede contener letras y espacios, sin números ni caracteres especiales.'}), 400

    try:
        if dao.existeDuplicado(descripcion, codigo, excluir_id=id_tipo_tratamiento):
            return jsonify({'success': False, 'error': 'Ya existe otro tipo de tratamiento con ese código o descripción.'}), 400

        if dao.updateTipoTratamiento(id_tipo_tratamiento, codigo, descripcion):
            return jsonify({
                'success': True,
                'data': {'id_tipo_tratamiento': id_tipo_tratamiento, 'codigo': codigo, 'descripcion': descripcion},
                'error': None
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el tipo de tratamiento con el ID proporcionado o no se pudo actualizar.'}), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar tipo de tratamiento: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Elimina (baja lógica) un tipo de tratamiento
# -------------------------
@tipotratamientoapi.route('/tipos-tratamiento/<int:id_tipo_tratamiento>', methods=['DELETE'])
def deleteTipoTratamiento(id_tipo_tratamiento):
    dao = TipoTratamientoDao()
    try:
        resultado = dao.deleteTipoTratamiento(id_tipo_tratamiento)
        if resultado == "EN_USO":
            return jsonify({'success': False, 'error': 'No se puede eliminar: este tipo de tratamiento está en uso en uno o más tratamientos registrados.'}), 409
        if resultado:
            return jsonify({'success': True, 'mensaje': f'Tipo de tratamiento con ID {id_tipo_tratamiento} eliminado correctamente.', 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el tipo de tratamiento con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar tipo de tratamiento: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
