"""API de la Agenda (cabecera + horarios). Movimiento con baja lógica: anular = estado 'Inactivo' (y sus horarios 'Cancelado'), reactivar sin conflicto
de médico y fecha. El funcionario sale de la sesión, nunca del navegador. Médico, especialidad, consultorio y funcionario anulados se rechazan.
Auditoría con nombres: AGENDA (módulo Agendamiento) y cada horario publicado o anulado.

    GET    /agenda/cabeceras[?inactivos=1&medico=&desde=&hasta=]   ('ver' de Agenda o de Cita)
    GET    /agenda/cabeceras/<id>  ·  GET /agenda/cabeceras/<id>/detalles
    POST   /agenda/cabeceras ('nuevo')   PUT .../<id> ('editar': solo Administrador)   DELETE .../<id> ('anular')   PATCH .../<id>/reactivar ('anular')
    POST   /agenda/cabeceras/<id>/detalles ('nuevo': ids_disponibilidades)   DELETE /agenda/detalles/<id> ('anular')
    PATCH  /agenda/detalles/<id>/cupos ('editar': solo Administrador)
"""
from datetime import date
from flask import Blueprint, current_app as app, jsonify, request

from app.dao.referenciales_agendamiento.agenda.AgendaCabeceraDao import AgendaCabeceraDao, NO_EXISTE, YA_ACTIVO, DUPLICADO, INVALIDO, EN_USO
from app.dao.referenciales_agendamiento.agenda.AgendaDetalleDao import AgendaDetalleDao
from app.rutas.modulo_agendamiento.utils import auditar, detalle_cambios, entero_id, error_interno, respuesta_error, validar_fecha
from app.rutas.modulo_seguridad.decorators import require_algun_permiso, require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_funcionario_sesion, puede

agendaapi = Blueprint('agendaapi', __name__)

ETIQUETAS = {'medico_nombre': 'Médico', 'especialidad': 'Especialidad', 'nombre_consultorio': 'Consultorio', 'fecha_agenda': 'Fecha'}
VER = (('agenda', 'ver'), ('cita', 'ver'))   # lookup que usan Agenda y Cita


def _auditado(c):
    return {k: c.get(k) for k in ETIQUETAS}


def _quien(c):
    return f"{c['medico_nombre']}, {c['fecha_agenda']}"


def _validar(data):
    """Valida el cuerpo del alta / modificación. Devuelve (valores, None) o (None, respuesta_de_error)."""
    if not isinstance(data, dict):
        return None, respuesta_error('Los datos enviados no son válidos.', 400)
    v = {}
    for campo, etiqueta in (('id_medico', 'médico'), ('id_especialidad', 'especialidad'), ('id_consultorio', 'consultorio')):
        v[campo] = entero_id(data.get(campo))
        if v[campo] is None:
            return None, respuesta_error(f'El campo {etiqueta} es obligatorio.', 400, campo)
    fecha, error = validar_fecha(data.get('fecha_agenda'), 'fecha')
    if error:
        return None, respuesta_error(error, 400, 'fecha_agenda')
    v['fecha_agenda'] = fecha
    obs = data.get('observaciones')
    if obs is not None and not isinstance(obs, str):
        return None, respuesta_error('Las observaciones deben ser un texto.', 400, 'observaciones')
    obs = (obs or '').strip()
    if len(obs) > 500:
        return None, respuesta_error('Las observaciones no pueden superar los 500 caracteres.', 400, 'observaciones')
    v['observaciones'] = obs or None
    return v, None


def _conflicto(res):
    codigo = 409 if res[0] in (DUPLICADO, EN_USO) else 400
    return respuesta_error(res[-1], codigo, res[1] if len(res) == 3 else None)


@agendaapi.route('/agenda/cabeceras', methods=['GET'])
@require_algun_permiso(*VER)
def getCabeceras():
    incluir_inactivos = request.args.get('inactivos', '').lower() in ('1', 'true')
    if incluir_inactivos and not puede('agenda', 'ver'):
        return respuesta_error('No tiene permiso para ver las agendas anuladas.', 403)
    try:
        datos = AgendaCabeceraDao().getCabeceras(incluir_inactivos, entero_id(request.args.get('medico')),
                                                 request.args.get('desde') or None, request.args.get('hasta') or None)
        return jsonify({'success': True, 'data': datos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener cabeceras: {str(e)}")
        return error_interno()


@agendaapi.route('/agenda/cabeceras/<int:id_cabecera>', methods=['GET'])
@require_algun_permiso(*VER)
def getCabecera(id_cabecera):
    try:
        c = AgendaCabeceraDao().getCabeceraById(id_cabecera, incluir_inactivos=puede('agenda', 'ver'))
        if c:
            return jsonify({'success': True, 'data': c, 'error': None}), 200
        return respuesta_error('No se encontró la agenda con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al obtener cabecera: {str(e)}")
        return error_interno()


@agendaapi.route('/agenda/cabeceras', methods=['POST'])
@require_permiso('agenda', 'nuevo')
def addCabecera():
    v, error = _validar(request.get_json(silent=True))
    if error:
        return error
    if v['fecha_agenda'] < date.today():
        return respuesta_error('No se puede crear una agenda en una fecha pasada.', 400, 'fecha_agenda')
    id_funcionario = id_funcionario_sesion()
    if not id_funcionario:
        return respuesta_error('Su usuario no está vinculado a un funcionario: no puede registrar agendas.', 403)
    dao = AgendaCabeceraDao()
    try:
        r = dao.guardarCabecera(v, id_funcionario)
        if isinstance(r, tuple):
            return _conflicto(r)
        if r:
            c = dao.getCabeceraById(r)
            auditar('agenda_cabecera', r, 'ALTA', detalle_cambios({}, _auditado(c), ETIQUETAS))
            return jsonify({'success': True, 'data': {'id_agenda_cabecera': r}, 'mensaje': f'Agenda de {_quien(c)} registrada correctamente.', 'error': None}), 201
        return respuesta_error('No se pudo guardar la agenda. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al crear cabecera: {str(e)}")
        return error_interno()


@agendaapi.route('/agenda/cabeceras/<int:id_cabecera>', methods=['PUT'])
@require_permiso('agenda', 'editar')
def updateCabecera(id_cabecera):
    v, error = _validar(request.get_json(silent=True))
    if error:
        return error
    dao = AgendaCabeceraDao()
    try:
        anterior = dao.getCabeceraById(id_cabecera)
        if not anterior:
            return respuesta_error('No se encontró la agenda con el ID proporcionado.', 404)
        r = dao.updateCabecera(id_cabecera, v)
        if isinstance(r, tuple):
            return _conflicto(r)
        if r:
            nuevo = dao.getCabeceraById(id_cabecera)
            detalle = detalle_cambios(_auditado(anterior), _auditado(nuevo), ETIQUETAS)
            if detalle:
                auditar('agenda_cabecera', id_cabecera, 'MODIFICACION', detalle)
            return jsonify({'success': True, 'data': {'id_agenda_cabecera': id_cabecera}, 'mensaje': f'Agenda de {_quien(nuevo)} actualizada correctamente.', 'error': None}), 200
        return respuesta_error('No se pudo actualizar la agenda.', 404)
    except Exception as e:
        app.logger.error(f"Error al actualizar cabecera: {str(e)}")
        return error_interno()


@agendaapi.route('/agenda/cabeceras/<int:id_cabecera>', methods=['DELETE'])
@require_permiso('agenda', 'anular')
def deleteCabecera(id_cabecera):
    dao = AgendaCabeceraDao()
    try:
        c = dao.getCabeceraById(id_cabecera)
        r = dao.deleteCabecera(id_cabecera)
        if isinstance(r, tuple):
            return _conflicto(r)
        if r:
            auditar('agenda_cabecera', id_cabecera, 'BAJA', detalle_cambios({}, _auditado(c), ETIQUETAS))
            return jsonify({'success': True, 'mensaje': f'Agenda de {_quien(c)} anulada correctamente.', 'error': None}), 200
        return respuesta_error('No se encontró la agenda con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al anular cabecera: {str(e)}")
        return error_interno()


@agendaapi.route('/agenda/cabeceras/<int:id_cabecera>/reactivar', methods=['PATCH'])
@require_permiso('agenda', 'anular')
def reactivarCabecera(id_cabecera):
    dao = AgendaCabeceraDao()
    try:
        r = dao.reactivarCabecera(id_cabecera)
        if r == NO_EXISTE:
            return respuesta_error('No se encontró la agenda con el ID proporcionado.', 404)
        if r == YA_ACTIVO:
            return respuesta_error('La agenda ya está activa.', 409)
        if isinstance(r, tuple):
            return respuesta_error(('No se puede reactivar: ' + r[-1][0].lower() + r[-1][1:]) if r[0] == INVALIDO else r[-1], 409)
        if r:
            c = dao.getCabeceraById(id_cabecera)
            auditar('agenda_cabecera', id_cabecera, 'REACTIVACION', detalle_cambios({}, _auditado(c), ETIQUETAS))
            return jsonify({'success': True, 'data': c, 'mensaje': f'Agenda de {_quien(c)} reactivada. Vuelva a publicar sus horarios.', 'error': None}), 200
        return respuesta_error('No se pudo reactivar la agenda. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al reactivar cabecera: {str(e)}")
        return error_interno()


# ---------------- horarios ----------------
@agendaapi.route('/agenda/cabeceras/<int:id_cabecera>/detalles', methods=['GET'])
@require_algun_permiso(*VER)
def getDetalles(id_cabecera):
    try:
        return jsonify({'success': True, 'data': AgendaDetalleDao().getDetallesPorCabecera(id_cabecera), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener detalles: {str(e)}")
        return error_interno()


@agendaapi.route('/agenda/detalles/<int:id_detalle>', methods=['GET'])
@require_permiso('agenda', 'ver')
def getDetalle(id_detalle):
    d = AgendaDetalleDao().getDetalleById(id_detalle)
    if d:
        return jsonify({'success': True, 'data': d, 'error': None}), 200
    return respuesta_error('No se encontró el horario con el ID proporcionado.', 404)


@agendaapi.route('/agenda/cabeceras/<int:id_cabecera>/detalles', methods=['POST'])
@require_permiso('agenda', 'nuevo')
def addDetalles(id_cabecera):
    data = request.get_json(silent=True) or {}
    ids = data.get('ids_disponibilidades')
    if not isinstance(ids, list) or not ids:
        return respuesta_error('Debe seleccionar al menos una disponibilidad.', 400, 'ids_disponibilidades')
    ids = [entero_id(i) for i in ids]
    if any(i is None for i in ids):
        return respuesta_error('Las disponibilidades seleccionadas no son válidas.', 400, 'ids_disponibilidades')
    try:
        cab = AgendaCabeceraDao().getCabeceraById(id_cabecera)
        if not cab:
            return respuesta_error('No se encontró la agenda con el ID proporcionado.', 404)
        r = AgendaDetalleDao().publicarDisponibilidades(id_cabecera, ids)
        if r and r[0] == INVALIDO:
            return respuesta_error(r[1], 409)
        creados, errores = r
        det = AgendaDetalleDao()
        for i in creados:
            d = det.getDetalleById(i)
            auditar('agenda_detalle', i, 'ALTA', detalle_cambios({}, {'a': _quien(cab), 'h': f"{d['hora_inicio']} a {d['hora_fin']}", 'c': d['cupos_maximos']},
                                                                 {'a': 'Agenda', 'h': 'Horario', 'c': 'Cupos'}))
        if creados:
            return jsonify({'success': True, 'data': {'ids_creados': creados, 'cantidad': len(creados), 'errores': errores or None},
                            'mensaje': f'{len(creados)} horario(s) publicado(s) en la agenda de {_quien(cab)}.', 'error': None}), 201
        return respuesta_error('No se publicó ningún horario. ' + ' '.join(errores), 400)
    except Exception as e:
        app.logger.error(f"Error al agregar detalles: {str(e)}")
        return error_interno()


@agendaapi.route('/agenda/detalles/<int:id_detalle>', methods=['DELETE'])
@require_permiso('agenda', 'anular')
def deleteDetalle(id_detalle):
    dao = AgendaDetalleDao()
    try:
        d = dao.getDetalleById(id_detalle)
        r = dao.deleteDetalle(id_detalle)
        if isinstance(r, tuple):
            return respuesta_error(r[1], 409)
        if r:
            cab = AgendaCabeceraDao().getCabeceraById(d['id_agenda_cabecera'], incluir_inactivos=True)
            auditar('agenda_detalle', id_detalle, 'BAJA', detalle_cambios({}, {'a': _quien(cab), 'h': f"{d['hora_inicio']} a {d['hora_fin']}"},
                                                                          {'a': 'Agenda', 'h': 'Horario'}))
            return jsonify({'success': True, 'mensaje': f"Horario de {d['hora_inicio']} a {d['hora_fin']} anulado correctamente.", 'error': None}), 200
        return respuesta_error('No se encontró el horario con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al anular detalle: {str(e)}")
        return error_interno()


@agendaapi.route('/agenda/detalles/<int:id_detalle>/cupos', methods=['PATCH'])
@require_permiso('agenda', 'editar')
def actualizarCupos(id_detalle):
    data = request.get_json(silent=True) or {}
    cupos = entero_id(data.get('cupos_disponibles')) if data.get('cupos_disponibles') not in (0, '0') else 0
    if cupos is None:
        return respuesta_error('Los cupos disponibles deben ser un número entero (0 o más).', 400, 'cupos_disponibles')
    dao = AgendaDetalleDao()
    try:
        antes = dao.getDetalleById(id_detalle)
        r = dao.actualizarCuposDisponibles(id_detalle, cupos)
        if isinstance(r, tuple):
            return respuesta_error(r[1], 409)
        if r:
            if antes and antes['cupos_disponibles'] != cupos:
                cab = AgendaCabeceraDao().getCabeceraById(antes['id_agenda_cabecera'], incluir_inactivos=True)
                auditar('agenda_detalle', id_detalle, 'MODIFICACION', detalle_cambios(
                    {'a': _quien(cab), 'c': antes['cupos_disponibles']}, {'a': _quien(cab), 'c': cupos}, {'a': 'Agenda', 'c': 'Cupos disponibles'}))
            return jsonify({'success': True, 'data': {'cupos_disponibles': cupos}, 'mensaje': 'Cupos actualizados.', 'error': None}), 200
        return respuesta_error('No se encontró el horario con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al actualizar cupos: {str(e)}")
        return error_interno()
