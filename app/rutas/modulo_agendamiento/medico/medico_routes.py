from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

medicomod = Blueprint('medico', __name__, template_folder='templates')


@medicomod.route('/medico-index')
@require_permiso('medico', 'ver')
def medicoIndex():
    return render_template('medico-index.html')