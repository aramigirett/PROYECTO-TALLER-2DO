from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

cajamod = Blueprint('caja', __name__, template_folder='templates')

@cajamod.route('/caja-index')
@require_permiso('caja', 'ver')
def cajaIndex():
    return render_template('caja-index.html')
