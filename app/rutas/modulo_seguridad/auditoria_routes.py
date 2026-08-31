from flask import Blueprint, render_template

from app.rutas.modulo_seguridad.decorators import require_admin

auditoriamod = Blueprint('auditoria', __name__, template_folder='templates')


@auditoriamod.route('/auditoria-index')
@require_admin
def auditoriaIndex():
    return render_template('auditoria-index.html')
