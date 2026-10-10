from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

avisos_bp = Blueprint('avisos_bp', __name__, 
                     template_folder='templates')  # ✅ Agregar esto

@avisos_bp.route('/avisos-recordatorios')
@require_permiso('avisos', 'ver')
def avisos_recordatorios():
    return render_template('AvisosRecordatorios-index.html')