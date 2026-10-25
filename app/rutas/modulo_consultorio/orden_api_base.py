"""
=====================================================
Fábrica de las APIs de las Órdenes de Estudios y de Análisis (idénticas: solo cambian el catálogo, la ventana y la tabla).
Cada API declara solo lo suyo y llama a crear_orden_api(); las reglas viven en OrdenBaseDao.

  GET    /<ruta>                  listado (filtros q, estado, desde, hasta, consulta + paginación); un médico solo ve las de SUS consultas
  GET    /<ruta>/<id>             detalle
  POST   /<ruta>                  alta (solo el médico de la consulta, consulta abierta)
  PUT    /<ruta>/<id>/estado      avanza UN paso (solo el médico de la orden; se permite con la consulta finalizada)
  DELETE /<ruta>/<id>             anula (definitivo; no con la consulta finalizada ni con la orden completada)
  GET    /<ruta>/<id>/pdf         el documento en PDF (lleva el contenido clínico; la descarga queda auditada como EXPORTACION)

Auditoría (`auditoria_cambios`): ALTA, BAJA, MODIFICACION (estado) y EXPORTACION (PDF) con el N.º de documento, el N.º de consulta y el paciente (con CI);
NUNCA con el tipo, el motivo ni las indicaciones (dato de salud).
=====================================================
"""
import datetime

from flask import Blueprint, Response, current_app as app, jsonify, request
from app.dao.referenciales_consultorio.consulta.ConsultaDao import numero_consulta
from app.dao.referenciales_consultorio.orden_base import ESTADOS
from app.rutas.modulo_consultorio.utils import acceso_consulta, auditar as _auditar, error_interno, respuesta_error
from app.rutas.modulo_seguridad.decorators import require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion
from app.Services.auditoria_detalle import DetalleAuditoria
from app.Services.documento_clinico_pdf_service import ETIQUETA_ESTADO, generarDocumentoPdf


def leer_filtros():
    """(desde, hasta, pagina, por_pagina, consulta, error) de la query string."""
    def fecha(nombre):
        valor = request.args.get(nombre, '').strip()
        if not valor:
            return None, None
        try:
            return datetime.date.fromisoformat(valor), None
        except ValueError:
            return None, f'El filtro "{nombre}" debe tener el formato AAAA-MM-DD.'

    def entero(nombre, defecto):
        valor = request.args.get(nombre, '').strip()
        if not valor:
            return defecto, None
        return (int(valor), None) if valor.isdigit() else (None, f'El filtro "{nombre}" debe ser numérico.')
    desde, e1 = fecha('desde')
    hasta, e2 = fecha('hasta')
    pagina, e3 = entero('pagina', 1)
    por_pagina, e4 = entero('por_pagina', 25)
    consulta, e5 = entero('consulta', None)
    error = e1 or e2 or e3 or e4 or e5
    if not error and desde and hasta and desde > hasta:
        error = 'La fecha "desde" no puede ser posterior a "hasta".'
    return desde, hasta, pagina, por_pagina, consulta, error


def respuesta_pdf(pdf, nombre_archivo):
    return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': f'inline; filename={nombre_archivo}'})


def crear_orden_api(blueprint, ventana, ruta, dao_cls, entidad, pk, tipo_col, nombre, pdf_tipo, validar):
    """
    `nombre`: 'orden de estudios' / 'orden de análisis' (para los mensajes). `pk`: 'id_orden_estudio'. `tipo_col`: 'id_tipo_estudio'.
    `validar`: función de validadores_clinicos (validar_orden_estudio / validar_orden_analisis).
    """
    bp = Blueprint(blueprint, __name__)
    etiqueta_tipo = tipo_col.replace('id_', '').replace('_', ' ')

    errores = {
        'CONSULTA_NO_ENCONTRADA': (404, 'No se encontró la consulta con el ID proporcionado.'),
        'ORDEN_NO_ENCONTRADA': (404, f'No se encontró la {nombre} con el ID proporcionado, o ya estaba cancelada.'),
        'NO_ES_SU_MEDICO': (403, f'Solo el médico de la consulta puede registrar, avanzar o anular sus {nombre.replace("orden", "órdenes", 1)}.'),
        'DIAGNOSTICO_INVALIDO': (400, 'El diagnóstico seleccionado no existe, está anulado o no pertenece a esta consulta.'),
        'TRATAMIENTO_INVALIDO': (400, 'El tratamiento seleccionado no existe, está cancelado o no pertenece a esta consulta.'),
        'TIPO_NO_EXISTE': (400, f'El {etiqueta_tipo} seleccionado no existe.'),
        'TIPO_INACTIVO': (409, f'El {etiqueta_tipo} seleccionado está inactivo.'),
        'YA_COMPLETADA': (409, f'La {nombre} ya está completada: no se puede cancelar ni avanzar.'),
        'CONSULTA_CANCELADA': (409, 'La consulta fue cancelada: la orden ya no se puede avanzar.'),
        'DATOS_INVALIDOS': (400, f'Los datos de la {nombre} no cumplen las reglas de la base de datos.'),
    }
    campo_del_error = {'TIPO_NO_EXISTE': tipo_col, 'TIPO_INACTIVO': tipo_col, 'DIAGNOSTICO_INVALIDO': 'id_diagnostico', 'TRATAMIENTO_INVALIDO': 'id_tratamiento'}

    def _error(r, anulando=False):
        codigo = r.get('error')
        if codigo == 'CONSULTA_NO_ABIERTA':
            estado = r.get('estado')
            if anulando and estado == 'finalizada':
                return respuesta_error(f'No se puede anular: la consulta ya está finalizada.', 409)
            return respuesta_error(f'La consulta está {estado}: ya no admite cambios.', 409)
        if codigo in errores:
            status, mensaje = errores[codigo]
            return respuesta_error(mensaje, status, campo_del_error.get(codigo))
        return error_interno()

    def _paciente(ctx):
        return f"{ctx['paciente']} (CI {ctx['cedula']})"

    @bp.route(ruta, methods=['GET'], endpoint=f'listar_{blueprint}')
    @require_permiso(ventana, 'ver')
    def listar():
        desde, hasta, pagina, por_pagina, consulta, error = leer_filtros()
        if error:
            return respuesta_error(error, 400)
        estado = request.args.get('estado', '').strip()
        if estado and estado not in ESTADOS:
            return respuesta_error('El estado no es válido.', 400)
        try:
            filas, total = dao_cls().listar(request.args.get('q', '').strip()[:80] or None, estado or None, desde, hasta, id_medico_sesion(), consulta, pagina, por_pagina)
            return jsonify({'success': True, 'data': filas, 'total': total, 'pagina': max(1, pagina), 'por_pagina': por_pagina, 'error': None}), 200
        except Exception as e:
            app.logger.error(f"Error al listar {nombre}: {str(e)}")
            return error_interno()

    def _leer_con_acceso(id_orden, solo_vigentes=True):
        orden = dao_cls().getById(id_orden, solo_vigentes)
        if not orden:
            return None, respuesta_error(f'No se encontró la {nombre} con el ID proporcionado.', 404)
        _, prohibido = acceso_consulta(orden['id_consulta_cab'])
        return (orden, prohibido) if not prohibido else (None, prohibido)

    @bp.route(f'{ruta}/<int:id_orden>', methods=['GET'], endpoint=f'detalle_{blueprint}')
    @require_permiso(ventana, 'ver')
    def detalle(id_orden):
        try:
            orden, prohibido = _leer_con_acceso(id_orden, solo_vigentes=False)
            if prohibido:
                return prohibido
            return jsonify({'success': True, 'data': orden, 'error': None}), 200
        except Exception as e:
            app.logger.error(f"Error al obtener {nombre}: {str(e)}")
            return error_interno()

    @bp.route(ruta, methods=['POST'], endpoint=f'alta_{blueprint}')
    @require_permiso(ventana, 'nuevo')
    def alta():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or data.get('id_consulta_cab') in (None, ''):
            return respuesta_error('El campo id_consulta_cab es obligatorio.', 400, 'id_consulta_cab')
        try:
            id_consulta = int(data['id_consulta_cab'])
        except (ValueError, TypeError):
            return respuesta_error('El campo id_consulta_cab no es válido.', 400, 'id_consulta_cab')
        valores, error, campo = validar(data)
        if error:
            return respuesta_error(error, 400, campo)
        valores['id_consulta_cab'] = id_consulta
        try:
            dao = dao_cls()
            r = dao.guardar(valores, id_medico_sesion())
            if pk in r:
                numero = f'{dao.PREFIJO}-{r[pk]:07d}'
                nuevos = {'Documento': numero, 'Consulta': numero_consulta(id_consulta), 'Paciente': _paciente(r['contexto'])}
                _auditar(entidad, r[pk], 'ALTA', DetalleAuditoria('; '.join(f'{k}: {v}' for k, v in nuevos.items()), {}, nuevos))
                return jsonify({'success': True, 'data': {pk: r[pk], 'numero': numero}, 'mensaje': f'{nombre.capitalize()} {numero} registrada correctamente.', 'error': None}), 201
            return _error(r)
        except Exception as e:
            app.logger.error(f"Error al agregar {nombre}: {str(e)}")
            return error_interno()

    @bp.route(f'{ruta}/<int:id_orden>/estado', methods=['PUT'], endpoint=f'estado_{blueprint}')
    @require_permiso(ventana, 'estado')
    def avanzar(id_orden):
        try:
            dao = dao_cls()
            r = dao.avanzarEstado(id_orden, id_medico_sesion())
            if r.get('ok'):
                ctx, numero = r['contexto'], f'{dao.PREFIJO}-{id_orden:07d}'
                ant, nue = ETIQUETA_ESTADO[r['anterior']], ETIQUETA_ESTADO[r['nuevo']]
                _auditar(entidad, id_orden, 'MODIFICACION',
                         DetalleAuditoria(f"{numero}; Consulta {numero_consulta(r['id_consulta_cab'])}; Paciente: {_paciente(ctx)}; Estado: {ant} -> {nue}", {'Estado': ant}, {'Estado': nue}))
                return jsonify({'success': True, 'data': {'estado': r['nuevo']}, 'mensaje': f'{nombre.capitalize()} {numero} actualizada a "{nue}".', 'error': None}), 200
            return _error(r)
        except Exception as e:
            app.logger.error(f"Error al avanzar el estado de {nombre}: {str(e)}")
            return error_interno()

    @bp.route(f'{ruta}/<int:id_orden>', methods=['DELETE'], endpoint=f'anular_{blueprint}')
    @require_permiso(ventana, 'anular')
    def anular(id_orden):
        try:
            dao = dao_cls()
            r = dao.anular(id_orden, id_medico_sesion())
            if r.get('ok'):
                ctx, numero = r['contexto'], f'{dao.PREFIJO}-{id_orden:07d}'
                _auditar(entidad, id_orden, 'BAJA', f"{numero}; Consulta {numero_consulta(r['id_consulta_cab'])}; Paciente: {_paciente(ctx)}")
                return jsonify({'success': True, 'mensaje': f'{nombre.capitalize()} {numero} anulada correctamente.', 'error': None}), 200
            return _error(r, anulando=True)
        except Exception as e:
            app.logger.error(f"Error al anular {nombre}: {str(e)}")
            return error_interno()

    @bp.route(f'{ruta}/<int:id_orden>/pdf', methods=['GET'], endpoint=f'pdf_{blueprint}')
    @require_permiso(ventana, 'ver')
    def pdf(id_orden):
        try:
            _, prohibido = _leer_con_acceso(id_orden, solo_vigentes=False)
            if prohibido:
                return prohibido
            doc = dao_cls().getParaPdf(id_orden)
            if not doc:
                return respuesta_error(f'No se encontró la {nombre} con el ID proporcionado.', 404)
            contenido = generarDocumentoPdf(pdf_tipo, doc)
            _auditar(entidad, id_orden, 'EXPORTACION',
                     f"PDF de la {nombre} {doc['numero']}; Consulta {doc['numero_consulta']}; Paciente: {doc['nombre_paciente']} (CI {doc['cedula_paciente']})")
            return respuesta_pdf(contenido, f"{doc['numero']}.pdf")
        except Exception as e:
            app.logger.error(f"Error al generar el PDF de {nombre}: {str(e)}")
            return error_interno()

    return bp
