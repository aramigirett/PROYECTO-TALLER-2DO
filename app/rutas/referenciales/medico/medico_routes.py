from flask import Blueprint,render_template

medicomod = Blueprint('medico', __name__, template_folder='templates')

@medicomod.route('/medico-index')
def medicoIndex():
    return render_template('medico-index.html')