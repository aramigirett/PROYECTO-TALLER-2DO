from flask import Blueprint, request, jsonify, current_app as app
from app.dao.modulo_facturacion.caja.CajaDao import (
    CajaDao, DUPLICADO, CONSULTORIO_INVALIDO, NO_EXISTE, YA_ACTIVA)
from app.rutas.modulo_facturacion.utils import (
    normalizar_descripcion, entero_id, detalle_cambios, respuesta_error,
    auditar as _auditar, error_interno)
from app.rutas.modulo_seguridad.decorators import require_permiso, require_login
from app.rutas.modulo_seguridad.permisos_contexto import puede

cajaapi = Blueprint('cajaapi', __name__)

ENTIDAD = 'caja'
ETIQUETAS = {'descripcion': 'Descripción', 'consultorio': 'Consultorio'}
MSG_DUPLICADO = 'Ya existe una caja con esa descripción en el consultorio.'
MSG_CONSULTORIO = 'El consultorio seleccionado no existe.'


def auditar(id_registro, accion, detalle):
    _auditar(ENTIDAD, id_registro, accion, detalle)


def validar_caja(data):
    """Devuelve (datos, error, campo)."""
    data = data if isinstance(data, dict) else {}
    descripcion, error = normalizar_descripcion(data)
    if error:
        return None, error, 'descripcion'
    id_consultorio = entero_id(data.get('id_consultorio'))
    if id_consultorio is None:
        return None, 'Debe seleccionar un consultorio.', 'id_consultorio'
    return {'id_consultorio': id_consultorio, 'descripcion': descripcion}, None, None


def respuesta_por_codigo(codigo):
    """Traduce los códigos de error del DAO a respuesta HTTP. None si no es un código de error."""
    if codigo == DUPLICADO:
        return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')
    if codigo == CONSULTORIO_INVALIDO:
        return respuesta_error(MSG_CONSULTORIO, 400, 'id_consultorio')
    return None


def _para_detalle(c):
    """Valores legibles para la auditoría: el nombre del consultorio, no su ID."""
    return {'descripcion': c['descripcion'], 'consultorio': c['consultorio']}


# -------------------------
# Trae las cajas. Por defecto solo activas; ?inactivas=1 incluye las anuladas (requiere 'ver').
# -------------------------
@cajaapi.route('/cajas', methods=['GET'])
@require_login  # lookup: alimenta combos de otras pantallas (Apertura/Cierre de caja, Cobros)
def getCajas():
    incluir_inactivas = request.args.get('inactivas', '').lower() in ('1', 'true')
    if incluir_inactivas and not puede('caja', 'ver'):
        return respuesta_error('No tiene permiso para ver las cajas inactivas.', 403)
    try:
        return jsonify({'success': True, 'data': CajaDao().getCajas(incluir_inactivas), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener cajas: {str(e)}")
        return error_interno()


# -------------------------
# Trae una caja activa por ID
# -------------------------
@cajaapi.route('/cajas/<int:id_caja>', methods=['GET'])
@require_permiso('caja', 'ver')
def getCaja(id_caja):
    try:
        caja = CajaDao().getCajaById(id_caja)
        if caja:
            return jsonify({'success': True, 'data': caja, 'error': None}), 200
        return respuesta_error('No se encontró la caja con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al obtener caja: {str(e)}")
        return error_interno()


# -------------------------
# Agrega una caja
# -------------------------
@cajaapi.route('/cajas', methods=['POST'])
@require_permiso('caja', 'nuevo')
def addCaja():
    datos, error, campo = validar_caja(request.get_json(silent=True))
    if error:
        return respuesta_error(error, 400, campo)

    dao = CajaDao()
    try:
        if dao.existeDuplicado(datos['id_consultorio'], datos['descripcion']):
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')

        nuevo_id = dao.guardarCaja(**datos)
        rechazo = respuesta_por_codigo(nuevo_id)
        if rechazo:
            return rechazo
        if nuevo_id:
            caja = dao.getCajaById(nuevo_id)
            auditar(nuevo_id, 'ALTA', detalle_cambios({}, _para_detalle(caja), ETIQUETAS))
            return jsonify({
                'success': True, 'data': caja,
                'mensaje': f'Caja "{caja["descripcion"]}" agregada correctamente.',
                'error': None
            }), 201
        return respuesta_error('No se pudo guardar la caja. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al agregar caja: {str(e)}")
        return error_interno()


# -------------------------
# Actualiza una caja activa
# -------------------------
@cajaapi.route('/cajas/<int:id_caja>', methods=['PUT'])
@require_permiso('caja', 'editar')
def updateCaja(id_caja):
    datos, error, campo = validar_caja(request.get_json(silent=True))
    if error:
        return respuesta_error(error, 400, campo)

    dao = CajaDao()
    try:
        anterior = dao.getCajaById(id_caja)
        if not anterior:
            return respuesta_error('No se encontró la caja con el ID proporcionado.', 404)

        if anterior['id_consultorio'] == datos['id_consultorio'] and anterior['descripcion'] == datos['descripcion']:
            # Sin cambios: no se toca la BD ni se audita.
            return jsonify({
                'success': True, 'data': anterior,
                'mensaje': f'Caja "{datos["descripcion"]}" sin cambios.', 'error': None
            }), 200

        if dao.existeDuplicado(datos['id_consultorio'], datos['descripcion'], excluir_id=id_caja):
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')

        resultado = dao.updateCaja(id_caja, **datos)
        rechazo = respuesta_por_codigo(resultado)
        if rechazo:
            return rechazo
        if resultado:
            nueva = dao.getCajaById(id_caja)
            auditar(id_caja, 'MODIFICACION',
                    detalle_cambios(_para_detalle(anterior), _para_detalle(nueva), ETIQUETAS))
            return jsonify({
                'success': True, 'data': nueva,
                'mensaje': f'Caja "{nueva["descripcion"]}" actualizada correctamente.', 'error': None
            }), 200
        return respuesta_error('No se pudo actualizar la caja.', 404)
    except Exception as e:
        app.logger.error(f"Error al actualizar caja: {str(e)}")
        return error_interno()


# -------------------------
# Anula (baja lógica) una caja
# -------------------------
@cajaapi.route('/cajas/<int:id_caja>', methods=['DELETE'])
@require_permiso('caja', 'anular')
def deleteCaja(id_caja):
    dao = CajaDao()
    try:
        registro = dao.getCajaById(id_caja)
        resultado = dao.deleteCaja(id_caja)
        if isinstance(resultado, tuple):  # ("EN_USO", motivo)
            return respuesta_error(resultado[1], 409)
        if resultado:
            descripcion = registro['descripcion'] if registro else 'seleccionada'
            auditar(id_caja, 'BAJA', f'Descripción: {descripcion}')
            return jsonify({'success': True, 'mensaje': f'Caja "{descripcion}" anulada correctamente.', 'error': None}), 200
        return respuesta_error('No se encontró la caja con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al anular caja: {str(e)}")
        return error_interno()


# -------------------------
# Reactiva una caja anulada (permiso: el mismo de editar)
# -------------------------
@cajaapi.route('/cajas/<int:id_caja>/reactivar', methods=['PATCH'])
@require_permiso('caja', 'editar')
def reactivarCaja(id_caja):
    dao = CajaDao()
    try:
        resultado = dao.reactivarCaja(id_caja)
        if resultado == NO_EXISTE:
            return respuesta_error('No se encontró la caja con el ID proporcionado.', 404)
        if resultado == YA_ACTIVA:
            return respuesta_error('La caja ya está activa.', 409)
        if resultado == CONSULTORIO_INVALIDO:
            return respuesta_error('No se puede reactivar: el consultorio ya no existe.', 409)
        if resultado == DUPLICADO:
            return respuesta_error('No se puede reactivar: ya existe una caja activa con esa descripción '
                                   'en el consultorio.', 409)
        if resultado:
            caja = dao.getCajaById(id_caja)
            auditar(id_caja, 'REACTIVACION', f'Descripción: {caja["descripcion"]}; Consultorio: {caja["consultorio"]}')
            return jsonify({'success': True, 'data': caja,
                            'mensaje': f'Caja "{caja["descripcion"]}" reactivada correctamente.', 'error': None}), 200
        return respuesta_error('No se pudo reactivar la caja. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al reactivar caja: {str(e)}")
        return error_interno()
