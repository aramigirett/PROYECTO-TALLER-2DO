from flask import Blueprint, render_template

especimod = Blueprint('especialidad', __name__, template_folder='templates')

@especimod.route('/especialidad-index')
def especialidadIndex():
    return render_template('especialidad-index.html')