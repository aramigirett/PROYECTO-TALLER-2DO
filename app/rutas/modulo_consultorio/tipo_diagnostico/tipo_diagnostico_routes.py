from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

tipodiagnosticomod = Blueprint('tipodiagnostico', __name__, template_folder='templates')

@tipodiagnosticomod.route('/tipo-diagnostico-index')
@require_permiso('tipodiagnostico', 'ver')
def tipoDiagnosticoIndex():
    return render_template('tipo-diagnostico-index.html')