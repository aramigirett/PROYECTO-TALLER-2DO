from datetime import date
from flask import Blueprint, request, jsonify, Response, session, current_app as app
from app.dao.modulo_facturacion.pedido_cliente.PedidoClienteDao import (
    PedidoClienteDao, PENDIENTE, FACTURADO, ANULADO, NO_EXISTE, CLIENTE_INVALIDO, ITEM_INVALIDO,
    TOTAL_EXCEDIDO, YA_FACTURADO, YA_ANULADO, STOCK_INSUFICIENTE)
from app.Services.pedido_pdf_service import generarPedidoPdf
from app.rutas.modulo_facturacion.utils import (
    entero_id, validar_cantidad_positiva, validar_observacion, respuesta_error, auditar as _auditar, error_interno)
from app.rutas.modulo_seguridad.decorators import require_permiso

pedidoclienteapi = Blueprint('pedidoclienteapi', __name__)

ENTIDAD = 'pedido_venta_cab'
ESTADOS = (PENDIENTE, FACTURADO, ANULADO)
MAX_LINEAS = 100


def auditar(id_registro, accion, detalle):
    _auditar(ENTIDAD, id_registro, accion, detalle)


def _id_usuario():
    """El cajero SIEMPRE sale de la sesión, nunca del cuerpo del pedido."""
    return session.get('id_usuario')


def _gs(n):
    return 'Gs. ' + f'{int(n):,}'.replace(',', '.')


def _parse_fecha(valor):
    return date.fromisoformat(valor) if valor else None


def _resumen_items(pedido):
    return ', '.join(f'{d["item"]} x{d["cantidad"]}' for d in pedido['detalle'])


def _detalle_alta(pedido):
    texto = (f'Cliente: {pedido["cliente"]}; Cajero: {pedido["cajero"]}; Total: {_gs(pedido["total"])}; '
             f'Ítems: {_resumen_items(pedido)}')
    return texto if len(texto) <= 255 else texto[:252] + '...'


def _validar_lineas(items):
    """Devuelve (lineas [(id_item, cantidad)], error, campo)."""
    if not isinstance(items, list) or not items:
        return None, 'Debe agregar al menos un ítem.', 'items'
    if len(items) > MAX_LINEAS:
        return None, f'Un pedido no puede tener más de {MAX_LINEAS} ítems.', 'items'
    lineas, vistos = [], set()
    for n, fila in enumerate(items, start=1):
        fila = fila if isinstance(fila, dict) else {}
        id_item = entero_id(fila.get('id_item'))
        if id_item is None:
            return None, f'El ítem de la fila {n} no es válido.', 'items'
        if id_item in vistos:
            return None, 'Un ítem no puede repetirse en el mismo pedido.', 'items'
        vistos.add(id_item)
        cantidad, error = validar_cantidad_positiva(fila.get('cantidad'))
        if error:
            return None, f'Fila {n}: {error}', 'items'
        lineas.append((id_item, cantidad))
    return lineas, None, None


# -------------------------
# Listado: TODOS los usuarios con permiso ver ven TODOS los pedidos (trabajo compartido entre cajeros).
# Filtros: ?estado=&cliente=(nombre o CI/RUC)&desde=AAAA-MM-DD&hasta=AAAA-MM-DD (ambos inclusive)
# -------------------------
@pedidoclienteapi.route('/pedidos-cliente', methods=['GET'])
@require_permiso('pedidocliente', 'ver')
def getPedidos():
    estado = (request.args.get('estado') or '').strip().upper() or None
    if estado and estado not in ESTADOS:
        return respuesta_error('El estado debe ser PENDIENTE, FACTURADO o ANULADO.', 400)
    try:
        desde = _parse_fecha(request.args.get('desde'))
        hasta = _parse_fecha(request.args.get('hasta'))
    except ValueError:
        return respuesta_error('Las fechas deben tener el formato AAAA-MM-DD.', 400)
    if desde and hasta and desde > hasta:
        return respuesta_error('La fecha "desde" no puede ser posterior a "hasta".', 400)
    cliente = (request.args.get('cliente') or '').strip()[:80] or None
    try:
        pedidos = PedidoClienteDao().getPedidos(estado=estado, cliente=cliente, desde=desde, hasta=hasta)
        return jsonify({'success': True, 'data': pedidos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener pedidos de cliente: {str(e)}")
        return error_interno()


# -------------------------
# Buscadores del formulario de Nuevo Pedido (piden `nuevo` de esta ventana, no el `ver` de otras)
# -------------------------
@pedidoclienteapi.route('/pedidos-cliente/clientes', methods=['GET'])
@require_permiso('pedidocliente', 'nuevo')
def buscarClientes():
    try:
        return jsonify({'success': True, 'data': PedidoClienteDao().buscarClientes(request.args.get('q')),
                        'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al buscar clientes: {str(e)}")
        return error_interno()


@pedidoclienteapi.route('/pedidos-cliente/items', methods=['GET'])
@require_permiso('pedidocliente', 'nuevo')
def buscarItems():
    try:
        return jsonify({'success': True, 'data': PedidoClienteDao().buscarItems(request.args.get('q')),
                        'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al buscar ítems: {str(e)}")
        return error_interno()


@pedidoclienteapi.route('/pedidos-cliente/<int:id_pedido>', methods=['GET'])
@require_permiso('pedidocliente', 'ver')
def getPedido(id_pedido):
    try:
        pedido = PedidoClienteDao().getPedidoById(id_pedido)
        if pedido is None:
            return respuesta_error('No se encontró el pedido con el ID proporcionado.', 404)
        return jsonify({'success': True, 'data': pedido, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener pedido de cliente: {str(e)}")
        return error_interno()


# -------------------------
# Nuevo pedido. Precio, IVA, subtotal y total los calcula el servidor desde `items`.
# Cuerpo: {id_cliente, observacion, items: [{id_item, cantidad}]}; cualquier otro dato se ignora.
# -------------------------
@pedidoclienteapi.route('/pedidos-cliente', methods=['POST'])
@require_permiso('pedidocliente', 'nuevo')
def addPedido():
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}

    id_cliente = entero_id(data.get('id_cliente'))
    if id_cliente is None:
        return respuesta_error('Debe seleccionar un cliente.', 400, 'id_cliente')
    observacion, error = validar_observacion(data.get('observacion'))
    if error:
        return respuesta_error(error, 400, 'observacion')
    lineas, error, campo = _validar_lineas(data.get('items'))
    if error:
        return respuesta_error(error, 400, campo)

    dao = PedidoClienteDao()
    try:
        resultado = dao.guardarPedido(_id_usuario(), id_cliente, observacion, lineas)
        if resultado == CLIENTE_INVALIDO:
            return respuesta_error('El cliente seleccionado no existe o está inactivo.', 400, 'id_cliente')
        if resultado == ITEM_INVALIDO:
            return respuesta_error('Uno de los ítems seleccionados no existe o está inactivo.', 400, 'items')
        if resultado == TOTAL_EXCEDIDO:
            return respuesta_error('El total del pedido supera el importe máximo permitido.', 400, 'items')
        if isinstance(resultado, tuple) and resultado[0] == STOCK_INSUFICIENTE:
            return respuesta_error(
                f'Stock insuficiente para {resultado[1]}: disponible {resultado[2]}, solicitado {resultado[3]}.',
                409, 'items')
        if resultado:
            pedido = dao.getPedidoById(resultado)
            auditar(resultado, 'ALTA', _detalle_alta(pedido))
            return jsonify({'success': True, 'data': pedido,
                            'mensaje': f'Pedido N.º {resultado} de {pedido["cliente"]} registrado correctamente.',
                            'error': None}), 201
        return respuesta_error('No se pudo registrar el pedido. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al registrar pedido de cliente: {str(e)}")
        return error_interno()


# -------------------------
# Anular: solo PENDIENTE; repone el stock. Cualquiera con permiso `anular` (la auditoría registra quién).
# -------------------------
@pedidoclienteapi.route('/pedidos-cliente/<int:id_pedido>', methods=['DELETE'])
@require_permiso('pedidocliente', 'anular')
def anularPedido(id_pedido):
    dao = PedidoClienteDao()
    try:
        antes = dao.getPedidoById(id_pedido)
        resultado = dao.anularPedido(id_pedido)
        if resultado == NO_EXISTE:
            return respuesta_error('No se encontró el pedido con el ID proporcionado.', 404)
        if resultado == YA_FACTURADO:
            return respuesta_error('El pedido ya fue facturado; no se puede anular.', 409)
        if resultado == YA_ANULADO:
            return respuesta_error('El pedido ya está anulado.', 409)
        if isinstance(resultado, dict):
            texto = f'Cliente: {antes["cliente"]}; Total: {_gs(antes["total"])}'
            if resultado['repuestos']:
                texto += '; Stock repuesto: ' + ', '.join(f'{n} +{c}' for n, c in resultado['repuestos'])
            if resultado['sin_reposicion']:
                texto += '; Sin reposición (el tipo ya no controla stock): ' + ', '.join(resultado['sin_reposicion'])
            auditar(id_pedido, 'BAJA', texto if len(texto) <= 255 else texto[:252] + '...')
            return jsonify({'success': True, 'data': dao.getPedidoById(id_pedido),
                            'mensaje': f'Pedido N.º {id_pedido} de {antes["cliente"]} anulado correctamente.',
                            'error': None}), 200
        return respuesta_error('No se pudo anular el pedido. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al anular pedido de cliente: {str(e)}")
        return error_interno()


# -------------------------
# Documento imprimible (PDF al vuelo). Un pedido anulado se descarga con la marca "ANULADO".
# -------------------------
@pedidoclienteapi.route('/pedidos-cliente/<int:id_pedido>/pdf', methods=['GET'])
@require_permiso('pedidocliente', 'ver')
def pedidoPdf(id_pedido):
    try:
        pedido = PedidoClienteDao().getPedidoById(id_pedido)
        if pedido is None:
            return respuesta_error('No se encontró el pedido con el ID proporcionado.', 404)
        return Response(generarPedidoPdf(pedido), mimetype='application/pdf',
                        headers={'Content-Disposition': f'inline; filename=pedido_{id_pedido}.pdf'})
    except Exception as e:
        app.logger.error(f"Error al generar PDF del pedido: {str(e)}")
        return error_interno()
