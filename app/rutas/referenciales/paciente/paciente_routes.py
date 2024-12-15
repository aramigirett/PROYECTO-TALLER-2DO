from flask import Blueprint,render_template

pacientemod = Blueprint('paciente', __name__, template_folder='templates')

@pacientemod.route('/paciente-index')
def pacienteIndex():
    return render_template('paciente-index.html')