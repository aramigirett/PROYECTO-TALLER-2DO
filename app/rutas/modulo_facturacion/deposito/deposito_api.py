from flask import Blueprint, request, jsonify, current_app as app
from app.dao.modulo_facturacion.deposito.DepositoDao import DepositoDao, DUPLICADO, NO_EXISTE, YA_ACTIVO
from app.rutas.modulo_facturacion.utils import (
    normalizar_descripcion, validar_texto, MAX_UBICACION, detalle_cambios, respuesta_error,
    auditar as _auditar, error_interno)
from app.rutas.modulo_seguridad.decorators import require_permiso, require_login
from app.rutas.modulo_seguridad.permisos_contexto import puede

depositoapi = Blueprint('depositoapi', __name__)

ENTIDAD = 'deposito'
ETIQUETAS = {'descripcion': 'Descripción', 'ubicacion': 'Ubicación'}
MSG_DUPLICADO = 'Ya existe un depósito con esa descripción.'


def auditar(id_registro, accion, detalle):
    _auditar(ENTIDAD, id_registro, accion, detalle)


def validar_deposito(data):
    """Devuelve (datos, error, campo). La ubicación se guarda en mayúsculas."""
    data = data if isinstance(data, dict) else {}
    descripcion, error = normalizar_descripcion(data)
    if error:
        return None, error, 'descripcion'
    ubicacion, error = validar_texto(data.get('ubicacion'), 'ubicación', MAX_UBICACION, mayusculas=True)
    if error:
        return None, error, 'ubicacion'
    return {'descripcion': descripcion, 'ubicacion': ubicacion}, None, None


# -------------------------
# Trae los depósitos. Por defecto solo activos; ?inactivos=1 incluye los anulados (requiere 'ver').
# -------------------------
@depositoapi.route('/depositos', methods=['GET'])
@require_login  # lookup: alimenta combos de otras pantallas (Ítems, Notas de remisión)
def getDepositos():
    incluir_inactivos = request.args.get('inactivos', '').lower() in ('1', 'true')
    if incluir_inactivos and not puede('deposito', 'ver'):
        return respuesta_error('No tiene permiso para ver los depósitos inactivos.', 403)
    try:
        return jsonify({'success': True, 'data': DepositoDao().getDepositos(incluir_inactivos), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener depósitos: {str(e)}")
        return error_interno()


# -------------------------
# Trae un depósito activo por ID
# -------------------------
@depositoapi.route('/depositos/<int:id_deposito>', methods=['GET'])
@require_permiso('deposito', 'ver')
def getDeposito(id_deposito):
    try:
        deposito = DepositoDao().getDepositoById(id_deposito)
        if deposito:
            return jsonify({'success': True, 'data': deposito, 'error': None}), 200
        return respuesta_error('No se encontró el depósito con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al obtener depósito: {str(e)}")
        return error_interno()


# -------------------------
# Agrega un depósito
# -------------------------
@depositoapi.route('/depositos', methods=['POST'])
@require_permiso('deposito', 'nuevo')
def addDeposito():
    datos, error, campo = validar_deposito(request.get_json(silent=True))
    if error:
        return respuesta_error(error, 400, campo)

    dao = DepositoDao()
    try:
        if dao.existeDuplicado(datos['descripcion']):
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')

        nuevo_id = dao.guardarDeposito(**datos)
        if nuevo_id == DUPLICADO:
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')
        if nuevo_id:
            auditar(nuevo_id, 'ALTA', detalle_cambios({}, datos, ETIQUETAS))
            return jsonify({
                'success': True, 'data': dao.getDepositoById(nuevo_id),
                'mensaje': f'Depósito "{datos["descripcion"]}" agregado correctamente.', 'error': None
            }), 201
        return respuesta_error('No se pudo guardar el depósito. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al agregar depósito: {str(e)}")
        return error_interno()


# -------------------------
# Actualiza un depósito activo
# -------------------------
@depositoapi.route('/depositos/<int:id_deposito>', methods=['PUT'])
@require_permiso('deposito', 'editar')
def updateDeposito(id_deposito):
    datos, error, campo = validar_deposito(request.get_json(silent=True))
    if error:
        return respuesta_error(error, 400, campo)

    dao = DepositoDao()
    try:
        anterior = dao.getDepositoById(id_deposito)
        if not anterior:
            return respuesta_error('No se encontró el depósito con el ID proporcionado.', 404)

        detalle = detalle_cambios(anterior, datos, ETIQUETAS)
        if not detalle:
            # Sin cambios: no se toca la BD ni se audita.
            return jsonify({
                'success': True, 'data': anterior,
                'mensaje': f'Depósito "{datos["descripcion"]}" sin cambios.', 'error': None
            }), 200

        if dao.existeDuplicado(datos['descripcion'], excluir_id=id_deposito):
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')

        resultado = dao.updateDeposito(id_deposito, **datos)
        if resultado == DUPLICADO:
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')
        if resultado:
            auditar(id_deposito, 'MODIFICACION', detalle)
            return jsonify({
                'success': True, 'data': dao.getDepositoById(id_deposito),
                'mensaje': f'Depósito "{datos["descripcion"]}" actualizado correctamente.', 'error': None
            }), 200
        return respuesta_error('No se pudo actualizar el depósito.', 404)
    except Exception as e:
        app.logger.error(f"Error al actualizar depósito: {str(e)}")
        return error_interno()


# -------------------------
# Anula (baja lógica) un depósito
# -------------------------
@depositoapi.route('/depositos/<int:id_deposito>', methods=['DELETE'])
@require_permiso('deposito', 'anular')
def deleteDeposito(id_deposito):
    dao = DepositoDao()
    try:
        registro = dao.getDepositoById(id_deposito)
        resultado = dao.deleteDeposito(id_deposito)
        if isinstance(resultado, tuple):  # ("EN_USO", motivo)
            return respuesta_error(resultado[1], 409)
        if resultado:
            descripcion = registro['descripcion'] if registro else 'seleccionado'
            auditar(id_deposito, 'BAJA', f'Descripción: {descripcion}')
            return jsonify({'success': True, 'mensaje': f'Depósito "{descripcion}" anulado correctamente.', 'error': None}), 200
        return respuesta_error('No se encontró el depósito con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al anular depósito: {str(e)}")
        return error_interno()


# -------------------------
# Reactiva un depósito anulado (permiso: el mismo de editar)
# -------------------------
@depositoapi.route('/depositos/<int:id_deposito>/reactivar', methods=['PATCH'])
@require_permiso('deposito', 'editar')
def reactivarDeposito(id_deposito):
    dao = DepositoDao()
    try:
        resultado = dao.reactivarDeposito(id_deposito)
        if resultado == NO_EXISTE:
            return respuesta_error('No se encontró el depósito con el ID proporcionado.', 404)
        if resultado == YA_ACTIVO:
            return respuesta_error('El depósito ya está activo.', 409)
        if resultado == DUPLICADO:
            return respuesta_error('No se puede reactivar: ya existe un depósito activo con esa descripción.', 409)
        if resultado:
            deposito = dao.getDepositoById(id_deposito)
            auditar(id_deposito, 'REACTIVACION',
                    f'Descripción: {deposito["descripcion"]}; Ubicación: {deposito["ubicacion"]}')
            return jsonify({'success': True, 'data': deposito,
                            'mensaje': f'Depósito "{deposito["descripcion"]}" reactivado correctamente.',
                            'error': None}), 200
        return respuesta_error('No se pudo reactivar el depósito. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al reactivar depósito: {str(e)}")
        return error_interno()
