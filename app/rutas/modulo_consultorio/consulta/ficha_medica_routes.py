"""
=====================================================
ROUTES: Gestión de Fichas Médicas
Descripción: Rutas para renderizar las vistas HTML
=====================================================
"""

from flask import Blueprint, render_template

# Crear Blueprint
fichamedicamod = Blueprint('fichamedica', __name__, template_folder='templates')

@fichamedicamod.route('/ficha-medica-index')
def fichaMedicaIndex():
    """
    Renderiza la página principal de Gestión de Fichas Médicas
    """
    return render_template('ficha-medica-index.html')