from flask import Blueprint, render_template

diagnosticos_medicos_mod = Blueprint('diagnostico_medico', __name__, template_folder='templates')

@diagnosticos_medicos_mod.route('/diagnostico-index')
def diagnosticoIndex():
    return render_template('diagnosticos-medicos-index.html')