from flask import Blueprint, request, jsonify, current_app as app
from app.dao.modulo_facturacion.marca_tarjeta.MarcaTarjetaDao import MarcaTarjetaDao
from app.rutas.modulo_facturacion.utils import normalizar_descripcion, auditar as _auditar, error_interno
from app.rutas.modulo_seguridad.decorators import require_permiso, require_login

marcatarjetaapi = Blueprint('marcatarjetaapi', __name__)

ENTIDAD = 'marca_tarjeta'


def auditar(id_registro, accion, detalle):
    _auditar(ENTIDAD, id_registro, accion, detalle)


# -------------------------
# Trae todas las marcas de tarjeta activas
# -------------------------
@marcatarjetaapi.route('/marcas-tarjeta', methods=['GET'])
@require_login  # lookup: alimenta combos de otras pantallas (ej. Cobros)
def getMarcasTarjeta():
    try:
        return jsonify({'success': True, 'data': MarcaTarjetaDao().getMarcasTarjeta(), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener marcas de tarjeta: {str(e)}")
        return error_interno()


# -------------------------
# Trae una marca de tarjeta por ID
# -------------------------
@marcatarjetaapi.route('/marcas-tarjeta/<int:id_marca_tarjeta>', methods=['GET'])
@require_permiso('marcatarjeta', 'ver')
def getMarcaTarjeta(id_marca_tarjeta):
    try:
        marca = MarcaTarjetaDao().getMarcaTarjetaById(id_marca_tarjeta)
        if marca:
            return jsonify({'success': True, 'data': marca, 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se encontró la marca de tarjeta con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener marca de tarjeta: {str(e)}")
        return error_interno()


# -------------------------
# Agrega una marca de tarjeta
# -------------------------
@marcatarjetaapi.route('/marcas-tarjeta', methods=['POST'])
@require_permiso('marcatarjeta', 'nuevo')
def addMarcaTarjeta():
    descripcion, error = normalizar_descripcion(request.get_json(silent=True))
    if error:
        return jsonify({'success': False, 'error': error}), 400

    dao = MarcaTarjetaDao()
    try:
        if dao.existeDuplicado(descripcion):
            return jsonify({'success': False, 'error': 'La descripción ya existe.'}), 400

        nuevo_id = dao.guardarMarcaTarjeta(descripcion)
        if nuevo_id == "DUPLICADO":
            return jsonify({'success': False, 'error': 'La descripción ya existe.'}), 400
        if nuevo_id:
            auditar(nuevo_id, 'ALTA', f'Descripción: {descripcion}')
            return jsonify({
                'success': True,
                'data': {'id_marca_tarjeta': nuevo_id, 'descripcion': descripcion},
                'mensaje': f'Marca de tarjeta "{descripcion}" agregada correctamente.',
                'error': None
            }), 201
        return jsonify({'success': False, 'error': 'No se pudo guardar la marca de tarjeta. Consulte con el administrador.'}), 500
    except Exception as e:
        app.logger.error(f"Error al agregar marca de tarjeta: {str(e)}")
        return error_interno()


# -------------------------
# Actualiza una marca de tarjeta
# -------------------------
@marcatarjetaapi.route('/marcas-tarjeta/<int:id_marca_tarjeta>', methods=['PUT'])
@require_permiso('marcatarjeta', 'editar')
def updateMarcaTarjeta(id_marca_tarjeta):
    descripcion, error = normalizar_descripcion(request.get_json(silent=True))
    if error:
        return jsonify({'success': False, 'error': error}), 400

    dao = MarcaTarjetaDao()
    try:
        anterior = dao.getMarcaTarjetaById(id_marca_tarjeta)
        if not anterior:
            return jsonify({'success': False, 'error': 'No se encontró la marca de tarjeta con el ID proporcionado.'}), 404

        if anterior['descripcion'] == descripcion:
            # Sin cambios: no se toca la BD ni se audita.
            return jsonify({
                'success': True,
                'data': {'id_marca_tarjeta': id_marca_tarjeta, 'descripcion': descripcion},
                'mensaje': f'Marca de tarjeta "{descripcion}" sin cambios.',
                'error': None
            }), 200

        if dao.existeDuplicado(descripcion, excluir_id=id_marca_tarjeta):
            return jsonify({'success': False, 'error': 'La descripción ya existe.'}), 400

        resultado = dao.updateMarcaTarjeta(id_marca_tarjeta, descripcion)
        if resultado == "DUPLICADO":
            return jsonify({'success': False, 'error': 'La descripción ya existe.'}), 400
        if resultado:
            auditar(id_marca_tarjeta, 'MODIFICACION', f'Descripción: {anterior["descripcion"]} -> {descripcion}')
            return jsonify({
                'success': True,
                'data': {'id_marca_tarjeta': id_marca_tarjeta, 'descripcion': descripcion},
                'mensaje': f'Marca de tarjeta "{descripcion}" actualizada correctamente.',
                'error': None
            }), 200
        return jsonify({'success': False, 'error': 'No se pudo actualizar la marca de tarjeta.'}), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar marca de tarjeta: {str(e)}")
        return error_interno()


# -------------------------
# Anula (baja lógica) una marca de tarjeta
# -------------------------
@marcatarjetaapi.route('/marcas-tarjeta/<int:id_marca_tarjeta>', methods=['DELETE'])
@require_permiso('marcatarjeta', 'anular')
def deleteMarcaTarjeta(id_marca_tarjeta):
    dao = MarcaTarjetaDao()
    try:
        registro = dao.getMarcaTarjetaById(id_marca_tarjeta)
        resultado = dao.deleteMarcaTarjeta(id_marca_tarjeta)
        if isinstance(resultado, tuple):  # ("EN_USO", motivo)
            return jsonify({'success': False, 'error': resultado[1]}), 409
        if resultado:
            descripcion = registro['descripcion'] if registro else 'seleccionada'
            auditar(id_marca_tarjeta, 'BAJA', f'Descripción: {descripcion}')
            return jsonify({'success': True, 'mensaje': f'Marca de tarjeta "{descripcion}" anulada correctamente.', 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se encontró la marca de tarjeta con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al anular marca de tarjeta: {str(e)}")
        return error_interno()
