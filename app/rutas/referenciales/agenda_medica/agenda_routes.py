from flask import Blueprint,render_template

agendamod = Blueprint('agenda', __name__, template_folder='templates')

@agendamod.route('/agenda-index')
def agendaIndex():
    return render_template('agenda-index.html')