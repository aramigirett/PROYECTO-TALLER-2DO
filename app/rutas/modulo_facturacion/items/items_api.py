from flask import Blueprint, request, jsonify, current_app as app
from app.rutas.modulo_seguridad.permisos_contexto import puede
from app.rutas.modulo_facturacion.utils import respuesta_error
from app.dao.modulo_facturacion.items.ItemDao import NO_EXISTE, YA_ACTIVO, TIPO_INACTIVO, DEPOSITO_INACTIVO, STOCK_REINICIADO
from app.dao.modulo_facturacion.items.ItemDao import ItemDao, DUPLICADO, TIPO_INVALIDO, DEPOSITO_INVALIDO
from app.dao.modulo_facturacion.deposito.DepositoDao import DepositoDao
from app.dao.modulo_facturacion.tipo_items.TipoItemDao import TipoItemDao
from app.rutas.modulo_facturacion.utils import (
    normalizar_descripcion, entero_id, validar_precio, validar_iva, validar_cantidad,
    detalle_cambios, respuesta_error, auditar as _auditar, error_interno)
from app.rutas.modulo_seguridad.decorators import require_permiso, require_login

itemapi = Blueprint('itemapi', __name__)

ENTIDAD = 'items'
MAX_DESCRIPCION_ITEM = 100
ETIQUETAS = {
    'descripcion': 'Descripción', 'tipo': 'Tipo', 'deposito': 'Depósito', 'precio_unitario': 'Precio',
    'iva': 'IVA', 'cantidad_disponible': 'Stock'
}
MSG_DUPLICADO = 'La descripción ya existe.'
MSG_TIPO = 'El tipo de ítem seleccionado no existe o está anulado.'
MSG_DEPOSITO = 'El depósito seleccionado no existe o está anulado.'


def auditar(id_registro, accion, detalle):
    _auditar(ENTIDAD, id_registro, accion, detalle)


def validar_item(data):
    """
    Valida los datos del formulario. El tipo debe existir y estar activo; si no controla stock, la
    cantidad se fuerza a 0 (y no se exige ni se valida lo que haya enviado el cliente).
    El depósito también debe existir y estar activo.
    Devuelve (datos, ref, error, campo); ref = {'tipo': ..., 'deposito': ...} (para la auditoría).
    """
    data = data if isinstance(data, dict) else {}
    descripcion, error = normalizar_descripcion(data, MAX_DESCRIPCION_ITEM, ampliada=True)
    if error:
        return None, None, error, 'descripcion'

    id_tipo = entero_id(data.get('id_tipo_item'))
    if id_tipo is None:
        return None, None, 'Debe seleccionar un tipo de ítem.', 'id_tipo_item'

    id_deposito = entero_id(data.get('id_deposito'))
    if id_deposito is None:
        return None, None, 'Debe seleccionar un depósito.', 'id_deposito'

    precio, error = validar_precio(data.get('precio_unitario'))
    if error:
        return None, None, error, 'precio_unitario'

    iva, error = validar_iva(data.get('iva'))
    if error:
        return None, None, error, 'iva'

    tipo = TipoItemDao().getTipoItemById(id_tipo)
    if tipo is None:
        return None, None, MSG_TIPO, 'id_tipo_item'

    deposito = DepositoDao().getDepositoById(id_deposito)
    if deposito is None:
        return None, None, MSG_DEPOSITO, 'id_deposito'

    if tipo['controla_stock']:
        cantidad, error = validar_cantidad(data.get('cantidad_disponible'))
        if error:
            return None, None, error, 'cantidad_disponible'
    else:
        cantidad = 0

    datos = {'id_tipo_item': id_tipo, 'id_deposito': id_deposito, 'descripcion': descripcion,
             'precio_unitario': precio, 'iva': iva, 'cantidad_disponible': cantidad}
    return datos, {'tipo': tipo, 'deposito': deposito}, None, None


def _para_detalle(descripcion, tipo, deposito, precio, iva, cantidad):
    """Valores legibles para la auditoría: el nombre del tipo y del depósito, no sus IDs."""
    return {'descripcion': descripcion, 'tipo': tipo, 'deposito': deposito, 'precio_unitario': precio,
            'iva': iva, 'cantidad_disponible': cantidad}


def _detalle_de_datos(datos, ref):
    return _para_detalle(datos['descripcion'], ref['tipo']['descripcion'], ref['deposito']['descripcion'],
                         datos['precio_unitario'], datos['iva'], datos['cantidad_disponible'])


def _detalle_de_registro(r):
    return _para_detalle(r['descripcion'], r['tipo_item'], r['deposito'], r['precio_unitario'], r['iva'],
                         r['cantidad_disponible'])


def respuesta_por_codigo(codigo):
    """Traduce los códigos de error del DAO a respuesta HTTP. None si no es un código de error."""
    if codigo == DUPLICADO:
        return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')
    if codigo == TIPO_INVALIDO:
        return respuesta_error(MSG_TIPO, 400, 'id_tipo_item')
    if codigo == DEPOSITO_INVALIDO:
        return respuesta_error(MSG_DEPOSITO, 400, 'id_deposito')
    return None


# -------------------------
# Trae todos los ítems activos (con tipo y si controla stock)
# -------------------------
@itemapi.route('/items', methods=['GET'])
@require_login  # lookup: alimenta combos de otras pantallas (Pedidos, Ventas)
def getItems():
    incluir_inactivos = request.args.get('inactivos', '').lower() in ('1', 'true')
    if incluir_inactivos and not puede('item', 'ver'):
        return respuesta_error('No tiene permiso para ver los ítems inactivos.', 403)
    try:
        return jsonify({'success': True, 'data': ItemDao().getItems(incluir_inactivos), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener ítems: {str(e)}")
        return error_interno()


# -------------------------
# Trae un ítem por ID
# -------------------------
@itemapi.route('/items/<int:id_item>', methods=['GET'])
@require_permiso('item', 'ver')
def getItem(id_item):
    try:
        item = ItemDao().getItemById(id_item)
        if item:
            return jsonify({'success': True, 'data': item, 'error': None}), 200
        return respuesta_error('No se encontró el ítem con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al obtener ítem: {str(e)}")
        return error_interno()


# -------------------------
# Agrega un ítem
# -------------------------
@itemapi.route('/items', methods=['POST'])
@require_permiso('item', 'nuevo')
def addItem():
    try:
        datos, ref, error, campo = validar_item(request.get_json(silent=True))
        if error:
            return respuesta_error(error, 400, campo)

        dao = ItemDao()
        if dao.existeDuplicado(datos['descripcion']):
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')

        nuevo_id = dao.guardarItem(**datos)
        rechazo = respuesta_por_codigo(nuevo_id)
        if rechazo:
            return rechazo
        if nuevo_id:
            auditar(nuevo_id, 'ALTA', detalle_cambios({}, _detalle_de_datos(datos, ref), ETIQUETAS))
            return jsonify({
                'success': True,
                'data': dao.getItemById(nuevo_id),
                'mensaje': f'Ítem "{datos["descripcion"]}" agregado correctamente.',
                'error': None
            }), 201
        return respuesta_error('No se pudo guardar el ítem. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al agregar ítem: {str(e)}")
        return error_interno()


# -------------------------
# Actualiza un ítem
# -------------------------
@itemapi.route('/items/<int:id_item>', methods=['PUT'])
@require_permiso('item', 'editar')
def updateItem(id_item):
    try:
        datos, ref, error, campo = validar_item(request.get_json(silent=True))
        if error:
            return respuesta_error(error, 400, campo)

        dao = ItemDao()
        anterior = dao.getItemById(id_item)
        if not anterior:
            return respuesta_error('No se encontró el ítem con el ID proporcionado.', 404)

        detalle = detalle_cambios(_detalle_de_registro(anterior), _detalle_de_datos(datos, ref), ETIQUETAS)
        if not detalle:
            # Sin cambios: no se toca la BD ni se audita.
            return jsonify({
                'success': True, 'data': anterior,
                'mensaje': f'Ítem "{datos["descripcion"]}" sin cambios.', 'error': None
            }), 200

        if dao.existeDuplicado(datos['descripcion'], excluir_id=id_item):
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')

        resultado = dao.updateItem(id_item, **datos)
        rechazo = respuesta_por_codigo(resultado)
        if rechazo:
            return rechazo
        if resultado:
            auditar(id_item, 'MODIFICACION', detalle)
            return jsonify({
                'success': True,
                'data': dao.getItemById(id_item),
                'mensaje': f'Ítem "{datos["descripcion"]}" actualizado correctamente.',
                'error': None
            }), 200
        return respuesta_error('No se pudo actualizar el ítem.', 404)
    except Exception as e:
        app.logger.error(f"Error al actualizar ítem: {str(e)}")
        return error_interno()


# -------------------------
# Anula (baja lógica) un ítem
# -------------------------
@itemapi.route('/items/<int:id_item>', methods=['DELETE'])
@require_permiso('item', 'anular')
def deleteItem(id_item):
    dao = ItemDao()
    try:
        registro = dao.getItemById(id_item)
        resultado = dao.deleteItem(id_item)
        if isinstance(resultado, tuple):  # ("EN_USO", motivo)
            return respuesta_error(resultado[1], 409)
        if resultado:
            descripcion = registro['descripcion'] if registro else 'seleccionado'
            auditar(id_item, 'BAJA', f'Descripción: {descripcion}')
            return jsonify({'success': True, 'mensaje': f'Ítem "{descripcion}" anulado correctamente.', 'error': None}), 200
        return respuesta_error('No se encontró el ítem con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al anular ítem: {str(e)}")
        return error_interno()


# -------------------------
# Reactiva el ítem anulado (permiso: el mismo de editar)
# -------------------------
@itemapi.route('/items/<int:id_item>/reactivar', methods=['PATCH'])
@require_permiso('item', 'editar')
def reactivarItem(id_item):
    dao = ItemDao()
    try:
        resultado = dao.reactivarItem(id_item)
        if resultado == NO_EXISTE:
            return respuesta_error('No se encontró el ítem con el ID proporcionado.', 404)
        if resultado == YA_ACTIVO:
            return respuesta_error('El ítem ya está activo.', 409)
        if resultado == TIPO_INACTIVO:
            return respuesta_error('No se puede reactivar: el tipo de ítem está anulado. Reactívelo primero.', 409)
        if resultado == DEPOSITO_INACTIVO:
            return respuesta_error('No se puede reactivar: el depósito está anulado. Reactívelo primero.', 409)
        if resultado == DUPLICADO:
            return respuesta_error('No se puede reactivar: ya existe un ítem activo con esa descripción.', 409)
        if isinstance(resultado, tuple) and resultado[0] == STOCK_REINICIADO:
            obj = dao.getItemById(id_item)
            auditar(id_item, 'REACTIVACION', f'Descripción: {obj["descripcion"]}; Tipo: {obj["tipo_item"]}; Depósito: {obj["deposito"]}' + f'; Stock: {resultado[1]} -> 0 (el tipo no controla stock)')
            return jsonify({'success': True, 'data': obj,
                            'mensaje': f'Ítem "{obj["descripcion"]}" reactivado correctamente. El stock se puso en 0 '
                                       f'porque su tipo ya no controla stock (tenía {resultado[1]}).',
                            'error': None}), 200
        if resultado:
            obj = dao.getItemById(id_item)
            auditar(id_item, 'REACTIVACION', f'Descripción: {obj["descripcion"]}; Tipo: {obj["tipo_item"]}; Depósito: {obj["deposito"]}')
            return jsonify({'success': True, 'data': obj,
                            'mensaje': f'Ítem "{obj["descripcion"]}" reactivado correctamente.',
                            'error': None}), 200
        return respuesta_error('No se pudo reactivar el ítem. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al reactivar ítem: {str(e)}")
        return error_interno()
