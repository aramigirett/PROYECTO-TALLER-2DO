from flask import Blueprint, render_template

duraconsumod = Blueprint('duracionconsulta', __name__, template_folder='templates')

@duraconsumod.route('/duracionconsulta-index')
def duracionconsultaIndex():
    return render_template('duracionconsulta-index.html')