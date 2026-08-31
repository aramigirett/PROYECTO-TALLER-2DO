from flask import Blueprint, render_template

from app.rutas.modulo_seguridad.decorators import require_admin

usuariomod = Blueprint('usuario', __name__, template_folder='templates')


@usuariomod.route('/usuario-index')
@require_admin
def usuarioIndex():
    return render_template('usuario-index.html')
