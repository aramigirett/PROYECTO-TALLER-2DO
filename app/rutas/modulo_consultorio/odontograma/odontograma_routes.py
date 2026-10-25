from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion

odontogramamod = Blueprint('odontograma', __name__, template_folder='templates')


@odontogramamod.route('/odontograma-index')
@require_permiso('odontograma', 'ver')
def odontogramaIndex():
    """
    Gestionar Odontograma. Sin parámetros: listado de los odontogramas (un médico ve solo los de SUS consultas). Con `?consulta=<id>` (llega desde la
    pantalla de Atención de la consulta): el odontograma visual de esa consulta, que se crea precargado con el último del paciente.
    `es_medico`: solo un usuario vinculado a un médico ve los botones de crear, modificar y anular (el servidor exige además ser el médico de la consulta).
    """
    return render_template('odontograma-index.html', es_medico=bool(id_medico_sesion()))
