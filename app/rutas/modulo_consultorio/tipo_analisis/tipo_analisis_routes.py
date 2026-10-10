from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

tipoanalisismod = Blueprint('tipoanalisis', __name__, template_folder='templates')

@tipoanalisismod.route('/tipo-analisis-index')
@require_permiso('tipoanalisis', 'ver')
def tipoAnalisisIndex():
    return render_template('tipo-analisis-index.html')
