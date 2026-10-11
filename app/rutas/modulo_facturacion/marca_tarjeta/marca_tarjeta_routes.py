from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

marcatarjetamod = Blueprint('marcatarjeta', __name__, template_folder='templates')

@marcatarjetamod.route('/marca-tarjeta-index')
@require_permiso('marcatarjeta', 'ver')
def marcaTarjetaIndex():
    return render_template('marca-tarjeta-index.html')
