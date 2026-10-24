import re
from datetime import date

from flask import Blueprint, request, jsonify, current_app as app

from app.dao.modulo_seguridad.AuditoriaDao import AuditoriaDao
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
        return jsonify({'success': False, 'error': 'Las fechas deben tener el formato AAAA-MM-DD.'}), 400

    if desde and hasta and desde > hasta:
        return jsonify({'success': False, 'error': 'La fecha "desde" no puede ser posterior a "hasta".'}), 400

    # Filtro por resultado (p. ej. IP_NO_PERMITIDA, IP_SIN_GEOLOCALIZAR, CIERRE_INACTIVIDAD); valor exacto
    resultado = (request.args.get('resultado') or '').strip().upper() or None
    if resultado and not _FORMATO_RESULTADO.match(resultado):
        return jsonify({'success': False, 'error': 'El resultado indicado no es válido.'}), 400

    try:
        intentos = AuditoriaDao().get_ultimos_intentos(limite, desde, hasta, resultado)
        return jsonify({'success': True, 'data': intentos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener intentos de acceso: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
