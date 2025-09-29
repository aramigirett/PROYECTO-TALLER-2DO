from flask import Blueprint, render_template

# Blueprint para avisos y recordatorios
avisomod = Blueprint('avisosrecordatorios', __name__, template_folder='templates')

@avisomod.route('/avisosrecordatorios-index')
def avisosrecordatorios_index():
    return render_template('avisosrecordatorios-index.html')
