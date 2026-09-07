from flask import Blueprint, render_template

tipoinsumomod = Blueprint('tipoinsumo', __name__, template_folder='templates')

@tipoinsumomod.route('/tipo-insumo-index')
def tipoInsumoIndex():
    return render_template('tipo-insumo-index.html')
