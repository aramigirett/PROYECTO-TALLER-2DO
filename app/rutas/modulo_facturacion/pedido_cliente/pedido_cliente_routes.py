from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

pedidoclientemod = Blueprint('pedidocliente', __name__, template_folder='templates')

@pedidoclientemod.route('/pedido-cliente-index')
@require_permiso('pedidocliente', 'ver')
def pedidoClienteIndex():
    return render_template('pedido-cliente-index.html')
