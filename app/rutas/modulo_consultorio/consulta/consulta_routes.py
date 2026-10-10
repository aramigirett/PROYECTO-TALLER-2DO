from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

consultamod = Blueprint('consulta', __name__, template_folder='templates')


@consultamod.route('/consulta-index')
@require_permiso('consulta', 'ver')
def consultaIndex():
    return render_template('consulta-index.html')