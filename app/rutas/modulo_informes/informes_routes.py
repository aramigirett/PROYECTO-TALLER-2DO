from flask import Blueprint, render_template, current_app as app

from app.rutas.modulo_facturacion.utils import auditar
from app.rutas.modulo_seguridad.decorators import require_admin

informesmod = Blueprint('informes', __name__, template_folder='templates')


@informesmod.route('/informes')
@require_admin
def informesIndex():
    """Única pantalla de Informes (solo Administrador). Cada visita queda auditada (acción CONSULTA)."""
    try:
        auditar('informes', 0, 'CONSULTA', 'Visita a la pantalla de Informes')
    except Exception as e:
        app.logger.error(f"No se pudo auditar la visita a Informes: {str(e)}")
    return render_template('informes-index.html')
