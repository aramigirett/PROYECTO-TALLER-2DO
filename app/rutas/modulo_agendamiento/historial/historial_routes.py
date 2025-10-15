"""
=====================================================
MÓDULO: Historial Médico - Rutas de Vistas
DESCRIPCIÓN: Define las rutas para renderizar las plantillas HTML
             del módulo de historial médico del paciente
=====================================================
"""

from flask import Blueprint, render_template

# Crear Blueprint para historial médico
historialmod = Blueprint('historial', __name__, template_folder='templates')

@historialmod.route('/historial-index')
def historialIndex():
    """
    Renderiza la página principal del historial médico del paciente
    
    Esta vista permite:
    - Buscar pacientes
    - Ver historial completo por categorías
    - Agregar/editar/eliminar documentos médicos
    """
    return render_template('historial-index.html')