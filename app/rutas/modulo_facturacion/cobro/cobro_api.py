from datetime import date
from flask import Blueprint, request, jsonify, session, Response, current_app as app
from app.dao.modulo_facturacion.cobro.CobroDao import (
    CobroDao, EMITIDO, ANULADO, NO_EXISTE, SIN_CAJA, CUENTA_NO_EXISTE, CUENTA_NO_PENDIENTE, SALDO_EXCEDIDO, FORMA_INVALIDA,
    FORMA_SIN_TIPO, FORMA_CAMBIO, ADHERIDA_INVALIDA, EMISORA_INVALIDA, ERROR_BD, YA_ANULADO, CAJA_CERRADA)
from app.Services.recibo_pdf_service import generarReciboPdf
from app.rutas.modulo_facturacion.utils import (
    entero_id, validar_monto_positivo, validar_codigo, validar_ultimos_digitos, validar_nombre, validar_observacion,
    respuesta_error, auditar as _auditar, error_interno)
from app.rutas.modulo_seguridad.decorators import require_permiso

cobroapi = Blueprint('cobroapi', __name__)

ESTADOS = (EMITIDO, ANULADO)
MAX_FORMAS = 10
MSG_SIN_CAJA = 'Debe abrir la caja antes de registrar un cobro.'
MSG_CAJA_CERRADA = 'La caja de este cobro ya fue cerrada; utilice una Nota de Crédito.'


def _id_usuario():
    """El cajero SIEMPRE sale de la sesión, nunca del cuerpo del pedido."""
    return session.get('id_usuario')


from app.Services.formato import formatear_gs as _gs   # 'Gs. 100.000' (helper único: app/Services/formato.py)


def _parse_fecha(valor):
    return date.fromisoformat(valor) if valor else None


def _recortar(texto, largo=255):
    return texto if len(texto) <= largo else texto[:largo - 3] + '...'


def _error_forma(n, mensaje, status=400):
    """Error de validación de UNA fila de la grilla de formas de cobro (fila 1-based)."""
    return respuesta_error(f'Forma {n}: {mensaje}', status, campo='formas', fila=n)


def _tipo_tarjeta_de(descripcion):
    """Crédito o débito deducido de la descripción de la forma ('TARJETA DE DÉBITO'); None si no se puede deducir."""
    d = (descripcion or '').upper().replace('É', 'E')
    if 'DEBITO' in d:
        return 'DEBITO'
    if 'CREDITO' in d:
        return 'CREDITO'
    return None


def _fecha(valor, nombre):
    """date desde 'AAAA-MM-DD' o (None, mensaje)."""
    try:
        return date.fromisoformat(str(valor or '').strip()), None
    except ValueError:
        return None, f'La fecha de {nombre} no es válida (use AAAA-MM-DD).'


def _validar_formas(dao, crudas):
    """Valida el arreglo `formas` del cuerpo. Devuelve (formas normalizadas, None) o (None, respuesta de error)."""
    if not isinstance(crudas, list) or not crudas:
        return None, respuesta_error('Debe agregar al menos una forma de cobro.', 400, 'formas')
    if len(crudas) > MAX_FORMAS:
        return None, respuesta_error(f'Un cobro no puede tener más de {MAX_FORMAS} formas de cobro.', 400, 'formas')
    ids = []
    for n, f in enumerate(crudas, start=1):
        i = entero_id((f or {}).get('id_forma_cobro') if isinstance(f, dict) else None)
        if i is None:
            return None, _error_forma(n, 'debe seleccionar la forma de cobro.')
        ids.append(i)
    vigentes = dao.getFormasPorIds(set(ids))

    formas, hoy = [], date.today()
    for n, (f, id_forma) in enumerate(zip(crudas, ids), start=1):
        v = vigentes.get(id_forma)
        if v is None or not v['activo']:
            return None, _error_forma(n, 'la forma de cobro no existe o está inactiva.')
        if v['tipo'] is None:
            return None, _error_forma(n, f'la forma de cobro {v["descripcion"]} no tiene tipo asignado.')
        monto, error = validar_monto_positivo(f.get('monto'))
        if error:
            return None, _error_forma(n, error)
        item = {'id_forma_cobro': id_forma, 'tipo': v['tipo'], 'monto': monto, 'numero_referencia': None,
                'tarjeta': None, 'cheque': None, 'descripcion': v['descripcion']}

        if v['tipo'] == 'TRANSFERENCIA':
            item['numero_referencia'], error = validar_codigo(f.get('numero_referencia'), 'número de referencia', 30)
            if error:
                return None, _error_forma(n, error)
        elif v['tipo'] == 'TARJETA':
            t = f.get('tarjeta') if isinstance(f.get('tarjeta'), dict) else {}
            adherida = entero_id(t.get('id_entidad_adherida'))
            if adherida is None:
                return None, _error_forma(n, 'debe seleccionar la entidad adherida.')
            deducido = _tipo_tarjeta_de(v['descripcion'])
            tipo_tarjeta = str(t.get('tipo_tarjeta') or deducido or '').strip().upper()
            if tipo_tarjeta not in ('CREDITO', 'DEBITO'):
                return None, _error_forma(n, 'el tipo de tarjeta debe ser Crédito o Débito.')
            if deducido and tipo_tarjeta != deducido:
                return None, _error_forma(n, 'el tipo de tarjeta no coincide con la forma de cobro seleccionada.')
            digitos, error = validar_ultimos_digitos(t.get('ultimos_digitos'))
            if error:
                return None, _error_forma(n, error)
            autorizacion, error = validar_codigo(t.get('numero_autorizacion'), 'número de autorización', 20)
            if error:
                return None, _error_forma(n, error)
            item['tarjeta'] = {'id_entidad_adherida': adherida, 'tipo_tarjeta': tipo_tarjeta,
                               'ultimos_digitos': digitos, 'numero_autorizacion': autorizacion}
        elif v['tipo'] == 'CHEQUE':
            c = f.get('cheque') if isinstance(f.get('cheque'), dict) else {}
            emisora = entero_id(c.get('id_entidad_emisora'))
            if emisora is None:
                return None, _error_forma(n, 'debe seleccionar la entidad emisora del cheque.')
            numero, error = validar_codigo(c.get('numero_cheque'), 'número de cheque', 20)
            if error:
                return None, _error_forma(n, error)
            titular, error = validar_nombre(c.get('titular'), 'titular', True, max_len=100)
            if error:
                return None, _error_forma(n, error)
            emision, error = _fecha(c.get('fecha_emision'), 'emisión')
            if error:
                return None, _error_forma(n, error)
            cobro, error = _fecha(c.get('fecha_cobro'), 'cobro')
            if error:
                return None, _error_forma(n, error)
            if emision > hoy:
                return None, _error_forma(n, 'la fecha de emisión del cheque no puede ser posterior a hoy.')
            if cobro < emision:   # cheque diferido: la fecha de cobro puede ser futura, pero no anterior a la emisión
                return None, _error_forma(n, 'la fecha de cobro no puede ser anterior a la de emisión.')
            item['cheque'] = {'id_entidad_emisora': emisora, 'numero_cheque': numero, 'titular': titular,
                              'fecha_emision': emision, 'fecha_cobro': cobro}
        formas.append(item)
    return formas, None


# -------------------------
# Listado: todos los usuarios con `ver` ven TODOS los cobros.
# Filtros: ?estado=&cliente=(nombre, CI/RUC, N.º de factura o de recibo)&desde=&hasta=
# -------------------------
@cobroapi.route('/cobros', methods=['GET'])
@require_permiso('cobro', 'ver')
def getCobros():
    estado = (request.args.get('estado') or '').strip().upper() or None
    if estado and estado not in ESTADOS:
        return respuesta_error('El estado debe ser EMITIDO o ANULADO.', 400)
    try:
        desde = _parse_fecha(request.args.get('desde'))
        hasta = _parse_fecha(request.args.get('hasta'))
    except ValueError:
        return respuesta_error('Las fechas deben tener el formato AAAA-MM-DD.', 400)
    if desde and hasta and desde > hasta:
        return respuesta_error('La fecha "desde" no puede ser posterior a "hasta".', 400)
    cliente = (request.args.get('cliente') or '').strip()[:80] or None
    try:
        return jsonify({'success': True, 'data': CobroDao().getCobros(estado=estado, cliente=cliente, desde=desde, hasta=hasta),
                        'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener cobros: {str(e)}")
        return error_interno()


# -------------------------
# Apoyo del formulario de Nuevo Cobro (piden `nuevo`)
# -------------------------
@cobroapi.route('/cobros/caja-actual', methods=['GET'])
@require_permiso('cobro', 'nuevo')
def getCajaActual():
    try:
        return jsonify({'success': True, 'data': CobroDao().getAperturaActual(_id_usuario()), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener la caja actual: {str(e)}")
        return error_interno()


@cobroapi.route('/cobros/cuentas', methods=['GET'])
@require_permiso('cobro', 'nuevo')
def buscarCuentas():
    try:
        return jsonify({'success': True, 'data': CobroDao().buscarCuentas(request.args.get('q')), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al buscar cuentas a cobrar: {str(e)}")
        return error_interno()


@cobroapi.route('/cobros/cuentas/<int:id_cuenta>', methods=['GET'])
@require_permiso('cobro', 'nuevo')
def getCuenta(id_cuenta):
    """Una cuenta a cobrar (de cualquier estado), para precargar el cobro desde "¿Cobrar ahora?" de la venta."""
    try:
        cuenta = CobroDao().getCuentaById(id_cuenta)
        if cuenta is None:
            return respuesta_error('No se encontró la cuenta a cobrar.', 404)
        return jsonify({'success': True, 'data': cuenta, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener la cuenta a cobrar: {str(e)}")
        return error_interno()


@cobroapi.route('/cobros/formas', methods=['GET'])
@require_permiso('cobro', 'nuevo')
def getFormas():
    try:
        return jsonify({'success': True, 'data': CobroDao().getFormasCobro(), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener formas de cobro: {str(e)}")
        return error_interno()


@cobroapi.route('/cobros/adheridas', methods=['GET'])
@require_permiso('cobro', 'nuevo')
def getAdheridas():
    try:
        return jsonify({'success': True, 'data': CobroDao().getAdheridas(), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener entidades adheridas: {str(e)}")
        return error_interno()


@cobroapi.route('/cobros/emisoras', methods=['GET'])
@require_permiso('cobro', 'nuevo')
def getEmisoras():
    try:
        return jsonify({'success': True, 'data': CobroDao().getEmisoras(), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener entidades emisoras: {str(e)}")
        return error_interno()


@cobroapi.route('/cobros/<int:id_cobro>', methods=['GET'])
@require_permiso('cobro', 'ver')
def getCobro(id_cobro):
    try:
        cobro = CobroDao().getCobroById(id_cobro)
        if cobro is None:
            return respuesta_error('No se encontró el cobro con el ID proporcionado.', 404)
        return jsonify({'success': True, 'data': cobro, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener cobro: {str(e)}")
        return error_interno()


# -------------------------
# Recibo de dinero en PDF (al vuelo): ORIGINAL y DUPLICADO; un cobro anulado se descarga con la marca "ANULADO".
# -------------------------
@cobroapi.route('/cobros/<int:id_cobro>/pdf', methods=['GET'])
@require_permiso('cobro', 'ver')
def getCobroPdf(id_cobro):
    try:
        cobro = CobroDao().getCobroById(id_cobro)
        if cobro is None:
            return respuesta_error('No se encontró el cobro con el ID proporcionado.', 404)
        return Response(generarReciboPdf(cobro), mimetype='application/pdf',
                        headers={'Content-Disposition': f'inline; filename=recibo_{cobro["numero_recibo"]}.pdf'})
    except Exception as e:
        app.logger.error(f"Error al generar el PDF del recibo: {str(e)}")
        return error_interno()


# -------------------------
# Nuevo cobro. Cuerpo: {id_cuenta, observacion, formas: [{id_forma_cobro, monto, numero_referencia | tarjeta{} | cheque{}}]}.
# El total es la suma de las formas (no se acepta un total aparte); el cajero y la caja salen de la sesión.
# -------------------------
@cobroapi.route('/cobros', methods=['POST'])
@require_permiso('cobro', 'nuevo')
def addCobro():
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}

    id_cuenta = entero_id(data.get('id_cuenta'))
    if id_cuenta is None:
        return respuesta_error('Debe seleccionar una cuenta a cobrar.', 400, 'id_cuenta')
    observacion, error = validar_observacion(data.get('observacion'))
    if error:
        return respuesta_error(error, 400, 'observacion')
    dao = CobroDao()
    formas, rechazo = _validar_formas(dao, data.get('formas'))
    if rechazo:
        return rechazo

    try:
        resultado = dao.guardarCobro(_id_usuario(), id_cuenta, observacion, formas)
        if resultado == SIN_CAJA:
            return respuesta_error(MSG_SIN_CAJA, 409)
        if resultado == CUENTA_NO_EXISTE:
            return respuesta_error('No se encontró la cuenta a cobrar.', 404, 'id_cuenta')
        if resultado == FORMA_CAMBIO:
            return respuesta_error('Una forma de cobro cambió mientras se registraba el cobro. Intente nuevamente.', 409, 'formas')
        if isinstance(resultado, tuple):
            codigo = resultado[0]
            if codigo == CUENTA_NO_PENDIENTE:
                return respuesta_error('La cuenta a cobrar ya está pagada.' if resultado[1] == 'PAGADA'
                                       else 'La cuenta a cobrar está anulada.', 409, 'id_cuenta')
            if codigo == SALDO_EXCEDIDO:
                return respuesta_error(f'El monto supera el saldo pendiente de {_gs(resultado[1])}.', 409, 'formas')
            if codigo == FORMA_INVALIDA:
                return _error_forma(resultado[1], 'la forma de cobro no existe o está inactiva.', 409)
            if codigo == FORMA_SIN_TIPO:
                return respuesta_error(f'La forma de cobro {resultado[1]} no tiene tipo asignado.', 409, 'formas')
            if codigo == ADHERIDA_INVALIDA:
                motivo = {'adherida': 'la entidad adherida', 'marca': 'la marca de la tarjeta', 'emisora': 'la entidad emisora'}[resultado[2]]
                return _error_forma(resultado[1], f'{motivo} no existe o está inactiva.', 409)
            if codigo == EMISORA_INVALIDA:
                return _error_forma(resultado[1], 'la entidad emisora del cheque no existe o está inactiva.', 409)
            if codigo == ERROR_BD:
                return respuesta_error(resultado[1], 409)   # texto del trigger de la base, tal cual
        if resultado:
            cobro = dao.getCobroById(resultado)
            _auditar('cobro_cab', resultado, 'ALTA', _recortar(
                f'Recibo {cobro["numero_recibo"]}; Cliente: {cobro["cliente"]}; Factura {cobro["numero_factura"]}; '
                f'Total: {_gs(cobro["total"])}; Formas: ' + ', '.join(f'{d["forma_cobro"]} {_gs(d["monto"])}' for d in cobro['detalle'])))
            return jsonify({'success': True, 'data': cobro,
                            'mensaje': f'Cobro registrado. Recibo N.º {cobro["numero_recibo"]} de {cobro["cliente"]} por {_gs(cobro["total"])}.',
                            'error': None}), 201
        return respuesta_error('No se pudo registrar el cobro. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al registrar cobro: {str(e)}")
        return error_interno()


# -------------------------
# Anular: cualquiera con `anular`, pero solo si la apertura de caja del cobro sigue ABIERTA.
# -------------------------
@cobroapi.route('/cobros/<int:id_cobro>', methods=['DELETE'])
@require_permiso('cobro', 'anular')
def anularCobro(id_cobro):
    dao = CobroDao()
    try:
        antes = dao.getCobroById(id_cobro)
        resultado = dao.anularCobro(id_cobro)
        if resultado == NO_EXISTE:
            return respuesta_error('No se encontró el cobro con el ID proporcionado.', 404)
        if resultado == YA_ANULADO:
            return respuesta_error('El cobro ya está anulado.', 409)
        if resultado == CAJA_CERRADA:
            return respuesta_error(MSG_CAJA_CERRADA, 409)
        if isinstance(resultado, tuple) and resultado[0] == ERROR_BD:
            return respuesta_error(resultado[1], 409)
        if isinstance(resultado, dict):
            _auditar('cobro_cab', id_cobro, 'BAJA',
                     f'Recibo {antes["numero_recibo"]}; Cliente: {antes["cliente"]}; Factura {antes["numero_factura"]}; '
                     f'Total: {_gs(antes["total"])}; el saldo de la factura se repone')
            return jsonify({'success': True, 'data': dao.getCobroById(id_cobro),
                            'mensaje': f'Recibo N.º {antes["numero_recibo"]} de {antes["cliente"]} anulado correctamente. '
                                       f'El saldo de la factura {antes["numero_factura"]} se repuso.', 'error': None}), 200
        return respuesta_error('No se pudo anular el cobro. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al anular cobro: {str(e)}")
        return error_interno()
