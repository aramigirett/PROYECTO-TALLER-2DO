"""
=====================================================
API: Tratamiento (/api/v1/tratamientos)
Gestionar Tratamientos: Ver / Nuevo / Anular / Finalizar (no hay edición). Crea y anula SOLO el médico de la consulta, con la consulta programada o en
proceso (revalidado en la transacción); finaliza solo el médico del tratamiento. Un médico solo lee lo de SUS consultas.

Auditoría (`auditoria_cambios`, entidad `tratamientos`): ALTA, BAJA y MODIFICACION (finalizar, Estado: En seguimiento -> Finalizado) con el N.º de consulta,
el paciente (con CI), el tipo de tratamiento y quién; NUNCA con la descripción (dato de salud).
=====================================================
"""
import datetime

from flask import Blueprint, request, jsonify, session, current_app as app
from app.dao.referenciales_consultorio.consulta.ConsultaDao import numero_consulta
from app.dao.referenciales_consultorio.sesion_tratamiento.SesionTratamientoDao import SesionTratamientoDao
from app.dao.referenciales_consultorio.tratamiento.TratamientoDao import TratamientoDao
from app.rutas.modulo_consultorio.utils import acceso_consulta, auditar as _auditar, error_interno, respuesta_error
from app.rutas.modulo_consultorio.validadores_clinicos import validar_tratamiento
from app.rutas.modulo_seguridad.decorators import require_algun_permiso, require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion
from app.Services.auditoria_detalle import DetalleAuditoria

tratamientoapi = Blueprint('tratamientoapi', __name__)

ENTIDAD = 'tratamientos'
ESTADOS = ('pendiente', 'en_seguimiento', 'finalizado')
ETIQUETA_ESTADO = {'pendiente': 'Pendiente', 'en_seguimiento': 'En seguimiento', 'finalizado': 'Finalizado'}

ERRORES = {
    'CONSULTA_NO_ENCONTRADA': (404, 'No se encontró la consulta con el ID proporcionado.'),
    'TRATAMIENTO_NO_ENCONTRADO': (404, 'No se encontró el tratamiento con el ID proporcionado, o ya estaba anulado.'),
    'NO_ES_SU_MEDICO': (403, 'Solo el médico del tratamiento puede registrarlo, finalizarlo o anularlo.'),
    'TIPO_NO_EXISTE': (400, 'El tipo de tratamiento seleccionado no existe.'),
    'TIPO_INACTIVO': (409, 'El tipo de tratamiento seleccionado está inactivo.'),
    'DIAGNOSTICO_INVALIDO': (400, 'El diagnóstico seleccionado no existe, está anulado o no pertenece a esta consulta.'),
    'EN_USO': (409, 'No se puede anular: el tratamiento tiene sesiones activas registradas.'),
    'PENDIENTE_SIN_SESIONES': (409, 'No se puede finalizar: el tratamiento está pendiente y no tiene sesiones registradas. Considere anularlo.'),
    'YA_FINALIZADO': (409, 'El tratamiento ya está finalizado.'),
}
CAMPO_DEL_ERROR = {'TIPO_NO_EXISTE': 'id_tipo_tratamiento', 'TIPO_INACTIVO': 'id_tipo_tratamiento', 'DIAGNOSTICO_INVALIDO': 'id_diagnostico'}


def _error(r, anulando=False):
    codigo = r.get('error')
    if codigo == 'CONSULTA_NO_ABIERTA':
        estado = r.get('estado')
        if anulando and estado == 'finalizada':
            return respuesta_error('No se puede anular: la consulta que creó el tratamiento ya está finalizada.', 409)
        return respuesta_error(f'La consulta está {estado}: ya no admite cambios en sus tratamientos.', 409)
    if codigo == 'FACTURADO':
        return respuesta_error('El tratamiento ya fue facturado; anule primero la factura.', 409)
    if codigo in ERRORES:
        status, mensaje = ERRORES[codigo]
        return respuesta_error(mensaje, status, CAMPO_DEL_ERROR.get(codigo))
    return error_interno()


def _fecha(nombre):
    valor = request.args.get(nombre, '').strip()
    if not valor:
        return None, None
    try:
        return datetime.date.fromisoformat(valor), None
    except ValueError:
        return None, f'El filtro "{nombre}" debe tener el formato AAAA-MM-DD.'


def _entero(nombre):
    valor = request.args.get(nombre, '').strip()
    if not valor:
        return None, None
    if not valor.isdigit():
        return None, f'El filtro "{nombre}" debe ser numérico.'
    return int(valor), None


# -------------------------
# Listado (no cancelados) con filtros y paginación en el servidor; un médico solo ve los de SUS consultas
# -------------------------
@tratamientoapi.route('/tratamientos', methods=['GET'])
@require_permiso('tratamiento', 'ver')
def getTratamientos():
    desde, e1 = _fecha('desde')
    hasta, e2 = _fecha('hasta')
    pagina, e3 = _entero('pagina')
    por_pagina, e4 = _entero('por_pagina')
    consulta, e5 = _entero('consulta')
    paciente, e6 = _entero('paciente')
    error = e1 or e2 or e3 or e4 or e5 or e6
    if error:
        return respuesta_error(error, 400)
    if desde and hasta and desde > hasta:
        return respuesta_error('La fecha "desde" no puede ser posterior a "hasta".', 400)
    estado = request.args.get('estado', '').strip()
    if estado and estado not in ESTADOS:
        return respuesta_error('El estado debe ser pendiente, en_seguimiento o finalizado.', 400)
    try:
        filas, total = TratamientoDao().listar(request.args.get('q', '').strip()[:80] or None, estado or None, desde, hasta, id_medico_sesion(),
                                               consulta, paciente, request.args.get('en_curso') == '1', pagina or 1, por_pagina or 25)
        return jsonify({'success': True, 'data': filas, 'total': total, 'pagina': max(1, pagina or 1), 'por_pagina': por_pagina or 25, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener los tratamientos: {str(e)}")
        return error_interno()


# -------------------------
# Los tratamientos de una consulta: lo usan los combos de Receta y Órdenes (ya no basta con tener sesión)
# -------------------------
@tratamientoapi.route('/tratamientos/consulta/<int:id_consulta_cab>', methods=['GET'])
@require_algun_permiso(('tratamiento', 'ver'), ('receta', 'ver'), ('ordenestudio', 'ver'), ('ordenanalisis', 'ver'))
def getTratamientosByConsulta(id_consulta_cab):
    try:
        _, prohibido = acceso_consulta(id_consulta_cab)
        if prohibido:
            return prohibido
        return jsonify({'success': True, 'data': TratamientoDao().getTratamientosByConsulta(id_consulta_cab), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener tratamientos de la consulta: {str(e)}")
        return error_interno()


# -------------------------
# Detalle con sus sesiones
# -------------------------
@tratamientoapi.route('/tratamientos/<int:id_tratamiento>', methods=['GET'])
@require_permiso('tratamiento', 'ver')
def getTratamiento(id_tratamiento):
    try:
        t = TratamientoDao().getTratamientoById(id_tratamiento)
        if not t:
            return respuesta_error('No se encontró el tratamiento con el ID proporcionado.', 404)
        medico = id_medico_sesion()
        if medico and t['id_medico'] != medico:
            return respuesta_error('Esa información no está disponible para su usuario.', 403)
        t['sesiones'] = SesionTratamientoDao().getSesionesByTratamiento(id_tratamiento)
        return jsonify({'success': True, 'data': t, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener el tratamiento: {str(e)}")
        return error_interno()


# -------------------------
# Alta: la consulta sale del cuerpo; el médico, de la sesión; paciente, médico, consultorio y estado los pone el servidor
# -------------------------
@tratamientoapi.route('/tratamientos', methods=['POST'])
@require_permiso('tratamiento', 'nuevo')
def addTratamiento():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get('id_consulta_cab') in (None, ''):
        return respuesta_error('El campo id_consulta_cab es obligatorio.', 400, 'id_consulta_cab')
    try:
        id_consulta = int(data['id_consulta_cab'])
    except (ValueError, TypeError):
        return respuesta_error('El campo id_consulta_cab no es válido.', 400, 'id_consulta_cab')
    valores, error, campo = validar_tratamiento(data)
    if error:
        return respuesta_error(error, 400, campo)
    valores['id_consulta_cab'] = id_consulta
    try:
        r = TratamientoDao().guardarTratamiento(valores, id_medico_sesion())
        if 'id_tratamiento' in r:
            ctx = r['contexto']
            nuevos = {'Consulta': numero_consulta(id_consulta), 'Paciente': f"{ctx['paciente']} (CI {ctx['cedula']})", 'Tipo de tratamiento': ctx['tipo']}
            _auditar(ENTIDAD, r['id_tratamiento'], 'ALTA', DetalleAuditoria('; '.join(f'{k}: {v}' for k, v in nuevos.items()), {}, nuevos))
            return jsonify({'success': True, 'data': {'id_tratamiento': r['id_tratamiento']},
                            'mensaje': f"Tratamiento de {ctx['tipo']} registrado correctamente.", 'error': None}), 201
        return _error(r)
    except Exception as e:
        app.logger.error(f"Error al agregar tratamiento: {str(e)}")
        return error_interno()


# -------------------------
# Anulación (baja lógica, definitiva)
# -------------------------
@tratamientoapi.route('/tratamientos/<int:id_tratamiento>', methods=['DELETE'])
@require_permiso('tratamiento', 'anular')
def deleteTratamiento(id_tratamiento):
    try:
        r = TratamientoDao().anularTratamiento(id_tratamiento, id_medico_sesion())
        if r.get('ok'):
            ctx = r['contexto']
            _auditar(ENTIDAD, id_tratamiento, 'BAJA',
                     f"Tratamiento de {ctx['tipo']}; Consulta {numero_consulta(r['id_consulta_cab'])}; Paciente: {ctx['paciente']} (CI {ctx['cedula']})")
            return jsonify({'success': True, 'mensaje': f"Tratamiento de {ctx['tipo']} anulado correctamente.", 'error': None}), 200
        return _error(r, anulando=True)
    except Exception as e:
        app.logger.error(f"Error al anular tratamiento: {str(e)}")
        return error_interno()


# -------------------------
# Finalizar (permiso `estado`): en_seguimiento -> finalizado
# -------------------------
@tratamientoapi.route('/tratamientos/<int:id_tratamiento>/finalizar', methods=['PUT'])
@require_permiso('tratamiento', 'estado')
def finalizarTratamiento(id_tratamiento):
    try:
        r = TratamientoDao().finalizarTratamiento(id_tratamiento, id_medico_sesion())
        if r.get('ok'):
            ctx = r['contexto']
            ant, nue = ETIQUETA_ESTADO['en_seguimiento'], ETIQUETA_ESTADO['finalizado']
            _auditar(ENTIDAD, id_tratamiento, 'MODIFICACION',
                     DetalleAuditoria(f"Tratamiento de {ctx['tipo']}; Consulta {numero_consulta(r['id_consulta_cab'])}; Paciente: {ctx['paciente']} (CI {ctx['cedula']}); "
                                      f"Estado: {ant} -> {nue}", {'Estado': ant}, {'Estado': nue}))
            return jsonify({'success': True, 'mensaje': f"Tratamiento de {ctx['tipo']} finalizado correctamente.", 'error': None}), 200
        return _error(r)
    except Exception as e:
        app.logger.error(f"Error al finalizar tratamiento: {str(e)}")
        return error_interno()
