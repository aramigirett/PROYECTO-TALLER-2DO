from flask import Blueprint, request, jsonify, current_app as app
from app.rutas.modulo_seguridad.permisos_contexto import puede
from app.rutas.modulo_facturacion.utils import respuesta_error
from app.dao.modulo_facturacion.tipo_items.TipoItemDao import NO_EXISTE, YA_ACTIVO, DUPLICADO
from app.dao.modulo_facturacion.tipo_items.TipoItemDao import TipoItemDao
from app.rutas.modulo_facturacion.utils import (
    normalizar_descripcion, validar_booleano, detalle_cambios, respuesta_error,
    auditar as _auditar, error_interno)
from app.rutas.modulo_seguridad.decorators import require_permiso, require_login

tipoitemapi = Blueprint('tipoitemapi', __name__)

ENTIDAD = 'tipo_items'
ETIQUETAS = {'descripcion': 'Descripción', 'controla_stock': 'Controla stock'}
MSG_DUPLICADO = 'La descripción ya existe.'


def auditar(id_registro, accion, detalle):
    _auditar(ENTIDAD, id_registro, accion, detalle)


def validar_tipo_item(data):
    """Devuelve (datos, error, campo)."""
    data = data if isinstance(data, dict) else {}
    descripcion, error = normalizar_descripcion(data)
    if error:
        return None, error, 'descripcion'
    controla_stock, error = validar_booleano(data.get('controla_stock'), 'Controla stock')
    if error:
        return None, error, 'controla_stock'
    return {'descripcion': descripcion, 'controla_stock': controla_stock}, None, None


def _para_detalle(d):
    """Valores legibles para la auditoría (Sí/No en vez de True/False)."""
    return {'descripcion': d.get('descripcion'), 'controla_stock': 'Sí' if d.get('controla_stock') else 'No'}


# -------------------------
# Trae todos los tipos de ítem activos
# -------------------------
@tipoitemapi.route('/tipos-item', methods=['GET'])
@require_login  # lookup: alimenta combos de otras pantallas (Ítems)
def getTiposItem():
    incluir_inactivos = request.args.get('inactivos', '').lower() in ('1', 'true')
    if incluir_inactivos and not puede('tipoitem', 'ver'):
        return respuesta_error('No tiene permiso para ver los tipos de ítem inactivos.', 403)
    try:
        return jsonify({'success': True, 'data': TipoItemDao().getTiposItem(incluir_inactivos), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener tipos de ítem: {str(e)}")
        return error_interno()


# -------------------------
# Trae un tipo de ítem por ID
# -------------------------
@tipoitemapi.route('/tipos-item/<int:id_tipo_item>', methods=['GET'])
@require_permiso('tipoitem', 'ver')
def getTipoItem(id_tipo_item):
    try:
        tipo = TipoItemDao().getTipoItemById(id_tipo_item)
        if tipo:
            return jsonify({'success': True, 'data': tipo, 'error': None}), 200
        return respuesta_error('No se encontró el tipo de ítem con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al obtener tipo de ítem: {str(e)}")
        return error_interno()


# -------------------------
# Agrega un tipo de ítem
# -------------------------
@tipoitemapi.route('/tipos-item', methods=['POST'])
@require_permiso('tipoitem', 'nuevo')
def addTipoItem():
    datos, error, campo = validar_tipo_item(request.get_json(silent=True))
    if error:
        return respuesta_error(error, 400, campo)

    dao = TipoItemDao()
    try:
        if dao.existeDuplicado(datos['descripcion']):
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')

        nuevo_id = dao.guardarTipoItem(**datos)
        if nuevo_id == "DUPLICADO":
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')
        if nuevo_id:
            auditar(nuevo_id, 'ALTA', detalle_cambios({}, _para_detalle(datos), ETIQUETAS))
            return jsonify({
                'success': True,
                'data': {'id_tipo_item': nuevo_id, **datos},
                'mensaje': f'Tipo de ítem "{datos["descripcion"]}" agregado correctamente.',
                'error': None
            }), 201
        return respuesta_error('No se pudo guardar el tipo de ítem. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al agregar tipo de ítem: {str(e)}")
        return error_interno()


# -------------------------
# Actualiza un tipo de ítem
# -------------------------
@tipoitemapi.route('/tipos-item/<int:id_tipo_item>', methods=['PUT'])
@require_permiso('tipoitem', 'editar')
def updateTipoItem(id_tipo_item):
    datos, error, campo = validar_tipo_item(request.get_json(silent=True))
    if error:
        return respuesta_error(error, 400, campo)

    dao = TipoItemDao()
    try:
        anterior = dao.getTipoItemById(id_tipo_item)
        if not anterior:
            return respuesta_error('No se encontró el tipo de ítem con el ID proporcionado.', 404)

        detalle = detalle_cambios(_para_detalle(anterior), _para_detalle(datos), ETIQUETAS)
        if not detalle:
            # Sin cambios: no se toca la BD ni se audita.
            return jsonify({
                'success': True,
                'data': {'id_tipo_item': id_tipo_item, **datos},
                'mensaje': f'Tipo de ítem "{datos["descripcion"]}" sin cambios.',
                'error': None
            }), 200

        if dao.existeDuplicado(datos['descripcion'], excluir_id=id_tipo_item):
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')

        resultado = dao.updateTipoItem(id_tipo_item, **datos)
        if isinstance(resultado, tuple):  # ("EN_USO", motivo): cambio de "Controla stock" con ítems activos
            return respuesta_error(resultado[1], 409, 'controla_stock')
        if resultado == "DUPLICADO":
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')
        if resultado:
            auditar(id_tipo_item, 'MODIFICACION', detalle)
            return jsonify({
                'success': True,
                'data': {'id_tipo_item': id_tipo_item, **datos},
                'mensaje': f'Tipo de ítem "{datos["descripcion"]}" actualizado correctamente.',
                'error': None
            }), 200
        return respuesta_error('No se pudo actualizar el tipo de ítem.', 404)
    except Exception as e:
        app.logger.error(f"Error al actualizar tipo de ítem: {str(e)}")
        return error_interno()


# -------------------------
# Anula (baja lógica) un tipo de ítem
# -------------------------
@tipoitemapi.route('/tipos-item/<int:id_tipo_item>', methods=['DELETE'])
@require_permiso('tipoitem', 'anular')
def deleteTipoItem(id_tipo_item):
    dao = TipoItemDao()
    try:
        registro = dao.getTipoItemById(id_tipo_item)
        resultado = dao.deleteTipoItem(id_tipo_item)
        if isinstance(resultado, tuple):  # ("EN_USO", motivo)
            return respuesta_error(resultado[1], 409)
        if resultado:
            descripcion = registro['descripcion'] if registro else 'seleccionado'
            auditar(id_tipo_item, 'BAJA', f'Descripción: {descripcion}')
            return jsonify({'success': True, 'mensaje': f'Tipo de ítem "{descripcion}" anulado correctamente.', 'error': None}), 200
        return respuesta_error('No se encontró el tipo de ítem con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al anular tipo de ítem: {str(e)}")
        return error_interno()


# -------------------------
# Reactiva el tipo de ítem anulado (permiso: el mismo de editar)
# -------------------------
@tipoitemapi.route('/tipos-item/<int:id_tipo_item>/reactivar', methods=['PATCH'])
@require_permiso('tipoitem', 'editar')
def reactivarTipoItem(id_tipo_item):
    dao = TipoItemDao()
    try:
        resultado = dao.reactivarTipoItem(id_tipo_item)
        if resultado == NO_EXISTE:
            return respuesta_error('No se encontró el tipo de ítem con el ID proporcionado.', 404)
        if resultado == YA_ACTIVO:
            return respuesta_error('El tipo de ítem ya está activo.', 409)
        if resultado == DUPLICADO:
            return respuesta_error('No se puede reactivar: ya existe un tipo de ítem activo con esa descripción.', 409)
        if resultado:
            obj = dao.getTipoItemById(id_tipo_item)
            auditar(id_tipo_item, 'REACTIVACION', f'Descripción: {obj["descripcion"]}; Controla stock: ' + ('Sí' if obj['controla_stock'] else 'No'))
            return jsonify({'success': True, 'data': obj,
                            'mensaje': f'Tipo de ítem "{obj["descripcion"]}" reactivado correctamente.',
                            'error': None}), 200
        return respuesta_error('No se pudo reactivar el tipo de ítem. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al reactivar tipo de ítem: {str(e)}")
        return error_interno()
