"""
=====================================================
API: Justificativo Médico (/api/v1/justificativos)
Generar Justificativo Médico: Ver / Nuevo (queda 'pendiente') / Generar (emitir, permiso `estado`) / Anular / PDF. Crea y anula SOLO el médico de la consulta, con la
consulta programada o en proceso (revalidado en la transacción); emite solo el médico de la consulta (también con la consulta finalizada). Un médico solo lee lo de
SUS consultas.

Auditoría (`auditoria_cambios`, entidad `justificativo_medico`): ALTA, MODIFICACION (Pendiente -> Emitido), BAJA (Pendiente / Emitido -> Anulado) y EXPORTACION (cada
descarga del PDF) con el N.º de justificativo, el N.º de consulta y el paciente (con CI); NUNCA con los días de reposo ni las recomendaciones (dato de salud). El PDF sí
lleva el contenido: es el documento que se entrega al paciente (PENDIENTE = marca BORRADOR, emitido = sin marca, anulado = marca ANULADO).
=====================================================
"""
from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_consultorio.consulta.ConsultaDao import numero_consulta
from app.dao.referenciales_consultorio.justificativo_medico.JustificativoMedicoDao import ESTADOS, JustificativoMedicoDao
from app.rutas.modulo_consultorio.orden_api_base import leer_filtros, respuesta_pdf
from app.rutas.modulo_consultorio.utils import acceso_consulta, auditar as _auditar, error_interno, respuesta_error
from app.rutas.modulo_consultorio.validadores_clinicos import validar_justificativo
from app.rutas.modulo_seguridad.decorators import require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion
from app.Services.auditoria_detalle import DetalleAuditoria
from app.Services.documento_clinico_pdf_service import generarDocumentoPdf

justificativomedicoapi = Blueprint('justificativomedicoapi', __name__)

ENTIDAD = 'justificativo_medico'
ETIQUETA_ESTADO = {'pendiente': 'Pendiente', 'emitido': 'Emitido', 'anulado': 'Anulado'}

ERRORES = {
    'CONSULTA_NO_ENCONTRADA': (404, 'No se encontró la consulta con el ID proporcionado.'),
    'JUSTIFICATIVO_NO_ENCONTRADO': (404, 'No se encontró el justificativo con el ID proporcionado, o ya estaba anulado.'),
    'NO_ES_SU_MEDICO': (403, 'Solo el médico de la consulta puede registrar, generar o anular sus justificativos.'),
    'DIAGNOSTICO_INVALIDO': (400, 'El diagnóstico seleccionado no existe, está anulado o no pertenece a esta consulta.'),
    'YA_EMITIDO': (409, 'El justificativo ya está emitido.'),
    'CONSULTA_CANCELADA': (409, 'La consulta fue cancelada: el justificativo ya no se puede generar.'),
}
CAMPO_DEL_ERROR = {'DIAGNOSTICO_INVALIDO': 'id_diagnostico'}


def _error(r, anulando=False):
    codigo = r.get('error')
    if codigo == 'CONSULTA_NO_ABIERTA':
        estado = r.get('estado')
        if anulando and estado == 'finalizada':
            return respuesta_error('No se puede anular: la consulta ya está finalizada.', 409)
        return respuesta_error(f'La consulta está {estado}: ya no admite nuevos justificativos.', 409)
    if codigo in ERRORES:
        status, mensaje = ERRORES[codigo]
        return respuesta_error(mensaje, status, CAMPO_DEL_ERROR.get(codigo))
    return error_interno()


def _paciente(ctx):
    return f"{ctx['paciente']} (CI {ctx['cedula']})"


def _leer_con_acceso(id_justificativo, solo_vigentes=True):
    j = JustificativoMedicoDao().getJustificativoById(id_justificativo, solo_vigentes)
    if not j:
        return None, respuesta_error('No se encontró el justificativo con el ID proporcionado.', 404)
    _, prohibido = acceso_consulta(j['id_consulta_cab'])
    return (None, prohibido) if prohibido else (j, None)


@justificativomedicoapi.route('/justificativos', methods=['GET'])
@require_permiso('justificativomedico', 'ver')
def getJustificativos():
    desde, hasta, pagina, por_pagina, consulta, error = leer_filtros()
    if error:
        return respuesta_error(error, 400)
    estado = request.args.get('estado', '').strip()
    if estado and estado not in ESTADOS:
        return respuesta_error('El estado debe ser pendiente, emitido o anulado.', 400)
    try:
        filas, total = JustificativoMedicoDao().listar(request.args.get('q', '').strip()[:80] or None, estado or None, desde, hasta, id_medico_sesion(), consulta, pagina, por_pagina)
        return jsonify({'success': True, 'data': filas, 'total': total, 'pagina': max(1, pagina), 'por_pagina': por_pagina, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener los justificativos: {str(e)}")
        return error_interno()


@justificativomedicoapi.route('/justificativos/<int:id_justificativo>', methods=['GET'])
@require_permiso('justificativomedico', 'ver')
def getJustificativo(id_justificativo):
    try:
        j, prohibido = _leer_con_acceso(id_justificativo, solo_vigentes=False)
        if prohibido:
            return prohibido
        return jsonify({'success': True, 'data': j, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener el justificativo: {str(e)}")
        return error_interno()


@justificativomedicoapi.route('/justificativos', methods=['POST'])
@require_permiso('justificativomedico', 'nuevo')
def addJustificativo():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get('id_consulta_cab') in (None, ''):
        return respuesta_error('El campo "Consulta" es obligatorio.', 400, 'id_consulta_cab')
    try:
        id_consulta = int(data['id_consulta_cab'])
    except (ValueError, TypeError):
        return respuesta_error('El campo "Consulta" no es válido.', 400, 'id_consulta_cab')
    valores, error, campo = validar_justificativo(data)
    if error:
        return respuesta_error(error, 400, campo)
    valores['id_consulta_cab'] = id_consulta
    try:
        r = JustificativoMedicoDao().guardarJustificativo(valores, id_medico_sesion())
        if 'id_justificativo' in r:
            numero = f"JUS-{r['id_justificativo']:07d}"
            nuevos = {'Documento': numero, 'Consulta': numero_consulta(id_consulta), 'Paciente': _paciente(r['contexto']), 'Estado': 'Pendiente'}
            _auditar(ENTIDAD, r['id_justificativo'], 'ALTA', DetalleAuditoria('; '.join(f'{k}: {v}' for k, v in nuevos.items()), {}, nuevos))
            return jsonify({'success': True, 'data': {'id_justificativo': r['id_justificativo'], 'numero': numero},
                            'mensaje': f'Justificativo {numero} registrado como pendiente.', 'error': None}), 201
        return _error(r)
    except Exception as e:
        app.logger.error(f"Error al registrar justificativo: {str(e)}")
        return error_interno()


@justificativomedicoapi.route('/justificativos/<int:id_justificativo>/emitir', methods=['PUT'])
@require_permiso('justificativomedico', 'estado')
def emitirJustificativo(id_justificativo):
    try:
        r = JustificativoMedicoDao().emitirJustificativo(id_justificativo, id_medico_sesion())
        if r.get('ok'):
            numero = f'JUS-{id_justificativo:07d}'
            ant, nue = ETIQUETA_ESTADO['pendiente'], ETIQUETA_ESTADO['emitido']
            _auditar(ENTIDAD, id_justificativo, 'MODIFICACION',
                     DetalleAuditoria(f"{numero}; Consulta {numero_consulta(r['id_consulta_cab'])}; Paciente: {_paciente(r['contexto'])}; Estado: {ant} -> {nue}", {'Estado': ant}, {'Estado': nue}))
            return jsonify({'success': True, 'data': {'estado': 'emitido'}, 'mensaje': f'Justificativo {numero} emitido correctamente.', 'error': None}), 200
        return _error(r)
    except Exception as e:
        app.logger.error(f"Error al emitir justificativo: {str(e)}")
        return error_interno()


@justificativomedicoapi.route('/justificativos/<int:id_justificativo>', methods=['DELETE'])
@require_permiso('justificativomedico', 'anular')
def deleteJustificativo(id_justificativo):
    try:
        r = JustificativoMedicoDao().anularJustificativo(id_justificativo, id_medico_sesion())
        if r.get('ok'):
            numero = f'JUS-{id_justificativo:07d}'
            ant, nue = ETIQUETA_ESTADO[r['anterior']], ETIQUETA_ESTADO['anulado']
            _auditar(ENTIDAD, id_justificativo, 'BAJA',
                     DetalleAuditoria(f"{numero}; Consulta {numero_consulta(r['id_consulta_cab'])}; Paciente: {_paciente(r['contexto'])}; Estado: {ant} -> {nue}", {'Estado': ant}, {'Estado': nue}))
            return jsonify({'success': True, 'mensaje': f'Justificativo {numero} anulado correctamente.', 'error': None}), 200
        return _error(r, anulando=True)
    except Exception as e:
        app.logger.error(f"Error al anular justificativo: {str(e)}")
        return error_interno()


@justificativomedicoapi.route('/justificativos/<int:id_justificativo>/pdf', methods=['GET'])
@require_permiso('justificativomedico', 'ver')
def pdfJustificativo(id_justificativo):
    try:
        _, prohibido = _leer_con_acceso(id_justificativo, solo_vigentes=False)
        if prohibido:
            return prohibido
        doc = JustificativoMedicoDao().getParaPdf(id_justificativo)
        if not doc:
            return respuesta_error('No se encontró el justificativo con el ID proporcionado.', 404)
        contenido = generarDocumentoPdf('justificativo', doc)
        _auditar(ENTIDAD, id_justificativo, 'EXPORTACION',
                 f"PDF del justificativo {doc['numero']}; Consulta {doc['numero_consulta']}; Paciente: {doc['nombre_paciente']} (CI {doc['cedula_paciente']})")
        return respuesta_pdf(contenido, f"{doc['numero']}.pdf")
    except Exception as e:
        app.logger.error(f"Error al generar el PDF del justificativo: {str(e)}")
        return error_interno()
