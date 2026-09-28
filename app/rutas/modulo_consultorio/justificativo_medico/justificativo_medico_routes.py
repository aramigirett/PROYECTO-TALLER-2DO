from flask import Blueprint, render_template

justificativomedicomod = Blueprint('justificativomedico', __name__, template_folder='templates')

@justificativomedicomod.route('/justificativo-medico-index')
def justificativoMedicoIndex():
    return render_template('justificativo-medico-index.html')
