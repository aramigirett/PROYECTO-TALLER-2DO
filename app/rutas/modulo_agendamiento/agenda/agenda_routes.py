from flask import Blueprint, render_template

# SIN template_folder - usa la carpeta global
agenda_bp = Blueprint('agenda_bp', __name__)

@agenda_bp.route('/agenda')
def index():
    # Busca en app/templates/agenda/index.html
    return render_template('agenda/index.html')