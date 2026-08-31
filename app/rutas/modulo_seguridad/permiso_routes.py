from flask import Blueprint, render_template

from app.rutas.modulo_seguridad.decorators import require_admin

permisomod = Blueprint('permiso', __name__, template_folder='templates')


@permisomod.route('/permiso-index')
@require_admin
def permisoIndex():
    return render_template('permiso-index.html')
