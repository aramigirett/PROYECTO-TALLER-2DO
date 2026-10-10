from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

cargomod = Blueprint('cargo', __name__, template_folder='templates')

@cargomod.route('/cargo-index')
@require_permiso('cargo', 'ver')
def cargoIndex():
    return render_template('cargo-index.html')