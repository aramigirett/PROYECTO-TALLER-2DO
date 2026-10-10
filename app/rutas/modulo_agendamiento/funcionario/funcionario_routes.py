from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

funcionariomod = Blueprint('funcionario', __name__, template_folder='templates')

@funcionariomod.route('/funcionario-index')
@require_permiso('funcionario', 'ver')
def funcionarioIndex():
    return render_template('funcionario-index.html')