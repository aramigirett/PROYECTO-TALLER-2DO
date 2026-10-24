from flask import Blueprint, request, jsonify, current_app as app
from app.rutas.modulo_seguridad.permisos_contexto import puede
from app.rutas.modulo_facturacion.utils import respuesta_error
from app.dao.modulo_facturacion.entidad_emisora.EntidadEmisoraDao import EntidadEmisoraDao
from app.dao.modulo_facturacion.entidad_emisora.EntidadEmisoraDao import NO_EXISTE, YA_ACTIVO, DUPLICADO
from app.rutas.modulo_facturacion.utils import (
    validar_datos_entidad, detalle_cambios, respuesta_error, auditar as _auditar, error_interno)
from app.rutas.modulo_seguridad.decorators import require_permiso, require_login

entidademisoraapi = Blueprint('entidademisoraapi', __name__)

ENTIDAD = 'entidad_emisora'
ETIQUETAS = {'descripcion': 'Descripción', 'direccion': 'Dirección', 'telefono': 'Teléfono', 'correo': 'Correo'}
MSG_DUPLICADO = 'La descripción ya existe.'


def auditar(id_registro, accion, detalle):
    _auditar(ENTIDAD, id_registro, accion, detalle)


# -------------------------
# Trae todas las entidades emisoras activas
# -------------------------
@entidademisoraapi.route('/entidades-emisoras', methods=['GET'])
@require_login  # lookup: alimenta combos de otras pantallas (Entidad Adherida, Cobros)
def getEntidadesEmisoras():
    incluir_inactivos = request.args.get('inactivos', '').lower() in ('1', 'true')
    if incluir_inactivos and not puede('entidademisora', 'ver'):
        return respuesta_error('No tiene permiso para ver las entidades emisoras inactivas.', 403)
    try:
        return jsonify({'success': True, 'data': EntidadEmisoraDao().getEntidadesEmisoras(incluir_inactivos), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener entidades emisoras: {str(e)}")
        return error_interno()


# -------------------------
# Trae una entidad emisora por ID
# -------------------------
@entidademisoraapi.route('/entidades-emisoras/<int:id_entidad_emisora>', methods=['GET'])
@require_permiso('entidademisora', 'ver')
def getEntidadEmisora(id_entidad_emisora):
    try:
        emisora = EntidadEmisoraDao().getEntidadEmisoraById(id_entidad_emisora)
        if emisora:
            return jsonify({'success': True, 'data': emisora, 'error': None}), 200
        return respuesta_error('No se encontró la entidad emisora con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al obtener entidad emisora: {str(e)}")
        return error_interno()


# -------------------------
# Agrega una entidad emisora
# -------------------------
@entidademisoraapi.route('/entidades-emisoras', methods=['POST'])
@require_permiso('entidademisora', 'nuevo')
def addEntidadEmisora():
    datos, error, campo = validar_datos_entidad(request.get_json(silent=True))
    if error:
        return respuesta_error(error, 400, campo)

    dao = EntidadEmisoraDao()
    try:
        if dao.existeDuplicado(datos['descripcion']):
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')

        nuevo_id = dao.guardarEntidadEmisora(**datos)
        if nuevo_id == "DUPLICADO":
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')
        if nuevo_id:
            auditar(nuevo_id, 'ALTA', detalle_cambios({}, datos, ETIQUETAS))
            return jsonify({
                'success': True,
                'data': {'id_entidad_emisora': nuevo_id, **datos},
                'mensaje': f'Entidad emisora "{datos["descripcion"]}" agregada correctamente.',
                'error': None
            }), 201
        return respuesta_error('No se pudo guardar la entidad emisora. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al agregar entidad emisora: {str(e)}")
        return error_interno()


# -------------------------
# Actualiza una entidad emisora
# -------------------------
@entidademisoraapi.route('/entidades-emisoras/<int:id_entidad_emisora>', methods=['PUT'])
@require_permiso('entidademisora', 'editar')
def updateEntidadEmisora(id_entidad_emisora):
    datos, error, campo = validar_datos_entidad(request.get_json(silent=True))
    if error:
        return respuesta_error(error, 400, campo)

    dao = EntidadEmisoraDao()
    try:
        anterior = dao.getEntidadEmisoraById(id_entidad_emisora)
        if not anterior:
            return respuesta_error('No se encontró la entidad emisora con el ID proporcionado.', 404)

        detalle = detalle_cambios(anterior, datos, ETIQUETAS)
        if not detalle:
            # Sin cambios: no se toca la BD ni se audita.
            return jsonify({
                'success': True,
                'data': {'id_entidad_emisora': id_entidad_emisora, **datos},
                'mensaje': f'Entidad emisora "{datos["descripcion"]}" sin cambios.',
                'error': None
            }), 200

        if dao.existeDuplicado(datos['descripcion'], excluir_id=id_entidad_emisora):
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')

        resultado = dao.updateEntidadEmisora(id_entidad_emisora, **datos)
        if resultado == "DUPLICADO":
            return respuesta_error(MSG_DUPLICADO, 400, 'descripcion')
        if resultado:
            auditar(id_entidad_emisora, 'MODIFICACION', detalle)
            return jsonify({
                'success': True,
                'data': {'id_entidad_emisora': id_entidad_emisora, **datos},
                'mensaje': f'Entidad emisora "{datos["descripcion"]}" actualizada correctamente.',
                'error': None
            }), 200
        return respuesta_error('No se pudo actualizar la entidad emisora.', 404)
    except Exception as e:
        app.logger.error(f"Error al actualizar entidad emisora: {str(e)}")
        return error_interno()


# -------------------------
# Anula (baja lógica) una entidad emisora
# -------------------------
@entidademisoraapi.route('/entidades-emisoras/<int:id_entidad_emisora>', methods=['DELETE'])
@require_permiso('entidademisora', 'anular')
def deleteEntidadEmisora(id_entidad_emisora):
    dao = EntidadEmisoraDao()
    try:
        registro = dao.getEntidadEmisoraById(id_entidad_emisora)
        resultado = dao.deleteEntidadEmisora(id_entidad_emisora)
        if isinstance(resultado, tuple):  # ("EN_USO", motivo)
            return respuesta_error(resultado[1], 409)
        if resultado:
            descripcion = registro['descripcion'] if registro else 'seleccionada'
            auditar(id_entidad_emisora, 'BAJA', f'Descripción: {descripcion}')
            return jsonify({'success': True, 'mensaje': f'Entidad emisora "{descripcion}" anulada correctamente.', 'error': None}), 200
        return respuesta_error('No se encontró la entidad emisora con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al anular entidad emisora: {str(e)}")
        return error_interno()


# -------------------------
# Reactiva la entidad emisora anulada (permiso: el mismo de editar)
# -------------------------
@entidademisoraapi.route('/entidades-emisoras/<int:id_entidad_emisora>/reactivar', methods=['PATCH'])
@require_permiso('entidademisora', 'editar')
def reactivarEntidadEmisora(id_entidad_emisora):
    dao = EntidadEmisoraDao()
    try:
        resultado = dao.reactivarEntidadEmisora(id_entidad_emisora)
        if resultado == NO_EXISTE:
            return respuesta_error('No se encontró la entidad emisora con el ID proporcionado.', 404)
        if resultado == YA_ACTIVO:
            return respuesta_error('La entidad emisora ya está activa.', 409)
        if resultado == DUPLICADO:
            return respuesta_error('No se puede reactivar: ya existe una entidad emisora activa con esa descripción.', 409)
        if resultado:
            obj = dao.getEntidadEmisoraById(id_entidad_emisora)
            auditar(id_entidad_emisora, 'REACTIVACION', f'Descripción: {obj["descripcion"]}')
            return jsonify({'success': True, 'data': obj,
                            'mensaje': f'Entidad emisora "{obj["descripcion"]}" reactivada correctamente.',
                            'error': None}), 200
        return respuesta_error('No se pudo reactivar la entidad emisora. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al reactivar entidad emisora: {str(e)}")
        return error_interno()
