from flask import Blueprint, render_template

avisos_bp = Blueprint('avisos_bp', __name__, 
                     template_folder='templates')  # ✅ Agregar esto

@avisos_bp.route('/avisos-recordatorios')
def avisos_recordatorios():
    return render_template('AvisosRecordatorios-index.html')