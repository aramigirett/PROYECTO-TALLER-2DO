from flask import Blueprint, render_template

tipoanalisismod = Blueprint('tipoanalisis', __name__, template_folder='templates')

@tipoanalisismod.route('/tipo-analisis-index')
def tipoAnalisisIndex():
    return render_template('tipo-analisis-index.html')
