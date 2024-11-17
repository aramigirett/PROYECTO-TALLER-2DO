from flask import Blueprint, render_template

paimod = Blueprint('pais', __name__, template_folder='templates')

@paimod.route('/pais-index')
def paisIndex():
    return render_template('pais-index.html')