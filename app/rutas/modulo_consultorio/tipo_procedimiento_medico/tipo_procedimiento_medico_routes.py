from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

tipoprocedimientomedicomod = Blueprint('tipoprocedimientomedico', __name__, template_folder='templates')

@tipoprocedimientomedicomod.route('/tipo-procedimiento-medico-index')
@require_permiso('tipoprocedimientomedico', 'ver')
def tipoProcedimientoMedicoIndex():
    return render_template('tipo-procedimiento-medico-index.html')
