from flask import Blueprint, request, jsonify, current_app as app
import re
from app.dao.referenciales.cargo.CargoDao import CargoDao

cargoapi = Blueprint('cargoapi', __name__)

# -------------------------
# Función auxiliar para validar descripción
# -------------------------
def validar_ciudad(nombre):
    # Permite letras (incluye ñ y acentos) y espacios
    patron = r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$'
    return re.match(patron, nombre) is not None


# -------------------------
# Trae todos los cargos
# -------------------------
@cargoapi.route('/cargos', methods=['GET'])
def getCargos():
    cargodao = CargoDao()
    try:
        cargos = cargodao.getCargos()
        return jsonify({
            'success': True,
            'data': cargos,
            'error': None
        }), 200
    except Exception as e:
        app.logger.error(f"Error al obtener todos los cargos: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# -------------------------
# Trae un cargo por ID
# -------------------------
@cargoapi.route('/cargos/<int:cargo_id>', methods=['GET'])
def getCargo(cargo_id):
    cargodao = CargoDao()
    try:
        cargo = cargodao.getCargoById(cargo_id)
        if cargo:
            return jsonify({'success': True, 'data': cargo, 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el cargo con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener cargo: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Agrega un nuevo cargo
# -------------------------
@cargoapi.route('/cargos', methods=['POST'])
def addCargo():
    data = request.get_json()
    cargodao = CargoDao()

    # Validación de campos
    if 'descripcion' not in data or not data['descripcion'].strip():
        return jsonify({'success': False, 'error': 'El campo descripcion es obligatorio y no puede estar vacío.'}), 400

    descripcion = data['descripcion'].strip().upper()

    # ✅ Validar caracteres permitidos
    if not validar_ciudad(descripcion):
        return jsonify({'success': False, 'error': 'La descripción solo puede contener letras y espacios, sin números ni caracteres especiales.'}), 400

    try:
        # Verificar duplicado
        if cargodao.existeDuplicado(descripcion):
            return jsonify({'success': False, 'error': 'El cargo ya existe.'}), 400

        cargo_id = cargodao.guardarCargo(descripcion)
        if cargo_id:
            return jsonify({'success': True, 'data': {'id_cargo': cargo_id, 'descripcion': descripcion}, 'error': None}), 201
        else:
            return jsonify({'success': False, 'error': 'No se pudo guardar el cargo. Consulte con el administrador.'}), 500
    except Exception as e:
        app.logger.error(f"Error al agregar cargo: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Actualiza un cargo
# -------------------------
@cargoapi.route('/cargos/<int:cargo_id>', methods=['PUT'])
def updateCargo(cargo_id):
    data = request.get_json()
    cargodao = CargoDao()

    if 'descripcion' not in data or not data['descripcion'].strip():
        return jsonify({'success': False, 'error': 'El campo descripcion es obligatorio y no puede estar vacío.'}), 400

    descripcion = data['descripcion'].strip().upper()

    # ✅ Validar caracteres permitidos
    if not validar_ciudad(descripcion):
        return jsonify({'success': False, 'error': 'La descripción solo puede contener letras y espacios, sin números ni caracteres especiales.'}), 400

    try:
        # Verificar duplicado antes de actualizar
        if cargodao.existeDuplicado(descripcion):
            return jsonify({'success': False, 'error': 'El cargo ya existe.'}), 400

        if cargodao.updateCargo(cargo_id, descripcion):
            return jsonify({'success': True, 'data': {'id_cargo': cargo_id, 'descripcion': descripcion}, 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el cargo con el ID proporcionado o no se pudo actualizar.'}), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar cargo: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Elimina un cargo
# -------------------------
@cargoapi.route('/cargos/<int:cargo_id>', methods=['DELETE'])
def deleteCargo(cargo_id):
    cargodao = CargoDao()
    try:
        if cargodao.deleteCargo(cargo_id):
            return jsonify({'success': True, 'mensaje': f'Cargo con ID {cargo_id} eliminado correctamente.', 'error': None}), 200
        else:
            return jsonify({'success': False, 'error': 'No se encontró el cargo con el ID proporcionado o no se pudo eliminar.'}), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar cargo: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500