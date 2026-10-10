from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

medicamentomod = Blueprint('medicamento', __name__, template_folder='templates')

@medicamentomod.route('/medicamento-index')
@require_permiso('medicamento', 'ver')
def medicamentoIndex():
    return render_template('medicamento-index.html')
