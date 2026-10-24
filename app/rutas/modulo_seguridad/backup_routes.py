from flask import Blueprint, render_template

from app.rutas.modulo_seguridad.decorators import require_permiso

backupmod = Blueprint('backup', __name__, template_folder='templates')


@backupmod.route('/backup-index')
@require_permiso('backup', 'ver')
def backupIndex():
    return render_template('backup-index.html')
