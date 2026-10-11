from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

formacobromod = Blueprint('formacobro', __name__, template_folder='templates')

@formacobromod.route('/forma-cobro-index')
@require_permiso('formacobro', 'ver')
def formaCobroIndex():
    return render_template('forma-cobro-index.html')
