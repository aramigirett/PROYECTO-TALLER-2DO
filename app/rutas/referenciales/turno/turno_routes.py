from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

turmod = Blueprint('turno', __name__, template_folder='templates')

@turmod.route('/turno-index')
@require_permiso('turno', 'ver')
def turnoIndex():
    return render_template('turno-index.html')
