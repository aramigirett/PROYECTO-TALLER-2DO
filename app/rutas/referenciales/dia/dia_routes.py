from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

diamod = Blueprint('dia', __name__, template_folder='templates')

@diamod.route('/dia-index')
@require_permiso('dia', 'ver')
def diaIndex():
    return render_template('dia-index.html')