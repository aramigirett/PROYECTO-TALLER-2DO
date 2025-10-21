from flask import Blueprint, render_template

diagnosticomod = Blueprint('diagnostico', __name__, template_folder='templates')

@diagnosticomod.route('/diagnostico-index')
def diagnosticoIndex():
    return render_template('diagnostico-index.html')