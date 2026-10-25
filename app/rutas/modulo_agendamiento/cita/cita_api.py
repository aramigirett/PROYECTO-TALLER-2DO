"""API de la Cita (cabecera + horarios) con el cupo de la agenda. El funcionario sale de la sesión; paciente, agenda y funcionario anulados se rechazan.
Una cita cancelada no se reactiva (no hay endpoint de reactivación). Auditoría con nombres y SIN el motivo de la consulta (es dato de salud).

    GET    /estados-cita · /citas-cabecera[?inactivos=1&paciente=&medico=&desde=&hasta=] · /citas-cabecera/<id> · /citas-detalle/cabecera/<id> · /citas-detalle/<id>
    POST   /citas ('nuevo': cabecera + primer horario en una transacción) · /citas-cabecera · /citas-detalle
    PUT    /citas-cabecera/<id> · /citas-detalle/<id>   ('editar': solo Administrador)
    PATCH  /citas-detalle/<id>/estado ('estado')
    DELETE /citas-cabecera/<id> · /citas-detalle/<id> ('anular': cancela y devuelve el cupo)
    Lookups: /citas/paciente/<id> · /citas-detalle/confirmadas-sin-consulta · /citas-detalle/pendientes · /agenda-detalle/cupos/<id>
"""
from datetime import datetime
from flask import Blueprint, current_app as app, jsonify, request

from app.dao.referenciales_agendamiento.cita.CitaDao import CitaDao, DUPLICADO, EN_USO, INVALIDO, SIN_CUPOS
from app.rutas.modulo_agendamiento.utils import auditar, detalle_cambios, entero_id, error_interno, respuesta_error, validar_hora
from app.rutas.modulo_seguridad.decorators import require_algun_permiso, require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_funcionario_sesion, puede

citaapi = Blueprint('citaapi', __name__)

ETIQ_CAB = {'paciente_nombre': 'Paciente', 'medico_nombre': 'Médico', 'fecha_agenda': 'Fecha', 'nombre_consultorio': 'Consultorio'}
ETIQ_DET = {'cita': 'Cita', 'hora_cita': 'Hora', 'estado_descripcion': 'Estado de la cita'}
MSG_SIN_CUPOS = 'No hay cupos disponibles en este horario.'


def _cita_txt(c):
    return f"{c['paciente_nombre']}, {c['fecha_agenda']}"


def _det_auditado(d, cab):
    return {'cita': _cita_txt(cab), 'hora_cita': d['hora_cita'], 'estado_descripcion': d['estado_descripcion']}


def _conflicto(r):
    if r == SIN_CUPOS:
        return respuesta_error(MSG_SIN_CUPOS, 409)
    return respuesta_error(r[-1], 409 if r[0] in (DUPLICADO, EN_USO) else 400, r[1] if len(r) == 3 else None)


def _funcionario():
    id_f = id_funcionario_sesion()
    if not id_f:
        return None, respuesta_error('Su usuario no está vinculado a un funcionario: no puede registrar citas.', 403)
    return id_f, None


def _datos_horario(data):
    """id_agenda_detalle, hora, motivo, estado de un horario de cita. Devuelve (valores, None) o (None, respuesta_de_error)."""
    ad = entero_id(data.get('id_agenda_detalle'))
    if ad is None:
        return None, respuesta_error('Debe seleccionar un horario de la agenda.', 400, 'id_agenda_detalle')
    hora, error = validar_hora(data.get('hora_cita'), 'hora de la cita')
    if error:
        return None, respuesta_error(error, 400, 'hora_cita')
    motivo = data.get('motivo_consulta')
    motivo = motivo.strip() if isinstance(motivo, str) else ''
    if not motivo:
        return None, respuesta_error('El campo motivo de la consulta es obligatorio y no puede estar vacío.', 400, 'motivo_consulta')
    if len(motivo) > 500:
        return None, respuesta_error('El motivo de la consulta no puede superar los 500 caracteres.', 400, 'motivo_consulta')
    est = entero_id(data.get('id_estado_cita'))
    if est is None:
        return None, respuesta_error('Debe seleccionar el estado de la cita.', 400, 'id_estado_cita')
    return {'id_agenda_detalle': ad, 'hora_cita': hora, 'motivo_consulta': motivo, 'id_estado_cita': est}, None


# ---------------- estados y lecturas ----------------
@citaapi.route('/estados-cita', methods=['GET'])
@require_algun_permiso(('cita', 'ver'))
def getEstadosCita():
    return jsonify({'success': True, 'data': CitaDao().getEstadosCita(), 'error': None}), 200


@citaapi.route('/citas-cabecera', methods=['GET'])
@require_permiso('cita', 'ver')
def getCitasCabecera():
    try:
        a = request.args
        datos = CitaDao().getCitasCabecera(a.get('inactivos', '').lower() in ('1', 'true'), entero_id(a.get('paciente')), entero_id(a.get('medico')),
                                           a.get('desde') or None, a.get('hasta') or None)
        return jsonify({'success': True, 'data': datos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener citas: {str(e)}")
        return error_interno()


@citaapi.route('/citas-cabecera/<int:id_cita_cabecera>', methods=['GET'])
@require_permiso('cita', 'ver')
def getCitaCabecera(id_cita_cabecera):
    c = CitaDao().getCitaCabeceraById(id_cita_cabecera, incluir_inactivos=True)
    if c:
        return jsonify({'success': True, 'data': c, 'error': None}), 200
    return respuesta_error('No se encontró la cita con el ID proporcionado.', 404)


@citaapi.route('/citas-detalle/cabecera/<int:id_cita_cabecera>', methods=['GET'])
@require_permiso('cita', 'ver')
def getDetallesPorCabecera(id_cita_cabecera):
    return jsonify({'success': True, 'data': CitaDao().getDetallesPorCabecera(id_cita_cabecera), 'error': None}), 200


@citaapi.route('/citas-detalle/<int:id_cita_detalle>', methods=['GET'])
@require_permiso('cita', 'ver')
def getDetalle(id_cita_detalle):
    d = CitaDao().getDetalleById(id_cita_detalle)
    if d:
        return jsonify({'success': True, 'data': d, 'error': None}), 200
    return respuesta_error('No se encontró el horario con el ID proporcionado.', 404)


# ---------------- altas ----------------
@citaapi.route('/citas', methods=['POST'])
@require_permiso('cita', 'nuevo')
def addCita():
    data = request.get_json(silent=True) or {}
    paciente = entero_id(data.get('id_paciente'))
    if paciente is None:
        return respuesta_error('Debe seleccionar el paciente.', 400, 'id_paciente')
    h, error = _datos_horario(data)
    if error:
        return error
    id_f, error = _funcionario()
    if error:
        return error
    obs = (data.get('observaciones') or '').strip() or None if isinstance(data.get('observaciones'), (str, type(None))) else None
    dao = CitaDao()
    try:
        r = dao.crearCita(paciente, h['id_agenda_detalle'], h['hora_cita'], h['motivo_consulta'], h['id_estado_cita'], id_f, obs)
        if r == SIN_CUPOS or isinstance(r, tuple) and r[0] in (INVALIDO, DUPLICADO, EN_USO):
            return _conflicto(r)
        if r:
            cab = dao.getCitaCabeceraById(r[0])
            d = dao.getDetalleById(r[1])
            auditar('cita_cabecera', r[0], 'ALTA', detalle_cambios({}, {k: cab.get(k) for k in ETIQ_CAB}, ETIQ_CAB))
            auditar('cita_detalle', r[1], 'ALTA', detalle_cambios({}, _det_auditado(d, cab), ETIQ_DET))
            return jsonify({'success': True, 'data': {'id_cita_cabecera': r[0], 'id_cita_detalle': r[1]},
                            'mensaje': f"Cita de {_cita_txt(cab)} a las {d['hora_cita']} registrada correctamente.", 'error': None}), 201
        return respuesta_error('No se pudo guardar la cita. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al crear cita: {str(e)}")
        return error_interno()


@citaapi.route('/citas-cabecera', methods=['POST'])
@require_permiso('cita', 'nuevo')
def addCitaCabecera():
    data = request.get_json(silent=True) or {}
    paciente, agenda = entero_id(data.get('id_paciente')), entero_id(data.get('id_agenda_cabecera'))
    if paciente is None or agenda is None:
        return respuesta_error('Debe seleccionar el paciente y la agenda.', 400, 'id_paciente' if paciente is None else 'id_agenda_cabecera')
    id_f, error = _funcionario()
    if error:
        return error
    dao = CitaDao()
    try:
        r = dao.guardarCitaCabecera(paciente, agenda, id_f, (data.get('observaciones') or '').strip() or None if isinstance(data.get('observaciones'), (str, type(None))) else None)
        if isinstance(r, tuple):
            return _conflicto(r)
        if r:
            cab = dao.getCitaCabeceraById(r)
            auditar('cita_cabecera', r, 'ALTA', detalle_cambios({}, {k: cab.get(k) for k in ETIQ_CAB}, ETIQ_CAB))
            return jsonify({'success': True, 'data': {'id_cita_cabecera': r}, 'mensaje': f'Cita de {_cita_txt(cab)} registrada correctamente.', 'error': None}), 201
        return respuesta_error('No se pudo guardar la cita. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al crear cabecera: {str(e)}")
        return error_interno()


@citaapi.route('/citas-detalle', methods=['POST'])
@require_permiso('cita', 'nuevo')
def addCitaDetalle():
    data = request.get_json(silent=True) or {}
    cab_id = entero_id(data.get('id_cita_cabecera'))
    if cab_id is None:
        return respuesta_error('Debe indicar la cita.', 400, 'id_cita_cabecera')
    h, error = _datos_horario(data)
    if error:
        return error
    dao = CitaDao()
    try:
        r = dao.guardarCitaDetalle(cab_id, h['id_agenda_detalle'], h['hora_cita'], h['motivo_consulta'], h['id_estado_cita'])
        if r == SIN_CUPOS or isinstance(r, tuple):
            return _conflicto(r)
        if r:
            cab = dao.getCitaCabeceraById(cab_id)
            d = dao.getDetalleById(r)
            auditar('cita_detalle', r, 'ALTA', detalle_cambios({}, _det_auditado(d, cab), ETIQ_DET))
            return jsonify({'success': True, 'data': {'id_cita_detalle': r}, 'mensaje': f"Horario de las {d['hora_cita']} agregado a la cita de {_cita_txt(cab)}.", 'error': None}), 201
        return respuesta_error('No se pudo guardar el horario de la cita.', 500)
    except Exception as e:
        app.logger.error(f"Error al crear detalle: {str(e)}")
        return error_interno()


# ---------------- ediciones ----------------
@citaapi.route('/citas-cabecera/<int:id_cita_cabecera>', methods=['PUT'])
@require_permiso('cita', 'editar')
def updateCitaCabecera(id_cita_cabecera):
    data = request.get_json(silent=True) or {}
    paciente, agenda = entero_id(data.get('id_paciente')), entero_id(data.get('id_agenda_cabecera'))
    if paciente is None or agenda is None:
        return respuesta_error('Debe seleccionar el paciente y la agenda.', 400)
    dao = CitaDao()
    try:
        antes = dao.getCitaCabeceraById(id_cita_cabecera)
        if not antes:
            return respuesta_error('No se encontró la cita con el ID proporcionado.', 404)
        r = dao.updateCitaCabecera(id_cita_cabecera, paciente, agenda, (data.get('observaciones') or '').strip() or None if isinstance(data.get('observaciones'), (str, type(None))) else None)
        if isinstance(r, tuple):
            return _conflicto(r)
        if r:
            nuevo = dao.getCitaCabeceraById(id_cita_cabecera)
            detalle = detalle_cambios({k: antes.get(k) for k in ETIQ_CAB}, {k: nuevo.get(k) for k in ETIQ_CAB}, ETIQ_CAB)
            if detalle:
                auditar('cita_cabecera', id_cita_cabecera, 'MODIFICACION', detalle)
            return jsonify({'success': True, 'data': {'id_cita_cabecera': id_cita_cabecera}, 'mensaje': f'Cita de {_cita_txt(nuevo)} actualizada correctamente.', 'error': None}), 200
        return respuesta_error('No se pudo actualizar la cita.', 404)
    except Exception as e:
        app.logger.error(f"Error al actualizar cabecera: {str(e)}")
        return error_interno()


def _cambiar_estado(id_cita_detalle, id_estado, motivo=None, hora=None):
    """Cambia el estado (y opcionalmente motivo / hora) de un horario, audita y responde."""
    dao = CitaDao()
    antes = dao.getDetalleById(id_cita_detalle)
    if not antes:
        return respuesta_error('No se encontró el horario con el ID proporcionado.', 404)
    r = dao.cambiarEstadoDetalle(id_cita_detalle, id_estado, motivo, hora)
    if r == SIN_CUPOS or isinstance(r, tuple):
        return _conflicto(r)
    if r:
        cab = dao.getCitaCabeceraById(antes['id_cita_cabecera'], incluir_inactivos=True)
        nuevo = dao.getDetalleById(id_cita_detalle)
        detalle = detalle_cambios(_det_auditado(antes, cab), _det_auditado(nuevo, cab), ETIQ_DET)
        if detalle:
            auditar('cita_detalle', id_cita_detalle, 'MODIFICACION', detalle)
        return jsonify({'success': True, 'data': {'id_cita_detalle': id_cita_detalle, 'id_estado_cita': nuevo['id_estado_cita']},
                        'mensaje': f"Cita de {_cita_txt(cab)}: {nuevo['estado_descripcion']}.", 'error': None}), 200
    return respuesta_error('No se pudo actualizar el horario de la cita.', 404)


@citaapi.route('/citas-detalle/<int:id_cita_detalle>', methods=['PUT'])
@require_permiso('cita', 'editar')
def updateCitaDetalle(id_cita_detalle):
    # Edita motivo y hora; el estado se conserva (cambiarlo es PATCH .../estado, acción 'estado').
    data = request.get_json(silent=True) or {}
    actual = CitaDao().getDetalleById(id_cita_detalle)
    if not actual:
        return respuesta_error('No se encontró el horario con el ID proporcionado.', 404)
    hora, error = validar_hora(data.get('hora_cita'), 'hora de la cita')
    if error:
        return respuesta_error(error, 400, 'hora_cita')
    motivo = (data.get('motivo_consulta') or '').strip() if isinstance(data.get('motivo_consulta'), str) else ''
    if not motivo or len(motivo) > 500:
        return respuesta_error('El motivo de la consulta es obligatorio (hasta 500 caracteres).', 400, 'motivo_consulta')
    return _cambiar_estado(id_cita_detalle, actual['id_estado_cita'], motivo, hora)


@citaapi.route('/citas-detalle/<int:id_cita_detalle>/estado', methods=['PATCH'])
@require_permiso('cita', 'estado')
def cambiarEstadoDetalle(id_cita_detalle):
    est = entero_id((request.get_json(silent=True) or {}).get('id_estado_cita'))
    if est is None:
        return respuesta_error('El campo estado de la cita es obligatorio.', 400, 'id_estado_cita')
    try:
        return _cambiar_estado(id_cita_detalle, est)
    except Exception as e:
        app.logger.error(f"Error al cambiar el estado del horario {id_cita_detalle}: {str(e)}")
        return error_interno()


# ---------------- bajas ----------------
@citaapi.route('/citas-cabecera/<int:id_cita_cabecera>', methods=['DELETE'])
@require_permiso('cita', 'anular')
def deleteCitaCabecera(id_cita_cabecera):
    dao = CitaDao()
    try:
        cab = dao.getCitaCabeceraById(id_cita_cabecera)
        r = dao.deleteCitaCabecera(id_cita_cabecera)
        if isinstance(r, tuple):
            return _conflicto(r)
        if r:
            auditar('cita_cabecera', id_cita_cabecera, 'BAJA', detalle_cambios({}, {k: cab.get(k) for k in ETIQ_CAB}, ETIQ_CAB))
            return jsonify({'success': True, 'mensaje': f'Cita de {_cita_txt(cab)} anulada correctamente.', 'error': None}), 200
        return respuesta_error('No se encontró la cita con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al anular cabecera {id_cita_cabecera}: {str(e)}")
        return error_interno()


@citaapi.route('/citas-detalle/<int:id_cita_detalle>', methods=['DELETE'])
@require_permiso('cita', 'anular')
def deleteCitaDetalle(id_cita_detalle):
    dao = CitaDao()
    try:
        antes = dao.getDetalleById(id_cita_detalle)
        r = dao.deleteCitaDetalle(id_cita_detalle)
        if isinstance(r, tuple):
            return _conflicto(r)
        if r:
            cab = dao.getCitaCabeceraById(antes['id_cita_cabecera'], incluir_inactivos=True)
            nuevo = dao.getDetalleById(id_cita_detalle)
            auditar('cita_detalle', id_cita_detalle, 'MODIFICACION', detalle_cambios(_det_auditado(antes, cab), _det_auditado(nuevo, cab), ETIQ_DET))
            return jsonify({'success': True, 'mensaje': f"Cita de {_cita_txt(cab)} a las {antes['hora_cita']} cancelada correctamente.", 'error': None}), 200
        return respuesta_error('No se encontró el horario con el ID proporcionado o ya estaba cancelado.', 404)
    except Exception as e:
        app.logger.error(f"Error al cancelar el horario {id_cita_detalle}: {str(e)}")
        return error_interno()


# ---------------- lookups de otras pantallas (con el permiso de la pantalla que los usa) ----------------
@citaapi.route('/agenda-detalle/cupos/<int:id_agenda_detalle>', methods=['GET'])
@require_permiso('cita', 'ver')
def verificarCupos(id_agenda_detalle):
    cupos = CitaDao().verificarCuposDisponibles(id_agenda_detalle)
    return jsonify({'success': True, 'data': {'id_agenda_detalle': id_agenda_detalle, 'cupos_disponibles': cupos}, 'error': None}), 200


@citaapi.route('/citas/paciente/<int:id_paciente>', methods=['GET'])
@require_algun_permiso(('avisos', 'ver'), ('cita', 'ver'), ('consulta', 'ver'))
def obtener_citas_paciente(id_paciente):
    """Citas vigentes del paciente (Avisos elige la cita a recordar)."""
    try:
        citas = CitaDao().obtenerCitasPacienteConfirmadas(id_paciente)
        return jsonify(success=True, data=citas, cantidad=len(citas)), 200
    except Exception as e:
        app.logger.error(f"Error en obtener_citas_paciente: {e}")
        return error_interno()


@citaapi.route('/citas-detalle/pendientes', methods=['GET'])
@require_algun_permiso(('avisos', 'ver'), ('cita', 'ver'))
def getCitasPendientes():
    return jsonify({'success': True, 'data': CitaDao().getCitasPendientes(), 'error': None}), 200


@citaapi.route('/citas-detalle/confirmadas-sin-consulta', methods=['GET'])
@require_algun_permiso(('consulta', 'ver'), ('cita', 'ver'))
def getCitasConfirmadasSinConsulta():
    """Fuente del selector de 'Nueva Consulta' en Consultorio."""
    try:
        return jsonify({'success': True, 'data': CitaDao().getCitasConfirmadasSinConsulta(), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener citas confirmadas sin consulta: {str(e)}")
        return error_interno()
