from flask import Blueprint, request, jsonify, current_app as app
import re
from app.dao.referenciales_consultorio.medicamento.MedicamentoDao import MedicamentoDao

medicamentoapi = Blueprint('medicamentoapi', __name__)


# -------------------------
# Funciones auxiliares de validación
# -------------------------
def nombre_valido(texto):
    # Permite letras (incluye ñ y acentos), números y espacios
    patron = r'^[A-Za-z0-9ÁÉÍÓÚáéíóúÑñ\s]+$'
    return re.match(patron, texto) is not None


def codigo_valido(texto):
    # Letras y números, sin espacios ni caracteres especiales, hasta 10 caracteres
    patron = r'^[A-Za-z0-9]{1,10}$'
    return re.match(patron, texto) is not None


# -------------------------
# Trae todos los medicamentos
# -------------------------
@medicamentoapi.route('/medicamentos', methods=['GET'])
def getMedicamentos():
    dao = MedicamentoDao()
    try:
        medicamentos = dao.getMedicamentos()
        return jsonify({'success': True, 'data': medicamentos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener medicamentos: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Trae un medicamento por ID
# -------------------------
@medicamentoapi.route('/medicamentos/<int:id_medicamento>', methods=['GET'])
def getMedicamento(id_medicamento):
    dao = MedicamentoDao()
    try:
        medicamento = dao.getMedicamentoById(id_medicamento)
        if medicamento:
            return jsonify({'success': True, 'data': medicamento, 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el medicamento con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener medicamento: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Agrega un nuevo medicamento
# -------------------------
@medicamentoapi.route('/medicamentos', methods=['POST'])
def addMedicamento():
    data = request.get_json()
    dao = MedicamentoDao()

    if not data or 'codigo' not in data or not data['codigo'].strip():
        return jsonify({'success': False, 'error': 'El campo código es obligatorio y no puede estar vacío.'}), 400
    if 'nombre_comercial' not in data or not data['nombre_comercial'].strip():
        return jsonify({'success': False, 'error': 'El campo nombre comercial es obligatorio y no puede estar vacío.'}), 400

    codigo = data['codigo'].strip().upper()
    nombre_comercial = data['nombre_comercial'].strip().upper()
    presentacion = data.get('presentacion', '').strip().upper() or None

    if not codigo_valido(codigo):
        return jsonify({'success': False, 'error': 'El código solo puede contener letras y números, sin espacios, hasta 10 caracteres.'}), 400
    if not nombre_valido(nombre_comercial):
        return jsonify({'success': False, 'error': 'El nombre comercial solo puede contener letras, números y espacios, sin caracteres especiales.'}), 400
    if presentacion and not nombre_valido(presentacion):
        return jsonify({'success': False, 'error': 'La presentación solo puede contener letras, números y espacios, sin caracteres especiales.'}), 400

    try:
        if dao.existeDuplicado(codigo):
            return jsonify({'success': False, 'error': 'Ya existe un medicamento con ese código.'}), 400

        nuevo_id = dao.guardarMedicamento(codigo, nombre_comercial, presentacion)
        if nuevo_id:
            return jsonify({
                'success': True,
                'data': {'id_medicamento': nuevo_id, 'codigo': codigo, 'nombre_comercial': nombre_comercial, 'presentacion': presentacion},
                'error': None
            }), 201
        else:
            return jsonify({'success': False, 'error': 'No se pudo guardar el medicamento. Consulte con el administrador.'}), 500
    except Exception as e:
        app.logger.error(f"Error al agregar medicamento: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Actualiza un medicamento
# -------------------------
@medicamentoapi.route('/medicamentos/<int:id_medicamento>', methods=['PUT'])
def updateMedicamento(id_medicamento):
    data = request.get_json()
    dao = MedicamentoDao()

    if not data or 'codigo' not in data or not data['codigo'].strip():
        return jsonify({'success': False, 'error': 'El campo código es obligatorio y no puede estar vacío.'}), 400
    if 'nombre_comercial' not in data or not data['nombre_comercial'].strip():
        return jsonify({'success': False, 'error': 'El campo nombre comercial es obligatorio y no puede estar vacío.'}), 400

    codigo = data['codigo'].strip().upper()
    nombre_comercial = data['nombre_comercial'].strip().upper()
    presentacion = data.get('presentacion', '').strip().upper() or None

    if not codigo_valido(codigo):
        return jsonify({'success': False, 'error': 'El código solo puede contener letras y números, sin espacios, hasta 10 caracteres.'}), 400
    if not nombre_valido(nombre_comercial):
        return jsonify({'success': False, 'error': 'El nombre comercial solo puede contener letras, números y espacios, sin caracteres especiales.'}), 400
    if presentacion and not nombre_valido(presentacion):
        return jsonify({'success': False, 'error': 'La presentación solo puede contener letras, números y espacios, sin caracteres especiales.'}), 400

    try:
        if dao.existeDuplicado(codigo, excluir_id=id_medicamento):
            return jsonify({'success': False, 'error': 'Ya existe otro medicamento con ese código.'}), 400

        if dao.updateMedicamento(id_medicamento, codigo, nombre_comercial, presentacion):
            return jsonify({
                'success': True,
                'data': {'id_medicamento': id_medicamento, 'codigo': codigo, 'nombre_comercial': nombre_comercial, 'presentacion': presentacion},
                'error': None
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el medicamento con el ID proporcionado o no se pudo actualizar.'}), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar medicamento: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Elimina (baja lógica) un medicamento
# -------------------------
@medicamentoapi.route('/medicamentos/<int:id_medicamento>', methods=['DELETE'])
def deleteMedicamento(id_medicamento):
    dao = MedicamentoDao()
    try:
        resultado = dao.deleteMedicamento(id_medicamento)
        if resultado == "EN_USO":
            return jsonify({'success': False, 'error': 'No se puede eliminar: este medicamento está en uso en una o más recetas.'}), 409
        if resultado:
            return jsonify({'success': True, 'mensaje': f'Medicamento con ID {id_medicamento} eliminado correctamente.', 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el medicamento con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar medicamento: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
