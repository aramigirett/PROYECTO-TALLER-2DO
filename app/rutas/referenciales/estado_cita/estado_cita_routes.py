from flask import Blueprint, render_template

estacitmod = Blueprint('estadocita', __name__, template_folder='templates')

@estacitmod.route('/estadocita-index')
def estadocitaIndex():
    return render_template('estadocita-index.html')