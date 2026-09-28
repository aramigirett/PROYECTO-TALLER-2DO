from flask import Blueprint, render_template

ordenestudiomod = Blueprint('ordenestudio', __name__, template_folder='templates')

@ordenestudiomod.route('/orden-estudio-index')
def ordenEstudioIndex():
    return render_template('orden-estudio-index.html')
