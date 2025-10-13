from flask import Blueprint, render_template

disponibilidadmod = Blueprint('disponibilidad', __name__, template_folder='templates')

@disponibilidadmod.route('/disponibilidad-index')
def disponibilidadIndex():
    return render_template('disponibilidad-index.html')