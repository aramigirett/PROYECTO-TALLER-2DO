from flask import Blueprint, render_template

from app.rutas.modulo_seguridad.decorators import require_permiso

menumod = Blueprint('menu', __name__, template_folder='templates')


@menumod.route('/menu-index')
@require_permiso('menu', 'ver')
def menuIndex():
    return render_template('menu-index.html')
