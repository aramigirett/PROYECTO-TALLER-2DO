from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion

ordenanalisismod = Blueprint('ordenanalisis', __name__, template_folder='templates')


@ordenanalisismod.route('/orden-analisis-index')
@require_permiso('ordenanalisis', 'ver')
def ordenAnalisisIndex():
    """
    Generar Orden de Análisis. Sin parámetros: listado (un médico ve solo las de SUS consultas). Con `?consulta=<id>` (llega desde la Atención de la consulta): las
    órdenes de esa consulta y el alta. Comparte la plantilla `orden-clinica-index.html` con la Orden de Estudios.
    `es_medico`: solo un usuario vinculado a un médico ve los botones de registrar, avanzar y cancelar (el servidor exige además ser el médico de la consulta).
    """
    cfg = {'titulo': 'Generar Orden de Análisis', 'singular': 'orden de análisis', 'api': '/api/v1/orden-analisis', 'pk': 'id_orden_analisis', 'tipo_col': 'id_tipo_analisis',
           'api_tipos': '/api/v1/tipos-analisis', 'etiqueta_tipo': 'Tipo de análisis', 'ventana': 'ordenanalisis', 'validador': 'ordenAnalisis', 'es_medico': bool(id_medico_sesion())}
    return render_template('orden-clinica-index.html', cfg=cfg)
