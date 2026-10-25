"""
=====================================================
API: Receta (/api/v1/recetas)
Generar Recetas e Indicaciones: Ver / Nuevo / Anular / PDF (no hay edición). Crea y anula SOLO el médico de la consulta, con la consulta programada o en
proceso (revalidado en la transacción). Un médico solo lee lo de SUS consultas.

Auditoría (`auditoria_cambios`, entidad `recetas`): ALTA, BAJA y EXPORTACION (cada descarga del PDF) con el N.º de receta, el N.º de consulta y el paciente
(con CI); NUNCA con los medicamentos, las dosis ni las indicaciones (dato de salud). El PDF sí lleva el contenido: es el documento que se entrega al paciente.
=====================================================
"""
from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_consultorio.consulta.ConsultaDao import numero_consulta
from app.dao.referenciales_consultorio.receta.RecetaDao import RecetaDao
from app.rutas.modulo_consultorio.orden_api_base import leer_filtros, respuesta_pdf
from app.rutas.modulo_consultorio.utils import acceso_consulta, auditar as _auditar, error_interno, respuesta_error
from app.rutas.modulo_consultorio.validadores_clinicos import validar_receta
from app.rutas.modulo_seguridad.decorators import require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion
from app.Services.auditoria_detalle import DetalleAuditoria
from app.Services.documento_clinico_pdf_service import generarDocumentoPdf

recetaapi = Blueprint('recetaapi', __name__)

ENTIDAD = 'recetas'

ERRORES = {
    'CONSULTA_NO_ENCONTRADA': (404, 'No se encontró la consulta con el ID proporcionado.'),
    'RECETA_NO_ENCONTRADA': (404, 'No se encontró la receta con el ID proporcionado, o ya estaba anulada.'),
    'NO_ES_SU_MEDICO': (403, 'Solo el médico de la consulta puede registrar o anular sus recetas.'),
    'DIAGNOSTICO_INVALIDO': (400, 'El diagnóstico seleccionado no existe, está anulado o no pertenece a esta consulta.'),
    'TRATAMIENTO_INVALIDO': (400, 'El tratamiento seleccionado no existe, está cancelado o no pertenece a esta consulta.'),
    'MEDICAMENTO_NO_EXISTE': (400, 'Alguno de los medicamentos seleccionados no existe.'),
    'DATOS_INVALIDOS': (400, 'Los datos de la receta no cumplen las reglas de la base de datos.'),
}
CAMPO_DEL_ERROR = {'DIAGNOSTICO_INVALIDO': 'id_diagnostico', 'TRATAMIENTO_INVALIDO': 'id_tratamiento', 'MEDICAMENTO_NO_EXISTE': 'medicamentos', 'MEDICAMENTO_INACTIVO': 'medicamentos'}


def _error(r, anulando=False):
    codigo = r.get('error')
    if codigo == 'CONSULTA_NO_ABIERTA':
        estado = r.get('estado')
        if anulando and estado == 'finalizada':
            return respuesta_error('No se puede anular: la consulta ya está finalizada.', 409)
        return respuesta_error(f'La consulta está {estado}: ya no admite cambios en sus recetas.', 409)
    if codigo == 'MEDICAMENTO_INACTIVO':
        return respuesta_error(f"Hay medicamentos inactivos: {r['detalle']}. Quítelos de la receta.", 409, 'medicamentos')
    if codigo in ERRORES:
        status, mensaje = ERRORES[codigo]
        return respuesta_error(mensaje, status, CAMPO_DEL_ERROR.get(codigo))
    return error_interno()


def _paciente(ctx):
    return f"{ctx['paciente']} (CI {ctx['cedula']})"


@recetaapi.route('/recetas', methods=['GET'])
@require_permiso('receta', 'ver')
def getRecetas():
    desde, hasta, pagina, por_pagina, consulta, error = leer_filtros()
    if error:
        return respuesta_error(error, 400)
    try:
        filas, total = RecetaDao().listar(request.args.get('q', '').strip()[:80] or None, desde, hasta, id_medico_sesion(), consulta, pagina, por_pagina)
        return jsonify({'success': True, 'data': filas, 'total': total, 'pagina': max(1, pagina), 'por_pagina': por_pagina, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener las recetas: {str(e)}")
        return error_interno()


def _leer_con_acceso(id_receta, solo_vigentes=True):
    receta = RecetaDao().getRecetaById(id_receta, solo_vigentes)
    if not receta:
        return None, respuesta_error('No se encontró la receta con el ID proporcionado.', 404)
    _, prohibido = acceso_consulta(receta['id_consulta_cab'])
    return (None, prohibido) if prohibido else (receta, None)


@recetaapi.route('/recetas/<int:id_receta>', methods=['GET'])
@require_permiso('receta', 'ver')
def getReceta(id_receta):
    try:
        receta, prohibido = _leer_con_acceso(id_receta, solo_vigentes=False)
        if prohibido:
            return prohibido
        return jsonify({'success': True, 'data': receta, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener la receta: {str(e)}")
        return error_interno()


@recetaapi.route('/recetas', methods=['POST'])
@require_permiso('receta', 'nuevo')
def addReceta():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get('id_consulta_cab') in (None, ''):
        return respuesta_error('El campo id_consulta_cab es obligatorio.', 400, 'id_consulta_cab')
    try:
        id_consulta = int(data['id_consulta_cab'])
    except (ValueError, TypeError):
        return respuesta_error('El campo id_consulta_cab no es válido.', 400, 'id_consulta_cab')
    valores, error, campo = validar_receta(data)
    if error:
        return respuesta_error(error, 400, campo)
    valores['id_consulta_cab'] = id_consulta
    try:
        r = RecetaDao().guardarReceta(valores, id_medico_sesion())
        if 'id_receta' in r:
            numero = f"RCT-{r['id_receta']:07d}"
            nuevos = {'Documento': numero, 'Consulta': numero_consulta(id_consulta), 'Paciente': _paciente(r['contexto'])}
            _auditar(ENTIDAD, r['id_receta'], 'ALTA', DetalleAuditoria('; '.join(f'{k}: {v}' for k, v in nuevos.items()), {}, nuevos))
            return jsonify({'success': True, 'data': {'id_receta': r['id_receta'], 'numero': numero}, 'mensaje': f'Receta {numero} registrada correctamente.', 'error': None}), 201
        return _error(r)
    except Exception as e:
        app.logger.error(f"Error al registrar receta: {str(e)}")
        return error_interno()


@recetaapi.route('/recetas/<int:id_receta>', methods=['DELETE'])
@require_permiso('receta', 'anular')
def deleteReceta(id_receta):
    try:
        r = RecetaDao().anularReceta(id_receta, id_medico_sesion())
        if r.get('ok'):
            numero = f'RCT-{id_receta:07d}'
            _auditar(ENTIDAD, id_receta, 'BAJA', f"{numero}; Consulta {numero_consulta(r['id_consulta_cab'])}; Paciente: {_paciente(r['contexto'])}")
            return jsonify({'success': True, 'mensaje': f'Receta {numero} anulada correctamente.', 'error': None}), 200
        return _error(r, anulando=True)
    except Exception as e:
        app.logger.error(f"Error al anular receta: {str(e)}")
        return error_interno()


@recetaapi.route('/recetas/<int:id_receta>/pdf', methods=['GET'])
@require_permiso('receta', 'ver')
def pdfReceta(id_receta):
    try:
        _, prohibido = _leer_con_acceso(id_receta, solo_vigentes=False)
        if prohibido:
            return prohibido
        doc = RecetaDao().getParaPdf(id_receta)
        if not doc:
            return respuesta_error('No se encontró la receta con el ID proporcionado.', 404)
        contenido = generarDocumentoPdf('receta', doc)
        _auditar(ENTIDAD, id_receta, 'EXPORTACION',
                 f"PDF de la receta {doc['numero']}; Consulta {doc['numero_consulta']}; Paciente: {doc['nombre_paciente']} (CI {doc['cedula_paciente']})")
        return respuesta_pdf(contenido, f"{doc['numero']}.pdf")
    except Exception as e:
        app.logger.error(f"Error al generar el PDF de la receta: {str(e)}")
        return error_interno()
