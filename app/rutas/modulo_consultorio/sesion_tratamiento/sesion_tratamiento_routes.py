from flask import Blueprint, render_template

sesiontratamientomod = Blueprint('sesiontratamiento', __name__, template_folder='templates')

@sesiontratamientomod.route('/sesion-tratamiento-index')
def sesionTratamientoIndex():
    return render_template('sesion-tratamiento-index.html')
