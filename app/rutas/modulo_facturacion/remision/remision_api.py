from datetime import date
from flask import Blueprint, request, jsonify, session, Response, current_app as app
from app.dao.modulo_facturacion.remision.RemisionDao import (
    RemisionDao, EMITIDA, ANULADA, NO_EXISTE, VENTA_NO_EXISTE, VENTA_NO_EMITIDA, VENTA_NO_ITEMS, DEPOSITO_INVALIDO, ITEM_INVALIDO,
    ERROR_BD, YA_ANULADA)
from app.Services.remision_pdf_service import generarRemisionPdf
from app.rutas.modulo_facturacion.utils import (
    entero_id, validar_texto, validar_nombre, validar_cantidad_positiva, validar_observacion, respuesta_error,
    auditar as _auditar, error_interno, MAX_DIRECCION)
from app.rutas.modulo_seguridad.decorators import require_permiso

remisionapi = Blueprint('remisionapi', __name__)

ESTADOS = (EMITIDA, ANULADA)
MAX_ITEMS = 100


def _id_usuario():
    """El usuario que emite SIEMPRE sale de la sesión, nunca del cuerpo del pedido."""
    return session.get('id_usuario')


def _parse_fecha(valor):
    return date.fromisoformat(valor) if valor else None


def _recortar(texto, largo=255):
    return texto if len(texto) <= largo else texto[:largo - 3] + '...'


def _error_item(n, mensaje, status=400):
    """Error de validación de UNA fila de la grilla de ítems (fila 1-based)."""
    return respuesta_error(f'Ítem {n}: {mensaje}', status, campo='items', fila=n)


def _validar_items(crudos):
    """Valida el arreglo `items` del cuerpo. Devuelve (items normalizados, None) o (None, respuesta de error)."""
    if not isinstance(crudos, list) or not crudos:
        return None, respuesta_error('Debe indicar al menos un ítem a remitir.', 400, 'items')
    if len(crudos) > MAX_ITEMS:
        return None, respuesta_error(f'Una remisión no puede tener más de {MAX_ITEMS} ítems.', 400, 'items')
    items, vistos = [], set()
    for n, x in enumerate(crudos, start=1):
        x = x if isinstance(x, dict) else {}
        id_item = entero_id(x.get('id_item'))
        if id_item is None:
            return None, _error_item(n, 'debe seleccionar el ítem.')
        if id_item in vistos:
            return None, _error_item(n, 'el ítem está repetido en la remisión.')
        vistos.add(id_item)
        cantidad, error = validar_cantidad_positiva(x.get('cantidad'))
        if error:
            return None, _error_item(n, error)
        items.append({'id_item': id_item, 'cantidad': cantidad})
    return items, None


# -------------------------
# Listado: todos los usuarios con `ver` ven TODAS las remisiones.
# Filtros: ?estado=&cliente=(nombre, CI/RUC, N.º de factura o de remisión)&desde=&hasta=
# -------------------------
@remisionapi.route('/remisiones', methods=['GET'])
@require_permiso('remision', 'ver')
def getRemisiones():
    estado = (request.args.get('estado') or '').strip().upper() or None
    if estado and estado not in ESTADOS:
        return respuesta_error('El estado debe ser EMITIDA o ANULADA.', 400)
    try:
        desde = _parse_fecha(request.args.get('desde'))
        hasta = _parse_fecha(request.args.get('hasta'))
    except ValueError:
        return respuesta_error('Las fechas deben tener el formato AAAA-MM-DD.', 400)
    if desde and hasta and desde > hasta:
        return respuesta_error('La fecha "desde" no puede ser posterior a "hasta".', 400)
    cliente = (request.args.get('cliente') or '').strip()[:80] or None
    try:
        return jsonify({'success': True, 'data': RemisionDao().getRemisiones(estado=estado, cliente=cliente, desde=desde, hasta=hasta),
                        'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener remisiones: {str(e)}")
        return error_interno()


# -------------------------
# Apoyo del formulario de Nueva Remisión (piden `nuevo`)
# -------------------------
@remisionapi.route('/remisiones/ventas', methods=['GET'])
@require_permiso('remision', 'nuevo')
def buscarVentas():
    try:
        return jsonify({'success': True, 'data': RemisionDao().buscarVentas(request.args.get('q')), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al buscar ventas para remitir: {str(e)}")
        return error_interno()


@remisionapi.route('/remisiones/ventas/<int:id_venta>/pendientes', methods=['GET'])
@require_permiso('remision', 'nuevo')
def getPendientes(id_venta):
    """La venta y sus ítems con facturado / ya remitido / pendiente (de todos los depósitos; la pantalla filtra por depósito)."""
    try:
        venta = RemisionDao().getPendientesVenta(id_venta)
        if venta is None:
            return respuesta_error('No se encontró la venta.', 404, 'id_venta')
        return jsonify({'success': True, 'data': venta, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener pendientes de entrega: {str(e)}")
        return error_interno()


@remisionapi.route('/remisiones/depositos', methods=['GET'])
@require_permiso('remision', 'nuevo')
def getDepositos():
    try:
        return jsonify({'success': True, 'data': RemisionDao().getDepositos(), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener depósitos: {str(e)}")
        return error_interno()


@remisionapi.route('/remisiones/<int:id_remision>', methods=['GET'])
@require_permiso('remision', 'ver')
def getRemision(id_remision):
    try:
        remision = RemisionDao().getRemisionById(id_remision)
        if remision is None:
            return respuesta_error('No se encontró la remisión con el ID proporcionado.', 404)
        return jsonify({'success': True, 'data': remision, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener remisión: {str(e)}")
        return error_interno()


# -------------------------
# Nota de remisión en PDF (al vuelo): ORIGINAL y DUPLICADO; una anulada se descarga con la marca "ANULADA".
# -------------------------
@remisionapi.route('/remisiones/<int:id_remision>/pdf', methods=['GET'])
@require_permiso('remision', 'ver')
def getRemisionPdf(id_remision):
    try:
        remision = RemisionDao().getRemisionById(id_remision)
        if remision is None:
            return respuesta_error('No se encontró la remisión con el ID proporcionado.', 404)
        return Response(generarRemisionPdf(remision), mimetype='application/pdf',
                        headers={'Content-Disposition': f'inline; filename=remision_{remision["numero_remision"]}.pdf'})
    except Exception as e:
        app.logger.error(f"Error al generar el PDF de la remisión: {str(e)}")
        return error_interno()


# -------------------------
# Nueva remisión. Cuerpo: {id_venta, id_deposito, fecha_traslado, direccion_llegada, responsable_traslado, observacion,
# items: [{id_item, cantidad}]}. El motivo es siempre VENTA y el usuario sale de la sesión; cualquier otro dato se ignora.
# -------------------------
@remisionapi.route('/remisiones', methods=['POST'])
@require_permiso('remision', 'nuevo')
def addRemision():
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}

    id_venta = entero_id(data.get('id_venta'))
    if id_venta is None:
        return respuesta_error('Debe seleccionar una venta.', 400, 'id_venta')
    id_deposito = entero_id(data.get('id_deposito'))
    if id_deposito is None:
        return respuesta_error('Debe seleccionar el depósito de origen.', 400, 'id_deposito')
    try:
        fecha_traslado = date.fromisoformat(str(data.get('fecha_traslado') or '').strip())
    except ValueError:
        return respuesta_error('La fecha de traslado no es válida (use AAAA-MM-DD).', 400, 'fecha_traslado')
    if fecha_traslado < date.today():
        return respuesta_error('La fecha de traslado no puede ser anterior a hoy.', 400, 'fecha_traslado')
    direccion, error = validar_texto(data.get('direccion_llegada'), 'dirección de llegada', MAX_DIRECCION)
    if error:
        return respuesta_error(error, 400, 'direccion_llegada')
    responsable, error = validar_nombre(data.get('responsable_traslado'), 'responsable del traslado', True)
    if error:
        return respuesta_error(error, 400, 'responsable_traslado')
    observacion, error = validar_observacion(data.get('observacion'))
    if error:
        return respuesta_error(error, 400, 'observacion')
    items, rechazo = _validar_items(data.get('items'))
    if rechazo:
        return rechazo

    dao = RemisionDao()
    try:
        resultado = dao.guardarRemision(_id_usuario(), id_venta, id_deposito, fecha_traslado, direccion, responsable, observacion, items)
        if resultado == VENTA_NO_EXISTE:
            return respuesta_error('No se encontró la venta.', 404, 'id_venta')
        if resultado == VENTA_NO_EMITIDA:
            return respuesta_error('No se puede emitir una remisión de una venta anulada.', 409, 'id_venta')
        if resultado == VENTA_NO_ITEMS:
            return respuesta_error('Solo se pueden remitir ventas de ítems.', 409, 'id_venta')
        if resultado == DEPOSITO_INVALIDO:
            return respuesta_error('El depósito no existe o está inactivo.', 409, 'id_deposito')
        if isinstance(resultado, tuple):
            if resultado[0] == ITEM_INVALIDO:
                n = next((i for i, x in enumerate(items, start=1) if x['id_item'] == resultado[1]), 1)
                return _error_item(n, 'el ítem no existe.', 409)
            if resultado[0] == ERROR_BD:
                return respuesta_error(resultado[1], 409, 'items')   # texto del trigger de la base, tal cual
        if resultado:
            remision = dao.getRemisionById(resultado)
            _auditar('nota_remision_cab', resultado, 'ALTA', _recortar(
                f'Remisión {remision["numero_remision"]}; Cliente: {remision["cliente"]}; Factura {remision["numero_factura"]}; '
                f'Depósito: {remision["deposito"]}; Responsable: {remision["responsable_traslado"]}; Ítems: ' +
                ', '.join(f'{d["item"]} x{d["cantidad"]}' for d in remision['detalle'])))
            return jsonify({'success': True, 'data': remision,
                            'mensaje': f'Remisión registrada. N.º {remision["numero_remision"]} de la factura {remision["numero_factura"]} '
                                       f'({remision["total_unidades"]} unidades).', 'error': None}), 201
        return respuesta_error('No se pudo registrar la remisión. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al registrar remisión: {str(e)}")
        return error_interno()


# -------------------------
# Anular: cualquiera con `anular`. Libera las cantidades; no mueve stock.
# -------------------------
@remisionapi.route('/remisiones/<int:id_remision>', methods=['DELETE'])
@require_permiso('remision', 'anular')
def anularRemision(id_remision):
    dao = RemisionDao()
    try:
        antes = dao.getRemisionById(id_remision)
        resultado = dao.anularRemision(id_remision)
        if resultado == NO_EXISTE:
            return respuesta_error('No se encontró la remisión con el ID proporcionado.', 404)
        if resultado == YA_ANULADA:
            return respuesta_error('La remisión ya está anulada.', 409)
        if isinstance(resultado, tuple) and resultado[0] == ERROR_BD:
            return respuesta_error(resultado[1], 409)
        if isinstance(resultado, dict):
            _auditar('nota_remision_cab', id_remision, 'BAJA',
                     f'Remisión {antes["numero_remision"]}; Cliente: {antes["cliente"]}; Factura {antes["numero_factura"]}; '
                     f'{antes["total_unidades"]} unidades; las cantidades vuelven a estar pendientes de entrega')
            return jsonify({'success': True, 'data': dao.getRemisionById(id_remision),
                            'mensaje': f'Remisión N.º {antes["numero_remision"]} de {antes["cliente"]} anulada correctamente. '
                                       f'Las cantidades quedaron pendientes de entrega.', 'error': None}), 200
        return respuesta_error('No se pudo anular la remisión. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al anular remisión: {str(e)}")
        return error_interno()
