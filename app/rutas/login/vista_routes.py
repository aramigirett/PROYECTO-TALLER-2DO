from flask import Blueprint, render_template

vistamod = Blueprint('vista', __name__, template_folder='templates')

@vistamod.route('/vista-index')
def vistaIndex():
    return render_template('vista-index.html')