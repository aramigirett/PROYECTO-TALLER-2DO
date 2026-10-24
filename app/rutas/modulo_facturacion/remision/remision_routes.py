from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

remisionmod = Blueprint('remision', __name__, template_folder='templates')

@remisionmod.route('/remision-index')
@require_permiso('remision', 'ver')
def remisionIndex():
    return render_template('remision-index.html')
