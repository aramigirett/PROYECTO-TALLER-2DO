from flask import Blueprint, render_template
from app.rutas.modulo_seguridad.decorators import require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion

justificativomedicomod = Blueprint('justificativomedico', __name__, template_folder='templates')


@justificativomedicomod.route('/justificativo-medico-index')
@require_permiso('justificativomedico', 'ver')
def justificativoMedicoIndex():
    """
    Generar Justificativo Médico. Sin parámetros: listado (un médico ve solo los de SUS consultas). Con `?consulta=<id>` (llega desde la Atención de la consulta): los
    justificativos de esa consulta y el alta. `es_medico`: solo un usuario vinculado a un médico ve los botones de registrar, generar y anular (el servidor exige además
    ser el médico de la consulta).
    """
    return render_template('justificativo-medico-index.html', es_medico=bool(id_medico_sesion()))
