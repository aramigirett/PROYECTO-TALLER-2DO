from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

tipotratamientomod = Blueprint('tipotratamiento', __name__, template_folder='templates')

@tipotratamientomod.route('/tipo-tratamiento-index')
@require_permiso('tipotratamiento', 'ver')
def tipoTratamientoIndex():
    return render_template('tipo-tratamiento-index.html')
