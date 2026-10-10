from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

tratamientomod = Blueprint('tratamiento', __name__, template_folder='templates')

@tratamientomod.route('/tratamiento-index')
@require_permiso('tratamiento', 'ver')
def tratamientoIndex():
    return render_template('tratamiento-index.html')
