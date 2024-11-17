from flask import Blueprint, render_template, jsonify
from app.dao.referenciales.turno.TurnoDao import TurnoDao

turmod = Blueprint('turno', __name__, template_folder='templates')

@turmod.route('/turno-index')
def turnoIndex():
    turnodao = TurnoDao()
    return render_template('turno-index.html', lista_turnos=turnodao.getTurnos())