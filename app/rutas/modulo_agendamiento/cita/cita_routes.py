from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

# Crear el Blueprint para las rutas de Cita
citamod = Blueprint('cita', __name__, template_folder='templates')

@citamod.route('/cita-index')
@require_permiso('cita', 'ver')
def citaIndex():
    """
    Ruta para mostrar la página principal de gestión de citas
    """
    return render_template('cita-index.html')