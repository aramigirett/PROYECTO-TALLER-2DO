from flask import Blueprint, request, jsonify, current_app as app
import re
from app.dao.referenciales_consultorio.tipo_insumo.TipoInsumoDao import TipoInsumoDao

tipoinsumoapi = Blueprint('tipoinsumoapi', __name__)


# -------------------------
# Funciones auxiliares de validación
# -------------------------
def descripcion_valida(texto):
    # Permite letras (incluye ñ y acentos), números y espacios
    patron = r'^[A-Za-z0-9ÁÉÍÓÚáéíóúÑñ\s]+$'
    return re.match(patron, texto) is not None


def codigo_valido(texto):
    # Letras y números, sin espacios ni caracteres especiales, hasta 10 caracteres
    patron = r'^[A-Za-z0-9]{1,10}$'
    return re.match(patron, texto) is not None


# -------------------------
# Trae todos los tipos de insumo
# -------------------------
@tipoinsumoapi.route('/tipos-insumo', methods=['GET'])
def getTiposInsumo():
    dao = TipoInsumoDao()
    try:
        tipos = dao.getTiposInsumo()
        return jsonify({'success': True, 'data': tipos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener tipos de insumo: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Trae un tipo de insumo por ID
# -------------------------
@tipoinsumoapi.route('/tipos-insumo/<int:id_insumo>', methods=['GET'])
def getTipoInsumo(id_insumo):
    dao = TipoInsumoDao()
    try:
        tipo = dao.getTipoInsumoById(id_insumo)
        if tipo:
            return jsonify({'success': True, 'data': tipo, 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el tipo de insumo con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener tipo de insumo: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Agrega un nuevo tipo de insumo
# -------------------------
@tipoinsumoapi.route('/tipos-insumo', methods=['POST'])
def addTipoInsumo():
    data = request.get_json()
    dao = TipoInsumoDao()

    if not data or 'codigo' not in data or not data['codigo'].strip():
        return jsonify({'success': False, 'error': 'El campo código es obligatorio y no puede estar vacío.'}), 400
    if 'descripcion' not in data or not data['descripcion'].strip():
        return jsonify({'success': False, 'error': 'El campo descripción es obligatorio y no puede estar vacío.'}), 400

    codigo = data['codigo'].strip().upper()
    descripcion = data['descripcion'].strip().upper()
    presentacion = data.get('presentacion', '').strip().upper() or None

    if not codigo_valido(codigo):
        return jsonify({'success': False, 'error': 'El código solo puede contener letras y números, sin espacios, hasta 10 caracteres.'}), 400
    if not descripcion_valida(descripcion):
        return jsonify({'success': False, 'error': 'La descripción solo puede contener letras, números y espacios, sin caracteres especiales.'}), 400
    if presentacion and not descripcion_valida(presentacion):
        return jsonify({'success': False, 'error': 'La presentación solo puede contener letras, números y espacios, sin caracteres especiales.'}), 400

    try:
        if dao.existeDuplicado(descripcion, codigo):
            return jsonify({'success': False, 'error': 'Ya existe un tipo de insumo con ese código o descripción.'}), 400

        nuevo_id = dao.guardarTipoInsumo(codigo, descripcion, presentacion)
        if nuevo_id:
            return jsonify({
                'success': True,
                'data': {'id_insumo': nuevo_id, 'codigo': codigo, 'descripcion': descripcion, 'presentacion': presentacion},
                'error': None
            }), 201
        else:
            return jsonify({'success': False, 'error': 'No se pudo guardar el tipo de insumo. Consulte con el administrador.'}), 500
    except Exception as e:
        app.logger.error(f"Error al agregar tipo de insumo: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Actualiza un tipo de insumo
# -------------------------
@tipoinsumoapi.route('/tipos-insumo/<int:id_insumo>', methods=['PUT'])
def updateTipoInsumo(id_insumo):
    data = request.get_json()
    dao = TipoInsumoDao()

    if not data or 'codigo' not in data or not data['codigo'].strip():
        return jsonify({'success': False, 'error': 'El campo código es obligatorio y no puede estar vacío.'}), 400
    if 'descripcion' not in data or not data['descripcion'].strip():
        return jsonify({'success': False, 'error': 'El campo descripción es obligatorio y no puede estar vacío.'}), 400

    codigo = data['codigo'].strip().upper()
    descripcion = data['descripcion'].strip().upper()
    presentacion = data.get('presentacion', '').strip().upper() or None

    if not codigo_valido(codigo):
        return jsonify({'success': False, 'error': 'El código solo puede contener letras y números, sin espacios, hasta 10 caracteres.'}), 400
    if not descripcion_valida(descripcion):
        return jsonify({'success': False, 'error': 'La descripción solo puede contener letras, números y espacios, sin caracteres especiales.'}), 400
    if presentacion and not descripcion_valida(presentacion):
        return jsonify({'success': False, 'error': 'La presentación solo puede contener letras, números y espacios, sin caracteres especiales.'}), 400

    try:
        if dao.existeDuplicado(descripcion, codigo, excluir_id=id_insumo):
            return jsonify({'success': False, 'error': 'Ya existe otro tipo de insumo con ese código o descripción.'}), 400

        if dao.updateTipoInsumo(id_insumo, codigo, descripcion, presentacion):
            return jsonify({
                'success': True,
                'data': {'id_insumo': id_insumo, 'codigo': codigo, 'descripcion': descripcion, 'presentacion': presentacion},
                'error': None
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el tipo de insumo con el ID proporcionado o no se pudo actualizar.'}), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar tipo de insumo: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Elimina (baja lógica) un tipo de insumo
# -------------------------
@tipoinsumoapi.route('/tipos-insumo/<int:id_insumo>', methods=['DELETE'])
def deleteTipoInsumo(id_insumo):
    dao = TipoInsumoDao()
    try:
        resultado = dao.deleteTipoInsumo(id_insumo)
        if resultado:
            return jsonify({'success': True, 'mensaje': f'Tipo de insumo con ID {id_insumo} eliminado correctamente.', 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el tipo de insumo con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar tipo de insumo: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
