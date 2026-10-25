"""Helpers compartidos por las APIs de Consultorio (referenciales y movimientos).

Reutiliza los de Facturación (misma auditoría estructurada, mismos validadores): las reglas viven en
app/rutas/modulo_facturacion/utils.py y su espejo en app/static/js/facturacion-validadores.js. Si cambia una regla, cambiar los dos.

AUDITORÍA DE CONSULTORIO: el detalle que se guarda en `auditoria_cambios` es dato de salud y NO lleva contenido clínico
(diagnósticos, síntomas, indicaciones, medicamentos, observaciones, resultados). Solo: quién (lo pone auditar()), cuándo, paciente,
N.º de documento (consulta, código, recibo) y cambios de estado. Los referenciales (catálogos) sí auditan su descripción.
Las entidades auditadas se declaran en app/Services/auditoria_detalle.py (MODULO_POR_ENTIDAD).
"""
from app.rutas.modulo_facturacion.utils import (  # noqa: F401  (se reexportan para las APIs de Consultorio)
    auditar, detalle_cambios, entero_id, error_interno, normalizar_descripcion, respuesta_error,
    validar_booleano, validar_observacion, validar_presentacion, validar_precio, validar_iva, validar_texto,
)


def acceso_consulta(id_consulta):
    """
    Lectura de lo clínico que cuelga de una consulta: la consulta debe existir y estar activa, y un médico solo accede a SUS consultas
    (Recepción y Administrador, con el permiso `ver` de la ventana que corresponda, acceden a todas).
    Devuelve (consulta, None) o (None, respuesta_de_error).
    """
    from app.dao.referenciales_consultorio.consulta.ConsultaDao import ConsultaDao
    from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion
    consulta = ConsultaDao().getConsultaById(id_consulta)
    if not consulta or not consulta['activo']:
        return None, respuesta_error('No se encontró la consulta con el ID proporcionado.', 404)
    id_medico = id_medico_sesion()
    if id_medico and consulta['id_medico'] != id_medico:
        return None, respuesta_error('Esta consulta pertenece a otro médico.', 403)
    return consulta, None
