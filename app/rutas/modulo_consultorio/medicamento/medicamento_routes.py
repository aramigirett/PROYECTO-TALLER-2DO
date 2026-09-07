from flask import Blueprint, render_template

medicamentomod = Blueprint('medicamento', __name__, template_folder='templates')

@medicamentomod.route('/medicamento-index')
def medicamentoIndex():
    return render_template('medicamento-index.html')
