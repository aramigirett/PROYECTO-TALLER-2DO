from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

consulmod = Blueprint('consultorio', __name__, template_folder='templates')

@consulmod.route('/consultorio-index')
@require_permiso('consultorio', 'ver')
def consultorioIndex():
    return render_template('consultorio-index.html')