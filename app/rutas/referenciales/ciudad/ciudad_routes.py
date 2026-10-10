from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

ciumod = Blueprint('ciudad', __name__, template_folder='templates')

@ciumod.route('/ciudad-index')
@require_permiso('ciudad', 'ver')
def ciudadIndex():
    return render_template('ciudad-index.html')