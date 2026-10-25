"""API de Avisos y Recordatorios. Se elige el paciente o la cita, se presiona "Enviar" y el mensaje sale solo de una plantilla (editable antes de enviar, no
obligatorio). WhatsApp Web con sesión persistente (el QR se escanea una vez) y, si no está vinculado o falla, el mismo recordatorio por correo. Cada aviso
queda ENVIADO o ERROR con el canal por el que salió y el motivo; la auditoría NO guarda el texto del mensaje.

    GET    /avisos[?inactivos=1&estado_envio=&desde=&hasta=] · /avisos/<id> · /avisos/<id>/mensaje-preview · /avisos/estadisticas      ('ver')
    POST   /avisos ('nuevo')   PUT /avisos/<id> ('editar': solo Administrador)   DELETE /avisos/<id> ('anular')   PATCH /avisos/<id>/reactivar ('anular')
    PATCH  /avisos/<id>/estado ('estado': confirmación del paciente)   POST /avisos/<id>/enviar ('estado': envío)
    GET    /avisos/whatsapp/estado ('ver')   POST /avisos/whatsapp/vincular ('estado')
"""
import threading
from flask import Blueprint, current_app as app, jsonify, request

from app.dao.referenciales_agendamiento.avisosRecordatorios.AvisosRecordatorioDao import (
    AvisoRecordatorioDao, DUPLICADO, EN_USO, INVALIDO, NO_EXISTE, YA_ACTIVO, sin_contacto)
from app.Services.whatsapp_service import construir_mensaje, enviar_recordatorio, sesion_whatsapp
from app.rutas.modulo_agendamiento.utils import auditar, detalle_cambios, entero_id, error_interno, respuesta_error, validar_fecha, validar_hora
from app.rutas.modulo_seguridad.decorators import require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_funcionario_sesion, puede

avisoapi = Blueprint('avisoapi', __name__, url_prefix='/api/v1')

dao = AvisoRecordatorioDao()
FORMAS = ('WhatsApp', 'Gmail')
ETIQ = {'paciente': 'Paciente', 'medico': 'Médico', 'nombre_consultorio': 'Consultorio', 'fecha_cita': 'Fecha de la cita', 'hora_cita': 'Hora', 'forma_envio': 'Forma de envío'}
ETIQ_ENVIO = {'estado_envio': 'Estado del envío', 'canal_enviado': 'Canal', 'motivo_error': 'Motivo'}
_enviando = set()
_candado = threading.Lock()


def _auditado(a):
    return {k: a.get(k) for k in ETIQ}


def _quien(a):
    return f"{a['paciente']}, {a['fecha_cita']} {a['hora_cita']}"


def _conflicto(r):
    return respuesta_error(r[-1], 409 if r[0] in (DUPLICADO, EN_USO) else 400, r[1] if len(r) == 3 else None)


def _validar(data):
    """Valida el cuerpo del alta / modificación. Con cita, paciente / médico / consultorio / fecha / hora salen de la cita (se ignoran los del navegador)."""
    if not isinstance(data, dict):
        return None, respuesta_error('Los datos enviados no son válidos.', 400)
    v = {'forma_envio': data.get('forma_envio') or 'WhatsApp'}
    if v['forma_envio'] not in FORMAS:
        return None, respuesta_error('La forma de envío debe ser WhatsApp o Gmail.', 400, 'forma_envio')
    msg = data.get('mensaje')
    if msg is not None and not isinstance(msg, str):
        return None, respuesta_error('El mensaje debe ser un texto.', 400, 'mensaje')
    msg = (msg or '').strip()
    if len(msg) > 1000:
        return None, respuesta_error('El mensaje no puede superar los 1000 caracteres.', 400, 'mensaje')
    v['mensaje'] = msg or None
    cita = data.get('id_cita_detalle')
    if cita not in (None, ''):
        v['id_cita_detalle'] = entero_id(cita)
        if v['id_cita_detalle'] is None:
            return None, respuesta_error('La cita seleccionada no es válida.', 400, 'id_cita_detalle')
        v.update({'id_paciente': None, 'fecha_cita': None, 'hora_cita': None})
        return v, None
    v['id_paciente'] = entero_id(data.get('id_paciente'))
    if v['id_paciente'] is None:
        return None, respuesta_error('Debe seleccionar el paciente o la cita.', 400, 'id_paciente')
    v['fecha_cita'], error = validar_fecha(data.get('fecha_cita'), 'fecha de la cita')
    if error:
        return None, respuesta_error(error, 400, 'fecha_cita')
    v['hora_cita'], error = validar_hora(data.get('hora_cita'), 'hora de la cita')
    if error:
        return None, respuesta_error(error, 400, 'hora_cita')
    for campo in ('id_medico', 'codigo'):
        v[campo] = entero_id(data.get(campo)) if data.get(campo) not in (None, '') else None
        if data.get(campo) not in (None, '') and v[campo] is None:
            return None, respuesta_error('El médico o el consultorio seleccionado no es válido.', 400, campo)
    return v, None


@avisoapi.route('/avisos', methods=['GET'])
@require_permiso('avisos', 'ver')
def listar_avisos():
    a = request.args
    try:
        datos = dao.getAvisos(a.get('inactivos', '').lower() in ('1', 'true'), a.get('estado_envio') or None, a.get('desde') or None, a.get('hasta') or None)
        return jsonify(success=True, data=[sin_contacto(x) for x in datos], error=None)
    except Exception as e:
        app.logger.error(f"Error en listar_avisos: {e}")
        return error_interno()


@avisoapi.route('/avisos/<int:id_aviso>', methods=['GET'])
@require_permiso('avisos', 'ver')
def get_aviso(id_aviso):
    a = dao.getAvisoById(id_aviso, incluir_inactivos=True)
    if a:
        return jsonify(success=True, data=sin_contacto(a), error=None)
    return respuesta_error('No se encontró el aviso con el ID proporcionado.', 404)


@avisoapi.route('/avisos', methods=['POST'])
@require_permiso('avisos', 'nuevo')
def crear_aviso():
    v, error = _validar(request.get_json(silent=True))
    if error:
        return error
    id_f = id_funcionario_sesion()
    if not id_f:
        return respuesta_error('Su usuario no está vinculado a un funcionario: no puede registrar avisos.', 403)
    try:
        r = dao.addAviso(v, id_f)
        if isinstance(r, tuple):
            return _conflicto(r)
        if r:
            a = dao.getAvisoById(r)
            auditar('avisos_recordatorios', r, 'ALTA', detalle_cambios({}, _auditado(a), ETIQ))
            return jsonify(success=True, data={'id_aviso': r}, mensaje=f'Aviso para {_quien(a)} registrado correctamente.', error=None), 201
        return respuesta_error('No se pudo guardar el aviso. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error en crear_aviso: {e}")
        return error_interno()


@avisoapi.route('/avisos/<int:id_aviso>', methods=['PUT'])
@require_permiso('avisos', 'editar')
def actualizar_aviso(id_aviso):
    v, error = _validar(request.get_json(silent=True))
    if error:
        return error
    try:
        antes = dao.getAvisoById(id_aviso)
        if not antes:
            return respuesta_error('No se encontró el aviso con el ID proporcionado.', 404)
        r = dao.updateAviso(id_aviso, v)
        if isinstance(r, tuple):
            return _conflicto(r)
        if r:
            nuevo = dao.getAvisoById(id_aviso)
            detalle = detalle_cambios(_auditado(antes), _auditado(nuevo), ETIQ)
            if detalle:
                auditar('avisos_recordatorios', id_aviso, 'MODIFICACION', detalle)
            return jsonify(success=True, data={'id_aviso': id_aviso}, mensaje=f'Aviso para {_quien(nuevo)} actualizado correctamente.', error=None)
        return respuesta_error('No se pudo actualizar el aviso.', 404)
    except Exception as e:
        app.logger.error(f"Error en actualizar_aviso: {e}")
        return error_interno()


@avisoapi.route('/avisos/<int:id_aviso>', methods=['DELETE'])
@require_permiso('avisos', 'anular')
def eliminar_aviso(id_aviso):
    try:
        a = dao.getAvisoById(id_aviso)
        if a and dao.deleteAviso(id_aviso):
            auditar('avisos_recordatorios', id_aviso, 'BAJA', detalle_cambios({}, _auditado(a), ETIQ))
            return jsonify(success=True, mensaje=f'Aviso para {_quien(a)} anulado correctamente.', error=None)
        return respuesta_error('No se encontró el aviso con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error en eliminar_aviso: {e}")
        return error_interno()


@avisoapi.route('/avisos/<int:id_aviso>/reactivar', methods=['PATCH'])
@require_permiso('avisos', 'anular')
def reactivar_aviso(id_aviso):
    try:
        r = dao.reactivarAviso(id_aviso)
        if r == NO_EXISTE:
            return respuesta_error('No se encontró el aviso con el ID proporcionado.', 404)
        if r == YA_ACTIVO:
            return respuesta_error('El aviso ya está activo.', 409)
        if isinstance(r, tuple):
            return respuesta_error('No se puede reactivar: ' + r[-1][0].lower() + r[-1][1:], 409, r[1])
        if r:
            a = dao.getAvisoById(id_aviso)
            auditar('avisos_recordatorios', id_aviso, 'REACTIVACION', detalle_cambios({}, _auditado(a), ETIQ))
            return jsonify(success=True, data=sin_contacto(a), mensaje=f'Aviso para {_quien(a)} reactivado correctamente.', error=None)
        return respuesta_error('No se pudo reactivar el aviso. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error en reactivar_aviso: {e}")
        return error_interno()


@avisoapi.route('/avisos/<int:id_aviso>/estado', methods=['PATCH'])
@require_permiso('avisos', 'estado')
def cambiar_estado_aviso(id_aviso):
    """Confirmación del paciente (acción 'estado')."""
    nuevo = (request.get_json(silent=True) or {}).get('estado_confirmacion')
    if nuevo not in ('Pendiente', 'Confirmado', 'Cancelado'):
        return respuesta_error('La confirmación debe ser Pendiente, Confirmado o Cancelado.', 400, 'estado_confirmacion')
    try:
        a = dao.getAvisoById(id_aviso)
        if not a:
            return respuesta_error('No se encontró el aviso con el ID proporcionado.', 404)
        if a['estado_confirmacion'] != nuevo and dao.cambiarConfirmacion(id_aviso, nuevo):
            auditar('avisos_recordatorios', id_aviso, 'MODIFICACION', detalle_cambios({'c': a['estado_confirmacion']}, {'c': nuevo}, {'c': 'Confirmación del paciente'}))
        return jsonify(success=True, data={'estado_confirmacion': nuevo}, mensaje=f'Aviso para {_quien(a)}: {nuevo}.', error=None)
    except Exception as e:
        app.logger.error(f"Error en cambiar_estado_aviso: {e}")
        return error_interno()


# ---------------- envío ----------------
@avisoapi.route('/avisos/<int:id_aviso>/mensaje-preview', methods=['GET'])
@require_permiso('avisos', 'ver')
def preview_mensaje(id_aviso):
    """El mensaje que saldría (plantilla con los datos actuales de la cita), para editarlo antes de enviar."""
    a = dao.getAvisoById(id_aviso)
    if not a:
        return respuesta_error('No se encontró el aviso con el ID proporcionado.', 404)
    texto = a['mensaje'] if (a['mensaje'] and a['estado_envio'] == 'Pendiente') else construir_mensaje(a)
    return jsonify(success=True, mensaje=texto, data={'forma_envio': a['forma_envio']}, error=None)


@avisoapi.route('/avisos/<int:id_aviso>/enviar', methods=['POST'])
@require_permiso('avisos', 'estado')
def enviar_aviso(id_aviso):
    """Envía el aviso: WhatsApp (si está vinculado) y, si no, el mismo recordatorio por correo. Síncrono: tarda unos segundos."""
    data = request.get_json(silent=True) or {}
    texto = data.get('mensaje')
    if texto is not None and (not isinstance(texto, str) or len(texto) > 1000):
        return respuesta_error('El mensaje debe ser un texto de hasta 1000 caracteres.', 400, 'mensaje')
    a = dao.getAvisoById(id_aviso)
    if not a:
        return respuesta_error('No se encontró el aviso con el ID proporcionado.', 404)
    if a['estado_envio'] == 'Enviado':
        return respuesta_error(f"El aviso para {_quien(a)} ya fue enviado por {a['canal_enviado'] or 'WhatsApp'}.", 409)
    with _candado:
        if id_aviso in _enviando:
            return respuesta_error('Este aviso se está enviando en este momento.', 409)
        _enviando.add(id_aviso)
    try:
        if not texto and a['mensaje'] and a['estado_envio'] == 'Pendiente':
            texto = a['mensaje']                      # el texto personalizado que se cargó al crear el aviso
        r = enviar_recordatorio(a, texto)
        estado = 'Enviado' if r['ok'] else 'Error'
        dao.registrarEnvio(id_aviso, estado, r['canal'], r['motivo'], r['mensaje'])
        detalle = detalle_cambios({'estado_envio': a['estado_envio'], 'canal_enviado': a['canal_enviado'], 'motivo_error': a['motivo_error']},
                                  {'estado_envio': estado, 'canal_enviado': r['canal'], 'motivo_error': r['motivo']}, ETIQ_ENVIO)
        if detalle:
            auditar('avisos_recordatorios', id_aviso, 'MODIFICACION', detalle)   # nunca el texto del mensaje
        if r['ok']:
            extra = f" (WhatsApp no salió: {r['motivo']})" if r['canal'] == 'Correo' and r['motivo'] else ''
            return jsonify(success=True, data={'estado_envio': estado, 'canal_enviado': r['canal'], 'motivo_error': r['motivo']},
                           mensaje=f"Aviso para {_quien(a)} enviado por {r['canal']}{extra}.", error=None)
        return respuesta_error(f"No se pudo enviar el aviso para {_quien(a)}. {r['motivo']}", 502)
    except Exception as e:
        app.logger.error(f"Error en enviar_aviso: {e}")
        dao.registrarEnvio(id_aviso, 'Error', None, 'Error interno del sistema al enviar.', a['mensaje'])
        return error_interno()
    finally:
        with _candado:
            _enviando.discard(id_aviso)


@avisoapi.route('/avisos/whatsapp/estado', methods=['GET'])
@require_permiso('avisos', 'ver')
def whatsapp_estado():
    """Estado de la sesión de WhatsApp. `?verificar=1` abre el navegador para comprobarlo (requiere 'estado')."""
    verificar = request.args.get('verificar', '').lower() in ('1', 'true')
    if verificar and not puede('avisos', 'estado'):
        return respuesta_error('No tiene permiso para verificar la sesión de WhatsApp.', 403)
    return jsonify(success=True, data=sesion_whatsapp().estado(abrir=verificar), error=None)


@avisoapi.route('/avisos/whatsapp/vincular', methods=['POST'])
@require_permiso('avisos', 'estado')
def whatsapp_vincular():
    """Abre WhatsApp Web para escanear el QR (una sola vez: la sesión queda en el perfil del navegador)."""
    return jsonify(success=True, data=sesion_whatsapp().vincular(), error=None)


@avisoapi.route('/avisos/estadisticas', methods=['GET'])
@require_permiso('avisos', 'ver')
def estadisticas_avisos():
    return jsonify(success=True, data=dao.estadisticas(), error=None)
