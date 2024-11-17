from flask import Blueprint, render_template, jsonify
from app.dao.referenciales.diagnostico.DiagnosticoDao import DiagnosticoDao

diagmod = Blueprint('diagnostico', __name__, template_folder='templates')

@diagmod.route('/diagnostico-index')
def diagnosticoIndex():
    diagdao = DiagnosticoDao()
    return render_template('diagnostico-index.html')