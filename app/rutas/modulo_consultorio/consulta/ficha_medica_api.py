"""
=====================================================
API: Ficha Médica de Consulta (/api/v1/ficha-medica)
Una ficha por consulta. Crear, editar y anular: solo el médico de esa consulta, con la consulta programada o en proceso (se revalida al
guardar). Las lecturas piden `fichamedica ver` (son datos de salud; un médico solo lee las fichas de SUS consultas).

Auditoría (`auditoria_cambios`, entidad `ficha_medica_consulta`): ALTA, MODIFICACION y BAJA con N.º de consulta, paciente (con CI) y quién;
NUNCA con los valores clínicos (ni antes ni después).
=====================================================
"""
import datetime

from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_consultorio.consulta.ConsultaDao import ConsultaDao, numero_consulta
from app.dao.referenciales_consultorio.consulta.FichaMedicaDao import FichaMedicaDao
from app.rutas.modulo_consultorio.utils import acceso_consulta, auditar as _auditar, error_interno, respuesta_error
from app.rutas.modulo_consultorio.validadores_clinicos import validar_ficha
from app.rutas.modulo_seguridad.decorators import require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion
from app.Services.auditoria_detalle import DetalleAuditoria

fichamedicaapi = Blueprint('fichamedicaapi', __name__)

ENTIDAD = 'ficha_medica_consulta'

ERRORES = {
    'CONSULTA_NO_ENCONTRADA': (404, 'No se encontró la consulta con el ID proporcionado.'),
    'FICHA_NO_ENCONTRADA': (404, 'No se encontró la ficha médica con el ID proporcionado.'),
    'NO_ES_SU_MEDICO': (403, 'Solo el médico de la consulta puede registrar, modificar o anular su ficha médica.'),
    'FICHA_YA_EXISTE': (409, 'Ya existe una ficha médica para esta consulta. Edítela en lugar de crear otra.'),
}


def _contexto(info, id_consulta):
    paciente = f"{info['paciente']} (CI {info['cedula']})" if info.get('cedula') else info['paciente']
    return numero_consulta(id_consulta), paciente


def _detalle_ficha(info, id_consulta, texto):
    numero, paciente = _contexto(info, id_consulta)
    return f"Ficha médica de la consulta {numero} de {paciente}; {texto}"


def _error(r, anulando=False):
    codigo = r.get('error')
    if codigo == 'CONSULTA_NO_ABIERTA':
        estado = r.get('estado')
        if anulando and estado == 'finalizada':
            return respuesta_error('No se puede anular: la consulta ya está finalizada.', 409)
        return respuesta_error(f'La consulta está {estado}: ya no admite cambios en la ficha médica.', 409)
    if codigo in ERRORES:
        status, mensaje = ERRORES[codigo]
        return respuesta_error(mensaje, status)
    return error_interno()


def _puede_leer_consulta(id_consulta):
    """Un médico solo lee las fichas de SUS consultas; Recepción y Administrador (con fichamedica ver) leen todas.
    Devuelve None si puede, o la respuesta de error."""
    return acceso_consulta(id_consulta)[1]


def _fecha_param(nombre):
    valor = request.args.get(nombre, '').strip()
    if not valor:
        return None, None
    try:
        return datetime.date.fromisoformat(valor), None
    except ValueError:
        return None, f'El filtro "{nombre}" debe tener el formato AAAA-MM-DD.'


# -------------------------
# Listado para la pantalla de Fichas Médicas: identifica la ficha, SIN valores clínicos
# -------------------------
@fichamedicaapi.route('/ficha-medica', methods=['GET'])
@require_permiso('fichamedica', 'ver')
def getFichas():
    desde, e1 = _fecha_param('desde')
    hasta, e2 = _fecha_param('hasta')
    if e1 or e2:
        return respuesta_error(e1 or e2, 400)
    if desde and hasta and desde > hasta:
        return respuesta_error('La fecha "desde" no puede ser posterior a "hasta".', 400)
    try:
        pagina, por_pagina = int(request.args.get('pagina', 1)), int(request.args.get('por_pagina', 25))
    except ValueError:
        return respuesta_error('La paginación debe ser numérica.', 400)
    try:
        filas, total = FichaMedicaDao().listar(request.args.get('q', '').strip()[:80] or None, desde, hasta, id_medico_sesion(), pagina, por_pagina)
        return jsonify({'success': True, 'data': filas, 'total': total, 'pagina': max(1, pagina), 'por_pagina': por_pagina, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al listar las fichas médicas: {str(e)}")
        return error_interno()


# -------------------------
# La ficha de una consulta
# -------------------------
@fichamedicaapi.route('/ficha-medica/consulta/<int:consulta_id>', methods=['GET'])
@require_permiso('fichamedica', 'ver')
def getFichaByConsulta(consulta_id):
    try:
        prohibido = _puede_leer_consulta(consulta_id)
        if prohibido:
            return prohibido
        ficha = FichaMedicaDao().getFichaByConsulta(consulta_id)
        if ficha:
            return jsonify({'success': True, 'data': ficha, 'error': None}), 200
        return respuesta_error('No se encontró ficha médica para esta consulta.', 404)
    except Exception as e:
        app.logger.error(f"Error al obtener la ficha médica: {str(e)}")
        return error_interno()


@fichamedicaapi.route('/ficha-medica/<int:ficha_id>', methods=['GET'])
@require_permiso('fichamedica', 'ver')
def getFicha(ficha_id):
    try:
        ficha = FichaMedicaDao().getFichaById(ficha_id)
        if not ficha:
            return respuesta_error('No se encontró la ficha médica con el ID proporcionado.', 404)
        prohibido = _puede_leer_consulta(ficha['id_consulta_cab'])
        if prohibido:
            return prohibido
        return jsonify({'success': True, 'data': ficha, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener la ficha médica: {str(e)}")
        return error_interno()


# -------------------------
# Alta: la consulta sale del cuerpo; el médico, de la sesión. El IMC lo calcula el servidor.
# -------------------------
@fichamedicaapi.route('/ficha-medica', methods=['POST'])
@require_permiso('fichamedica', 'nuevo')
def addFicha():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get('id_consulta_cab') in (None, ''):
        return respuesta_error('El campo "Consulta" es obligatorio.', 400, 'id_consulta_cab')
    try:
        id_consulta = int(data['id_consulta_cab'])
    except (ValueError, TypeError):
        return respuesta_error('El campo "Consulta" no es válido.', 400, 'id_consulta_cab')
    valores, error, campo = validar_ficha(data)
    if error:
        return respuesta_error(error, 400, campo)
    try:
        r = FichaMedicaDao().guardarFicha(id_consulta, valores, id_medico_sesion())
        if 'id_ficha_medica' in r:
            info = r['contexto']
            numero, paciente = _contexto(info, id_consulta)
            _auditar(ENTIDAD, r['id_ficha_medica'], 'ALTA',
                     DetalleAuditoria(_detalle_ficha(info, id_consulta, 'ficha registrada'), {}, {'Consulta': numero, 'Paciente': paciente}))
            return jsonify({'success': True, 'data': {'id_ficha_medica': r['id_ficha_medica'],
                                                      'imc': float(valores['imc']) if valores['imc'] is not None else None},
                            'mensaje': f"Ficha médica de la consulta {numero} registrada correctamente.", 'error': None}), 201
        return _error(r)
    except Exception as e:
        app.logger.error(f"Error al crear la ficha médica: {str(e)}")
        return error_interno()


# -------------------------
# Modificación (excepción del CUS: se corrige la misma ficha mientras la consulta sigue abierta)
# -------------------------
@fichamedicaapi.route('/ficha-medica/<int:ficha_id>', methods=['PUT'])
@require_permiso('fichamedica', 'editar')
def updateFicha(ficha_id):
    valores, error, campo = validar_ficha(request.get_json(silent=True))
    if error:
        return respuesta_error(error, 400, campo)
    try:
        r = FichaMedicaDao().updateFicha(ficha_id, valores, id_medico_sesion())
        if r.get('sin_cambios'):
            return jsonify({'success': True, 'data': {'id_ficha_medica': ficha_id}, 'mensaje': 'La ficha médica no tiene cambios.',
                            'error': None}), 200
        if r.get('ok'):
            info, id_consulta = r['contexto'], r['id_consulta_cab']
            numero, _ = _contexto(info, id_consulta)
            # modificación SIN valores (ni anteriores ni nuevos): son datos de salud
            _auditar(ENTIDAD, ficha_id, 'MODIFICACION', DetalleAuditoria(_detalle_ficha(info, id_consulta, 'ficha modificada'), {}, {}))
            return jsonify({'success': True, 'data': {'id_ficha_medica': ficha_id,
                                                      'imc': float(valores['imc']) if valores['imc'] is not None else None},
                            'mensaje': f'Ficha médica de la consulta {numero} actualizada correctamente.', 'error': None}), 200
        return _error(r)
    except Exception as e:
        app.logger.error(f"Error al actualizar la ficha médica: {str(e)}")
        return error_interno()


# -------------------------
# Anulación (baja lógica, definitiva)
# -------------------------
@fichamedicaapi.route('/ficha-medica/<int:ficha_id>', methods=['DELETE'])
@require_permiso('fichamedica', 'anular')
def deleteFicha(ficha_id):
    try:
        r = FichaMedicaDao().deleteFicha(ficha_id, id_medico_sesion())
        if r.get('ok'):
            info, id_consulta = r['contexto'], r['id_consulta_cab']
            numero, _ = _contexto(info, id_consulta)
            _auditar(ENTIDAD, ficha_id, 'BAJA', _detalle_ficha(info, id_consulta, 'ficha anulada'))
            return jsonify({'success': True, 'mensaje': f'Ficha médica de la consulta {numero} anulada correctamente.', 'error': None}), 200
        return _error(r, anulando=True)
    except Exception as e:
        app.logger.error(f"Error al anular la ficha médica: {str(e)}")
        return error_interno()
