from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

sintomod = Blueprint('sintoma', __name__, template_folder='templates')

@sintomod.route('/sintoma-index')
@require_permiso('sintoma', 'ver')
def sintomaIndex():
    return render_template('sintoma-index.html')