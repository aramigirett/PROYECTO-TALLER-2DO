from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

especimod = Blueprint('especialidad', __name__, template_folder='templates')

@especimod.route('/especialidad-index')
@require_permiso('especialidad', 'ver')
def especialidadIndex():
    return render_template('especialidad-index.html')