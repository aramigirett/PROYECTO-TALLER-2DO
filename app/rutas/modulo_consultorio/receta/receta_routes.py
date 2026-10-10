from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

recetamod = Blueprint('receta', __name__, template_folder='templates')

@recetamod.route('/receta-index')
@require_permiso('receta', 'ver')
def recetaIndex():
    return render_template('receta-index.html')
