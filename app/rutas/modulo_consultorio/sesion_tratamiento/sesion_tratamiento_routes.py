from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion

sesiontratamientomod = Blueprint('sesiontratamiento', __name__, template_folder='templates')


@sesiontratamientomod.route('/sesion-tratamiento-index')
@require_permiso('sesiontratamiento', 'ver')
def sesionTratamientoIndex():
    """
    Procedimientos e Insumos Utilizados: las sesiones de un tratamiento (`?tratamiento=<id>`). Con `&consulta=<id>` se registran en esa consulta (que debe ser
    del mismo paciente y médico que el tratamiento). Pantalla contextual: sin entrada de menú.
    `es_medico`: solo un usuario vinculado a un médico ve los botones de registrar, anular y finalizar (el servidor exige además ser el médico de la consulta).
    """
    return render_template('sesion-tratamiento-index.html', es_medico=bool(id_medico_sesion()))
