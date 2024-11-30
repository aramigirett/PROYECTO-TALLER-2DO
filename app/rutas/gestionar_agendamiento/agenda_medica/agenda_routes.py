from flask import Blueprint, render_template

agenda_vista = Blueprint('agenda_medica', __name__, template_folder='templates')

@agenda_vista.route('/agenda_vista-index')
def agenda_vistaIndex():
    return render_template('agenda_vista.html')
