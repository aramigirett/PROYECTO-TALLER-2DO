from flask import Blueprint, jsonify, current_app as app

from app.Services import backup_service
from app.Services.backup_service import BackupError
from app.rutas.modulo_facturacion.utils import auditar, error_interno
from app.rutas.modulo_seguridad.decorators import require_permiso

backupapi = Blueprint('backupapi', __name__)


@backupapi.route('/backups', methods=['GET'])
@require_permiso('backup', 'ver')
def getBackups():
    """Copias existentes (la más reciente primero). Solo lista: la restauración NO se hace desde la web."""
    try:
        copias = [{'nombre': c['nombre'], 'tamano': c['tamano'],
                   'tamano_texto': backup_service.formatear_tamano(c['tamano']),
                   'fecha': c['fecha'].strftime('%Y-%m-%d %H:%M:%S')}
                  for c in backup_service.listar_backups()]
        return jsonify({'success': True, 'data': copias, 'retencion': backup_service.RETENCION, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al listar las copias de seguridad: {str(e)}")
        return error_interno()


@backupapi.route('/backups', methods=['POST'])
@require_permiso('backup', 'nuevo')
def generarBackup():
    """Genera una copia ahora. El usuario y la IP de la auditoría salen de la sesión y del request."""
    try:
        r = backup_service.generar_backup()
    except BackupError as e:
        app.logger.error(f"Error al generar la copia de seguridad: {str(e)}")
        # El detalle (ya sin contraseñas) queda en backup.log y en el log de la app, no en la respuesta
        return jsonify({'success': False, 'error': 'No se pudo generar la copia de seguridad. Revisá backup.log.'}), 500
    except Exception as e:
        app.logger.error(f"Error inesperado al generar la copia de seguridad: {str(e)}")
        return error_interno()

    detalle = f"Copia {r['archivo']} ({backup_service.formatear_tamano(r['tamano'])})"
    if r['borradas']:
        detalle += f"; retención: se borraron {len(r['borradas'])}"
    auditar('backup', 0, 'ALTA', detalle)
    return jsonify({'success': True, 'mensaje': f"Copia generada: {r['archivo']} "
                                                f"({backup_service.formatear_tamano(r['tamano'])}).",
                    'archivo': r['archivo'], 'error': None}), 201
