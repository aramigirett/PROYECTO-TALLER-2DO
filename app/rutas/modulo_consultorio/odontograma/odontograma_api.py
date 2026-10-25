"""
=====================================================
API: Odontograma (/api/v1/odontogramas)
Uno por consulta, precargado con el último del paciente. Lo crea, lo modifica (agrega / quita hallazgos) y lo anula SOLO el médico de la consulta, con la
consulta programada o en proceso (revalidado en la transacción). Un médico solo lee lo de SUS consultas.

Auditoría (`auditoria_cambios`, entidad `odontograma`): ALTA (con la consulta de la que se precargó), MODIFICACION ("odontograma modificado", una por cambio)
y BAJA, con el N.º de consulta, el paciente (con CI) y quién; NUNCA con piezas, superficies ni estados (datos de salud).
=====================================================
"""
import datetime

from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_consultorio.consulta.ConsultaDao import numero_consulta
from app.dao.referenciales_consultorio.odontograma.OdontogramaDao import OdontogramaDao
from app.rutas.modulo_consultorio.utils import acceso_consulta, auditar as _auditar, error_interno, respuesta_error
from app.rutas.modulo_consultorio.validadores_clinicos import validar_pieza_fdi, validar_superficie, NOMBRE_SUPERFICIE
from app.rutas.modulo_seguridad.decorators import require_login, require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion
from app.Services.auditoria_detalle import DetalleAuditoria

odontogramaapi = Blueprint('odontogramaapi', __name__)

ENTIDAD = 'odontograma'

ERRORES = {
    'CONSULTA_NO_ENCONTRADA': (404, 'No se encontró la consulta con el ID proporcionado.'),
    'ODONTOGRAMA_NO_ENCONTRADO': (404, 'No se encontró el odontograma con el ID proporcionado.'),
    'HALLAZGO_NO_ENCONTRADO': (404, 'No se encontró el hallazgo con el ID proporcionado.'),
    'NO_ES_SU_MEDICO': (403, 'Solo el médico de la consulta puede crear, modificar o anular su odontograma.'),
    'YA_EXISTE': (409, 'Esta consulta ya tiene un odontograma. Hay uno solo por consulta: ábralo para modificarlo.'),
    'ESTADO_NO_EXISTE': (400, 'El estado dental seleccionado no existe.'),
}
CAMPO = {'ESTADO_NO_EXISTE': 'id_estado_dental', 'ESTADO_INACTIVO': 'id_estado_dental', 'ESTADO_DE_PIEZA': 'superficie',
         'ESTADO_DE_SUPERFICIE': 'superficie', 'DUPLICADO': 'id_estado_dental'}


def _error(r):
    codigo = r.get('error')
    if codigo == 'CONSULTA_NO_ABIERTA':
        return respuesta_error(f"La consulta está {r.get('estado')}: ya no admite cambios en su odontograma.", 409)
    if codigo == 'ESTADO_INACTIVO':
        return respuesta_error(f"El estado dental «{r['detalle']}» está inactivo.", 409, CAMPO[codigo])
    if codigo == 'ESTADO_DE_PIEZA':
        return respuesta_error(f"«{r['detalle']}» es un hallazgo de la pieza completa: use la superficie T (pieza completa).", 400, CAMPO[codigo])
    if codigo == 'ESTADO_DE_SUPERFICIE':
        return respuesta_error(f"«{r['detalle']}» es un hallazgo de una superficie: elija O, V, L, M o D.", 400, CAMPO[codigo])
    if codigo == 'DUPLICADO':
        return respuesta_error('Ese hallazgo ya está registrado en el odontograma (misma pieza, superficie y estado).', 409, CAMPO[codigo])
    if codigo in ERRORES:
        status, mensaje = ERRORES[codigo]
        return respuesta_error(mensaje, status, CAMPO.get(codigo))
    return error_interno()


def _paciente(ctx):
    return f"{ctx['paciente']} (CI {ctx['cedula']})"


def _fecha(nombre):
    valor = request.args.get(nombre, '').strip()
    if not valor:
        return None, None
    try:
        return datetime.date.fromisoformat(valor), None
    except ValueError:
        return None, f'El filtro "{nombre}" debe tener el formato AAAA-MM-DD.'


# -------------------------
# Catálogo de estados dentales (color, símbolo y si aplica a la pieza completa o a una superficie): lo usa el dibujo del odontograma
# -------------------------
@odontogramaapi.route('/estados-dentales', methods=['GET'])
@require_login
def getEstadosDentales():
    try:
        return jsonify({'success': True, 'data': OdontogramaDao().getEstadosDentales(), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener los estados dentales: {str(e)}")
        return error_interno()


# -------------------------
# Lecturas (un médico solo ve lo de SUS consultas)
# -------------------------
@odontogramaapi.route('/odontogramas', methods=['GET'])
@require_permiso('odontograma', 'ver')
def getOdontogramas():
    desde, e1 = _fecha('desde')
    hasta, e2 = _fecha('hasta')
    if e1 or e2:
        return respuesta_error(e1 or e2, 400)
    if desde and hasta and desde > hasta:
        return respuesta_error('La fecha "desde" no puede ser posterior a "hasta".', 400)
    try:
        pagina, por_pagina = int(request.args.get('pagina', 1)), int(request.args.get('por_pagina', 25))
    except ValueError:
        return respuesta_error('La paginación debe ser numérica.', 400)
    try:
        filas, total = OdontogramaDao().listar(request.args.get('q', '').strip()[:80] or None, desde, hasta, id_medico_sesion(),
                                               pagina=pagina, por_pagina=por_pagina)
        return jsonify({'success': True, 'data': filas, 'total': total, 'pagina': max(1, pagina), 'por_pagina': por_pagina, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al listar odontogramas: {str(e)}")
        return error_interno()


@odontogramaapi.route('/odontogramas/consulta/<int:id_consulta_cab>', methods=['GET'])
@require_permiso('odontograma', 'ver')
def getOdontogramaDeConsulta(id_consulta_cab):
    """El odontograma vigente de la consulta (con sus hallazgos) o data = None si todavía no se creó."""
    try:
        _, prohibido = acceso_consulta(id_consulta_cab)
        if prohibido:
            return prohibido
        return jsonify({'success': True, 'data': OdontogramaDao().getOdontogramaByConsulta(id_consulta_cab), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener el odontograma de la consulta: {str(e)}")
        return error_interno()


@odontogramaapi.route('/odontogramas/<int:id_odontograma>', methods=['GET'])
@require_permiso('odontograma', 'ver')
def getOdontograma(id_odontograma):
    try:
        odo = OdontogramaDao().getOdontogramaById(id_odontograma)
        if not odo:
            return respuesta_error('No se encontró el odontograma con el ID proporcionado.', 404)
        _, prohibido = acceso_consulta(odo['id_consulta_cab'])
        if prohibido:
            return prohibido
        return jsonify({'success': True, 'data': odo, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener el odontograma: {str(e)}")
        return error_interno()


@odontogramaapi.route('/odontogramas/paciente/<int:id_paciente>', methods=['GET'])
@require_permiso('odontograma', 'ver')
def getOdontogramasPaciente(id_paciente):
    try:
        filas, total = OdontogramaDao().listar(id_medico=id_medico_sesion(), id_paciente=id_paciente, por_pagina=100)
        return jsonify({'success': True, 'data': filas, 'total': total, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener los odontogramas del paciente: {str(e)}")
        return error_interno()


# -------------------------
# Alta (con la precarga hecha por el servidor)
# -------------------------
@odontogramaapi.route('/odontogramas', methods=['POST'])
@require_permiso('odontograma', 'nuevo')
def addOdontograma():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get('id_consulta_cab') in (None, ''):
        return respuesta_error('El campo id_consulta_cab es obligatorio.', 400, 'id_consulta_cab')
    try:
        id_consulta = int(data['id_consulta_cab'])
    except (ValueError, TypeError):
        return respuesta_error('El campo id_consulta_cab no es válido.', 400, 'id_consulta_cab')
    try:
        r = OdontogramaDao().crearOdontograma(id_consulta, id_medico_sesion())
        if 'id_odontograma' in r:
            numero = numero_consulta(id_consulta)
            origen = r['precargado_de']
            nuevos = {'Consulta': numero, 'Paciente': _paciente(r['contexto'])}
            if origen:
                nuevos['Precargado desde'] = origen['numero_consulta']
            _auditar(ENTIDAD, r['id_odontograma'], 'ALTA', DetalleAuditoria('; '.join(f'{k}: {v}' for k, v in nuevos.items()), {}, nuevos))
            msg = f'Odontograma de la consulta {numero} creado correctamente.'
            if origen:
                msg += f" Se precargó con el estado de la consulta {origen['numero_consulta']}."
            return jsonify({'success': True, 'data': {'id_odontograma': r['id_odontograma'], 'precargado_de': origen}, 'mensaje': msg, 'error': None}), 201
        return _error(r)
    except Exception as e:
        app.logger.error(f"Error al crear el odontograma: {str(e)}")
        return error_interno()


# -------------------------
# Hallazgos: agregar y quitar (modificar el odontograma)
# -------------------------
@odontogramaapi.route('/odontogramas/<int:id_odontograma>/hallazgos', methods=['POST'])
@require_permiso('odontograma', 'editar')
def addHallazgo(id_odontograma):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return respuesta_error('Los datos enviados no son válidos.', 400)
    pieza, e = validar_pieza_fdi(data.get('numero_diente'), obligatoria=True)
    if e:
        return respuesta_error(e, 400, 'numero_diente')
    superficie, e = validar_superficie(data.get('superficie'))
    if e:
        return respuesta_error(e, 400, 'superficie')
    estado = data.get('id_estado_dental')
    if isinstance(estado, bool) or estado in (None, '') or not str(estado).strip().isdigit() or int(str(estado).strip()) <= 0:
        return respuesta_error('Debe elegir el estado dental del hallazgo.', 400, 'id_estado_dental')
    observacion = data.get('observacion')
    if observacion in (None, ''):
        observacion = None
    elif not isinstance(observacion, str) or len(observacion.strip()) > 500:
        return respuesta_error('La observación debe ser un texto de hasta 500 caracteres.', 400, 'observacion')
    else:
        observacion = observacion.strip() or None
    try:
        r = OdontogramaDao().agregarHallazgo(id_odontograma, pieza, superficie, int(str(estado).strip()), observacion, id_medico_sesion())
        if 'id_odontograma_detalle' in r:
            numero = numero_consulta(r['id_consulta_cab'])
            _auditar(ENTIDAD, id_odontograma, 'MODIFICACION',
                     DetalleAuditoria(f"Odontograma de la consulta {numero} de {_paciente(r['contexto'])}; odontograma modificado", {}, {}))
            return jsonify({'success': True, 'data': {'id_odontograma_detalle': r['id_odontograma_detalle']},
                            'mensaje': f'Hallazgo registrado en la pieza {pieza} ({NOMBRE_SUPERFICIE[superficie]}).', 'error': None}), 201
        return _error(r)
    except Exception as e:
        app.logger.error(f"Error al agregar el hallazgo: {str(e)}")
        return error_interno()


@odontogramaapi.route('/odontogramas/hallazgos/<int:id_detalle>', methods=['DELETE'])
@require_permiso('odontograma', 'editar')
def deleteHallazgo(id_detalle):
    try:
        r = OdontogramaDao().quitarHallazgo(id_detalle, id_medico_sesion())
        if r.get('ok'):
            numero = numero_consulta(r['id_consulta_cab'])
            _auditar(ENTIDAD, r['id_odontograma'], 'MODIFICACION',
                     DetalleAuditoria(f"Odontograma de la consulta {numero} de {_paciente(r['contexto'])}; odontograma modificado", {}, {}))
            return jsonify({'success': True, 'mensaje': 'Hallazgo quitado del odontograma.', 'error': None}), 200
        return _error(r)
    except Exception as e:
        app.logger.error(f"Error al quitar el hallazgo: {str(e)}")
        return error_interno()


# -------------------------
# Anulación (definitiva)
# -------------------------
@odontogramaapi.route('/odontogramas/<int:id_odontograma>', methods=['DELETE'])
@require_permiso('odontograma', 'anular')
def deleteOdontograma(id_odontograma):
    try:
        r = OdontogramaDao().anularOdontograma(id_odontograma, id_medico_sesion())
        if r.get('ok'):
            numero = numero_consulta(r['id_consulta_cab'])
            _auditar(ENTIDAD, id_odontograma, 'BAJA', f"Odontograma de la consulta {numero}; Paciente: {_paciente(r['contexto'])}")
            return jsonify({'success': True, 'mensaje': f'Odontograma de la consulta {numero} anulado correctamente.', 'error': None}), 200
        return _error(r)
    except Exception as e:
        app.logger.error(f"Error al anular el odontograma: {str(e)}")
        return error_interno()
