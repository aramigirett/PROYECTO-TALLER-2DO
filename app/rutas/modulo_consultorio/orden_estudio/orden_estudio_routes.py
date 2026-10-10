from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

ordenestudiomod = Blueprint('ordenestudio', __name__, template_folder='templates')

@ordenestudiomod.route('/orden-estudio-index')
@require_permiso('ordenestudio', 'ver')
def ordenEstudioIndex():
    return render_template('orden-estudio-index.html')
