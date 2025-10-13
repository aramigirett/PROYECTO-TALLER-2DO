from flask import Blueprint, render_template

odontogramamod = Blueprint('odontograma', __name__, template_folder='templates')


@odontogramamod.route('/odontograma-index')
def odontogramaIndex():
    return render_template('odontograma-index.html')