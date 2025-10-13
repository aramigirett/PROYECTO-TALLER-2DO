from flask import Blueprint, render_template

cargomod = Blueprint('cargo', __name__, template_folder='templates')

@cargomod.route('/cargo-index')
def cargoIndex():
    return render_template('cargo-index.html')