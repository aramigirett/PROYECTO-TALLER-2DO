import re
from datetime import date

from flask import Blueprint, request, jsonify, current_app as app

from app.dao.modulo_seguridad.AuditoriaConsultaDao import AuditoriaConsultaDao, TOPE_EXPORTACION
from app.dao.modulo_seguridad.AuditoriaDao import AuditoriaDao
from app.Services import auditoria_pdf_service as informes
from app.rutas.modulo_facturacion.utils import auditar, error_interno, respuesta_error
from app.rutas.modulo_seguridad.auditoria_cambios_api import FORMATOS, respuesta_archivo
from app.rutas.modulo_seguridad.auditoria_cambios_api import _nombre_emisor as nombre_emisor
from app.rutas.modulo_seguridad.decorators import require_permiso

auditoriaapi = Blueprint('auditoriaapi', __name__)

_FORMATO_RESULTADO = re.compile(r'^[A-Z0-9_]{1,30}$')


def _parse_fecha(valor):
    """date desde 'YYYY-MM-DD'; None si viene vacío; ValueError si el formato es inválido."""
    valor = (valor or '').strip()
    return date.fromisoformat(valor) if valor else None


@auditoriaapi.route('/auditoria/intentos', methods=['GET'])
@require_permiso('auditoria', 'ver')
def getUltimosIntentos():
    limite = request.args.get('limite', default=200, type=int)
    limite = max(1, min(limite, 1000))

    try:
        desde = _parse_fecha(request.args.get('desde'))
        hasta = _parse_fecha(request.args.get('hasta'))
    except ValueError:
        return respuesta_error('Las fechas deben tener el formato AAAA-MM-DD.', 400, 'desde')

    if desde and hasta and desde > hasta:
        return respuesta_error('La fecha "desde" no puede ser posterior a "hasta".', 400, 'desde')

    # Filtro por resultado (p. ej. IP_NO_PERMITIDA, IP_SIN_GEOLOCALIZAR, CIERRE_INACTIVIDAD); valor exacto
    resultado = (request.args.get('resultado') or '').strip().upper() or None
    if resultado and not _FORMATO_RESULTADO.match(resultado):
        return respuesta_error('El resultado indicado no es válido.', 400, 'resultado')

    try:
        intentos = AuditoriaDao().get_ultimos_intentos(limite, desde, hasta, resultado)
        return jsonify({'success': True, 'data': intentos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener intentos de acceso: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


@auditoriaapi.route('/auditoria/intentos/exportar', methods=['GET'])
@require_permiso('auditoria', 'ver')
def exportarIntentos():
    """PDF o CSV de los intentos de acceso con el filtro de fechas / resultado aplicado (hasta TOPE_EXPORTACION).
    Cada exportación queda auditada en auditoria_cambios."""
    formato = (request.args.get('formato') or '').strip().lower()
    if formato not in FORMATOS:
        return respuesta_error('El formato debe ser pdf o csv.', 400)
    try:
        desde, hasta = _parse_fecha(request.args.get('desde')), _parse_fecha(request.args.get('hasta'))
    except ValueError:
        return respuesta_error('Las fechas deben tener el formato AAAA-MM-DD.', 400)
    if desde and hasta and desde > hasta:
        return respuesta_error('La fecha "desde" no puede ser posterior a "hasta".', 400)
    resultado = (request.args.get('resultado') or '').strip().upper() or None
    if resultado and not _FORMATO_RESULTADO.match(resultado):
        return respuesta_error('El resultado indicado no es válido.', 400)

    try:
        dao = AuditoriaDao()
        total = dao.contar_intentos(desde, hasta, resultado)
        intentos = dao.get_ultimos_intentos(TOPE_EXPORTACION, desde, hasta, resultado)
        recortado = total > TOPE_EXPORTACION
        etiquetas = []
        if desde or hasta:
            etiquetas.append(('Período', f"{desde.strftime('%d/%m/%Y') if desde else 'inicio'} al "
                                         f"{hasta.strftime('%d/%m/%Y') if hasta else 'hoy'}"))
        if resultado:
            etiquetas.append(('Resultado', resultado))
        datos = informes.datos_auditoria_accesos(intentos, etiquetas, AuditoriaConsultaDao().get_empresa(), nombre_emisor(),
                                                 total, recortado, TOPE_EXPORTACION)
        respuesta = respuesta_archivo(datos, formato, 'tablero_accesos')
        auditar('auditoria_acceso', 0, 'EXPORTACION',
                f"{formato.upper()}; {len(intentos)} intentos" + (f" de {total} (recortado al tope)" if recortado else '')
                + '; Filtros: ' + ('; '.join(f'{k}: {v}' for k, v in etiquetas) or 'ninguno'))
        return respuesta
    except Exception as e:
        app.logger.error(f"Error al exportar los intentos de acceso: {str(e)}")
        return error_interno()
