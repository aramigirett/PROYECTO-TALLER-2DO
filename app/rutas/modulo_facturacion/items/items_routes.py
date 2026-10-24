from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

itemmod = Blueprint('item', __name__, template_folder='templates')

@itemmod.route('/item-index')
@require_permiso('item', 'ver')
def itemIndex():
    return render_template('item-index.html')
