from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

cuentabancariamod = Blueprint('cuentabancaria', __name__, template_folder='templates')

@cuentabancariamod.route('/cuenta-bancaria-index')
@require_permiso('cuentabancaria', 'ver')
def cuentaBancariaIndex():
    return render_template('cuenta-bancaria-index.html')
