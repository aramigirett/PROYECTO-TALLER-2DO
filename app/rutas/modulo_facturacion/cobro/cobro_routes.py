from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

cobromod = Blueprint('cobro', __name__, template_folder='templates')

@cobromod.route('/cobro-index')
@require_permiso('cobro', 'ver')
def cobroIndex():
    return render_template('cobro-index.html')
