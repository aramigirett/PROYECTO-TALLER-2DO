from flask import Blueprint, render_template

tipodiagnosticomod = Blueprint('tipodiagnostico', __name__, template_folder='templates')

@tipodiagnosticomod.route('/tipo-diagnostico-index')
def tipoDiagnosticoIndex():
    return render_template('tipo-diagnostico-index.html')