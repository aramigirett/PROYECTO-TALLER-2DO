from datetime import date

from flask import Blueprint, Response, request, jsonify, session, current_app as app

from app.dao.modulo_informes.InformesDao import InformesDao
from app.Services import informes_export_service as exportacion
from app.rutas.modulo_facturacion.utils import auditar, error_interno, respuesta_error
from app.rutas.modulo_seguridad.decorators import require_admin

informesapi = Blueprint('informesapi', __name__)

# pestaña -> (método del DAO, título, filtros que aplican). Resumen no se exporta.
PESTANAS = {
    'resumen': ('resumen', 'Resumen', ('medico',)),
    'agendamiento': ('agendamiento', 'Agendamiento', ('medico',)),
    'consultorio': ('consultorio', 'Consultorio', ('medico',)),
    'facturacion': ('facturacion', 'Facturación', ('condicion',)),
    'auditoria': ('auditoria', 'Auditoría', ()),
}
CONDICIONES = ('CONTADO', 'CREDITO')


def _dmy(d):
    return d.strftime('%d/%m/%Y')


def leer_filtros(args, pestana):
    """(filtros, None, None) o (None, mensaje 400, campo). Desde / Hasta por defecto: el día 1 del mes actual y hoy. Médico y Condición solo si la pestaña los usa."""
    hoy = date.today()
    try:
        desde = date.fromisoformat(args.get('desde')) if (args.get('desde') or '').strip() else hoy.replace(day=1)
        hasta = date.fromisoformat(args.get('hasta')) if (args.get('hasta') or '').strip() else hoy
    except ValueError:
        return None, 'Las fechas deben tener el formato AAAA-MM-DD.', 'desde'
    if desde > hasta:
        return None, 'La fecha "desde" no puede ser posterior a "hasta".', 'desde'
    aplican = PESTANAS[pestana][2]
    id_medico = None
    if 'medico' in aplican and (args.get('id_medico') or '').strip():
        valor = args['id_medico'].strip()
        if not valor.isdigit() or int(valor) > 2147483647:
            return None, 'El médico indicado no es válido.', 'id_medico'
        id_medico = int(valor)
    condicion = None
    if 'condicion' in aplican and (args.get('condicion') or '').strip():
        condicion = args['condicion'].strip().upper()
        if condicion not in CONDICIONES:
            return None, 'La condición debe ser contado o crédito.', 'condicion'
    return {'desde': desde, 'hasta': hasta, 'id_medico': id_medico, 'condicion': condicion}, None, None


def etiquetas_filtros(filtros, dao=None):
    """Filtros aplicados en texto legible (auditoría y exportaciones)."""
    r = [('Período', f"{_dmy(filtros['desde'])} al {_dmy(filtros['hasta'])}")]
    if filtros['id_medico']:
        nombre = (dao or InformesDao()).get_nombre_medico(filtros['id_medico'])
        r.append(('Médico', nombre or f"N.º {filtros['id_medico']}"))
    if filtros['condicion']:
        r.append(('Condición', filtros['condicion'].capitalize()))
    return r


def texto_filtros(etiquetas):
    return '; '.join(f'{k}: {v}' for k, v in etiquetas)


@informesapi.route('/informes/medicos', methods=['GET'])
@require_admin
def getMedicos():
    try:
        return jsonify({'success': True, 'data': InformesDao().get_medicos(), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al listar médicos para Informes: {str(e)}")
        return error_interno()


@informesapi.route('/informes/<pestana>', methods=['GET'])
@require_admin
def getInforme(pestana):
    """Datos de una pestaña (kpis, gráficos y tablas). Cada carga queda auditada con el informe y los filtros."""
    if pestana not in PESTANAS:
        return respuesta_error('El informe indicado no existe.', 404)
    filtros, error, campo = leer_filtros(request.args, pestana)
    if error:
        return respuesta_error(error, 400, campo)
    try:
        dao = InformesDao()
        datos = getattr(dao, PESTANAS[pestana][0])(filtros)
        auditar('informes', 0, 'CONSULTA', f"Informe: {PESTANAS[pestana][1]}; " + texto_filtros(etiquetas_filtros(filtros, dao)))
        return jsonify({'success': True, 'data': datos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al generar el informe {pestana}: {str(e)}")
        return error_interno()


FORMATOS = {
    'pdf': ('application/pdf', 'inline', 'pdf'),
    'xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'attachment', 'xlsx'),
}


def _nombre_emisor():
    return session.get('nombre_completo') or session.get('ci_ruc') or 'Usuario'


@informesapi.route('/informes/<pestana>/exportar', methods=['GET'])
@require_admin
def exportarInforme(pestana):
    """PDF o Excel de una pestaña con los filtros aplicados (el Resumen no se exporta). Cada exportación queda auditada con el informe y los filtros."""
    if pestana not in PESTANAS:
        return respuesta_error('El informe indicado no existe.', 404)
    if pestana == 'resumen':
        return respuesta_error('El Resumen no se exporta.', 400)
    formato = (request.args.get('formato') or '').strip().lower()
    if formato not in FORMATOS:
        return respuesta_error('El formato debe ser pdf o xlsx.', 400)
    filtros, error, campo = leer_filtros(request.args, pestana)
    if error:
        return respuesta_error(error, 400, campo)
    try:
        dao = InformesDao()
        titulo = PESTANAS[pestana][1]
        etiquetas = etiquetas_filtros(filtros, dao)
        datos = getattr(dao, PESTANAS[pestana][0])(filtros)
        armado = exportacion.calcular_datos_exportacion(titulo, dao.get_empresa(), etiquetas, datos, _nombre_emisor())
        contenido = (exportacion.generarInformePdf(armado) if formato == 'pdf' else exportacion.generarInformeExcel(armado))
        mimetype, disposicion, extension = FORMATOS[formato]
        auditar('informes', 0, 'EXPORTACION', f"{formato.upper()}; Informe: {titulo}; {texto_filtros(etiquetas)}; {exportacion.total_filas(datos)} filas")
        return Response(contenido, mimetype=mimetype,
                        headers={'Content-Disposition': f'{disposicion}; filename=informe_{pestana}_{date.today().strftime("%Y%m%d")}.{extension}'})
    except Exception as e:
        app.logger.error(f"Error al exportar el informe {pestana}: {str(e)}")
        return error_interno()
