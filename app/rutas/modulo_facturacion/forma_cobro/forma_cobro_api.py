from flask import Blueprint, request, jsonify, current_app as app
from app.rutas.modulo_seguridad.permisos_contexto import puede
from app.rutas.modulo_facturacion.utils import respuesta_error
from app.dao.modulo_facturacion.forma_cobro.FormaCobroDao import FormaCobroDao
from app.dao.modulo_facturacion.forma_cobro.FormaCobroDao import NO_EXISTE, YA_ACTIVO, DUPLICADO, TIPOS
from app.rutas.modulo_facturacion.utils import normalizar_descripcion, auditar as _auditar, error_interno
from app.rutas.modulo_seguridad.decorators import require_permiso, require_login

formacobroapi = Blueprint('formacobroapi', __name__)

ENTIDAD = 'forma_cobro'
MSG_TIPO = 'El tipo debe ser Efectivo, Tarjeta, Cheque o Transferencia.'


def _tipo(cuerpo):
    """Tipo de la forma de cobro (obligatorio, uno de los 4). Devuelve (tipo, error)."""
    tipo = str((cuerpo or {}).get('tipo') or '').strip().upper() if isinstance(cuerpo, dict) else ''
    return (tipo, None) if tipo in TIPOS else (None, MSG_TIPO)


def auditar(id_registro, accion, detalle):
    _auditar(ENTIDAD, id_registro, accion, detalle)


# -------------------------
# Trae todas las formas de cobro activas
# -------------------------
@formacobroapi.route('/formas-cobro', methods=['GET'])
@require_login  # lookup: alimenta combos de otras pantallas (ej. Cobros)
def getFormasCobro():
    incluir_inactivos = request.args.get('inactivos', '').lower() in ('1', 'true')
    if incluir_inactivos and not puede('formacobro', 'ver'):
        return respuesta_error('No tiene permiso para ver las formas de cobro inactivas.', 403)
    try:
        return jsonify({'success': True, 'data': FormaCobroDao().getFormasCobro(incluir_inactivos), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener formas de cobro: {str(e)}")
        return error_interno()


# -------------------------
# Trae una forma de cobro por ID
# -------------------------
@formacobroapi.route('/formas-cobro/<int:id_forma_cobro>', methods=['GET'])
@require_permiso('formacobro', 'ver')
def getFormaCobro(id_forma_cobro):
    try:
        forma = FormaCobroDao().getFormaCobroById(id_forma_cobro)
        if forma:
            return jsonify({'success': True, 'data': forma, 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se encontró la forma de cobro con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener forma de cobro: {str(e)}")
        return error_interno()


# -------------------------
# Agrega una forma de cobro
# -------------------------
@formacobroapi.route('/formas-cobro', methods=['POST'])
@require_permiso('formacobro', 'nuevo')
def addFormaCobro():
    cuerpo = request.get_json(silent=True)
    descripcion, error = normalizar_descripcion(cuerpo)
    if error:
        return jsonify({'success': False, 'error': error}), 400
    tipo, error = _tipo(cuerpo)
    if error:
        return respuesta_error(error, 400, 'tipo')

    dao = FormaCobroDao()
    try:
        if dao.existeDuplicado(descripcion):
            return jsonify({'success': False, 'error': 'La descripción ya existe.'}), 400

        nuevo_id = dao.guardarFormaCobro(descripcion, tipo)
        if nuevo_id == "DUPLICADO":
            return jsonify({'success': False, 'error': 'La descripción ya existe.'}), 400
        if nuevo_id:
            auditar(nuevo_id, 'ALTA', f'Descripción: {descripcion}; Tipo: {tipo}')
            return jsonify({
                'success': True,
                'data': {'id_forma_cobro': nuevo_id, 'descripcion': descripcion, 'tipo': tipo},
                'mensaje': f'Forma de cobro "{descripcion}" agregada correctamente.',
                'error': None
            }), 201
        return jsonify({'success': False, 'error': 'No se pudo guardar la forma de cobro. Consulte con el administrador.'}), 500
    except Exception as e:
        app.logger.error(f"Error al agregar forma de cobro: {str(e)}")
        return error_interno()


# -------------------------
# Actualiza una forma de cobro
# -------------------------
@formacobroapi.route('/formas-cobro/<int:id_forma_cobro>', methods=['PUT'])
@require_permiso('formacobro', 'editar')
def updateFormaCobro(id_forma_cobro):
    cuerpo = request.get_json(silent=True)
    descripcion, error = normalizar_descripcion(cuerpo)
    if error:
        return jsonify({'success': False, 'error': error}), 400
    tipo, error = _tipo(cuerpo)
    if error:
        return respuesta_error(error, 400, 'tipo')

    dao = FormaCobroDao()
    try:
        anterior = dao.getFormaCobroById(id_forma_cobro)
        if not anterior:
            return jsonify({'success': False, 'error': 'No se encontró la forma de cobro con el ID proporcionado.'}), 404

        if anterior['descripcion'] == descripcion and anterior['tipo'] == tipo:
            # Sin cambios: no se toca la BD ni se audita.
            return jsonify({
                'success': True,
                'data': {'id_forma_cobro': id_forma_cobro, 'descripcion': descripcion, 'tipo': tipo},
                'mensaje': f'Forma de cobro "{descripcion}" sin cambios.',
                'error': None
            }), 200

        if dao.existeDuplicado(descripcion, excluir_id=id_forma_cobro):
            return jsonify({'success': False, 'error': 'La descripción ya existe.'}), 400

        resultado = dao.updateFormaCobro(id_forma_cobro, descripcion, tipo)
        if isinstance(resultado, tuple):  # ("EN_USO", motivo): no se puede cambiar el tipo de una forma ya usada
            return respuesta_error(resultado[1], 409, 'tipo')
        if resultado == "DUPLICADO":
            return jsonify({'success': False, 'error': 'La descripción ya existe.'}), 400
        if resultado:
            cambios = []
            if anterior['descripcion'] != descripcion:
                cambios.append(f'Descripción: {anterior["descripcion"]} -> {descripcion}')
            if anterior['tipo'] != tipo:
                cambios.append(f'Tipo: {anterior["tipo"] or "(sin tipo)"} -> {tipo}')
            auditar(id_forma_cobro, 'MODIFICACION', '; '.join(cambios))
            return jsonify({
                'success': True,
                'data': {'id_forma_cobro': id_forma_cobro, 'descripcion': descripcion, 'tipo': tipo},
                'mensaje': f'Forma de cobro "{descripcion}" actualizada correctamente.',
                'error': None
            }), 200
        return jsonify({'success': False, 'error': 'No se pudo actualizar la forma de cobro.'}), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar forma de cobro: {str(e)}")
        return error_interno()


# -------------------------
# Anula (baja lógica) una forma de cobro
# -------------------------
@formacobroapi.route('/formas-cobro/<int:id_forma_cobro>', methods=['DELETE'])
@require_permiso('formacobro', 'anular')
def deleteFormaCobro(id_forma_cobro):
    dao = FormaCobroDao()
    try:
        registro = dao.getFormaCobroById(id_forma_cobro)
        resultado = dao.deleteFormaCobro(id_forma_cobro)
        if isinstance(resultado, tuple):  # ("EN_USO", motivo)
            return respuesta_error(resultado[1], 409)
        if resultado:
            descripcion = registro['descripcion'] if registro else 'seleccionada'
            auditar(id_forma_cobro, 'BAJA', f'Descripción: {descripcion}; Tipo: {registro["tipo"] if registro else "-"}')
            return jsonify({'success': True, 'mensaje': f'Forma de cobro "{descripcion}" anulada correctamente.', 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se encontró la forma de cobro con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al anular forma de cobro: {str(e)}")
        return error_interno()


# -------------------------
# Reactiva la forma de cobro anulada (permiso: el mismo de editar)
# -------------------------
@formacobroapi.route('/formas-cobro/<int:id_forma_cobro>/reactivar', methods=['PATCH'])
@require_permiso('formacobro', 'editar')
def reactivarFormaCobro(id_forma_cobro):
    dao = FormaCobroDao()
    try:
        resultado = dao.reactivarFormaCobro(id_forma_cobro)
        if resultado == NO_EXISTE:
            return respuesta_error('No se encontró la forma de cobro con el ID proporcionado.', 404)
        if resultado == YA_ACTIVO:
            return respuesta_error('La forma de cobro ya está activa.', 409)
        if resultado == DUPLICADO:
            return respuesta_error('No se puede reactivar: ya existe una forma de cobro activa con esa descripción.', 409)
        if resultado:
            obj = dao.getFormaCobroById(id_forma_cobro)
            auditar(id_forma_cobro, 'REACTIVACION', f'Descripción: {obj["descripcion"]}; Tipo: {obj["tipo"]}')
            return jsonify({'success': True, 'data': obj,
                            'mensaje': f'Forma de cobro "{obj["descripcion"]}" reactivada correctamente.',
                            'error': None}), 200
        return respuesta_error('No se pudo reactivar la forma de cobro. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al reactivar forma de cobro: {str(e)}")
        return error_interno()
