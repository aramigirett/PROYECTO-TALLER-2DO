from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

agenda_bp = Blueprint('agenda_bp', __name__, template_folder='templates')

@agenda_bp.route('/agenda')
@require_permiso('agenda', 'ver')
def index():
    return render_template('agenda-index.html')
