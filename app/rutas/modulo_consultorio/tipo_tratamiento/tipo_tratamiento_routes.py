from flask import Blueprint, render_template

tipotratamientomod = Blueprint('tipotratamiento', __name__, template_folder='templates')

@tipotratamientomod.route('/tipo-tratamiento-index')
def tipoTratamientoIndex():
    return render_template('tipo-tratamiento-index.html')
