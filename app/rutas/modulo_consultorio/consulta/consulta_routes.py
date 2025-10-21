from flask import Blueprint, render_template

consultamod = Blueprint('consulta', __name__, template_folder='templates')


@consultamod.route('/consulta-index')
def consultaIndex():
    return render_template('consulta-index.html')