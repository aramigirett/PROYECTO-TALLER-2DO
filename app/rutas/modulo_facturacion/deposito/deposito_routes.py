from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

depositomod = Blueprint('deposito', __name__, template_folder='templates')

@depositomod.route('/deposito-index')
@require_permiso('deposito', 'ver')
def depositoIndex():
    return render_template('deposito-index.html')
