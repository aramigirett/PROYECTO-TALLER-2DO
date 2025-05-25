from flask import Blueprint, render_template

persona_mod = Blueprint('persona', __name__, template_folder='templates')

@persona_mod.route('/persona-index')
def personaIndex():
    return render_template('persona-index.html')


