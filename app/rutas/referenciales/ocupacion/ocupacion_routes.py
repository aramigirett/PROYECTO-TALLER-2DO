from flask import Blueprint, render_template

ocupmod = Blueprint('ocupacion', __name__, template_folder='templates')

@ocupmod.route('/ocupacion-index')
def ocupacionIndex():
    return render_template('ocupacion-index.html')