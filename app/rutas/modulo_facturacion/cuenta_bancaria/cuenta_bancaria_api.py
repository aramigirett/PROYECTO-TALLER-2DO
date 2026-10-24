from flask import Blueprint, request, jsonify, current_app as app
from app.rutas.modulo_seguridad.permisos_contexto import puede
from app.dao.modulo_facturacion.cuenta_bancaria.CuentaBancariaDao import (
    CuentaBancariaDao, DUPLICADO, EMISORA_INVALIDA, NO_EXISTE, YA_ACTIVO, EMISORA_INACTIVA, TIPOS_CUENTA)
from app.rutas.modulo_facturacion.utils import (
    entero_id, validar_numero_cuenta, validar_nombre, detalle_cambios, respuesta_error, auditar as _auditar, error_interno)
from app.rutas.modulo_seguridad.decorators import require_permiso, require_login

cuentabancariaapi = Blueprint('cuentabancariaapi', __name__)

ENTIDAD = 'cuenta_bancaria'
ETIQUETAS = {'entidad_emisora': 'Banco', 'tipo_cuenta': 'Tipo', 'numero_cuenta': 'Número', 'titular': 'Titular'}
MSG_DUPLICADO = 'Ya existe una cuenta activa de ese banco con ese número.'
MSG_EMISORA = 'El banco seleccionado no existe o está anulado.'
MSG_TIPO = 'El tipo de cuenta debe ser Corriente o Caja de ahorro.'


def auditar(id_registro, accion, detalle):
    _auditar(ENTIDAD, id_registro, accion, detalle)


def validar_cuenta(data):
    """Devuelve (datos, error, campo): banco como entero, tipo, número (dígitos y guiones) y titular en MAYÚSCULAS."""
    data = data if isinstance(data, dict) else {}
    id_emisora = entero_id(data.get('id_entidad_emisora'))
    if id_emisora is None:
        return None, 'Debe seleccionar un banco (entidad emisora).', 'id_entidad_emisora'
    tipo = str(data.get('tipo_cuenta') or '').strip().upper()
    if tipo not in TIPOS_CUENTA:
        return None, MSG_TIPO, 'tipo_cuenta'
    numero, error = validar_numero_cuenta(data.get('numero_cuenta'))
    if error:
        return None, error, 'numero_cuenta'
    titular, error = validar_nombre(data.get('titular'), 'titular', True)
    if error:
        return None, error, 'titular'
    return {'id_entidad_emisora': id_emisora, 'tipo_cuenta': tipo, 'numero_cuenta': numero, 'titular': titular}, None, None


def respuesta_por_codigo(codigo):
    """Traduce los códigos de error del DAO a respuesta HTTP. None si no es un código de error."""
    if codigo == DUPLICADO:
        return respuesta_error(MSG_DUPLICADO, 400, 'numero_cuenta')
    if codigo == EMISORA_INVALIDA:
        return respuesta_error(MSG_EMISORA, 400, 'id_entidad_emisora')
    if isinstance(codigo, tuple) and codigo[0] == 'EN_USO':
        return respuesta_error(codigo[1], 409, 'numero_cuenta')
    return None


def _detalle(registro):
    return {k: registro.get(k) for k in ETIQUETAS}


# -------------------------
# Cuentas activas (alimenta combos de otras pantallas, p. ej. "Marcar depositada"); `?inactivos=1` exige `ver`
# -------------------------
@cuentabancariaapi.route('/cuentas-bancarias', methods=['GET'])
@require_login
def getCuentasBancarias():
    incluir_inactivos = request.args.get('inactivos', '').lower() in ('1', 'true')
    if incluir_inactivos and not puede('cuentabancaria', 'ver'):
        return respuesta_error('No tiene permiso para ver las cuentas bancarias inactivas.', 403)
    try:
        return jsonify({'success': True, 'data': CuentaBancariaDao().getCuentasBancarias(incluir_inactivos), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener cuentas bancarias: {str(e)}")
        return error_interno()


@cuentabancariaapi.route('/cuentas-bancarias/<int:id_cuenta_bancaria>', methods=['GET'])
@require_permiso('cuentabancaria', 'ver')
def getCuentaBancaria(id_cuenta_bancaria):
    try:
        cuenta = CuentaBancariaDao().getCuentaBancariaById(id_cuenta_bancaria)
        if cuenta:
            return jsonify({'success': True, 'data': cuenta, 'error': None}), 200
        return respuesta_error('No se encontró la cuenta bancaria con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al obtener cuenta bancaria: {str(e)}")
        return error_interno()


@cuentabancariaapi.route('/cuentas-bancarias', methods=['POST'])
@require_permiso('cuentabancaria', 'nuevo')
def addCuentaBancaria():
    datos, error, campo = validar_cuenta(request.get_json(silent=True))
    if error:
        return respuesta_error(error, 400, campo)
    dao = CuentaBancariaDao()
    try:
        if dao.existeDuplicado(datos['id_entidad_emisora'], datos['numero_cuenta']):
            return respuesta_error(MSG_DUPLICADO, 400, 'numero_cuenta')
        nuevo_id = dao.guardarCuentaBancaria(**datos)
        rechazo = respuesta_por_codigo(nuevo_id)
        if rechazo:
            return rechazo
        if nuevo_id:
            nueva = dao.getCuentaBancariaById(nuevo_id)
            auditar(nuevo_id, 'ALTA', detalle_cambios({}, _detalle(nueva), ETIQUETAS))
            return jsonify({'success': True, 'data': nueva, 'mensaje': f'Cuenta bancaria "{nueva["descripcion"]}" agregada correctamente.', 'error': None}), 201
        return respuesta_error('No se pudo guardar la cuenta bancaria. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al agregar cuenta bancaria: {str(e)}")
        return error_interno()


@cuentabancariaapi.route('/cuentas-bancarias/<int:id_cuenta_bancaria>', methods=['PUT'])
@require_permiso('cuentabancaria', 'editar')
def updateCuentaBancaria(id_cuenta_bancaria):
    datos, error, campo = validar_cuenta(request.get_json(silent=True))
    if error:
        return respuesta_error(error, 400, campo)
    dao = CuentaBancariaDao()
    try:
        anterior = dao.getCuentaBancariaById(id_cuenta_bancaria)
        if not anterior:
            return respuesta_error('No se encontró la cuenta bancaria con el ID proporcionado.', 404)
        if all(anterior[k] == datos[k] for k in datos):   # sin cambios: no se toca la BD ni se audita
            return jsonify({'success': True, 'data': anterior, 'mensaje': f'Cuenta bancaria "{anterior["descripcion"]}" sin cambios.', 'error': None}), 200
        if dao.existeDuplicado(datos['id_entidad_emisora'], datos['numero_cuenta'], excluir_id=id_cuenta_bancaria):
            return respuesta_error(MSG_DUPLICADO, 400, 'numero_cuenta')
        resultado = dao.updateCuentaBancaria(id_cuenta_bancaria, **datos)
        rechazo = respuesta_por_codigo(resultado)
        if rechazo:
            return rechazo
        if resultado:
            nueva = dao.getCuentaBancariaById(id_cuenta_bancaria)
            auditar(id_cuenta_bancaria, 'MODIFICACION', detalle_cambios(_detalle(anterior), _detalle(nueva), ETIQUETAS))
            return jsonify({'success': True, 'data': nueva, 'mensaje': f'Cuenta bancaria "{nueva["descripcion"]}" actualizada correctamente.', 'error': None}), 200
        return respuesta_error('No se pudo actualizar la cuenta bancaria.', 404)
    except Exception as e:
        app.logger.error(f"Error al actualizar cuenta bancaria: {str(e)}")
        return error_interno()


@cuentabancariaapi.route('/cuentas-bancarias/<int:id_cuenta_bancaria>', methods=['DELETE'])
@require_permiso('cuentabancaria', 'anular')
def deleteCuentaBancaria(id_cuenta_bancaria):
    dao = CuentaBancariaDao()
    try:
        registro = dao.getCuentaBancariaById(id_cuenta_bancaria)
        resultado = dao.deleteCuentaBancaria(id_cuenta_bancaria)
        if isinstance(resultado, tuple):  # ("EN_USO", motivo)
            return respuesta_error(resultado[1], 409)
        if resultado:
            descripcion = registro['descripcion'] if registro else 'seleccionada'
            auditar(id_cuenta_bancaria, 'BAJA', f'Cuenta: {descripcion}')
            return jsonify({'success': True, 'mensaje': f'Cuenta bancaria "{descripcion}" anulada correctamente.', 'error': None}), 200
        return respuesta_error('No se encontró la cuenta bancaria con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al anular cuenta bancaria: {str(e)}")
        return error_interno()


@cuentabancariaapi.route('/cuentas-bancarias/<int:id_cuenta_bancaria>/reactivar', methods=['PATCH'])
@require_permiso('cuentabancaria', 'editar')
def reactivarCuentaBancaria(id_cuenta_bancaria):
    dao = CuentaBancariaDao()
    try:
        resultado = dao.reactivarCuentaBancaria(id_cuenta_bancaria)
        if resultado == NO_EXISTE:
            return respuesta_error('No se encontró la cuenta bancaria con el ID proporcionado.', 404)
        if resultado == YA_ACTIVO:
            return respuesta_error('La cuenta bancaria ya está activa.', 409)
        if resultado == EMISORA_INACTIVA:
            return respuesta_error('No se puede reactivar: el banco (entidad emisora) está anulado. Reactívelo primero.', 409)
        if resultado == DUPLICADO:
            return respuesta_error('No se puede reactivar: ya existe una cuenta activa de ese banco con ese número.', 409)
        if resultado:
            obj = dao.getCuentaBancariaById(id_cuenta_bancaria)
            auditar(id_cuenta_bancaria, 'REACTIVACION', f'Cuenta: {obj["descripcion"]}; Titular: {obj["titular"]}')
            return jsonify({'success': True, 'data': obj, 'mensaje': f'Cuenta bancaria "{obj["descripcion"]}" reactivada correctamente.', 'error': None}), 200
        return respuesta_error('No se pudo reactivar la cuenta bancaria. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al reactivar cuenta bancaria: {str(e)}")
        return error_interno()
