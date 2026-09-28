from flask import Blueprint, render_template

ordenanalisismod = Blueprint('ordenanalisis', __name__, template_folder='templates')

@ordenanalisismod.route('/orden-analisis-index')
def ordenAnalisisIndex():
    return render_template('orden-analisis-index.html')
