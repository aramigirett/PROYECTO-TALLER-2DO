from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

ventamod = Blueprint('venta', __name__, template_folder='templates')

@ventamod.route('/venta-index')
@require_permiso('venta', 'ver')
def ventaIndex():
    return render_template('venta-index.html')
