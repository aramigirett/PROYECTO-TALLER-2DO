from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

diagnosticos_medicos_mod = Blueprint('diagnostico_medico', __name__, template_folder='templates')

@diagnosticos_medicos_mod.route('/diagnostico-index')
@require_permiso('diagnostico', 'ver')
def diagnosticoIndex():
    return render_template('diagnosticos-medicos-index.html')