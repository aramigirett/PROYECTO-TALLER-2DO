from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

tipoestudiomod = Blueprint('tipoestudio', __name__, template_folder='templates')

@tipoestudiomod.route('/tipo-estudio-index')
@require_permiso('tipoestudio', 'ver')
def tipoEstudioIndex():
    return render_template('tipo-estudio-index.html')
