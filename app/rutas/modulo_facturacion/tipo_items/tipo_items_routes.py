from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

tipoitemmod = Blueprint('tipoitem', __name__, template_folder='templates')

@tipoitemmod.route('/tipo-item-index')
@require_permiso('tipoitem', 'ver')
def tipoItemIndex():
    return render_template('tipo-item-index.html')
