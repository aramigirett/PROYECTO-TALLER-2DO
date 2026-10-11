from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

entidademisoramod = Blueprint('entidademisora', __name__, template_folder='templates')

@entidademisoramod.route('/entidad-emisora-index')
@require_permiso('entidademisora', 'ver')
def entidadEmisoraIndex():
    return render_template('entidad-emisora-index.html')
