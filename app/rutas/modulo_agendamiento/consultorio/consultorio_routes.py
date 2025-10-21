from flask import Blueprint, render_template

consulmod = Blueprint('consultorio', __name__, template_folder='templates')

@consulmod.route('/consultorio-index')
def consultorioIndex():
    return render_template('consultorio-index.html')