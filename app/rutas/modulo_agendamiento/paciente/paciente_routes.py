from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

pacientemod = Blueprint('paciente', __name__, template_folder='templates')

@pacientemod.route('/paciente-index')
@require_permiso('paciente', 'ver')
def pacienteIndex():
    return render_template('paciente-index.html')