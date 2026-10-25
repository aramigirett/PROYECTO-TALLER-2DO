from flask import Blueprint, abort, render_template
from app.dao.referenciales_consultorio.consulta.ConsultaDao import ConsultaDao, numero_consulta
from app.rutas.modulo_seguridad.decorators import require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion

consultamod = Blueprint('consulta', __name__, template_folder='templates')


@consultamod.route('/consulta-index')
@require_permiso('consulta', 'ver')
def consultaIndex():
    """Registrar Consulta: listado, indicadores y alta desde una cita Confirmado."""
    return render_template('consulta-index.html')


@consultamod.route('/consulta-detalle/<int:id_consulta>')
@require_permiso('consulta', 'ver')
def consultaDetalle(id_consulta):
    """
    Atención de la consulta: pantalla central desde la que se llega a la Ficha Médica y al resto de los movimientos clínicos.
    Contextual (sin entrada de menú): usa el permiso `consulta ver`. Un médico solo abre SUS consultas.
    """
    consulta = ConsultaDao().getConsultaById(id_consulta)
    if not consulta or not consulta['activo']:
        abort(404)
    id_medico = id_medico_sesion()
    if id_medico and consulta['id_medico'] != id_medico:
        abort(403)
    return render_template('consulta-detalle.html', id_consulta=id_consulta, numero=numero_consulta(id_consulta))
