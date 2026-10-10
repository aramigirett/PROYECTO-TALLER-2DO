from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

ordenanalisismod = Blueprint('ordenanalisis', __name__, template_folder='templates')

@ordenanalisismod.route('/orden-analisis-index')
@require_permiso('ordenanalisis', 'ver')
def ordenAnalisisIndex():
    return render_template('orden-analisis-index.html')
