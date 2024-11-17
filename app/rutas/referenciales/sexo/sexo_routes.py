from flask import Blueprint, render_template

sexmod = Blueprint('sexo', __name__, template_folder='templates')

@sexmod.route('/sexo-index')
def sexoIndex():
    return render_template('sexo-index.html')