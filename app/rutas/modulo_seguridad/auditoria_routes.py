from flask import Blueprint, render_template

from app.rutas.modulo_seguridad.decorators import require_permiso

auditoriamod = Blueprint('auditoria', __name__, template_folder='templates')


@auditoriamod.route('/auditoria-index')
@require_permiso('auditoria', 'ver')
def auditoriaIndex():
    return render_template('auditoria-index.html')
