from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

sesiontratamientomod = Blueprint('sesiontratamiento', __name__, template_folder='templates')

@sesiontratamientomod.route('/sesion-tratamiento-index')
@require_permiso('sesiontratamiento', 'ver')
def sesionTratamientoIndex():
    return render_template('sesion-tratamiento-index.html')
