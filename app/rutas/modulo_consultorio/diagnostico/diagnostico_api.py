"""
=====================================================
API: Diagnóstico (/api/v1/diagnosticos-medicos)
Gestionar Diagnóstico: Ver / Nuevo / Anular (no hay edición). Crea y anula SOLO el médico de la consulta, con la consulta programada o en proceso
(revalidado en la transacción). Un médico solo lee lo de SUS consultas.

Auditoría (`auditoria_cambios`, entidad `diagnosticos`): ALTA y BAJA con el código DX, el N.º de consulta, el paciente (con CI) y quién; NUNCA con el
tipo, los síntomas, la descripción, la pieza ni las observaciones (datos de salud).
=====================================================
"""
import datetime

from flask import Blueprint, request, jsonify, session, current_app as app
from app.dao.referenciales_consultorio.consulta.ConsultaDao import numero_consulta
from app.dao.referenciales_consultorio.diagnostico.DiagnosticoDao import DiagnosticoDao
from app.rutas.modulo_consultorio.utils import acceso_consulta, auditar as _auditar, error_interno, respuesta_error
from app.rutas.modulo_consultorio.validadores_clinicos import validar_diagnostico
from app.rutas.modulo_seguridad.decorators import require_algun_permiso, require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion
from app.Services.auditoria_detalle import DetalleAuditoria

diagnostico_medico_api = Blueprint('diagnostico_medico_api', __name__)

ENTIDAD = 'diagnosticos'

ERRORES = {
    'CONSULTA_NO_ENCONTRADA': (404, 'No se encontró la consulta con el ID proporcionado.'),
    'DIAGNOSTICO_NO_ENCONTRADO': (404, 'No se encontró el diagnóstico con el ID proporcionado.'),
    'NO_ES_SU_MEDICO': (403, 'Solo el médico de la consulta puede registrar o anular sus diagnósticos.'),
    'TIPO_NO_EXISTE': (400, 'El tipo de diagnóstico seleccionado no existe.'),
    'TIPO_INACTIVO': (409, 'El tipo de diagnóstico seleccionado está inactivo.'),
    'SINTOMA_NO_EXISTE': (400, 'Alguno de los síntomas seleccionados no existe.'),
    'DATOS_INVALIDOS': (400, 'Los datos del diagnóstico no cumplen las reglas de la base de datos.'),
}
CAMPO_DEL_ERROR = {'TIPO_NO_EXISTE': 'id_tipo_diagnostico', 'TIPO_INACTIVO': 'id_tipo_diagnostico', 'SINTOMA_NO_EXISTE': 'sintomas',
                   'SINTOMA_INACTIVO': 'sintomas'}

# Quién más lee los diagnósticos de una consulta: las ventanas que los eligen en sus formularios
VENTANAS_QUE_LOS_USAN = (('diagnostico', 'ver'), ('tratamiento', 'ver'), ('receta', 'ver'), ('ordenestudio', 'ver'),
                         ('ordenanalisis', 'ver'), ('justificativomedico', 'ver'))


def _error(r, anulando=False):
    codigo = r.get('error')
    if codigo == 'CONSULTA_NO_ABIERTA':
        estado = r.get('estado')
        if anulando and estado == 'finalizada':
            return respuesta_error('No se puede anular: la consulta ya está finalizada.', 409)
        return respuesta_error(f'La consulta está {estado}: ya no admite cambios en sus diagnósticos.', 409)
    if codigo == 'SINTOMA_INACTIVO':
        return respuesta_error(f"Hay síntomas inactivos: {r['detalle']}. Quítelos de la selección.", 409, 'sintomas')
    if codigo == 'EN_USO':
        return respuesta_error('No se puede anular: este diagnóstico tiene un tratamiento asociado.', 409)
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


def _por_pagina():
    try:
        return int(request.args.get('pagina', 1)), int(request.args.get('por_pagina', 25))
    except ValueError:
        return None


# -------------------------
# Listado (vigentes) con filtros y paginación en el servidor; un médico solo ve los de SUS consultas
# -------------------------
@diagnostico_medico_api.route('/diagnosticos-medicos', methods=['GET'])
@require_permiso('diagnostico', 'ver')
def getDiagnosticosMedicos():
    desde, e1 = _fecha('desde')
    hasta, e2 = _fecha('hasta')
    if e1 or e2:
        return respuesta_error(e1 or e2, 400)
    if desde and hasta and desde > hasta:
        return respuesta_error('La fecha "desde" no puede ser posterior a "hasta".', 400)
    pag = _por_pagina()
    if pag is None:
        return respuesta_error('La paginación debe ser numérica.', 400)
    try:
        filas, total = DiagnosticoDao().listar(request.args.get('q', '').strip()[:80] or None, desde, hasta, id_medico_sesion(),
                                               pagina=pag[0], por_pagina=pag[1])
        return jsonify({'success': True, 'data': filas, 'total': total, 'pagina': max(1, pag[0]), 'por_pagina': pag[1], 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener los diagnósticos: {str(e)}")
        return error_interno()


@diagnostico_medico_api.route('/diagnosticos-medicos/<int:diagnostico_id>', methods=['GET'])
@require_permiso('diagnostico', 'ver')
def getDiagnosticoMedico(diagnostico_id):
    try:
        dx = DiagnosticoDao().getDiagnosticoById(diagnostico_id)
        if not dx:
            return respuesta_error('No se encontró el diagnóstico con el ID proporcionado.', 404)
        _, prohibido = acceso_consulta(dx['id_consulta_cab'])
        if prohibido:
            return prohibido
        return jsonify({'success': True, 'data': dx, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener el diagnóstico: {str(e)}")
        return error_interno()


# -------------------------
# Los diagnósticos de una consulta: lo usan los combos de Tratamiento, Receta, Órdenes y Justificativo (ya no basta con tener sesión)
# -------------------------
@diagnostico_medico_api.route('/diagnosticos-medicos/consulta/<int:id_consulta_cab>', methods=['GET'])
@require_algun_permiso(*VENTANAS_QUE_LOS_USAN)
def getDiagnosticosByConsulta(id_consulta_cab):
    try:
        _, prohibido = acceso_consulta(id_consulta_cab)
        if prohibido:
            return prohibido
        return jsonify({'success': True, 'data': DiagnosticoDao().getDiagnosticosByConsulta(id_consulta_cab), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener los diagnósticos de la consulta: {str(e)}")
        return error_interno()


# -------------------------
# Alta: la consulta sale del cuerpo; el médico, de la sesión; paciente y fecha las pone el servidor
# -------------------------
@diagnostico_medico_api.route('/diagnosticos-medicos', methods=['POST'])
@require_permiso('diagnostico', 'nuevo')
def addDiagnosticoMedico():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get('id_consulta_cab') in (None, ''):
        return respuesta_error('El campo id_consulta_cab es obligatorio.', 400, 'id_consulta_cab')
    try:
        id_consulta = int(data['id_consulta_cab'])
    except (ValueError, TypeError):
        return respuesta_error('El campo id_consulta_cab no es válido.', 400, 'id_consulta_cab')
    valores, error, campo = validar_diagnostico(data)
    if error:
        return respuesta_error(error, 400, campo)
    valores['id_consulta_cab'] = id_consulta
    try:
        r = DiagnosticoDao().guardarDiagnostico(valores, session.get('id_usuario'), id_medico_sesion())
        if 'id_diagnostico' in r:
            ctx = r['contexto']
            paciente = f"{ctx['paciente']} (CI {ctx['cedula']})"
            nuevos = {'Diagnóstico': r['codigo'], 'Consulta': numero_consulta(id_consulta), 'Paciente': paciente}
            _auditar(ENTIDAD, r['id_diagnostico'], 'ALTA', DetalleAuditoria('; '.join(f'{k}: {v}' for k, v in nuevos.items()), {}, nuevos))
            return jsonify({'success': True, 'data': {'id_diagnostico': r['id_diagnostico'], 'codigo': r['codigo']},
                            'mensaje': f"Diagnóstico {r['codigo']} registrado correctamente.", 'error': None}), 201
        return _error(r)
    except Exception as e:
        app.logger.error(f"Error al agregar diagnóstico: {str(e)}")
        return error_interno()


# -------------------------
# Anulación (baja lógica, definitiva)
# -------------------------
@diagnostico_medico_api.route('/diagnosticos-medicos/<int:diagnostico_id>', methods=['DELETE'])
@require_permiso('diagnostico', 'anular')
def deleteDiagnosticoMedico(diagnostico_id):
    try:
        r = DiagnosticoDao().anularDiagnostico(diagnostico_id, id_medico_sesion())
        if r.get('ok'):
            ctx = r['contexto']
            numero = numero_consulta(r['id_consulta_cab'])
            _auditar(ENTIDAD, diagnostico_id, 'BAJA',
                     f"Diagnóstico {r['codigo']}; Consulta {numero}; Paciente: {ctx['paciente']} (CI {ctx['cedula']})")
            return jsonify({'success': True, 'mensaje': f"Diagnóstico {r['codigo']} anulado correctamente.", 'error': None}), 200
        return _error(r, anulando=True)
    except Exception as e:
        app.logger.error(f"Error al anular diagnóstico: {str(e)}")
        return error_interno()
