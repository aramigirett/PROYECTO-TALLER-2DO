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
    validar_booleano, validar_observacion, validar_precio, validar_iva, validar_texto,
)
