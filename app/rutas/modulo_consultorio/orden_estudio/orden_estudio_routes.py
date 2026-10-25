from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion

ordenestudiomod = Blueprint('ordenestudio', __name__, template_folder='templates')


@ordenestudiomod.route('/orden-estudio-index')
@require_permiso('ordenestudio', 'ver')
def ordenEstudioIndex():
    """
    Generar Orden de Estudios. Sin parámetros: listado (un médico ve solo las de SUS consultas). Con `?consulta=<id>` (llega desde la Atención de la consulta): las
    órdenes de esa consulta y el alta. Comparte la plantilla `orden-clinica-index.html` con la Orden de Análisis.
    `es_medico`: solo un usuario vinculado a un médico ve los botones de registrar, avanzar y cancelar (el servidor exige además ser el médico de la consulta).
    """
    cfg = {'titulo': 'Generar Orden de Estudios', 'singular': 'orden de estudios', 'api': '/api/v1/orden-estudios', 'pk': 'id_orden_estudio', 'tipo_col': 'id_tipo_estudio',
           'api_tipos': '/api/v1/tipos-estudio', 'etiqueta_tipo': 'Tipo de estudio', 'ventana': 'ordenestudio', 'validador': 'ordenEstudio', 'es_medico': bool(id_medico_sesion())}
    return render_template('orden-clinica-index.html', cfg=cfg)
