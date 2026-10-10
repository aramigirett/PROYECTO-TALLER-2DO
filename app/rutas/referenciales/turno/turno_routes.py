from flask import Blueprint, render_template, jsonify
from app.dao.referenciales.turno.TurnoDao import TurnoDao
from app.rutas.modulo_seguridad.decorators import require_permiso

turmod = Blueprint('turno', __name__, template_folder='templates')

@turmod.route('/turno-index')
@require_permiso('turno', 'ver')
def turnoIndex():
    turnodao = TurnoDao()
    return render_template('turno-index.html', lista_turnos=turnodao.getTurnos())