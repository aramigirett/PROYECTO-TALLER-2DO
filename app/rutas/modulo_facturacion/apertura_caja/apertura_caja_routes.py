from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

aperturacajamod = Blueprint('aperturacaja', __name__, template_folder='templates')

@aperturacajamod.route('/apertura-caja-index')
@require_permiso('aperturacaja', 'ver')
def aperturaCajaIndex():
    return render_template('apertura-caja-index.html')
