from flask import Blueprint, render_template

sintomod = Blueprint('sintoma', __name__, template_folder='templates')

@sintomod.route('/sintoma-index')
def sintomaIndex():
    return render_template('sintoma-index.html')