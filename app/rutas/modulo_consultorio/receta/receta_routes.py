from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion

recetamod = Blueprint('receta', __name__, template_folder='templates')


@recetamod.route('/receta-index')
@require_permiso('receta', 'ver')
def recetaIndex():
    """
    Generar Recetas e Indicaciones. Sin parámetros: listado (un médico ve solo las de SUS consultas). Con `?consulta=<id>` (llega desde la Atención de la consulta): las
    recetas de esa consulta y el alta. `es_medico`: solo un usuario vinculado a un médico ve los botones de registrar y anular (el servidor exige además ser el médico
    de la consulta).
    """
    return render_template('receta-index.html', es_medico=bool(id_medico_sesion()))
