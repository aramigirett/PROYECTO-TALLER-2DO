from flask import Blueprint, render_template

estacivmod = Blueprint('estadocivil', __name__, template_folder='templates')

@estacivmod.route('/estadocivil-index')
def estadocivilIndex():
    return render_template('estadocivil-index.html')