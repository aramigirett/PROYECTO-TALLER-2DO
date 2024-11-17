from flask import Blueprint, render_template

naciomod = Blueprint('nacionalidad', __name__, template_folder='templates')

@naciomod.route('/nacionalidad-index')
def nacionalidadIndex():
    return render_template('nacionalidad-index.html')