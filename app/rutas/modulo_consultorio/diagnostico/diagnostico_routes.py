from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion

diagnosticos_medicos_mod = Blueprint('diagnostico_medico', __name__, template_folder='templates')


@diagnosticos_medicos_mod.route('/diagnostico-index')
@require_permiso('diagnostico', 'ver')
def diagnosticoIndex():
    """
    Gestionar Diagnóstico. Sin parámetros: listado de los diagnósticos (un médico ve solo los de SUS consultas). Con `?consulta=<id>` (llega desde la
    pantalla de Atención de la consulta): los diagnósticos de esa consulta y el formulario para registrar uno nuevo.
    `es_medico`: solo un usuario vinculado a un médico ve los botones de registrar y anular (el servidor exige además ser el médico de la consulta).
    """
    return render_template('diagnostico-index.html', es_medico=bool(id_medico_sesion()))
