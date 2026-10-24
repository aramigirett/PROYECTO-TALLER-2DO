from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

clientemod = Blueprint('cliente', __name__, template_folder='templates')

@clientemod.route('/cliente-index')
@require_permiso('cliente', 'ver')
def clienteIndex():
    return render_template('cliente-index.html')
