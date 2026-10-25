"""
=====================================================
API: Consulta Médica (Registrar Consulta)
Descripción: Endpoints REST de /api/v1/consultas. Reglas en ConsultaDao (alta desde una cita Confirmado, estados, anulación).

Auditoría (`auditoria_cambios`, entidad `consultas_cab`): ALTA, MODIFICACION (cambio de estado) y BAJA. Es dato de salud: el detalle lleva
solo el N.º de consulta, el paciente (con su CI), quién y el cambio de estado; nunca contenido clínico.
=====================================================
"""
import datetime

from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_consultorio.consulta.ConsultaDao import ConsultaDao, ESTADOS, numero_consulta
from app.rutas.modulo_consultorio.utils import auditar as _auditar, error_interno, respuesta_error
from app.rutas.modulo_seguridad.decorators import require_permiso, require_login
from app.rutas.modulo_seguridad.permisos_contexto import id_funcionario_sesion, id_medico_sesion
from app.Services.auditoria_detalle import DetalleAuditoria

consultaapi = Blueprint('consultaapi', __name__)

ENTIDAD = 'consultas_cab'

ERRORES_ALTA = {
    'CITA_NO_ENCONTRADA': (404, 'No se encontró la cita seleccionada.'),
    'CITA_NO_CONFIRMADA': (409, 'La cita no está en estado Confirmado.'),
    'CITA_YA_TIENE_CONSULTA': (409, 'Esta cita ya tiene una consulta registrada.'),
    'SIN_FUNCIONARIO': (403, 'Solo un funcionario puede registrar consultas.'),
    'FUNCIONARIO_INACTIVO': (409, 'El funcionario que registra la consulta está inactivo.'),
    'DURACION_INVALIDA': (400, 'La duración debe ser un número entero de minutos entre 1 y 480.'),
}
ERRORES_ESTADO = {
    'NO_ENCONTRADA': (404, 'No se encontró la consulta con el ID proporcionado.'),
    'ESTADO_INVALIDO': (400, 'El estado debe ser programada, en_proceso, finalizada o cancelada.'),
    'DURACION_INVALIDA': (400, 'La duración debe ser un número entero de minutos entre 1 y 480.'),
    'DURACION_SOLO_AL_FINALIZAR': (400, 'La duración solo se registra al finalizar la atención.'),
    'SOLO_MEDICO_DE_LA_CONSULTA': (403, 'Solo el médico de la consulta puede iniciar o finalizar la atención.'),
    'NO_AUTORIZADO': (403, 'Solo Recepción o el médico de la consulta pueden cancelarla.'),
}
ETIQUETA_ESTADO = {'programada': 'Programada', 'en_proceso': 'En proceso', 'finalizada': 'Finalizada', 'cancelada': 'Cancelada'}


def _paciente(ctx):
    return f"{ctx['paciente']} (CI {ctx['cedula']})" if ctx.get('cedula') else ctx['paciente']


def _fecha_param(nombre):
    """(fecha|None, error). Formato AAAA-MM-DD."""
    valor = request.args.get(nombre, '').strip()
    if not valor:
        return None, None
    try:
        return datetime.date.fromisoformat(valor), None
    except ValueError:
        return None, f'El filtro "{nombre}" debe tener el formato AAAA-MM-DD.'


def _solo_las_propias():
    """Un médico solo ve SUS consultas (Recepción y Administrador ven todas)."""
    return id_medico_sesion()


# -------------------------
# Listado (activas) con filtros y paginación en el servidor
# -------------------------
@consultaapi.route('/consultas', methods=['GET'])
@require_permiso('consulta', 'ver')
def getConsultas():
    estado = request.args.get('estado', '').strip() or None
    if estado and estado not in ESTADOS:
        return respuesta_error('El filtro "estado" no es válido.', 400)
    desde, e1 = _fecha_param('desde')
    hasta, e2 = _fecha_param('hasta')
    if e1 or e2:
        return respuesta_error(e1 or e2, 400)
    if desde and hasta and desde > hasta:
        return respuesta_error('La fecha "desde" no puede ser posterior a "hasta".', 400)
    try:
        pagina = int(request.args.get('pagina', 1))
        por_pagina = int(request.args.get('por_pagina', 25))
    except ValueError:
        return respuesta_error('La paginación debe ser numérica.', 400)
    texto = request.args.get('q', '').strip()[:80] or None
    try:
        filas, total = ConsultaDao().listar(estado, texto, desde, hasta, _solo_las_propias(), pagina, por_pagina)
        return jsonify({'success': True, 'data': filas, 'total': total, 'pagina': max(1, pagina), 'por_pagina': por_pagina,
                        'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener las consultas: {str(e)}")
        return error_interno()


@consultaapi.route('/consultas/indicadores', methods=['GET'])
@require_permiso('consulta', 'ver')
def getIndicadores():
    try:
        return jsonify({'success': True, 'data': ConsultaDao().indicadores(_solo_las_propias()), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al calcular los indicadores: {str(e)}")
        return error_interno()


# -------------------------
# Citas que se pueden consultar (buscador de "Nueva consulta"): piden `nuevo` de esta ventana
# -------------------------
@consultaapi.route('/consultas/citas-disponibles', methods=['GET'])
@require_permiso('consulta', 'nuevo')
def getCitasDisponibles():
    try:
        return jsonify({'success': True, 'data': ConsultaDao().citasDisponibles(request.args.get('q', '').strip()[:80] or None),
                        'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al buscar citas disponibles: {str(e)}")
        return error_interno()


# -------------------------
# Consultas activas (programada / en_proceso): lookup de otras pantallas
# -------------------------
@consultaapi.route('/consultas/activas', methods=['GET'])
@require_login
def getConsultasActivas():
    try:
        return jsonify({'success': True, 'data': ConsultaDao().getConsultasActivas(), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener consultas activas: {str(e)}")
        return error_interno()


# -------------------------
# Una consulta por ID (lookup de otras pantallas)
# -------------------------
@consultaapi.route('/consultas/<int:consulta_id>', methods=['GET'])
@require_login
def getConsulta(consulta_id):
    try:
        consulta = ConsultaDao().getConsultaById(consulta_id)
        if consulta:
            return jsonify({'success': True, 'data': consulta, 'error': None}), 200
        return respuesta_error('No se encontró la consulta con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al obtener consulta: {str(e)}")
        return error_interno()


# -------------------------
# Resumen para la pantalla central: contadores de registros vigentes (solo cantidades) y qué permite el estado actual
# -------------------------
@consultaapi.route('/consultas/<int:consulta_id>/resumen', methods=['GET'])
@require_permiso('consulta', 'ver')
def getResumenConsulta(consulta_id):
    dao = ConsultaDao()
    try:
        consulta = dao.getConsultaById(consulta_id)
        if not consulta or not consulta['activo']:
            return respuesta_error('No se encontró la consulta con el ID proporcionado.', 404)
        id_medico = id_medico_sesion()
        if id_medico and consulta['id_medico'] != id_medico:
            return respuesta_error('Esta consulta pertenece a otro médico.', 403)
        estado = consulta['estado']
        es_su_medico = bool(id_medico) and consulta['id_medico'] == id_medico
        abierta = estado in ('programada', 'en_proceso')
        return jsonify({'success': True, 'error': None, 'data': {
            'consulta': consulta,
            'contadores': dao.getResumen(consulta_id),
            # qué puede hacer QUIEN pregunta (el servidor vuelve a validar en cada operación)
            'acciones': {
                'iniciar': estado == 'programada' and es_su_medico,
                'finalizar': estado == 'en_proceso' and es_su_medico,
                'cancelar': abierta and (es_su_medico or bool(id_funcionario_sesion())),
                'cargar_clinico': abierta and es_su_medico,
            },
        }}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener el resumen de la consulta: {str(e)}")
        return error_interno()


# -------------------------
# Alta: desde una cita Confirmado. El funcionario sale de la sesión; estado inicial siempre 'programada'.
# -------------------------
@consultaapi.route('/consultas', methods=['POST'])
@require_permiso('consulta', 'nuevo')
def addConsulta():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data.get('id_cita'):
        return respuesta_error('El campo id_cita es obligatorio: la consulta debe partir de una Cita Confirmada.', 400, 'id_cita')
    try:
        id_cita = int(data['id_cita'])
    except (ValueError, TypeError):
        return respuesta_error('El campo id_cita no es válido.', 400, 'id_cita')

    id_funcionario = id_funcionario_sesion()
    if not id_funcionario:
        return respuesta_error('Solo un funcionario puede registrar consultas.', 403)
    try:
        r = ConsultaDao().guardarConsulta({'id_cita': id_cita, 'duracion_minutos': data.get('duracion_minutos'),
                                           'id_funcionario': id_funcionario})
        if 'id_consulta_cab' in r:
            ctx = r['contexto']
            numero = numero_consulta(r['id_consulta_cab'])
            valores = {'Consulta': numero, 'Paciente': _paciente(ctx), 'Médico': ctx['medico'],
                       'Fecha de la cita': f"{ctx['fecha']} {str(ctx['hora'])[:5]}", 'Estado': ETIQUETA_ESTADO['programada']}
            _auditar(ENTIDAD, r['id_consulta_cab'], 'ALTA',
                     DetalleAuditoria('; '.join(f'{k}: {v}' for k, v in valores.items()), {}, valores))
            return jsonify({'success': True, 'data': {'id_consulta_cab': r['id_consulta_cab'], 'numero': numero},
                            'mensaje': f"Consulta {numero} de {ctx['paciente']} registrada correctamente.", 'error': None}), 201
        codigo = r.get('error')
        if codigo in ERRORES_ALTA:
            status, mensaje = ERRORES_ALTA[codigo]
            return respuesta_error(mensaje, status, 'duracion_minutos' if codigo == 'DURACION_INVALIDA' else None)
        if codigo == 'PACIENTE_INACTIVO':
            return respuesta_error(f"El paciente {r['detalle']} está inactivo: no se puede registrar la consulta.", 409)
        if codigo == 'MEDICO_INACTIVO':
            return respuesta_error(f"El médico {r['detalle']} está inactivo: no se puede registrar la consulta.", 409)
        if codigo == 'CONSULTORIO_INACTIVO':
            return respuesta_error(f"El consultorio {r['detalle']} está inactivo: no se puede registrar la consulta.", 409)
        return error_interno()
    except Exception as e:
        app.logger.error(f"Error al agregar consulta: {str(e)}")
        return error_interno()


# -------------------------
# Cambio de estado: programada -> en_proceso -> finalizada, y programada | en_proceso -> cancelada.
# Inicia y finaliza el médico de la consulta; cancela Recepción (funcionario) o el médico de la consulta.
# -------------------------
@consultaapi.route('/consultas/<int:consulta_id>/estado', methods=['PATCH'])
@require_permiso('consulta', 'estado')
def cambiarEstadoConsulta(consulta_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data.get('estado'):
        return respuesta_error('El campo estado es obligatorio.', 400, 'estado')
    try:
        r = ConsultaDao().cambiarEstado(consulta_id, str(data['estado']).strip(), data.get('duracion_minutos'),
                                        id_medico_sesion(), id_funcionario_sesion())
        if r.get('ok'):
            ctx = r['contexto']
            numero = numero_consulta(consulta_id)
            ant, nue = ETIQUETA_ESTADO[r['anterior']], ETIQUETA_ESTADO[r['nuevo']]
            _auditar(ENTIDAD, consulta_id, 'MODIFICACION',
                     DetalleAuditoria(f"Consulta {numero} de {_paciente(ctx)}; Estado: {ant} -> {nue}", {'Estado': ant}, {'Estado': nue}))
            return jsonify({'success': True, 'data': {'id_consulta_cab': consulta_id, 'estado': r['nuevo']},
                            'mensaje': f"Consulta {numero}: {ant.lower()} → {nue.lower()}.", 'error': None}), 200
        codigo = r.get('error')
        if codigo == 'TRANSICION_INVALIDA':
            return respuesta_error(f"No se puede pasar una consulta de {ETIQUETA_ESTADO[r['anterior']].lower()} a "
                                   f"{ETIQUETA_ESTADO[r['nuevo']].lower()}.", 409)
        if codigo in ERRORES_ESTADO:
            status, mensaje = ERRORES_ESTADO[codigo]
            return respuesta_error(mensaje, status, 'duracion_minutos' if codigo.startswith('DURACION') else None)
        return error_interno()
    except Exception as e:
        app.logger.error(f"Error al cambiar el estado de la consulta: {str(e)}")
        return error_interno()


# -------------------------
# Anular (baja por error, definitiva): bloqueada con la consulta finalizada o con datos clínicos vigentes.
# La cita vuelve a 'Confirmado'.
# -------------------------
@consultaapi.route('/consultas/<int:consulta_id>', methods=['DELETE'])
@require_permiso('consulta', 'anular')
def deleteConsulta(consulta_id):
    try:
        r = ConsultaDao().anular(consulta_id)
        if r.get('ok'):
            ctx = r['contexto']
            numero = numero_consulta(consulta_id)
            texto = f"Consulta {numero} de {_paciente(ctx)}; " + (
                f"cita N.º {r['id_cita']} vuelve a Confirmado" if r['cita_revertida']
                else f"la cita N.º {r['id_cita']} no estaba Realizado ({r['estado_cita']}): no se modificó")
            _auditar(ENTIDAD, consulta_id, 'BAJA', texto)
            return jsonify({'success': True, 'error': None, 'data': {'cita_revertida': r['cita_revertida']},
                            'mensaje': f"Consulta {numero} de {ctx['paciente']} anulada correctamente."
                                       + (' La cita volvió a Confirmado.' if r['cita_revertida'] else '')}), 200
        codigo = r.get('error')
        if codigo == 'NO_ENCONTRADA':
            return respuesta_error('No se encontró la consulta con el ID proporcionado.', 404)
        if codigo == 'CONSULTA_FINALIZADA':
            return respuesta_error('No se puede anular: la consulta ya está finalizada.', 409)
        if codigo == 'EN_USO':
            return respuesta_error('No se puede anular: la consulta tiene datos clínicos asociados '
                                   f"({r['detalle']}). Anule primero esos registros.", 409)
        return error_interno()
    except Exception as e:
        app.logger.error(f"Error al anular consulta: {str(e)}")
        return error_interno()
