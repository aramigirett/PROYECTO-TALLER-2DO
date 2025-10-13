from flask import Blueprint, render_template

funcionariomod = Blueprint('funcionario', __name__, template_folder='templates')

@funcionariomod.route('/funcionario-index')
def funcionarioIndex():
    return render_template('funcionario-index.html')