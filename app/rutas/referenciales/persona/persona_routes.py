from flask import Blueprint, render_template

persmod = Blueprint('persona', __name__, template_folder='templates')

@persmod.route('/persona-index')
def personaIndex():
    return render_template('persona-index.html')