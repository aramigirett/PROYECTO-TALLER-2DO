from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

tipoinsumomod = Blueprint('tipoinsumo', __name__, template_folder='templates')

@tipoinsumomod.route('/tipo-insumo-index')
@require_permiso('tipoinsumo', 'ver')
def tipoInsumoIndex():
    return render_template('tipo-insumo-index.html')
