from flask import Blueprint, render_template

from app.rutas.modulo_seguridad.decorators import require_permiso

auditoriacambiosmod = Blueprint('auditoriacambios', __name__, template_folder='templates')


@auditoriacambiosmod.route('/auditoria-cambios-index')
@require_permiso('auditoriacambios', 'ver')
def auditoriaCambiosIndex():
    return render_template('auditoria-cambios-index.html')
