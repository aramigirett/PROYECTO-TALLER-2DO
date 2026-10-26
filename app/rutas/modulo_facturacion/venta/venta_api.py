from datetime import date
from flask import Blueprint, request, jsonify, session, Response, current_app as app
from app.dao.modulo_facturacion.venta.VentaDao import (
    VentaDao, EMITIDA, ANULADA, CONTADO, CREDITO, NO_EXISTE, SIN_CAJA, PEDIDO_NO_EXISTE, PEDIDO_NO_PENDIENTE,
    ERROR_TIMBRADO, YA_ANULADA, CAJA_CERRADA, CLIENTE_INVALIDO, PACIENTE_INVALIDO, TRATAMIENTO_INVALIDO,
    TRATAMIENTO_OTRO_PACIENTE, TRATAMIENTO_CANCELADO, TRATAMIENTO_FACTURADO)
from app.dao.modulo_facturacion.pedido_cliente.PedidoClienteDao import PedidoClienteDao
from app.Services.factura_pdf_service import generarFacturaPdf
from app.rutas.modulo_facturacion.utils import entero_id, respuesta_error, auditar as _auditar, error_interno
from app.rutas.modulo_seguridad.decorators import require_permiso

ventaapi = Blueprint('ventaapi', __name__)

ESTADOS = (EMITIDA, ANULADA)
TIPOS = ('ITEMS', 'TRATAMIENTO')
MAX_TRATAMIENTOS = 50
ETIQUETA_CONDICION = {CONTADO: 'Contado', CREDITO: 'Crédito'}
MSG_SIN_CAJA = 'Debe abrir la caja antes de registrar una venta.'
MSG_CAJA_CERRADA = 'La caja de esta venta ya fue cerrada; utilice una Nota de Crédito.'


def _id_usuario():
    """El cajero SIEMPRE sale de la sesión, nunca del cuerpo del pedido."""
    return session.get('id_usuario')


from app.Services.formato import formatear_gs as _gs   # 'Gs. 100.000' (helper único: app/Services/formato.py)


def _parse_fecha(valor):
    return date.fromisoformat(valor) if valor else None


def _recortar(texto, largo=255):
    return texto if len(texto) <= largo else texto[:largo - 3] + '...'


def _detalle_alta(v):
    if v['tipo_venta'] == 'TRATAMIENTO':
        origen = 'Tratamientos: ' + ', '.join(d['descripcion'] for d in v['detalle'])
    else:
        origen = f'Pedido N.º {v["id_pedido"]}'
    # La auditoría guarda hasta 255 caracteres: lo importante va primero y la lista de tratamientos (la parte larga) al final.
    return _recortar(f'Factura {v["numero_factura"]}; Cliente: {v["cliente"]}; '
                     f'Condición: {ETIQUETA_CONDICION[v["condicion"]]}; Total: {_gs(v["total"])}; {origen}')


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


@ventaapi.route('/ventas/clientes', methods=['GET'])
@require_permiso('venta', 'nuevo')
def buscarClientes():
    """Clientes activos (con el paciente vinculado, si lo hay) para la venta de tratamiento."""
    try:
        return jsonify({'success': True, 'data': VentaDao().buscarClientes(request.args.get('q')), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al buscar clientes para la venta: {str(e)}")
        return error_interno()


@ventaapi.route('/ventas/pacientes', methods=['GET'])
@require_permiso('venta', 'nuevo')
def buscarPacientes():
    """Pacientes por cédula o nombre (mínimo 2 caracteres: expone datos personales, por eso exige `nuevo`)."""
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return respuesta_error('Ingrese al menos 2 caracteres para buscar.', 400)
    try:
        return jsonify({'success': True, 'data': VentaDao().buscarPacientes(q), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al buscar pacientes para la venta: {str(e)}")
        return error_interno()


@ventaapi.route('/ventas/tratamientos', methods=['GET'])
@require_permiso('venta', 'nuevo')
def getTratamientosDisponibles():
    """Tratamientos del paciente que no están cancelados y no tienen una venta EMITIDA, con precio e IVA vigentes."""
    id_paciente = entero_id(request.args.get('id_paciente'))
    if id_paciente is None:
        return respuesta_error('Debe indicar el paciente.', 400, 'id_paciente')
    try:
        return jsonify({'success': True, 'data': VentaDao().getTratamientosDisponibles(id_paciente), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener tratamientos disponibles: {str(e)}")
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
# Factura en PDF (al vuelo): ORIGINAL y DUPLICADO; una factura anulada se descarga con la marca "ANULADA".
# -------------------------
@ventaapi.route('/ventas/<int:id_venta>/pdf', methods=['GET'])
@require_permiso('venta', 'ver')
def getVentaPdf(id_venta):
    try:
        venta = VentaDao().getVentaById(id_venta)
        if venta is None:
            return respuesta_error('No se encontró la venta con el ID proporcionado.', 404)
        return Response(generarFacturaPdf(venta), mimetype='application/pdf',
                        headers={'Content-Disposition': f'inline; filename=factura_{venta["numero_factura"]}.pdf'})
    except Exception as e:
        app.logger.error(f"Error al generar el PDF de la factura: {str(e)}")
        return error_interno()


# -------------------------
# Nueva venta. Cuerpo común: {condicion: CONTADO|CREDITO, tipo_venta: ITEMS (por omisión) | TRATAMIENTO}.
#   ITEMS      : {id_pedido}                                          cliente, ítems, precios e IVA salen del pedido.
#   TRATAMIENTO: {id_cliente, id_paciente, ids_tratamiento: [...]}    descripción, precio e IVA salen de tipos_tratamiento.
# Totales, números y cajero los pone el servidor (cualquier otro dato se ignora).
# -------------------------
@ventaapi.route('/ventas', methods=['POST'])
@require_permiso('venta', 'nuevo')
def addVenta():
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}

    tipo = str(data.get('tipo_venta') or 'ITEMS').strip().upper()
    if tipo not in TIPOS:
        return respuesta_error('El tipo de venta debe ser ITEMS o TRATAMIENTO.', 400, 'tipo_venta')
    condicion = str(data.get('condicion') or '').strip().upper().replace('É', 'E')
    if condicion not in (CONTADO, CREDITO):
        return respuesta_error('La condición debe ser Contado o Crédito.', 400, 'condicion')
    return _addVentaTratamientos(data, condicion) if tipo == 'TRATAMIENTO' else _addVentaItems(data, condicion)


def _respuesta_alta(dao, id_venta):
    venta = dao.getVentaById(id_venta)
    _auditar('venta_cab', id_venta, 'ALTA', _detalle_alta(venta))
    if venta['id_pedido']:
        _auditar('pedido_venta_cab', venta['id_pedido'], 'MODIFICACION',
                 f'Estado: PENDIENTE -> FACTURADO (factura {venta["numero_factura"]})')
    return jsonify({'success': True, 'data': venta,
                    'mensaje': f'Venta registrada. Factura N.º {venta["numero_factura"]} '
                               f'de {venta["cliente"]} por {_gs(venta["total"])}.',
                    'error': None}), 201


def _addVentaItems(data, condicion):
    id_pedido = entero_id(data.get('id_pedido'))
    if id_pedido is None:
        return respuesta_error('Debe seleccionar un pedido.', 400, 'id_pedido')
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
            return _respuesta_alta(dao, resultado)
        return respuesta_error('No se pudo registrar la venta. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al registrar venta de ítems: {str(e)}")
        return error_interno()


def _addVentaTratamientos(data, condicion):
    id_cliente = entero_id(data.get('id_cliente'))
    if id_cliente is None:
        return respuesta_error('Debe seleccionar un cliente.', 400, 'id_cliente')
    id_paciente = entero_id(data.get('id_paciente'))
    if id_paciente is None:
        return respuesta_error('Debe seleccionar un paciente.', 400, 'id_paciente')
    crudos = data.get('ids_tratamiento')
    if not isinstance(crudos, list) or not crudos:
        return respuesta_error('Debe seleccionar al menos un tratamiento.', 400, 'ids_tratamiento')
    if len(crudos) > MAX_TRATAMIENTOS:
        return respuesta_error(f'Una factura no puede tener más de {MAX_TRATAMIENTOS} tratamientos.', 400, 'ids_tratamiento')
    ids = [entero_id(x) for x in crudos]
    if any(i is None for i in ids):
        return respuesta_error('Uno de los tratamientos seleccionados no es válido.', 400, 'ids_tratamiento')
    if len(set(ids)) != len(ids):
        return respuesta_error('Un tratamiento no puede repetirse en la misma factura.', 400, 'ids_tratamiento')

    dao = VentaDao()
    try:
        resultado = dao.guardarVentaTratamientos(_id_usuario(), id_cliente, id_paciente, ids, condicion)
        if resultado == SIN_CAJA:
            return respuesta_error(MSG_SIN_CAJA, 409)
        if resultado == CLIENTE_INVALIDO:
            return respuesta_error('El cliente seleccionado no existe o está inactivo.', 400, 'id_cliente')
        if resultado == PACIENTE_INVALIDO:
            return respuesta_error('El paciente seleccionado no existe.', 400, 'id_paciente')
        if resultado == TRATAMIENTO_INVALIDO:
            return respuesta_error('Uno de los tratamientos seleccionados no existe.', 400, 'ids_tratamiento')
        if isinstance(resultado, tuple):
            if resultado[0] == TRATAMIENTO_OTRO_PACIENTE:
                return respuesta_error(f'El tratamiento {resultado[1]} no pertenece al paciente seleccionado.', 400, 'ids_tratamiento')
            if resultado[0] == TRATAMIENTO_CANCELADO:
                return respuesta_error(f'El tratamiento {resultado[1]} está cancelado y no se puede facturar.', 409, 'ids_tratamiento')
            if resultado[0] == TRATAMIENTO_FACTURADO:
                return respuesta_error(f'El tratamiento {resultado[1]} ya fue facturado en la factura {resultado[2]}.', 409, 'ids_tratamiento')
            if resultado[0] == ERROR_TIMBRADO:
                return respuesta_error(resultado[1], 409)   # texto del procedimiento almacenado, tal cual
        if resultado:
            return _respuesta_alta(dao, resultado)
        return respuesta_error('No se pudo registrar la venta. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al registrar venta de tratamientos: {str(e)}")
        return error_interno()


# -------------------------
# Anular: cualquiera con `anular`, pero solo si la apertura de caja de la venta sigue ABIERTA y sin cobros.
# ?anular_pedido=1 (venta de ítems): anula también el pedido y repone el stock, todo en la misma transacción;
# sin el parámetro el pedido vuelve a PENDIENTE. En una venta de tratamiento los tratamientos quedan libres.
# -------------------------
@ventaapi.route('/ventas/<int:id_venta>', methods=['DELETE'])
@require_permiso('venta', 'anular')
def anularVenta(id_venta):
    anular_pedido = (request.args.get('anular_pedido') or '').strip().lower() in ('1', 'true', 'si', 'sí')
    dao = VentaDao()
    try:
        antes = dao.getVentaById(id_venta)
        resultado = dao.anularVenta(id_venta, anular_pedido)
        if resultado == NO_EXISTE:
            return respuesta_error('No se encontró la venta con el ID proporcionado.', 404)
        if resultado == YA_ANULADA:
            return respuesta_error('La venta ya está anulada.', 409)
        if resultado == CAJA_CERRADA:
            return respuesta_error(MSG_CAJA_CERRADA, 409)
        if isinstance(resultado, tuple) and resultado[0] == 'EN_USO':
            return respuesta_error(resultado[1], 409)
        if isinstance(resultado, dict):
            base = f'Factura {antes["numero_factura"]}; Cliente: {antes["cliente"]}; Total: {_gs(antes["total"])}'
            nota = ''
            if resultado['pedido_anulado']:
                nota = f'; Pedido N.º {resultado["id_pedido"]} anulado'
                if resultado['repuestos']:
                    nota += '; Stock repuesto: ' + ', '.join(f'{n} +{c}' for n, c in resultado['repuestos'])
                if resultado['sin_reposicion']:
                    nota += '; Sin reposición (el tipo ya no controla stock): ' + ', '.join(resultado['sin_reposicion'])
            elif resultado['id_pedido']:
                nota = f'; Pedido N.º {resultado["id_pedido"]} vuelve a PENDIENTE'
            elif resultado['tipo_venta'] == 'TRATAMIENTO':
                nota = '; Los tratamientos quedan libres para facturarse'
            _auditar('venta_cab', id_venta, 'BAJA', _recortar(base + nota))
            if resultado['pedido_anulado']:
                texto = f'Se anuló la factura {antes["numero_factura"]}'
                if resultado['repuestos']:
                    texto += '; stock repuesto: ' + ', '.join(f'{n} +{c}' for n, c in resultado['repuestos'])
                _auditar('pedido_venta_cab', resultado['id_pedido'], 'BAJA', _recortar(texto))
            elif resultado['id_pedido']:
                _auditar('pedido_venta_cab', resultado['id_pedido'], 'MODIFICACION',
                         f'Estado: FACTURADO -> PENDIENTE (se anuló la factura {antes["numero_factura"]})')
            mensaje = f'Factura N.º {antes["numero_factura"]} de {antes["cliente"]} anulada correctamente.'
            if resultado['pedido_anulado']:
                mensaje += f' El pedido N.º {resultado["id_pedido"]} también se anuló y el stock se repuso.'
            return jsonify({'success': True, 'data': dao.getVentaById(id_venta), 'mensaje': mensaje, 'error': None}), 200
        return respuesta_error('No se pudo anular la venta. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al anular venta: {str(e)}")
        return error_interno()
