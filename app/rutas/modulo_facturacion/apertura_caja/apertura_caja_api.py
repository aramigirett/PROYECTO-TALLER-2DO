from datetime import date
from flask import Blueprint, request, jsonify, session, current_app as app
from app.dao.modulo_facturacion.apertura_caja.AperturaCajaDao import (
    AperturaCajaDao, ABIERTA, CERRADA, ANULADA, NO_EXISTE, SIN_PERMISO_PROPIO, NO_ABIERTA,
    CAJA_INVALIDA, USUARIO_YA_ABIERTO, CAJA_ABIERTA)
from app.rutas.modulo_facturacion.utils import (
    entero_id, validar_monto, respuesta_error, auditar as _auditar, error_interno)
from app.rutas.modulo_seguridad.decorators import require_permiso

aperturacajaapi = Blueprint('aperturacajaapi', __name__)

ENTIDAD = 'apertura_cierre_caja'
ESTADOS = (ABIERTA, CERRADA, ANULADA)
MSG_MONTO = 'El monto de apertura debe ser un número entero mayor o igual a 0.'
MSG_USUARIO_YA_ABIERTO = 'Debe cerrar la apertura actual antes de abrir una nueva.'
MSG_CAJA_ABIERTA = 'La caja ya está abierta por otro usuario.'
MSG_CAJA_INVALIDA = 'La caja seleccionada no existe o está inactiva.'


def auditar(id_registro, accion, detalle):
    _auditar(ENTIDAD, id_registro, accion, detalle)


def _es_admin():
    return session.get('nombre_rol') == 'Administrador'


def _id_usuario():
    """El cajero SIEMPRE sale de la sesión, nunca del cuerpo del pedido."""
    return session.get('id_usuario')


def _gs(n):
    return 'Gs. ' + f'{int(n):,}'.replace(',', '.')


def _parse_fecha(valor):
    """date desde 'YYYY-MM-DD'; None si viene vacío; ValueError si el formato es inválido."""
    return date.fromisoformat(valor) if valor else None


def _detalle(a):
    return (f'Caja: {a["caja"]}; Consultorio: {a["consultorio"]}; Cajero: {a["cajero"]}; '
            f'Monto de apertura: {_gs(a["monto_apertura"])}')


def _respuesta_por_resultado(resultado, accion):
    """Traduce los códigos de error del DAO (anular/cerrar). None si no es un código de error."""
    if resultado == NO_EXISTE:
        return respuesta_error('No se encontró la apertura de caja con el ID proporcionado.', 404)
    if resultado == SIN_PERMISO_PROPIO:
        return respuesta_error(f'Solo el cajero que abrió la caja (o un Administrador) puede {accion} la apertura.', 403)
    if isinstance(resultado, tuple) and resultado[0] == NO_ABIERTA:
        return respuesta_error(f'La apertura ya no está abierta (estado: {resultado[1]}).', 409)
    if isinstance(resultado, tuple) and resultado[0] == 'EN_USO':
        return respuesta_error(resultado[1], 409)
    return None


# -------------------------
# Listado. El Administrador ve todas; el resto solo las propias (filtro en el servidor).
# Filtros: ?estado=ABIERTA|CERRADA|ANULADA&desde=AAAA-MM-DD&hasta=AAAA-MM-DD (ambos inclusive)
# -------------------------
@aperturacajaapi.route('/aperturas-caja', methods=['GET'])
@require_permiso('aperturacaja', 'ver')
def getAperturas():
    estado = (request.args.get('estado') or '').strip().upper() or None
    if estado and estado not in ESTADOS:
        return respuesta_error('El estado debe ser ABIERTA, CERRADA o ANULADA.', 400)
    try:
        desde = _parse_fecha(request.args.get('desde'))
        hasta = _parse_fecha(request.args.get('hasta'))
    except ValueError:
        return respuesta_error('Las fechas deben tener el formato AAAA-MM-DD.', 400)
    if desde and hasta and desde > hasta:
        return respuesta_error('La fecha "desde" no puede ser posterior a "hasta".', 400)
    try:
        aperturas = AperturaCajaDao().getAperturas(
            id_usuario=None if _es_admin() else _id_usuario(), estado=estado, desde=desde, hasta=hasta)
        return jsonify({'success': True, 'data': aperturas, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener aperturas de caja: {str(e)}")
        return error_interno()


# -------------------------
# La apertura ABIERTA del cajero de la sesión (alimenta la tarjeta de arriba); data = null si no tiene
# -------------------------
@aperturacajaapi.route('/aperturas-caja/actual', methods=['GET'])
@require_permiso('aperturacaja', 'ver')
def getAperturaActual():
    try:
        return jsonify({'success': True, 'data': AperturaCajaDao().getActualDeUsuario(_id_usuario()), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener la apertura actual: {str(e)}")
        return error_interno()


# -------------------------
# Cajas activas que no están abiertas (combo del modal de apertura)
# -------------------------
@aperturacajaapi.route('/aperturas-caja/cajas-disponibles', methods=['GET'])
@require_permiso('aperturacaja', 'nuevo')
def getCajasDisponibles():
    try:
        return jsonify({'success': True, 'data': AperturaCajaDao().getCajasDisponibles(), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener cajas disponibles: {str(e)}")
        return error_interno()


# -------------------------
# Abrir caja
# -------------------------
@aperturacajaapi.route('/aperturas-caja', methods=['POST'])
@require_permiso('aperturacaja', 'nuevo')
def addApertura():
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}

    id_caja = entero_id(data.get('id_caja'))
    if id_caja is None:
        return respuesta_error('Debe seleccionar una caja.', 400, 'id_caja')
    monto, error = validar_monto(data.get('monto_apertura'))
    if error:
        return respuesta_error(MSG_MONTO, 400, 'monto_apertura')

    dao = AperturaCajaDao()
    try:
        nuevo_id = dao.abrirCaja(_id_usuario(), id_caja, monto)
        if nuevo_id == CAJA_INVALIDA:
            return respuesta_error(MSG_CAJA_INVALIDA, 400, 'id_caja')
        if nuevo_id == USUARIO_YA_ABIERTO:
            return respuesta_error(MSG_USUARIO_YA_ABIERTO, 409)
        if nuevo_id == CAJA_ABIERTA:
            return respuesta_error(MSG_CAJA_ABIERTA, 409, 'id_caja')
        if nuevo_id:
            apertura = dao.getAperturaById(nuevo_id)
            auditar(nuevo_id, 'ALTA', _detalle(apertura))
            return jsonify({'success': True, 'data': apertura,
                            'mensaje': f'Caja "{apertura["caja"]}" abierta correctamente.', 'error': None}), 201
        return respuesta_error('No se pudo abrir la caja. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al abrir caja: {str(e)}")
        return error_interno()


# -------------------------
# Anular una apertura ABIERTA (la propia, o cualquiera si es Administrador)
# -------------------------
@aperturacajaapi.route('/aperturas-caja/<int:id_apertura>', methods=['DELETE'])
@require_permiso('aperturacaja', 'anular')
def anularApertura(id_apertura):
    dao = AperturaCajaDao()
    try:
        antes = dao.getAperturaById(id_apertura)
        resultado = dao.anularApertura(id_apertura, _id_usuario(), _es_admin())
        rechazo = _respuesta_por_resultado(resultado, 'anular')
        if rechazo:
            return rechazo
        if resultado:
            auditar(id_apertura, 'BAJA', _detalle(antes))
            return jsonify({'success': True, 'data': dao.getAperturaById(id_apertura),
                            'mensaje': f'Apertura de la caja "{antes["caja"]}" anulada correctamente.', 'error': None}), 200
        return respuesta_error('No se pudo anular la apertura. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al anular apertura de caja: {str(e)}")
        return error_interno()


# -------------------------
# Detalle previo al cierre: monto de apertura + total recaudado = monto de cierre (lo calcula el servidor)
# -------------------------
@aperturacajaapi.route('/aperturas-caja/<int:id_apertura>/cierre', methods=['GET'])
@require_permiso('aperturacaja', 'estado')
def previewCierre(id_apertura):
    dao = AperturaCajaDao()
    try:
        resultado = dao.previewCierre(id_apertura, _id_usuario(), _es_admin())
        rechazo = _respuesta_por_resultado(resultado, 'cerrar')
        if rechazo:
            return rechazo
        if isinstance(resultado, dict):
            apertura = dao.getAperturaById(id_apertura)
            return jsonify({'success': True, 'data': {**resultado, 'caja': apertura['caja'],
                                                      'consultorio': apertura['consultorio'],
                                                      'cajero': apertura['cajero']}, 'error': None}), 200
        return error_interno()
    except Exception as e:
        app.logger.error(f"Error al calcular el cierre de caja: {str(e)}")
        return error_interno()


# -------------------------
# Cerrar la caja (los importes no vienen del cliente: se recalculan en el servidor)
# -------------------------
@aperturacajaapi.route('/aperturas-caja/<int:id_apertura>/cerrar', methods=['PATCH'])
@require_permiso('aperturacaja', 'estado')
def cerrarApertura(id_apertura):
    dao = AperturaCajaDao()
    try:
        resultado = dao.cerrarApertura(id_apertura, _id_usuario(), _es_admin())
        rechazo = _respuesta_por_resultado(resultado, 'cerrar')
        if rechazo:
            return rechazo
        if isinstance(resultado, dict):
            apertura = dao.getAperturaById(id_apertura)
            auditar(id_apertura, 'CIERRE',
                    f'Caja: {apertura["caja"]}; Cajero: {apertura["cajero"]}; '
                    f'Monto de apertura: {_gs(resultado["monto_apertura"])}; '
                    f'Total recaudado: {_gs(resultado["total_recaudado"])}; '
                    f'Monto de cierre: {_gs(resultado["monto_cierre"])}')
            return jsonify({'success': True, 'data': apertura,
                            'mensaje': f'Caja "{apertura["caja"]}" cerrada correctamente. '
                                       f'Monto de cierre: {_gs(resultado["monto_cierre"])}.', 'error': None}), 200
        return respuesta_error('No se pudo cerrar la caja. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al cerrar la caja: {str(e)}")
        return error_interno()
