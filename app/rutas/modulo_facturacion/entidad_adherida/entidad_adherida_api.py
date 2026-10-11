from flask import Blueprint, request, jsonify, current_app as app
from app.dao.modulo_facturacion.entidad_adherida.EntidadAdheridaDao import (
    EntidadAdheridaDao, DUPLICADO, EMISORA_INVALIDA, MARCA_INVALIDA)
from app.rutas.modulo_facturacion.utils import (
    validar_datos_entidad, detalle_cambios, respuesta_error, auditar as _auditar, error_interno)
from app.rutas.modulo_seguridad.decorators import require_permiso, require_login

entidadadheridaapi = Blueprint('entidadadheridaapi', __name__)

ENTIDAD = 'entidad_adherida'
ETIQUETAS = {
    'descripcion': 'Descripción', 'id_entidad_emisora': 'Banco (ID)', 'id_marca_tarjeta': 'Marca (ID)',
    'direccion': 'Dirección', 'telefono': 'Teléfono', 'correo': 'Correo'
}
MSG_DUPLICADO = 'Ya existe una entidad adherida con esa descripción, banco y marca.'
MSG_EMISORA = 'El banco seleccionado no existe o está anulado.'
MSG_MARCA = 'La marca de tarjeta seleccionada no existe o está anulada.'


def auditar(id_registro, accion, detalle):
    _auditar(ENTIDAD, id_registro, accion, detalle)


def _entero(valor):
    """ID entero positivo (acepta int o texto numérico; rechaza bool/vacío/otros). None si no es válido."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor if valor > 0 else None
    if isinstance(valor, str) and valor.strip().isdigit():
        return int(valor.strip()) or None
    return None


def validar_adherida(data):
    """Devuelve (datos, error, campo): los datos de contacto + emisora y marca como enteros."""
    data = data if isinstance(data, dict) else {}
    datos, error, campo = validar_datos_entidad(data)
    if error:
        return None, error, campo
    id_emisora = _entero(data.get('id_entidad_emisora'))
    if id_emisora is None:
        return None, 'Debe seleccionar un banco (entidad emisora).', 'id_entidad_emisora'
    id_marca = _entero(data.get('id_marca_tarjeta'))
    if id_marca is None:
        return None, 'Debe seleccionar una marca de tarjeta.', 'id_marca_tarjeta'
    datos['id_entidad_emisora'] = id_emisora
    datos['id_marca_tarjeta'] = id_marca
    return datos, None, None


def respuesta_por_codigo(codigo):
    """Traduce los códigos de error del DAO a respuesta HTTP. None si no es un código de error."""
    if codigo == DUPLICADO:
        return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')
    if codigo == EMISORA_INVALIDA:
        return respuesta_error(MSG_EMISORA, 400, 'id_entidad_emisora')
    if codigo == MARCA_INVALIDA:
        return respuesta_error(MSG_MARCA, 400, 'id_marca_tarjeta')
    return None


def _datos_para_detalle(registro):
    return {k: registro.get(k) for k in ETIQUETAS}


# -------------------------
# Trae todas las entidades adheridas activas (con nombre de banco y marca)
# -------------------------
@entidadadheridaapi.route('/entidades-adheridas', methods=['GET'])
@require_login  # lookup: alimenta combos de otras pantallas (Cobros)
def getEntidadesAdheridas():
    try:
        return jsonify({'success': True, 'data': EntidadAdheridaDao().getEntidadesAdheridas(), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener entidades adheridas: {str(e)}")
        return error_interno()


# -------------------------
# Trae una entidad adherida por ID
# -------------------------
@entidadadheridaapi.route('/entidades-adheridas/<int:id_entidad_adherida>', methods=['GET'])
@require_permiso('entidadadherida', 'ver')
def getEntidadAdherida(id_entidad_adherida):
    try:
        adherida = EntidadAdheridaDao().getEntidadAdheridaById(id_entidad_adherida)
        if adherida:
            return jsonify({'success': True, 'data': adherida, 'error': None}), 200
        return respuesta_error('No se encontró la entidad adherida con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al obtener entidad adherida: {str(e)}")
        return error_interno()


# -------------------------
# Agrega una entidad adherida
# -------------------------
@entidadadheridaapi.route('/entidades-adheridas', methods=['POST'])
@require_permiso('entidadadherida', 'nuevo')
def addEntidadAdherida():
    datos, error, campo = validar_adherida(request.get_json(silent=True))
    if error:
        return respuesta_error(error, 400, campo)

    dao = EntidadAdheridaDao()
    try:
        if dao.existeDuplicado(datos['descripcion'], datos['id_entidad_emisora'], datos['id_marca_tarjeta']):
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')

        nuevo_id = dao.guardarEntidadAdherida(**datos)
        rechazo = respuesta_por_codigo(nuevo_id)
        if rechazo:
            return rechazo
        if nuevo_id:
            auditar(nuevo_id, 'ALTA', detalle_cambios({}, datos, ETIQUETAS))
            return jsonify({
                'success': True,
                'data': {'id_entidad_adherida': nuevo_id, **datos},
                'mensaje': f'Entidad adherida "{datos["descripcion"]}" agregada correctamente.',
                'error': None
            }), 201
        return respuesta_error('No se pudo guardar la entidad adherida. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al agregar entidad adherida: {str(e)}")
        return error_interno()


# -------------------------
# Actualiza una entidad adherida
# -------------------------
@entidadadheridaapi.route('/entidades-adheridas/<int:id_entidad_adherida>', methods=['PUT'])
@require_permiso('entidadadherida', 'editar')
def updateEntidadAdherida(id_entidad_adherida):
    datos, error, campo = validar_adherida(request.get_json(silent=True))
    if error:
        return respuesta_error(error, 400, campo)

    dao = EntidadAdheridaDao()
    try:
        anterior = dao.getEntidadAdheridaById(id_entidad_adherida)
        if not anterior:
            return respuesta_error('No se encontró la entidad adherida con el ID proporcionado.', 404)

        detalle = detalle_cambios(_datos_para_detalle(anterior), datos, ETIQUETAS)
        if not detalle:
            # Sin cambios: no se toca la BD ni se audita.
            return jsonify({
                'success': True,
                'data': {'id_entidad_adherida': id_entidad_adherida, **datos},
                'mensaje': f'Entidad adherida "{datos["descripcion"]}" sin cambios.',
                'error': None
            }), 200

        if dao.existeDuplicado(datos['descripcion'], datos['id_entidad_emisora'],
                               datos['id_marca_tarjeta'], excluir_id=id_entidad_adherida):
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')

        resultado = dao.updateEntidadAdherida(id_entidad_adherida, **datos)
        rechazo = respuesta_por_codigo(resultado)
        if rechazo:
            return rechazo
        if resultado:
            auditar(id_entidad_adherida, 'MODIFICACION', detalle)
            return jsonify({
                'success': True,
                'data': {'id_entidad_adherida': id_entidad_adherida, **datos},
                'mensaje': f'Entidad adherida "{datos["descripcion"]}" actualizada correctamente.',
                'error': None
            }), 200
        return respuesta_error('No se pudo actualizar la entidad adherida.', 404)
    except Exception as e:
        app.logger.error(f"Error al actualizar entidad adherida: {str(e)}")
        return error_interno()


# -------------------------
# Anula (baja lógica) una entidad adherida
# -------------------------
@entidadadheridaapi.route('/entidades-adheridas/<int:id_entidad_adherida>', methods=['DELETE'])
@require_permiso('entidadadherida', 'anular')
def deleteEntidadAdherida(id_entidad_adherida):
    dao = EntidadAdheridaDao()
    try:
        registro = dao.getEntidadAdheridaById(id_entidad_adherida)
        resultado = dao.deleteEntidadAdherida(id_entidad_adherida)
        if isinstance(resultado, tuple):  # ("EN_USO", motivo)
            return respuesta_error(resultado[1], 409)
        if resultado:
            descripcion = registro['descripcion'] if registro else 'seleccionada'
            auditar(id_entidad_adherida, 'BAJA', f'Descripción: {descripcion}')
            return jsonify({'success': True, 'mensaje': f'Entidad adherida "{descripcion}" anulada correctamente.', 'error': None}), 200
        return respuesta_error('No se encontró la entidad adherida con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al anular entidad adherida: {str(e)}")
        return error_interno()
