from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion

tratamientomod = Blueprint('tratamiento', __name__, template_folder='templates')


@tratamientomod.route('/tratamiento-index')
@require_permiso('tratamiento', 'ver')
def tratamientoIndex():
    """
    Gestionar Tratamientos. Sin parámetros: listado (un médico ve solo los de SUS consultas). Con `?consulta=<id>` (llega desde la Atención de la consulta): los
    tratamientos de esa consulta, los tratamientos en curso del paciente (de otras consultas, para registrarles sesiones) y el alta.
    `es_medico`: solo un usuario vinculado a un médico ve los botones de registrar, finalizar y anular (el servidor exige además ser el médico de la consulta).
    """
    return render_template('tratamiento-index.html', es_medico=bool(id_medico_sesion()))
