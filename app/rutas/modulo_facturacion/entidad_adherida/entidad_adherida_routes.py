from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

entidadadheridamod = Blueprint('entidadadherida', __name__, template_folder='templates')

@entidadadheridamod.route('/entidad-adherida-index')
@require_permiso('entidadadherida', 'ver')
def entidadAdheridaIndex():
    return render_template('entidad-adherida-index.html')
