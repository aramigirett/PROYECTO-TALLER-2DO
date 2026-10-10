from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

# SIN template_folder - usa la carpeta global
agenda_bp = Blueprint('agenda_bp', __name__)

@agenda_bp.route('/agenda')
@require_permiso('agenda', 'ver')
def index():
    # Busca en app/templates/agenda/index.html
    return render_template('agenda/index.html')