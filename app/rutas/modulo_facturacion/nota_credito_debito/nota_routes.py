from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

notacdmod = Blueprint('notacd', __name__, template_folder='templates')

@notacdmod.route('/nota-index')
@require_permiso('notacd', 'ver')
def notaIndex():
    return render_template('nota-index.html')
