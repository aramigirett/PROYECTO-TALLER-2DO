from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

odontogramamod = Blueprint('odontograma', __name__, template_folder='templates')


@odontogramamod.route('/odontograma-index')
@require_permiso('odontograma', 'ver')
def odontogramaIndex():
    return render_template('odontograma-index.html')