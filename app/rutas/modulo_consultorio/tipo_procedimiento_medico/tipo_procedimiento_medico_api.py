from flask import Blueprint, request, jsonify, current_app as app
import re
from app.dao.referenciales_consultorio.tipo_procedimiento_medico.TipoProcedimientoMedicoDao import TipoProcedimientoMedicoDao

tipoprocedimientomedicoapi = Blueprint('tipoprocedimientomedicoapi', __name__)


# -------------------------
# Funciones auxiliares de validación
# -------------------------
def descripcion_valida(texto):
    # Permite letras (incluye ñ y acentos) y espacios
    patron = r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$'
    return re.match(patron, texto) is not None


# -------------------------
# Trae todos los tipos de procedimiento médico
# -------------------------
@tipoprocedimientomedicoapi.route('/tipos-procedimiento-medico', methods=['GET'])
def getTiposProcedimientoMedico():
    dao = TipoProcedimientoMedicoDao()
    try:
        tipos = dao.getTiposProcedimientoMedico()
        return jsonify({'success': True, 'data': tipos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener tipos de procedimiento médico: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Trae un tipo de procedimiento médico por ID
# -------------------------
@tipoprocedimientomedicoapi.route('/tipos-procedimiento-medico/<int:id_tipo_procedimiento>', methods=['GET'])
def getTipoProcedimientoMedico(id_tipo_procedimiento):
    dao = TipoProcedimientoMedicoDao()
    try:
        tipo = dao.getTipoProcedimientoMedicoById(id_tipo_procedimiento)
        if tipo:
            return jsonify({'success': True, 'data': tipo, 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el tipo de procedimiento médico con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener tipo de procedimiento médico: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Agrega un nuevo tipo de procedimiento médico
# -------------------------
@tipoprocedimientomedicoapi.route('/tipos-procedimiento-medico', methods=['POST'])
def addTipoProcedimientoMedico():
    data = request.get_json()
    dao = TipoProcedimientoMedicoDao()

    if not data or 'descripcion' not in data or not data['descripcion'].strip():
        return jsonify({'success': False, 'error': 'El campo descripción es obligatorio y no puede estar vacío.'}), 400

    descripcion = data['descripcion'].strip().upper()

    if not descripcion_valida(descripcion):
        return jsonify({'success': False, 'error': 'La descripción solo puede contener letras y espacios, sin números ni caracteres especiales.'}), 400

    try:
        if dao.existeDuplicado(descripcion):
            return jsonify({'success': False, 'error': 'Ya existe un tipo de procedimiento médico con esa descripción.'}), 400

        nuevo_id = dao.guardarTipoProcedimientoMedico(descripcion)
        if nuevo_id:
            return jsonify({
                'success': True,
                'data': {'id_tipo_procedimiento': nuevo_id, 'descripcion': descripcion},
                'error': None
            }), 201
        else:
            return jsonify({'success': False, 'error': 'No se pudo guardar el tipo de procedimiento médico. Consulte con el administrador.'}), 500
    except Exception as e:
        app.logger.error(f"Error al agregar tipo de procedimiento médico: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Actualiza un tipo de procedimiento médico
# -------------------------
@tipoprocedimientomedicoapi.route('/tipos-procedimiento-medico/<int:id_tipo_procedimiento>', methods=['PUT'])
def updateTipoProcedimientoMedico(id_tipo_procedimiento):
    data = request.get_json()
    dao = TipoProcedimientoMedicoDao()

    if not data or 'descripcion' not in data or not data['descripcion'].strip():
        return jsonify({'success': False, 'error': 'El campo descripción es obligatorio y no puede estar vacío.'}), 400

    descripcion = data['descripcion'].strip().upper()

    if not descripcion_valida(descripcion):
        return jsonify({'success': False, 'error': 'La descripción solo puede contener letras y espacios, sin números ni caracteres especiales.'}), 400

    try:
        if dao.existeDuplicado(descripcion, excluir_id=id_tipo_procedimiento):
            return jsonify({'success': False, 'error': 'Ya existe otro tipo de procedimiento médico con esa descripción.'}), 400

        if dao.updateTipoProcedimientoMedico(id_tipo_procedimiento, descripcion):
            return jsonify({
                'success': True,
                'data': {'id_tipo_procedimiento': id_tipo_procedimiento, 'descripcion': descripcion},
                'error': None
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el tipo de procedimiento médico con el ID proporcionado o no se pudo actualizar.'}), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar tipo de procedimiento médico: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Elimina (baja lógica) un tipo de procedimiento médico
# -------------------------
@tipoprocedimientomedicoapi.route('/tipos-procedimiento-medico/<int:id_tipo_procedimiento>', methods=['DELETE'])
def deleteTipoProcedimientoMedico(id_tipo_procedimiento):
    dao = TipoProcedimientoMedicoDao()
    try:
        resultado = dao.deleteTipoProcedimientoMedico(id_tipo_procedimiento)
        if resultado == "EN_USO":
            return jsonify({'success': False, 'error': 'No se puede eliminar: este tipo de procedimiento médico está en uso en uno o más detalles de consulta.'}), 409
        if resultado:
            return jsonify({'success': True, 'mensaje': f'Tipo de procedimiento médico con ID {id_tipo_procedimiento} eliminado correctamente.', 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el tipo de procedimiento médico con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar tipo de procedimiento médico: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
