from datetime import datetime
from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_agendamiento.disponibilidad_horaria.DisponibilidadHorariaDao import (
    DisponibilidadDao, DUPLICADO, NO_EXISTE, YA_ACTIVO)
from app.rutas.modulo_agendamiento.utils import (
    auditar, detalle_cambios, entero_id, error_interno, respuesta_error, validar_cupos, validar_fecha, validar_hora, validar_horario)
from app.rutas.modulo_seguridad.decorators import require_permiso, require_login
from app.rutas.modulo_seguridad.permisos_contexto import puede

disponibilidadapi = Blueprint('disponibilidadapi', __name__)

ENTIDAD = 'disponibilidad_horaria'
ETIQUETAS = {'medico': 'Médico', 'dia': 'Día', 'turno': 'Turno', 'fecha': 'Fecha', 'desde': 'Desde', 'hasta': 'Hasta', 'cupos': 'Cupos'}


def _para_auditar(d):
    """Lo que se audita de una disponibilidad: nombres (no IDs)."""
    return {'medico': d['medico_nombre'], 'dia': d['des_dia'], 'turno': d['des_turno'], 'fecha': d['dispo_fecha'],
            'desde': d['dispo_hora_inicio'][:5], 'hasta': d['dispo_hora_fin'][:5], 'cupos': d['dispo_cupos']}


def _descripcion(d):
    return f"{d['medico_nombre']}, {d['dispo_fecha']} de {d['dispo_hora_inicio'][:5]} a {d['dispo_hora_fin'][:5]}"


def _validar(data):
    """Valida el cuerpo del alta / modificación. Devuelve (valores, None) o (None, respuesta_de_error)."""
    if not isinstance(data, dict):
        return None, respuesta_error('Los datos enviados no son válidos.', 400)
    ids = {}
    for campo, etiqueta in (('id_medico', 'médico'), ('id_turno', 'turno')):      # el día NO se envía: se calcula desde la fecha
        ids[campo] = entero_id(data.get(campo))
        if ids[campo] is None:
            return None, respuesta_error(f'El campo {etiqueta} es obligatorio.', 400, campo)
    fecha, error = validar_fecha(data.get('dispo_fecha'), 'fecha')
    if error:
        return None, respuesta_error(error, 400, 'dispo_fecha')
    inicio, error = validar_hora(data.get('dispo_hora_inicio'), 'hora de inicio')
    if error:
        return None, respuesta_error(error, 400, 'dispo_hora_inicio')
    fin, error = validar_hora(data.get('dispo_hora_fin'), 'hora de fin')
    if error:
        return None, respuesta_error(error, 400, 'dispo_hora_fin')
    error = validar_horario(inicio, fin)
    if error:
        return None, respuesta_error(error, 400, 'dispo_hora_fin')
    cupos, error = validar_cupos(data.get('dispo_cupos'))
    if error:
        return None, respuesta_error(error, 400, 'dispo_cupos')
    return {**ids, 'dispo_fecha': fecha, 'dispo_hora_inicio': inicio, 'dispo_hora_fin': fin, 'dispo_cupos': cupos}, None


def _args(v):
    return (v['id_medico'], v['id_turno'], v['dispo_hora_inicio'], v['dispo_hora_fin'], v['dispo_fecha'], v['dispo_cupos'])


# Lista las disponibilidades activas (alimenta combos de otras pantallas); `?inactivos=1` exige 'ver'
@disponibilidadapi.route('/disponibilidades', methods=['GET'])
@require_login
def getDisponibilidades():
    incluir_inactivos = request.args.get('inactivos', '').lower() in ('1', 'true')
    if incluir_inactivos and not puede('disponibilidad', 'ver'):
        return respuesta_error('No tiene permiso para ver las disponibilidades inactivas.', 403)
    try:
        return jsonify({'success': True, 'data': DisponibilidadDao().getDisponibilidades(incluir_inactivos), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener disponibilidades: {str(e)}")
        return error_interno()


# Disponibilidades de un médico en una fecha (para la agenda)
@disponibilidadapi.route('/disponibilidades/medico-fecha', methods=['GET'])
@require_login
def getDisponibilidadesPorMedicoFecha():
    id_medico = entero_id(request.args.get('id_medico'))
    fecha = request.args.get('fecha')  # formato YYYY-MM-DD
    if not id_medico or not fecha:
        return respuesta_error('Faltan parámetros id_medico o fecha', 400)
    try:
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
    except ValueError:
        return respuesta_error('Formato de fecha inválido. Use YYYY-MM-DD', 400)
    try:
        return jsonify({'success': True, 'data': DisponibilidadDao().getDisponibilidadesPorMedicoFecha(id_medico, fecha_obj), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener disponibilidades: {str(e)}")
        return error_interno()


# Próxima fecha (posterior a `desde`) con disponibilidad del médico: la usa la agenda cuando no hay horarios para su fecha
@disponibilidadapi.route('/disponibilidades/proxima', methods=['GET'])
@require_login
def getProximaDisponibilidad():
    id_medico = entero_id(request.args.get('id_medico'))
    desde = request.args.get('desde')  # formato YYYY-MM-DD
    if not id_medico or not desde:
        return respuesta_error('Faltan parámetros id_medico o desde', 400)
    try:
        desde_obj = datetime.strptime(desde, '%Y-%m-%d').date()
    except ValueError:
        return respuesta_error('Formato de fecha inválido. Use YYYY-MM-DD', 400)
    try:
        return jsonify({'success': True, 'data': DisponibilidadDao().getProximaDisponibilidad(id_medico, desde_obj), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener la próxima disponibilidad: {str(e)}")
        return error_interno()


@disponibilidadapi.route('/disponibilidades/<int:id_disponibilidad>', methods=['GET'])
@require_permiso('disponibilidad', 'ver')
def getDisponibilidadById(id_disponibilidad):
    try:
        d = DisponibilidadDao().getDisponibilidadById(id_disponibilidad)
        if d:
            return jsonify({'success': True, 'data': d, 'error': None}), 200
        return respuesta_error('No se encontró la disponibilidad con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al obtener disponibilidad: {str(e)}")
        return error_interno()


@disponibilidadapi.route('/disponibilidades', methods=['POST'])
@require_permiso('disponibilidad', 'nuevo')
def addDisponibilidad():
    valores, error = _validar(request.get_json(silent=True))
    if error:
        return error
    dao = DisponibilidadDao()
    try:
        resultado = dao.guardarDisponibilidad(*_args(valores))
        if isinstance(resultado, tuple):  # ("INVALIDO", mensaje)
            return respuesta_error(resultado[1], 400)
        if resultado == DUPLICADO:
            return respuesta_error('El médico ya tiene una disponibilidad que se superpone en esa fecha y horario.', 409)
        if resultado:
            d = dao.getDisponibilidadById(resultado)
            auditar(ENTIDAD, resultado, 'ALTA', detalle_cambios({}, _para_auditar(d), ETIQUETAS))
            return jsonify({'success': True, 'data': {'id_disponibilidad': resultado},
                            'mensaje': f'Disponibilidad de {_descripcion(d)} agregada correctamente.', 'error': None}), 201
        return respuesta_error('No se pudo guardar la disponibilidad. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al agregar disponibilidad: {str(e)}")
        return error_interno()


@disponibilidadapi.route('/disponibilidades/<int:id_disponibilidad>', methods=['PUT'])
@require_permiso('disponibilidad', 'editar')
def updateDisponibilidad(id_disponibilidad):
    valores, error = _validar(request.get_json(silent=True))
    if error:
        return error
    dao = DisponibilidadDao()
    try:
        anterior = dao.getDisponibilidadById(id_disponibilidad)
        if not anterior:
            return respuesta_error('No se encontró la disponibilidad con el ID proporcionado.', 404)
        resultado = dao.updateDisponibilidad(id_disponibilidad, *_args(valores))
        if isinstance(resultado, tuple):  # ("EN_USO", motivo) o ("INVALIDO", mensaje)
            return respuesta_error(resultado[1], 409 if resultado[0] == 'EN_USO' else 400)
        if resultado == DUPLICADO:
            return respuesta_error('El médico ya tiene una disponibilidad que se superpone en esa fecha y horario.', 409)
        if resultado:
            nuevo = dao.getDisponibilidadById(id_disponibilidad)
            detalle = detalle_cambios(_para_auditar(anterior), _para_auditar(nuevo), ETIQUETAS)
            if detalle:  # sin cambios: no audita
                auditar(ENTIDAD, id_disponibilidad, 'MODIFICACION', detalle)
            return jsonify({'success': True, 'data': {'id_disponibilidad': id_disponibilidad},
                            'mensaje': f'Disponibilidad de {_descripcion(nuevo)} actualizada correctamente.', 'error': None}), 200
        return respuesta_error('No se pudo actualizar la disponibilidad.', 404)
    except Exception as e:
        app.logger.error(f"Error al actualizar disponibilidad: {str(e)}")
        return error_interno()


@disponibilidadapi.route('/disponibilidades/<int:id_disponibilidad>', methods=['DELETE'])
@require_permiso('disponibilidad', 'anular')
def deleteDisponibilidad(id_disponibilidad):
    dao = DisponibilidadDao()
    try:
        registro = dao.getDisponibilidadById(id_disponibilidad)
        resultado = dao.deleteDisponibilidad(id_disponibilidad)
        if isinstance(resultado, tuple):  # ("EN_USO", motivo)
            return respuesta_error(resultado[1], 409)
        if resultado:
            auditar(ENTIDAD, id_disponibilidad, 'BAJA', detalle_cambios({}, _para_auditar(registro), ETIQUETAS))
            return jsonify({'success': True, 'mensaje': f'Disponibilidad de {_descripcion(registro)} anulada correctamente.', 'error': None}), 200
        return respuesta_error('No se encontró la disponibilidad con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al anular disponibilidad: {str(e)}")
        return error_interno()


# Reactiva una disponibilidad anulada (permiso: el mismo de editar)
@disponibilidadapi.route('/disponibilidades/<int:id_disponibilidad>/reactivar', methods=['PATCH'])
@require_permiso('disponibilidad', 'editar')
def reactivarDisponibilidad(id_disponibilidad):
    dao = DisponibilidadDao()
    try:
        resultado = dao.reactivarDisponibilidad(id_disponibilidad)
        if isinstance(resultado, tuple):  # ("INVALIDO", mensaje)
            return respuesta_error('No se puede reactivar: ' + resultado[1][0].lower() + resultado[1][1:], 409)
        if resultado == NO_EXISTE:
            return respuesta_error('No se encontró la disponibilidad con el ID proporcionado.', 404)
        if resultado == YA_ACTIVO:
            return respuesta_error('La disponibilidad ya está activa.', 409)
        if resultado == DUPLICADO:
            return respuesta_error('No se puede reactivar: el médico ya tiene una disponibilidad activa que se superpone en esa fecha y horario.', 409)
        if resultado:
            d = dao.getDisponibilidadById(id_disponibilidad)
            auditar(ENTIDAD, id_disponibilidad, 'REACTIVACION', detalle_cambios({}, _para_auditar(d), ETIQUETAS))
            return jsonify({'success': True, 'data': d, 'mensaje': f'Disponibilidad de {_descripcion(d)} reactivada correctamente.', 'error': None}), 200
        return respuesta_error('No se pudo reactivar la disponibilidad. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al reactivar disponibilidad: {str(e)}")
        return error_interno()
