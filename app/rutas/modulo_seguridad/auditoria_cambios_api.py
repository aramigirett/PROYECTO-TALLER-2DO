import re
from datetime import date

from flask import Blueprint, request, jsonify, session, Response, current_app as app

from app.dao.modulo_seguridad.AuditoriaConsultaDao import AuditoriaConsultaDao, TOPE_EXPORTACION
from app.Services import auditoria_pdf_service as informes
from app.Services.auditoria_detalle import ACCIONES, MODULOS, etiqueta_accion, etiqueta_entidad, filas_detalle
from app.rutas.modulo_facturacion.utils import auditar, error_interno, respuesta_error
from app.rutas.modulo_seguridad.decorators import require_permiso

auditoriacambiosapi = Blueprint('auditoriacambiosapi', __name__)

VENTANA = 'auditoriacambios'
POR_PAGINA_MAX = 100
_FORMATO_ENTIDAD = re.compile(r'^[a-z_]{1,50}$')
FORMATOS = ('pdf', 'csv')


def parse_fecha(valor):
    """date desde 'YYYY-MM-DD'; None si viene vacío; ValueError si el formato es inválido."""
    valor = (valor or '').strip()
    return date.fromisoformat(valor) if valor else None


def _entero(valor, nombre):
    valor = (valor or '').strip()
    if not valor:
        return None
    if not valor.isdigit() or int(valor) > 2147483647:
        raise ValueError(f'El valor de {nombre} no es válido.')
    return int(valor)


def leer_filtros(args):
    """Filtros de la consulta: (filtros, None) o (None, mensaje de error 400). Solo lectura de la query string."""
    try:
        desde, hasta = parse_fecha(args.get('desde')), parse_fecha(args.get('hasta'))
    except ValueError:
        return None, 'Las fechas deben tener el formato AAAA-MM-DD.'
    if desde and hasta and desde > hasta:
        return None, 'La fecha "desde" no puede ser posterior a "hasta".'
    try:
        id_usuario, id_registro = _entero(args.get('id_usuario'), 'usuario'), _entero(args.get('id_registro'), 'registro')
    except ValueError as e:
        return None, str(e)
    modulo = (args.get('modulo') or '').strip() or None
    if modulo and modulo not in MODULOS:
        return None, 'El módulo indicado no es válido.'
    entidad = (args.get('entidad') or '').strip() or None
    if entidad and not _FORMATO_ENTIDAD.match(entidad):
        return None, 'La entidad indicada no es válida.'
    accion = (args.get('accion') or '').strip().upper() or None
    if accion and accion not in ACCIONES:
        return None, 'La acción indicada no es válida.'
    return {'desde': desde, 'hasta': hasta, 'id_usuario': id_usuario, 'modulo': modulo, 'entidad': entidad,
            'accion': accion, 'id_registro': id_registro}, None


def _dmy(d):
    return d.strftime('%d/%m/%Y')


def etiquetas_filtros(filtros, dao):
    """Filtros aplicados en texto legible, para el encabezado del PDF y del CSV."""
    r = []
    if filtros['desde'] or filtros['hasta']:
        r.append(('Período', f"{_dmy(filtros['desde']) if filtros['desde'] else 'inicio'} al "
                             f"{_dmy(filtros['hasta']) if filtros['hasta'] else 'hoy'}"))
    if filtros['id_usuario']:
        usuario = next((u for u in dao.get_opciones_filtros()['usuarios'] if u['id_usuario'] == filtros['id_usuario']), None)
        r.append(('Usuario', f"{usuario['nombre']} ({usuario['ci_ruc']})" if usuario else f"N.º {filtros['id_usuario']}"))
    if filtros['modulo']:
        r.append(('Módulo', filtros['modulo']))
    if filtros['entidad']:
        r.append(('Entidad', etiqueta_entidad(filtros['entidad'])))
    if filtros['accion']:
        r.append(('Acción', etiqueta_accion(filtros['accion'])))
    if filtros['id_registro'] is not None:
        r.append(('N.º de registro', filtros['id_registro']))
    return r


def _nombre_emisor():
    return session.get('nombre_completo') or session.get('ci_ruc') or 'Usuario'


def respuesta_archivo(datos, formato, nombre_base):
    """Response de descarga del informe en el formato pedido. PDF inline (se ve en el navegador), CSV como adjunto."""
    hoy = date.today().strftime('%Y%m%d')
    if formato == 'pdf':
        return Response(informes.generarInformePdf(datos), mimetype='application/pdf',
                        headers={'Content-Disposition': f'inline; filename={nombre_base}_{hoy}.pdf'})
    return Response(informes.generar_csv(datos), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename={nombre_base}_{hoy}.csv'})


@auditoriacambiosapi.route('/auditoria-cambios', methods=['GET'])
@require_permiso(VENTANA, 'ver')
def getAuditoriaCambios():
    filtros, error = leer_filtros(request.args)
    if error:
        return respuesta_error(error, 400)
    pagina = max(1, request.args.get('pagina', default=1, type=int))
    por_pagina = max(1, min(request.args.get('por_pagina', default=25, type=int), POR_PAGINA_MAX))
    try:
        filas, total = AuditoriaConsultaDao().listar(filtros, pagina, por_pagina)
        for f in filas:
            f['accion_etiqueta'] = etiqueta_accion(f['accion'])
        return jsonify({'success': True, 'data': filas, 'total': total, 'pagina': pagina, 'por_pagina': por_pagina,
                        'paginas': max(1, -(-total // por_pagina)), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al consultar la auditoría de cambios: {str(e)}")
        return error_interno()


@auditoriacambiosapi.route('/auditoria-cambios/filtros', methods=['GET'])
@require_permiso(VENTANA, 'ver')
def getOpcionesFiltros():
    try:
        datos = AuditoriaConsultaDao().get_opciones_filtros()
        datos['acciones'] = [{'valor': a, 'etiqueta': etiqueta_accion(a)} for a in ACCIONES]
        return jsonify({'success': True, 'data': datos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener las opciones de filtro de auditoría: {str(e)}")
        return error_interno()


@auditoriacambiosapi.route('/auditoria-cambios/alertas', methods=['GET'])
@require_permiso(VENTANA, 'ver')
def getAlertas():
    try:
        return jsonify({'success': True, 'data': AuditoriaConsultaDao().get_alertas(), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener las alertas de auditoría: {str(e)}")
        return error_interno()


@auditoriacambiosapi.route('/auditoria-cambios/exportar', methods=['GET'])
@require_permiso(VENTANA, 'ver')
def exportarAuditoriaCambios():
    """PDF o CSV con los filtros aplicados (hasta TOPE_EXPORTACION filas). Cada exportación queda auditada."""
    formato = (request.args.get('formato') or '').strip().lower()
    if formato not in FORMATOS:
        return respuesta_error('El formato debe ser pdf o csv.', 400)
    filtros, error = leer_filtros(request.args)
    if error:
        return respuesta_error(error, 400)
    try:
        dao = AuditoriaConsultaDao()
        filas, total, recortado = dao.listar_para_exportar(filtros, TOPE_EXPORTACION)
        etiquetas = etiquetas_filtros(filtros, dao)
        datos = informes.datos_auditoria_cambios(filas, etiquetas, dao.get_empresa(), _nombre_emisor(),
                                                 total, recortado, TOPE_EXPORTACION)
        respuesta = respuesta_archivo(datos, formato, 'auditoria_cambios')
        auditar('auditoria_cambios', 0, 'EXPORTACION',
                f"{formato.upper()}; {len(filas)} filas" + (f" de {total} (recortado al tope)" if recortado else '')
                + '; Filtros: ' + ('; '.join(f'{k}: {v}' for k, v in etiquetas) or 'ninguno'))
        return respuesta
    except Exception as e:
        app.logger.error(f"Error al exportar la auditoría de cambios: {str(e)}")
        return error_interno()


@auditoriacambiosapi.route('/auditoria-cambios/<int:id_auditoria>', methods=['GET'])
@require_permiso(VENTANA, 'ver')
def getAuditoriaCambio(id_auditoria):
    """Detalle de un registro: filas campo / valor anterior / valor nuevo (del JSON, o del texto en las filas viejas)."""
    try:
        fila = AuditoriaConsultaDao().get_by_id(id_auditoria)
        if fila is None:
            return respuesta_error('No se encontró el registro de auditoría.', 404)
        filas, mostrar_texto = filas_detalle(fila)
        fila['accion_etiqueta'] = etiqueta_accion(fila['accion'])
        fila['campos'] = filas
        fila['mostrar_texto'] = mostrar_texto
        fila.pop('valores_anteriores', None)
        fila.pop('valores_nuevos', None)
        return jsonify({'success': True, 'data': fila, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener el registro de auditoría: {str(e)}")
        return error_interno()
