from datetime import date
from flask import Blueprint, request, jsonify, session, Response, current_app as app
from app.dao.modulo_facturacion.nota_credito_debito.NotaCreditoDebitoDao import (
    NotaCreditoDebitoDao, EMITIDA, ANULADA, CREDITO, DEBITO, NO_EXISTE, SIN_CAJA, CUENTA_NO_EXISTE, VENTA_NO_EMITIDA, VENTA_NO_ITEMS,
    ITEM_INVALIDO, ERROR_BD, YA_ANULADA, CAJA_CERRADA, STOCK_INSUFICIENTE)
from app.Services.nota_pdf_service import generarNotaPdf
from app.rutas.modulo_facturacion.utils import (
    entero_id, validar_texto, validar_iva, validar_monto_positivo, validar_cantidad_positiva, validar_booleano, respuesta_error,
    auditar as _auditar, error_interno)
from app.rutas.modulo_seguridad.decorators import require_permiso

notacdapi = Blueprint('notacdapi', __name__)

ESTADOS = (EMITIDA, ANULADA)
TIPOS = (CREDITO, DEBITO)
MAX_RENGLONES = 30
MAX_MOTIVO = 200
MAX_DESCRIPCION = 200
ETIQUETA_TIPO = {CREDITO: 'Nota de Crédito', DEBITO: 'Nota de Débito'}
MSG_SIN_CAJA = 'Debe abrir la caja antes de registrar una nota.'
MSG_CAJA_CERRADA = 'La caja de esta nota ya fue cerrada; no se puede anular.'


def _id_usuario():
    """El cajero SIEMPRE sale de la sesión, nunca del cuerpo del pedido."""
    return session.get('id_usuario')


from app.Services.formato import formatear_gs as _gs   # 'Gs. 100.000' (helper único: app/Services/formato.py)


def _parse_fecha(valor):
    return date.fromisoformat(valor) if valor else None


def _recortar(texto, largo=255):
    return texto if len(texto) <= largo else texto[:largo - 3] + '...'


def _error_renglon(n, mensaje, status=400):
    """Error de validación de UN renglón de la grilla (fila 1-based)."""
    return respuesta_error(f'Renglón {n}: {mensaje}', status, campo='renglones', fila=n)


def _validar_renglones(crudos, devolucion):
    """Valida el arreglo `renglones` del cuerpo. Devuelve (renglones normalizados, None) o (None, respuesta de error).
    Nota libre: [{descripcion, monto, iva}]. Devolución de mercadería: [{id_item, cantidad}]."""
    if not isinstance(crudos, list) or not crudos:
        return None, respuesta_error('Debe agregar al menos un renglón a la nota.', 400, 'renglones')
    if len(crudos) > MAX_RENGLONES:
        return None, respuesta_error(f'Una nota no puede tener más de {MAX_RENGLONES} renglones.', 400, 'renglones')
    renglones, vistos = [], set()
    for n, x in enumerate(crudos, start=1):
        x = x if isinstance(x, dict) else {}
        if devolucion:
            id_item = entero_id(x.get('id_item'))
            if id_item is None:
                return None, _error_renglon(n, 'debe seleccionar el ítem.')
            if id_item in vistos:
                return None, _error_renglon(n, 'el ítem está repetido en la nota.')
            vistos.add(id_item)
            cantidad, error = validar_cantidad_positiva(x.get('cantidad'))
            if error:
                return None, _error_renglon(n, error)
            renglones.append({'id_item': id_item, 'cantidad': cantidad})
        else:
            descripcion, error = validar_texto(x.get('descripcion'), 'descripción', MAX_DESCRIPCION)
            if error:
                return None, _error_renglon(n, error)
            monto, error = validar_monto_positivo(x.get('monto'))
            if error:
                return None, _error_renglon(n, error)
            iva, error = validar_iva(x.get('iva'))
            if error:
                return None, _error_renglon(n, error)
            renglones.append({'descripcion': descripcion, 'monto': monto, 'iva': iva})
    return renglones, None


# -------------------------
# Listado: todos los usuarios con `ver` ven TODAS las notas.
# Filtros: ?estado=&tipo=&cliente=(nombre, CI/RUC, N.º de factura o de nota)&desde=&hasta=
# -------------------------
@notacdapi.route('/notas-credito-debito', methods=['GET'])
@require_permiso('notacd', 'ver')
def getNotas():
    estado = (request.args.get('estado') or '').strip().upper() or None
    if estado and estado not in ESTADOS:
        return respuesta_error('El estado debe ser EMITIDA o ANULADA.', 400)
    tipo = (request.args.get('tipo') or '').strip().upper() or None
    if tipo and tipo not in TIPOS:
        return respuesta_error('El tipo debe ser CREDITO o DEBITO.', 400)
    try:
        desde = _parse_fecha(request.args.get('desde'))
        hasta = _parse_fecha(request.args.get('hasta'))
    except ValueError:
        return respuesta_error('Las fechas deben tener el formato AAAA-MM-DD.', 400)
    if desde and hasta and desde > hasta:
        return respuesta_error('La fecha "desde" no puede ser posterior a "hasta".', 400)
    cliente = (request.args.get('cliente') or '').strip()[:80] or None
    try:
        return jsonify({'success': True, 'error': None,
                        'data': NotaCreditoDebitoDao().getNotas(estado=estado, tipo=tipo, cliente=cliente, desde=desde, hasta=hasta)}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener notas: {str(e)}")
        return error_interno()


# -------------------------
# Apoyo del formulario de Nueva Nota (piden `nuevo`)
# -------------------------
@notacdapi.route('/notas-credito-debito/caja-actual', methods=['GET'])
@require_permiso('notacd', 'nuevo')
def getCajaActual():
    try:
        return jsonify({'success': True, 'data': NotaCreditoDebitoDao().getAperturaActual(_id_usuario()), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener la caja actual: {str(e)}")
        return error_interno()


@notacdapi.route('/notas-credito-debito/facturas', methods=['GET'])
@require_permiso('notacd', 'nuevo')
def buscarFacturas():
    try:
        return jsonify({'success': True, 'data': NotaCreditoDebitoDao().buscarFacturas(request.args.get('q')), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al buscar facturas para notas: {str(e)}")
        return error_interno()


@notacdapi.route('/notas-credito-debito/facturas/<int:id_cuenta>', methods=['GET'])
@require_permiso('notacd', 'nuevo')
def getFactura(id_cuenta):
    """La factura (por su cuenta a cobrar) con total, saldo, notas previas, máximo del crédito y mercadería devolvible."""
    try:
        factura = NotaCreditoDebitoDao().getFacturaParaNota(id_cuenta)
        if factura is None:
            return respuesta_error('No se encontró la factura, o está anulada.', 404, 'id_cuenta')
        return jsonify({'success': True, 'data': factura, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener la factura para la nota: {str(e)}")
        return error_interno()


@notacdapi.route('/notas-credito-debito/<int:id_nota>', methods=['GET'])
@require_permiso('notacd', 'ver')
def getNota(id_nota):
    try:
        nota = NotaCreditoDebitoDao().getNotaById(id_nota)
        if nota is None:
            return respuesta_error('No se encontró la nota con el ID proporcionado.', 404)
        return jsonify({'success': True, 'data': nota, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener nota: {str(e)}")
        return error_interno()


# -------------------------
# Nota en PDF (al vuelo): ORIGINAL y DUPLICADO; una anulada se descarga con la marca "ANULADA".
# -------------------------
@notacdapi.route('/notas-credito-debito/<int:id_nota>/pdf', methods=['GET'])
@require_permiso('notacd', 'ver')
def getNotaPdf(id_nota):
    try:
        nota = NotaCreditoDebitoDao().getNotaById(id_nota)
        if nota is None:
            return respuesta_error('No se encontró la nota con el ID proporcionado.', 404)
        return Response(generarNotaPdf(nota), mimetype='application/pdf',
                        headers={'Content-Disposition': f'inline; filename=nota_{nota["tipo_nota"].lower()}_{nota["numero_nota"]}.pdf'})
    except Exception as e:
        app.logger.error(f"Error al generar el PDF de la nota: {str(e)}")
        return error_interno()


# -------------------------
# Nueva nota. Cuerpo: {tipo, id_cuenta, motivo, devolucion, renglones}. Nota libre: renglones [{descripcion, monto, iva}];
# devolución de mercadería (solo crédito sobre venta de ítems): renglones [{id_item, cantidad}]; el precio y el IVA salen de la
# factura. Los totales, el IVA, el reintegro y el número los calcula el servidor; el cajero y la caja salen de la sesión.
# -------------------------
@notacdapi.route('/notas-credito-debito', methods=['POST'])
@require_permiso('notacd', 'nuevo')
def addNota():
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}

    tipo = str(data.get('tipo') or '').strip().upper()
    if tipo not in TIPOS:
        return respuesta_error('Debe indicar si la nota es de crédito o de débito.', 400, 'tipo')
    id_cuenta = entero_id(data.get('id_cuenta'))
    if id_cuenta is None:
        return respuesta_error('Debe seleccionar una factura.', 400, 'id_cuenta')
    motivo, error = validar_texto(data.get('motivo'), 'motivo', MAX_MOTIVO)
    if error:
        return respuesta_error(error, 400, 'motivo')
    devolucion = False
    if data.get('devolucion') not in (None, '', False):
        devolucion, error = validar_booleano(data.get('devolucion'), 'devolución de mercadería')
        if error:
            return respuesta_error(error, 400, 'devolucion')
    if devolucion and tipo != CREDITO:
        return respuesta_error('Solo una nota de crédito puede devolver mercadería.', 400, 'devolucion')
    renglones, rechazo = _validar_renglones(data.get('renglones'), devolucion)
    if rechazo:
        return rechazo

    dao = NotaCreditoDebitoDao()
    try:
        resultado = dao.guardarNota(_id_usuario(), tipo, id_cuenta, motivo, renglones, devolucion)
        if resultado == SIN_CAJA:
            return respuesta_error(MSG_SIN_CAJA, 409)
        if resultado == CUENTA_NO_EXISTE:
            return respuesta_error('No se encontró la factura.', 404, 'id_cuenta')
        if resultado == VENTA_NO_EMITIDA:
            return respuesta_error('No se puede emitir una nota sobre una venta anulada.', 409, 'id_cuenta')
        if resultado == VENTA_NO_ITEMS:
            return respuesta_error('Solo se devuelve mercadería de ventas de ítems.', 409, 'devolucion')
        if isinstance(resultado, tuple):
            if resultado[0] == ITEM_INVALIDO:
                n = next((i for i, x in enumerate(renglones, start=1) if x.get('id_item') == resultado[1]), 1)
                return _error_renglon(n, 'el ítem no pertenece a la factura.', 409)
            if resultado[0] == ERROR_BD:
                return respuesta_error(resultado[1], 409, 'renglones')   # texto del trigger de la base, tal cual
        if resultado:
            nota = dao.getNotaById(resultado)
            detalle = ', '.join(f'{d["descripcion"]} {_gs(d["subtotal"])}' for d in nota['detalle'])
            _auditar('nota_credito_debito_cab', resultado, 'ALTA', _recortar(
                f'{ETIQUETA_TIPO[tipo]} {nota["numero_nota"]}; Cliente: {nota["cliente"]}; Factura {nota["numero_factura"]}; '
                f'Total: {_gs(nota["total"])}' + (f'; Reintegro en efectivo: {_gs(nota["monto_reintegro"])}' if nota['monto_reintegro'] else '') +
                ('; Devolución de mercadería' if nota['es_devolucion'] else '') + f'; Motivo: {nota["motivo"]}; Renglones: {detalle}'))
            extra = f' Reintegro en efectivo al cliente: {_gs(nota["monto_reintegro"])}.' if nota['monto_reintegro'] else ''
            return jsonify({'success': True, 'data': nota,
                            'mensaje': f'{ETIQUETA_TIPO[tipo]} registrada. N.º {nota["numero_nota"]} de {nota["cliente"]} por {_gs(nota["total"])}.{extra}',
                            'error': None}), 201
        return respuesta_error('No se pudo registrar la nota. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al registrar nota: {str(e)}")
        return error_interno()


# -------------------------
# Anular: cualquiera con `anular`, pero solo si la apertura de caja de la nota sigue ABIERTA.
# -------------------------
@notacdapi.route('/notas-credito-debito/<int:id_nota>', methods=['DELETE'])
@require_permiso('notacd', 'anular')
def anularNota(id_nota):
    dao = NotaCreditoDebitoDao()
    try:
        antes = dao.getNotaById(id_nota)
        resultado = dao.anularNota(id_nota)
        if resultado == NO_EXISTE:
            return respuesta_error('No se encontró la nota con el ID proporcionado.', 404)
        if resultado == YA_ANULADA:
            return respuesta_error('La nota ya está anulada.', 409)
        if resultado == CAJA_CERRADA:
            return respuesta_error(MSG_CAJA_CERRADA, 409)
        if isinstance(resultado, tuple):
            if resultado[0] == STOCK_INSUFICIENTE:
                return respuesta_error(f'No se puede anular: para deshacer la devolución de {resultado[1]} se necesitan {resultado[3]} '
                                       f'unidades en stock y hay {resultado[2]}.', 409)
            if resultado[0] == ERROR_BD:
                return respuesta_error(resultado[1], 409)
        if isinstance(resultado, dict):
            _auditar('nota_credito_debito_cab', id_nota, 'BAJA',
                     f'{ETIQUETA_TIPO[antes["tipo_nota"]]} {antes["numero_nota"]}; Cliente: {antes["cliente"]}; Factura {antes["numero_factura"]}; '
                     f'Total: {_gs(antes["total"])}; se revierte el efecto en el saldo' +
                     ('; se descuenta del stock lo devuelto' if antes['es_devolucion'] else '') +
                     (f'; el reintegro de {_gs(antes["monto_reintegro"])} vuelve a la caja' if antes['monto_reintegro'] else ''))
            return jsonify({'success': True, 'data': dao.getNotaById(id_nota),
                            'mensaje': f'{ETIQUETA_TIPO[antes["tipo_nota"]]} N.º {antes["numero_nota"]} de {antes["cliente"]} anulada correctamente. '
                                       f'Se revirtió su efecto en el saldo de la factura {antes["numero_factura"]}.', 'error': None}), 200
        return respuesta_error('No se pudo anular la nota. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al anular nota: {str(e)}")
        return error_interno()
