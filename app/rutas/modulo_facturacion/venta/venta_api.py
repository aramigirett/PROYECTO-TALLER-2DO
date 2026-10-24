from datetime import date
from flask import Blueprint, request, jsonify, session, current_app as app
from app.dao.modulo_facturacion.venta.VentaDao import (
    VentaDao, EMITIDA, ANULADA, CONTADO, CREDITO, NO_EXISTE, SIN_CAJA, PEDIDO_NO_EXISTE, PEDIDO_NO_PENDIENTE,
    ERROR_TIMBRADO, YA_ANULADA, CAJA_CERRADA)
from app.dao.modulo_facturacion.pedido_cliente.PedidoClienteDao import PedidoClienteDao
from app.rutas.modulo_facturacion.utils import entero_id, respuesta_error, auditar as _auditar, error_interno
from app.rutas.modulo_seguridad.decorators import require_permiso

ventaapi = Blueprint('ventaapi', __name__)

ESTADOS = (EMITIDA, ANULADA)
TIPOS = ('ITEMS', 'TRATAMIENTO')
ETIQUETA_CONDICION = {CONTADO: 'Contado', CREDITO: 'Crédito'}
MSG_SIN_CAJA = 'Debe abrir la caja antes de registrar una venta.'
MSG_CAJA_CERRADA = 'La caja de esta venta ya fue cerrada; utilice una Nota de Crédito.'


def _id_usuario():
    """El cajero SIEMPRE sale de la sesión, nunca del cuerpo del pedido."""
    return session.get('id_usuario')


def _gs(n):
    return 'Gs. ' + f'{int(n):,}'.replace(',', '.')


def _parse_fecha(valor):
    return date.fromisoformat(valor) if valor else None


def _detalle_alta(v):
    return (f'Factura {v["numero_factura"]}; Cliente: {v["cliente"]}; Pedido N.º {v["id_pedido"]}; '
            f'Condición: {ETIQUETA_CONDICION[v["condicion"]]}; Total: {_gs(v["total"])}')


# -------------------------
# Listado: todos los usuarios con `ver` ven TODAS las ventas.
# Filtros: ?estado=&cliente=(nombre, CI/RUC o N.º de factura)&desde=&hasta=&tipo=ITEMS|TRATAMIENTO
# -------------------------
@ventaapi.route('/ventas', methods=['GET'])
@require_permiso('venta', 'ver')
def getVentas():
    estado = (request.args.get('estado') or '').strip().upper() or None
    if estado and estado not in ESTADOS:
        return respuesta_error('El estado debe ser EMITIDA o ANULADA.', 400)
    tipo = (request.args.get('tipo') or '').strip().upper() or None
    if tipo and tipo not in TIPOS:
        return respuesta_error('El tipo debe ser ITEMS o TRATAMIENTO.', 400)
    try:
        desde = _parse_fecha(request.args.get('desde'))
        hasta = _parse_fecha(request.args.get('hasta'))
    except ValueError:
        return respuesta_error('Las fechas deben tener el formato AAAA-MM-DD.', 400)
    if desde and hasta and desde > hasta:
        return respuesta_error('La fecha "desde" no puede ser posterior a "hasta".', 400)
    cliente = (request.args.get('cliente') or '').strip()[:80] or None
    try:
        ventas = VentaDao().getVentas(estado=estado, cliente=cliente, desde=desde, hasta=hasta, tipo=tipo)
        return jsonify({'success': True, 'data': ventas, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener ventas: {str(e)}")
        return error_interno()


# -------------------------
# Apoyo del formulario de Nueva Venta (piden `nuevo`)
# -------------------------
@ventaapi.route('/ventas/caja-actual', methods=['GET'])
@require_permiso('venta', 'nuevo')
def getCajaActual():
    try:
        return jsonify({'success': True, 'data': VentaDao().getAperturaActual(_id_usuario()), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener la caja actual: {str(e)}")
        return error_interno()


@ventaapi.route('/ventas/pedidos', methods=['GET'])
@require_permiso('venta', 'nuevo')
def buscarPedidos():
    try:
        return jsonify({'success': True, 'data': VentaDao().buscarPedidosPendientes(request.args.get('q')),
                        'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al buscar pedidos pendientes: {str(e)}")
        return error_interno()


@ventaapi.route('/ventas/pedidos/<int:id_pedido>', methods=['GET'])
@require_permiso('venta', 'nuevo')
def getPedidoParaVenta(id_pedido):
    """Cliente e ítems del pedido, solo lectura, para precargar la venta (solo si sigue PENDIENTE)."""
    try:
        pedido = PedidoClienteDao().getPedidoById(id_pedido)
        if pedido is None:
            return respuesta_error('No se encontró el pedido seleccionado.', 404)
        if pedido['estado'] != 'PENDIENTE':
            return respuesta_error('El pedido ya fue facturado.' if pedido['estado'] == 'FACTURADO'
                                   else 'El pedido está anulado y no se puede facturar.', 409)
        return jsonify({'success': True, 'data': pedido, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener el pedido para la venta: {str(e)}")
        return error_interno()


@ventaapi.route('/ventas/<int:id_venta>', methods=['GET'])
@require_permiso('venta', 'ver')
def getVenta(id_venta):
    try:
        venta = VentaDao().getVentaById(id_venta)
        if venta is None:
            return respuesta_error('No se encontró la venta con el ID proporcionado.', 404)
        return jsonify({'success': True, 'data': venta, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener venta: {str(e)}")
        return error_interno()


# -------------------------
# Nueva venta de ítems. Cuerpo: {id_pedido, condicion: CONTADO|CREDITO}; cliente, ítems, precios, IVA y totales los
# toma el servidor del pedido (cualquier otro dato se ignora); el cajero sale de la sesión.
# -------------------------
@ventaapi.route('/ventas', methods=['POST'])
@require_permiso('venta', 'nuevo')
def addVenta():
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}

    id_pedido = entero_id(data.get('id_pedido'))
    if id_pedido is None:
        return respuesta_error('Debe seleccionar un pedido.', 400, 'id_pedido')
    condicion = str(data.get('condicion') or '').strip().upper().replace('É', 'E')
    if condicion not in (CONTADO, CREDITO):
        return respuesta_error('La condición debe ser Contado o Crédito.', 400, 'condicion')

    dao = VentaDao()
    try:
        resultado = dao.guardarVentaItems(_id_usuario(), id_pedido, condicion)
        if resultado == SIN_CAJA:
            return respuesta_error(MSG_SIN_CAJA, 409)
        if resultado == PEDIDO_NO_EXISTE:
            return respuesta_error('No se encontró el pedido seleccionado.', 404, 'id_pedido')
        if isinstance(resultado, tuple) and resultado[0] == PEDIDO_NO_PENDIENTE:
            return respuesta_error('El pedido ya fue facturado.' if resultado[1] == 'FACTURADO'
                                   else 'El pedido está anulado y no se puede facturar.', 409, 'id_pedido')
        if isinstance(resultado, tuple) and resultado[0] == ERROR_TIMBRADO:
            return respuesta_error(resultado[1], 409)   # texto del procedimiento almacenado, tal cual
        if resultado:
            venta = dao.getVentaById(resultado)
            _auditar('venta_cab', resultado, 'ALTA', _detalle_alta(venta))
            _auditar('pedido_venta_cab', id_pedido, 'MODIFICACION',
                     f'Estado: PENDIENTE -> FACTURADO (factura {venta["numero_factura"]})')
            return jsonify({'success': True, 'data': venta,
                            'mensaje': f'Venta registrada. Factura N.º {venta["numero_factura"]} '
                                       f'de {venta["cliente"]} por {_gs(venta["total"])}.',
                            'error': None}), 201
        return respuesta_error('No se pudo registrar la venta. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al registrar venta: {str(e)}")
        return error_interno()


# -------------------------
# Anular: cualquiera con `anular`, pero solo si la apertura de caja de la venta sigue ABIERTA y sin cobros.
# -------------------------
@ventaapi.route('/ventas/<int:id_venta>', methods=['DELETE'])
@require_permiso('venta', 'anular')
def anularVenta(id_venta):
    dao = VentaDao()
    try:
        antes = dao.getVentaById(id_venta)
        resultado = dao.anularVenta(id_venta)
        if resultado == NO_EXISTE:
            return respuesta_error('No se encontró la venta con el ID proporcionado.', 404)
        if resultado == YA_ANULADA:
            return respuesta_error('La venta ya está anulada.', 409)
        if resultado == CAJA_CERRADA:
            return respuesta_error(MSG_CAJA_CERRADA, 409)
        if isinstance(resultado, tuple) and resultado[0] == 'EN_USO':
            return respuesta_error(resultado[1], 409)
        if isinstance(resultado, dict):
            _auditar('venta_cab', id_venta, 'BAJA',
                     f'Factura {antes["numero_factura"]}; Cliente: {antes["cliente"]}; Total: {_gs(antes["total"])}; '
                     f'Pedido N.º {resultado["id_pedido"]} vuelve a PENDIENTE')
            if resultado['id_pedido']:
                _auditar('pedido_venta_cab', resultado['id_pedido'], 'MODIFICACION',
                         f'Estado: FACTURADO -> PENDIENTE (se anuló la factura {antes["numero_factura"]})')
            return jsonify({'success': True, 'data': dao.getVentaById(id_venta),
                            'mensaje': f'Factura N.º {antes["numero_factura"]} de {antes["cliente"]} anulada correctamente.',
                            'error': None}), 200
        return respuesta_error('No se pudo anular la venta. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al anular venta: {str(e)}")
        return error_interno()
