from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

disponibilidadmod = Blueprint('disponibilidad', __name__, template_folder='templates')

@disponibilidadmod.route('/disponibilidad-index')
@require_permiso('disponibilidad', 'ver')
def disponibilidadIndex():
    return render_template('disponibilidad-index.html')