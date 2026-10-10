from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

justificativomedicomod = Blueprint('justificativomedico', __name__, template_folder='templates')

@justificativomedicomod.route('/justificativo-medico-index')
@require_permiso('justificativomedico', 'ver')
def justificativoMedicoIndex():
    return render_template('justificativo-medico-index.html')
