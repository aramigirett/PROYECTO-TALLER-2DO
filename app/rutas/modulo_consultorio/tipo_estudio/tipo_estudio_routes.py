from flask import Blueprint, render_template

tipoestudiomod = Blueprint('tipoestudio', __name__, template_folder='templates')

@tipoestudiomod.route('/tipo-estudio-index')
def tipoEstudioIndex():
    return render_template('tipo-estudio-index.html')
