"""
=====================================================
API: Sesión de Tratamiento (/api/v1/sesiones-tratamiento)
Gestionar Procedimientos e Insumos Utilizados: Ver / Nuevo / Anular. Cada sesión se registra dentro de una consulta (mismo paciente y médico que el
tratamiento). Crea y anula SOLO el médico de esa consulta, con la consulta programada o en proceso (revalidado en la transacción). Un médico solo lee lo suyo.

Auditoría (`auditoria_cambios`, entidad `sesiones_tratamiento`): ALTA y BAJA con el N.º de sesión, el tratamiento, el N.º de consulta y el paciente (con CI);
y, cuando la sesión cambia el estado del tratamiento (pendiente <-> en seguimiento), una MODIFICACION de `tratamientos`. NUNCA con descripciones,
observaciones, procedimientos ni insumos (dato de salud).
=====================================================
"""
from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_consultorio.consulta.ConsultaDao import numero_consulta
from app.dao.referenciales_consultorio.sesion_tratamiento.SesionTratamientoDao import SesionTratamientoDao
from app.dao.referenciales_consultorio.tratamiento.TratamientoDao import TratamientoDao
from app.rutas.modulo_consultorio.utils import auditar as _auditar, error_interno, respuesta_error
from app.rutas.modulo_consultorio.validadores_clinicos import validar_sesion
from app.rutas.modulo_seguridad.decorators import require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion
from app.Services.auditoria_detalle import DetalleAuditoria

sesiontratamientoapi = Blueprint('sesiontratamientoapi', __name__)

ENTIDAD = 'sesiones_tratamiento'

ERRORES = {
    'CONSULTA_NO_ENCONTRADA': (404, 'No se encontró la consulta con el ID proporcionado.'),
    'TRATAMIENTO_NO_ENCONTRADO': (404, 'No se encontró el tratamiento seleccionado.'),
    'SESION_NO_ENCONTRADA': (404, 'No se encontró la sesión con el ID proporcionado, o ya estaba anulada.'),
    'NO_ES_SU_MEDICO': (403, 'Solo el médico de la consulta puede registrar o anular sus sesiones.'),
    'TRATAMIENTO_OTRA_CONSULTA': (409, 'La consulta debe ser del mismo paciente y del mismo médico que el tratamiento.'),
    'PROCEDIMIENTO_NO_EXISTE': (400, 'Alguno de los procedimientos seleccionados no existe.'),
    'INSUMO_NO_EXISTE': (400, 'Alguno de los insumos seleccionados no existe.'),
    'NO_ES_ULTIMA': (409, 'Solo se puede anular la última sesión del tratamiento.'),
    'TRATAMIENTO_FINALIZADO': (409, 'No se puede anular: el tratamiento ya está finalizado.'),
    'DATOS_INVALIDOS': (400, 'Los datos de la sesión no cumplen las reglas de la base de datos.'),
}
CAMPO_DEL_ERROR = {'PROCEDIMIENTO_NO_EXISTE': 'procedimientos', 'PROCEDIMIENTO_INACTIVO': 'procedimientos', 'INSUMO_NO_EXISTE': 'insumos', 'INSUMO_INACTIVO': 'insumos'}


def _error(r, anulando=False):
    codigo = r.get('error')
    if codigo == 'CONSULTA_NO_ABIERTA':
        estado = r.get('estado')
        if anulando:
            return respuesta_error(f'No se puede anular: la consulta de la sesión está {estado}.', 409)
        return respuesta_error(f'La consulta está {estado}: ya no admite nuevas sesiones.', 409)
    if codigo == 'TRATAMIENTO_NO_ACTIVO':
        return respuesta_error(f"El tratamiento está {r.get('estado')}: ya no admite sesiones (debe estar pendiente o en seguimiento).", 409)
    if codigo == 'PROCEDIMIENTO_INACTIVO':
        return respuesta_error(f"Hay procedimientos inactivos: {r['detalle']}. Quítelos de la selección.", 409, 'procedimientos')
    if codigo == 'INSUMO_INACTIVO':
        return respuesta_error(f"Hay insumos inactivos: {r['detalle']}. Quítelos de la selección.", 409, 'insumos')
    if codigo in ERRORES:
        status, mensaje = ERRORES[codigo]
        return respuesta_error(mensaje, status, CAMPO_DEL_ERROR.get(codigo))
    return error_interno()


def _paciente(ctx):
    return f"{ctx['paciente']} (CI {ctx['cedula']})"


def _acceso_tratamiento(id_tratamiento):
    """(tratamiento, None) o (None, respuesta de error): existe y, si el usuario es médico, es suyo."""
    t = TratamientoDao().getTratamientoById(id_tratamiento)
    if not t:
        return None, respuesta_error('No se encontró el tratamiento seleccionado.', 404)
    medico = id_medico_sesion()
    if medico and t['id_medico'] != medico:
        return None, respuesta_error('Esa información no está disponible para su usuario.', 403)
    return t, None


@sesiontratamientoapi.route('/sesiones-tratamiento/tratamiento/<int:id_tratamiento>', methods=['GET'])
@require_permiso('sesiontratamiento', 'ver')
def getSesionesByTratamiento(id_tratamiento):
    try:
        _, prohibido = _acceso_tratamiento(id_tratamiento)
        if prohibido:
            return prohibido
        return jsonify({'success': True, 'data': SesionTratamientoDao().getSesionesByTratamiento(id_tratamiento), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener sesiones de tratamiento: {str(e)}")
        return error_interno()


@sesiontratamientoapi.route('/sesiones-tratamiento/<int:id_sesion>', methods=['GET'])
@require_permiso('sesiontratamiento', 'ver')
def getSesion(id_sesion):
    try:
        sesion = SesionTratamientoDao().getSesionById(id_sesion)
        if not sesion:
            return respuesta_error('No se encontró la sesión con el ID proporcionado.', 404)
        medico = id_medico_sesion()
        if medico and sesion['id_medico'] != medico:
            return respuesta_error('Esa información no está disponible para su usuario.', 403)
        return jsonify({'success': True, 'data': sesion, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener la sesión: {str(e)}")
        return error_interno()


def _auditar_estado(id_tratamiento, ctx, id_consulta, anterior, nuevo):
    etiquetas = {'pendiente': 'Pendiente', 'en_seguimiento': 'En seguimiento'}
    ant, nue = etiquetas[anterior], etiquetas[nuevo]
    _auditar('tratamientos', id_tratamiento, 'MODIFICACION',
             DetalleAuditoria(f"Tratamiento de {ctx['tipo']}; Consulta {numero_consulta(id_consulta)}; Paciente: {_paciente(ctx)}; Estado: {ant} -> {nue}",
                              {'Estado': ant}, {'Estado': nue}))


@sesiontratamientoapi.route('/sesiones-tratamiento', methods=['POST'])
@require_permiso('sesiontratamiento', 'nuevo')
def addSesion():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return respuesta_error('Los datos enviados no son válidos.', 400)
    ids = {}
    for campo in ('id_tratamiento', 'id_consulta_cab'):
        if data.get(campo) in (None, ''):
            return respuesta_error(f'El campo {campo} es obligatorio.', 400, campo)
        try:
            ids[campo] = int(data[campo])
        except (ValueError, TypeError):
            return respuesta_error(f'El campo {campo} no es válido.', 400, campo)
    valores, error, campo = validar_sesion(data)
    if error:
        return respuesta_error(error, 400, campo)
    valores.update(ids)
    try:
        r = SesionTratamientoDao().guardarSesion(valores, id_medico_sesion())
        if 'id_sesion' in r:
            ctx = r['contexto']
            nuevos = {'Sesión': r['numero_sesion'], 'Tratamiento': ctx['tipo'], 'Consulta': numero_consulta(ids['id_consulta_cab']), 'Paciente': _paciente(ctx)}
            _auditar(ENTIDAD, r['id_sesion'], 'ALTA', DetalleAuditoria('; '.join(f'{k}: {v}' for k, v in nuevos.items()), {}, nuevos))
            if ctx['pasa_a_seguimiento']:
                _auditar_estado(ids['id_tratamiento'], ctx, ids['id_consulta_cab'], 'pendiente', 'en_seguimiento')
            return jsonify({'success': True, 'data': {'id_sesion': r['id_sesion'], 'numero_sesion': r['numero_sesion']},
                            'mensaje': f"Sesión {r['numero_sesion']} del tratamiento de {ctx['tipo']} registrada correctamente.", 'error': None}), 201
        return _error(r)
    except Exception as e:
        app.logger.error(f"Error al agregar sesión de tratamiento: {str(e)}")
        return error_interno()


@sesiontratamientoapi.route('/sesiones-tratamiento/<int:id_sesion>', methods=['DELETE'])
@require_permiso('sesiontratamiento', 'anular')
def deleteSesion(id_sesion):
    try:
        r = SesionTratamientoDao().anularSesion(id_sesion, id_medico_sesion())
        if r.get('ok'):
            ctx = r['contexto']
            _auditar(ENTIDAD, id_sesion, 'BAJA',
                     f"Sesión {r['numero_sesion']} del tratamiento de {ctx['tipo']}; Consulta {numero_consulta(r['id_consulta_cab'])}; Paciente: {_paciente(ctx)}")
            if r['vuelve_a_pendiente']:
                _auditar_estado(r['id_tratamiento'], ctx, r['id_consulta_cab'], 'en_seguimiento', 'pendiente')
            return jsonify({'success': True, 'mensaje': f"Sesión {r['numero_sesion']} anulada correctamente.", 'error': None}), 200
        return _error(r, anulando=True)
    except Exception as e:
        app.logger.error(f"Error al anular sesión de tratamiento: {str(e)}")
        return error_interno()
