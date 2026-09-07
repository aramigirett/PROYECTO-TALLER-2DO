from flask import Blueprint, render_template

tipoprocedimientomedicomod = Blueprint('tipoprocedimientomedico', __name__, template_folder='templates')

@tipoprocedimientomedicomod.route('/tipo-procedimiento-medico-index')
def tipoProcedimientoMedicoIndex():
    return render_template('tipo-procedimiento-medico-index.html')
