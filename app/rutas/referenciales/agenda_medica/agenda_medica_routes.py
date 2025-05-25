from flask import Blueprint, render_template

agendamedmod = Blueprint('agenda_medica', __name__, template_folder='templates')

@agendamedmod.route('/agenda_medica-index')
def agenda_medicaIndex():
    return render_template('agenda_medica-index.html')
