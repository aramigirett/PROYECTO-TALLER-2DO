from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

arqueomod = Blueprint('arqueo', __name__, template_folder='templates')

@arqueomod.route('/arqueo-index')
@require_permiso('arqueo', 'ver')
def arqueoIndex():
    return render_template('arqueo-index.html')
