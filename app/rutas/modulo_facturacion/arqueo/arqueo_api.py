from datetime import date
from flask import Blueprint, request, jsonify, session, Response, current_app as app
from app.dao.modulo_facturacion.arqueo.ArqueoDao import (
    ArqueoDao, REGISTRADO, ANULADO, PENDIENTE, DEPOSITADA, ANULADA, NO_EXISTE, YA_ANULADO, RECAUDACION_DEPOSITADA, NO_PENDIENTE,
    CUENTA_INVALIDA, FECHA_ANTERIOR, ERROR_BD)
from app.Services.arqueo_pdf_service import generarArqueoPdf
from app.rutas.modulo_facturacion.utils import (
    entero_id, validar_monto, validar_observacion, validar_codigo, respuesta_error, auditar as _auditar, error_interno)
from app.rutas.modulo_seguridad.decorators import require_permiso

arqueoapi = Blueprint('arqueoapi', __name__)

ESTADOS = (REGISTRADO, ANULADO)
RESULTADOS = ('CUADRA', 'SOBRANTE', 'FALTANTE')
ESTADOS_RECAUDACION = (PENDIENTE, DEPOSITADA, ANULADA)
MAX_FORMAS = 20
MSG_PROPIA = 'No puede arquear su propia caja; el arqueo debe hacerlo otro usuario.'


def _id_usuario():
    """Quien arquea SIEMPRE sale de la sesión, nunca del cuerpo del pedido."""
    return session.get('id_usuario')


from app.Services.formato import formatear_gs as _gs   # 'Gs. 100.000' (helper único: app/Services/formato.py)


def _parse_fecha(valor):
    return date.fromisoformat(valor) if valor else None


def _recortar(texto, largo=255):
    return texto if len(texto) <= largo else texto[:largo - 3] + '...'


def _error_forma(n, mensaje, status=400):
    """Error de validación de UNA fila de la grilla de formas de cobro (fila 1-based)."""
    return respuesta_error(f'Forma {n}: {mensaje}', status, campo='formas', fila=n)


# -------------------------
# Listado: todos los usuarios con `ver` ven TODOS los arqueos.
# Filtros: ?estado=&resultado=(CUADRA|SOBRANTE|FALTANTE)&texto=(caja, cajero o arqueador)&desde=&hasta=
# -------------------------
@arqueoapi.route('/arqueos', methods=['GET'])
@require_permiso('arqueo', 'ver')
def getArqueos():
    estado = (request.args.get('estado') or '').strip().upper() or None
    if estado and estado not in ESTADOS:
        return respuesta_error('El estado debe ser REGISTRADO o ANULADO.', 400)
    resultado = (request.args.get('resultado') or '').strip().upper() or None
    if resultado and resultado not in RESULTADOS:
        return respuesta_error('El resultado debe ser CUADRA, SOBRANTE o FALTANTE.', 400)
    try:
        desde = _parse_fecha(request.args.get('desde'))
        hasta = _parse_fecha(request.args.get('hasta'))
    except ValueError:
        return respuesta_error('Las fechas deben tener el formato AAAA-MM-DD.', 400)
    if desde and hasta and desde > hasta:
        return respuesta_error('La fecha "desde" no puede ser posterior a "hasta".', 400)
    texto = (request.args.get('texto') or '').strip()[:80] or None
    try:
        return jsonify({'success': True, 'error': None,
                        'data': ArqueoDao().getArqueos(estado=estado, resultado=resultado, texto=texto, desde=desde, hasta=hasta)}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener arqueos: {str(e)}")
        return error_interno()


# -------------------------
# Apoyo del formulario de Nuevo Arqueo (piden `nuevo`)
# -------------------------
@arqueoapi.route('/arqueos/aperturas', methods=['GET'])
@require_permiso('arqueo', 'nuevo')
def getAperturasSinArqueo():
    """Aperturas CERRADAS sin arqueo, sin las del propio usuario (nadie arquea su propia caja)."""
    try:
        return jsonify({'success': True, 'data': ArqueoDao().getAperturasSinArqueo(excluir_usuario=_id_usuario()), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener aperturas sin arqueo: {str(e)}")
        return error_interno()


@arqueoapi.route('/arqueos/aperturas/<int:id_apertura>/formas', methods=['GET'])
@require_permiso('arqueo', 'nuevo')
def getFormasArqueo(id_apertura):
    """La apertura y las formas de cobro a contar con el monto del SISTEMA, calculado en la base."""
    try:
        datos = ArqueoDao().getFormasArqueo(id_apertura)
        if datos is None:
            return respuesta_error('No se encontró la apertura de caja.', 404, 'id_apertura')
        datos['propia'] = datos['id_cajero'] == _id_usuario()
        return jsonify({'success': True, 'data': datos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener las formas del arqueo: {str(e)}")
        return error_interno()


# -------------------------
# Recaudaciones a depositar
# -------------------------
@arqueoapi.route('/recaudaciones', methods=['GET'])
@require_permiso('arqueo', 'ver')
def getRecaudaciones():
    estado = (request.args.get('estado') or '').strip().upper() or None
    if estado and estado not in ESTADOS_RECAUDACION:
        return respuesta_error('El estado debe ser PENDIENTE, DEPOSITADA o ANULADA.', 400)
    try:
        return jsonify({'success': True, 'data': ArqueoDao().getRecaudaciones(estado=estado), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener recaudaciones: {str(e)}")
        return error_interno()


@arqueoapi.route('/recaudaciones/<int:id_recaudacion>/depositar', methods=['PATCH'])
@require_permiso('arqueo', 'estado')
def depositarRecaudacion(id_recaudacion):
    """Marca la recaudación como DEPOSITADA: {id_cuenta_bancaria, numero_boleta, fecha_deposito}."""
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}
    id_cuenta = entero_id(data.get('id_cuenta_bancaria'))
    if id_cuenta is None:
        return respuesta_error('Debe seleccionar la cuenta bancaria del depósito.', 400, 'id_cuenta_bancaria')
    boleta, error = validar_codigo(data.get('numero_boleta'), 'número de boleta', 30)
    if error:
        return respuesta_error(error, 400, 'numero_boleta')
    try:
        fecha = date.fromisoformat(str(data.get('fecha_deposito') or '').strip())
    except ValueError:
        return respuesta_error('La fecha del depósito no es válida (use AAAA-MM-DD).', 400, 'fecha_deposito')
    if fecha > date.today():
        return respuesta_error('La fecha del depósito no puede ser posterior a hoy.', 400, 'fecha_deposito')

    dao = ArqueoDao()
    try:
        antes = dao.getRecaudacionById(id_recaudacion)
        resultado = dao.marcarDepositada(id_recaudacion, id_cuenta, boleta, fecha)
        if resultado == NO_EXISTE:
            return respuesta_error('No se encontró la recaudación con el ID proporcionado.', 404)
        if resultado == CUENTA_INVALIDA:
            return respuesta_error('La cuenta bancaria no existe o está anulada.', 409, 'id_cuenta_bancaria')
        if resultado == FECHA_ANTERIOR:
            return respuesta_error('La fecha del depósito no puede ser anterior a la del arqueo.', 400, 'fecha_deposito')
        if isinstance(resultado, tuple):
            if resultado[0] == NO_PENDIENTE:
                return respuesta_error('La recaudación ya está depositada.' if resultado[1] == DEPOSITADA else 'La recaudación está anulada.', 409)
            if resultado[0] == ERROR_BD:
                return respuesta_error(resultado[1], 409)
        if resultado is True:
            nueva = dao.getRecaudacionById(id_recaudacion)
            _auditar('recaudacion_depositar', id_recaudacion, 'MODIFICACION',
                     f'Recaudación del arqueo {antes["id_arqueo"]} ({antes["caja"]}); Total: {_gs(antes["total"])}; Estado: PENDIENTE -> DEPOSITADA; '
                     f'Cuenta: {nueva["cuenta"]}; Boleta: {boleta}; Fecha: {fecha.strftime("%d/%m/%Y")}')
            return jsonify({'success': True, 'data': nueva,
                            'mensaje': f'Recaudación de {_gs(nueva["total"])} depositada en {nueva["cuenta"]} (boleta {boleta}).', 'error': None}), 200
        return respuesta_error('No se pudo marcar la recaudación como depositada. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al marcar la recaudación como depositada: {str(e)}")
        return error_interno()


@arqueoapi.route('/arqueos/<int:id_arqueo>', methods=['GET'])
@require_permiso('arqueo', 'ver')
def getArqueo(id_arqueo):
    try:
        arqueo = ArqueoDao().getArqueoById(id_arqueo)
        if arqueo is None:
            return respuesta_error('No se encontró el arqueo con el ID proporcionado.', 404)
        return jsonify({'success': True, 'data': arqueo, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener arqueo: {str(e)}")
        return error_interno()


# -------------------------
# Arqueo en PDF (al vuelo): ORIGINAL y DUPLICADO; uno anulado se descarga con la marca "ANULADO".
# -------------------------
@arqueoapi.route('/arqueos/<int:id_arqueo>/pdf', methods=['GET'])
@require_permiso('arqueo', 'ver')
def getArqueoPdf(id_arqueo):
    try:
        arqueo = ArqueoDao().getArqueoById(id_arqueo)
        if arqueo is None:
            return respuesta_error('No se encontró el arqueo con el ID proporcionado.', 404)
        return Response(generarArqueoPdf(arqueo), mimetype='application/pdf',
                        headers={'Content-Disposition': f'inline; filename=arqueo_{id_arqueo}.pdf'})
    except Exception as e:
        app.logger.error(f"Error al generar el PDF del arqueo: {str(e)}")
        return error_interno()


# -------------------------
# Nuevo arqueo. Cuerpo: {id_apertura, observacion, formas: [{id_forma_cobro, monto_contado}]}. El monto del sistema, las diferencias, los
# totales y la recaudación los calcula la base (sp_registrar_arqueo); quien arquea sale de la sesión.
# -------------------------
@arqueoapi.route('/arqueos', methods=['POST'])
@require_permiso('arqueo', 'nuevo')
def addArqueo():
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}

    id_apertura = entero_id(data.get('id_apertura'))
    if id_apertura is None:
        return respuesta_error('Debe seleccionar una apertura de caja.', 400, 'id_apertura')
    observacion, error = validar_observacion(data.get('observacion'))
    if error:
        return respuesta_error(error, 400, 'observacion')
    crudas = data.get('formas')
    if not isinstance(crudas, list) or not crudas:
        return respuesta_error('Debe indicar el monto contado de cada forma de cobro.', 400, 'formas')
    if len(crudas) > MAX_FORMAS:
        return respuesta_error(f'Un arqueo no puede tener más de {MAX_FORMAS} formas de cobro.', 400, 'formas')
    formas, contados, vistos = [], [], set()
    for n, x in enumerate(crudas, start=1):
        x = x if isinstance(x, dict) else {}
        id_forma = entero_id(x.get('id_forma_cobro'))
        if id_forma is None:
            return _error_forma(n, 'debe seleccionar la forma de cobro.')
        if id_forma in vistos:
            return _error_forma(n, 'la forma de cobro está repetida.')
        vistos.add(id_forma)
        monto, error = validar_monto(x.get('monto_contado'))
        if error:
            return _error_forma(n, error)
        formas.append(id_forma); contados.append(monto)

    dao = ArqueoDao()
    try:
        apertura = dao.getFormasArqueo(id_apertura)
        if apertura is None:
            return respuesta_error('No se encontró la apertura de caja.', 404, 'id_apertura')
        if apertura['id_cajero'] == _id_usuario():
            return respuesta_error(MSG_PROPIA, 409, 'id_apertura')
        resultado = dao.registrarArqueo(id_apertura, _id_usuario(), formas, contados, observacion)
        if isinstance(resultado, tuple) and resultado[0] == ERROR_BD:
            mensaje = resultado[1]
            campo = 'observacion' if 'observación' in mensaje else ('formas' if ('forma' in mensaje or 'montos' in mensaje) else 'id_apertura')
            return respuesta_error(mensaje, 409 if campo == 'id_apertura' else 400, campo)
        if isinstance(resultado, tuple):
            id_arqueo, id_recaudacion = resultado
            arqueo = dao.getArqueoById(id_arqueo)
            _auditar('arqueo_caja', id_arqueo, 'ALTA', _recortar(
                f'Caja: {arqueo["caja"]}; Cajero: {arqueo["cajero"]}; Total sistema: {_gs(arqueo["total_sistema"])}; Total contado: {_gs(arqueo["total_contado"])}; '
                f'Resultado: {arqueo["resultado"]}' + (f' ({_gs(arqueo["diferencia"])})' if arqueo['diferencia'] else '') +
                (f'; Recaudación a depositar: {_gs(arqueo["recaudacion"]["total"])}' if arqueo['recaudacion'] else '; Sin recaudación a depositar') +
                (f'; Observación: {arqueo["observacion"]}' if arqueo['observacion'] else '')))
            extra = (f' Recaudación a depositar: {_gs(arqueo["recaudacion"]["total"])}.' if arqueo['recaudacion'] else ' No hay recaudación a depositar.')
            return jsonify({'success': True, 'data': arqueo,
                            'mensaje': f'Arqueo registrado: {arqueo["resultado"].lower()}' + (f' ({_gs(abs(arqueo["diferencia"]))})' if arqueo['diferencia'] else '') + f'.{extra}',
                            'error': None}), 201
        return respuesta_error('No se pudo registrar el arqueo. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al registrar arqueo: {str(e)}")
        return error_interno()


# -------------------------
# Anular: cualquiera con `anular`, solo si la recaudación del arqueo sigue PENDIENTE (la anula también).
# -------------------------
@arqueoapi.route('/arqueos/<int:id_arqueo>', methods=['DELETE'])
@require_permiso('arqueo', 'anular')
def anularArqueo(id_arqueo):
    dao = ArqueoDao()
    try:
        antes = dao.getArqueoById(id_arqueo)
        resultado = dao.anularArqueo(id_arqueo)
        if resultado == NO_EXISTE:
            return respuesta_error('No se encontró el arqueo con el ID proporcionado.', 404)
        if resultado == YA_ANULADO:
            return respuesta_error('El arqueo ya está anulado.', 409)
        if resultado == RECAUDACION_DEPOSITADA:
            return respuesta_error('No se puede anular el arqueo: su recaudación ya fue depositada.', 409)
        if isinstance(resultado, tuple) and resultado[0] == ERROR_BD:
            return respuesta_error(resultado[1], 409)
        if isinstance(resultado, dict):
            _auditar('arqueo_caja', id_arqueo, 'BAJA',
                     f'Caja: {antes["caja"]}; Cajero: {antes["cajero"]}; Total contado: {_gs(antes["total_contado"])}' +
                     ('; se anula también su recaudación a depositar' if resultado['recaudacion_anulada'] else '') +
                     '; la apertura puede arquearse de nuevo')
            return jsonify({'success': True, 'data': dao.getArqueoById(id_arqueo),
                            'mensaje': f'Arqueo de la caja {antes["caja"]} anulado correctamente.' +
                                       (' Su recaudación a depositar también quedó anulada.' if resultado['recaudacion_anulada'] else ''), 'error': None}), 200
        return respuesta_error('No se pudo anular el arqueo. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al anular arqueo: {str(e)}")
        return error_interno()
