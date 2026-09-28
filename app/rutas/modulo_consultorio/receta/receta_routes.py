from flask import Blueprint, render_template

recetamod = Blueprint('receta', __name__, template_folder='templates')

@recetamod.route('/receta-index')
def recetaIndex():
    return render_template('receta-index.html')
