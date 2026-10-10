"""
=====================================================
ROUTES: Gestión de Fichas Médicas
Descripción: Rutas para renderizar las vistas HTML
=====================================================
"""

from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso

# Crear Blueprint
fichamedicamod = Blueprint('fichamedica', __name__, template_folder='templates')

@fichamedicamod.route('/ficha-medica-index')
@require_permiso('fichamedica', 'ver')
def fichaMedicaIndex():
    """
    Renderiza la página principal de Gestión de Fichas Médicas
    """
    return render_template('ficha-medica-index.html')