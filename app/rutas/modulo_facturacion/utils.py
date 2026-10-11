"""Helpers compartidos por las APIs de los referenciales de Facturación.

OJO: las reglas de validación (descripción, dirección, teléfono, correo) están
duplicadas en app/static/js/facturacion-validadores.js para avisar en el
formulario antes de enviar. Si cambia una regla, cambiar los dos archivos.
"""
import re
from flask import jsonify, request, session
from app.dao.modulo_facturacion.AuditoriaCambiosDao import AuditoriaCambiosDao

MAX_DESCRIPCION = 60
MAX_DIRECCION = 150
MAX_CORREO = 100
TELEFONO_MIN_LARGO = 6
TELEFONO_MAX_LARGO = 20
TELEFONO_MIN_DIGITOS = 6

_RE_DESCRIPCION = re.compile(r'^[A-ZÁÉÍÓÚÜÑ0-9][A-ZÁÉÍÓÚÜÑ0-9 .\-/]*$')
_RE_CONTROL = re.compile(r'[\x00-\x1f\x7f]')
_RE_TELEFONO = re.compile(r'^\+?[0-9][0-9 \-]*$')
_RE_CORREO = re.compile(r'^[a-z0-9._%+\-]+@[a-z0-9\-]+(\.[a-z0-9\-]+)*\.[a-z]{2,}$')


def _como_texto(valor):
    """Colapsa espacios (incluye saltos de línea) y recorta. None/no-str => ''."""
    if not isinstance(valor, str):
        return ''
    return re.sub(r'\s+', ' ', valor).strip()


def normalizar_descripcion(data):
    """Devuelve (descripcion, error). Quita espacios sobrantes y pasa a mayúsculas."""
    descripcion = _como_texto(data.get('descripcion') if data else None).upper()
    if not descripcion:
        return None, 'El campo descripción es obligatorio y no puede estar vacío.'
    if len(descripcion) > MAX_DESCRIPCION:
        return None, f'La descripción no puede superar los {MAX_DESCRIPCION} caracteres.'
    if not _RE_DESCRIPCION.match(descripcion):
        return None, 'La descripción solo puede contener letras, números, espacios y los símbolos . - /'
    return descripcion, None


def validar_texto(valor, nombre, max_len):
    """Texto libre obligatorio (ej. dirección). Devuelve (texto, error)."""
    texto = _como_texto(valor)
    if not texto:
        return None, f'El campo {nombre} es obligatorio y no puede estar vacío.'
    if len(texto) > max_len:
        return None, f'El campo {nombre} no puede superar los {max_len} caracteres.'
    if _RE_CONTROL.search(texto):
        return None, f'El campo {nombre} contiene caracteres no permitidos.'
    return texto, None


def validar_telefono(valor):
    """
    Obligatorio; solo dígitos, espacios, guiones y un + inicial opcional; entre 6 y 20
    caracteres en total y al menos 6 dígitos reales (sin contar +, espacios ni guiones).
    Devuelve (telefono, error).
    """
    telefono = _como_texto(valor)
    if not telefono:
        return None, 'El campo teléfono es obligatorio y no puede estar vacío.'
    if not _RE_TELEFONO.match(telefono):
        return None, 'El teléfono solo puede contener dígitos, espacios, guiones y un + inicial.'
    if not (TELEFONO_MIN_LARGO <= len(telefono) <= TELEFONO_MAX_LARGO):
        return None, f'El teléfono debe tener entre {TELEFONO_MIN_LARGO} y {TELEFONO_MAX_LARGO} caracteres.'
    if sum(c.isdigit() for c in telefono) < TELEFONO_MIN_DIGITOS:
        return None, f'El teléfono debe tener al menos {TELEFONO_MIN_DIGITOS} dígitos.'
    return telefono, None


def validar_correo(valor):
    """Obligatorio, formato válido, se guarda en minúsculas. Devuelve (correo, error)."""
    correo = _como_texto(valor).lower()
    if not correo:
        return None, 'El campo correo es obligatorio y no puede estar vacío.'
    if len(correo) > MAX_CORREO:
        return None, f'El correo no puede superar los {MAX_CORREO} caracteres.'
    if not _RE_CORREO.match(correo):
        return None, 'El correo no tiene un formato válido.'
    return correo, None


def validar_datos_entidad(data):
    """
    Valida descripción + dirección + teléfono + correo (Entidad Emisora, Entidad Adherida).
    Devuelve (datos, error, campo): si hay error, `campo` es el campo del formulario.
    """
    data = data if isinstance(data, dict) else {}
    descripcion, error = normalizar_descripcion(data)
    if error:
        return None, error, 'descripcion'
    direccion, error = validar_texto(data.get('direccion'), 'dirección', MAX_DIRECCION)
    if error:
        return None, error, 'direccion'
    telefono, error = validar_telefono(data.get('telefono'))
    if error:
        return None, error, 'telefono'
    correo, error = validar_correo(data.get('correo'))
    if error:
        return None, error, 'correo'
    return {'descripcion': descripcion, 'direccion': direccion,
            'telefono': telefono, 'correo': correo}, None, None


def detalle_cambios(anterior, nuevo, etiquetas):
    """
    Compara dos dicts y arma el detalle de auditoría solo con lo que cambió:
    "Teléfono: A -> B; Correo: X -> Y". `etiquetas` = {clave: texto visible}.
    Si `anterior` está vacío (alta) lista los valores: "Teléfono: B; Correo: Y".
    Devuelve '' si no hay cambios.
    """
    if not anterior:
        return '; '.join(f'{etq}: {nuevo.get(k)}' for k, etq in etiquetas.items())
    return '; '.join(
        f'{etq}: {anterior.get(k)} -> {nuevo.get(k)}'
        for k, etq in etiquetas.items() if anterior.get(k) != nuevo.get(k)
    )


def respuesta_error(mensaje, status, campo=None):
    cuerpo = {'success': False, 'error': mensaje}
    if campo:
        cuerpo['campo'] = campo
    return jsonify(cuerpo), status


def auditar(entidad, id_registro, accion, detalle):
    """Registra en auditoria_cambios. id_usuario e ip salen de la sesión y del request, nunca del cliente."""
    AuditoriaCambiosDao().registrar(session.get('id_usuario'), entidad, id_registro,
                                    accion, detalle, request.remote_addr)


def error_interno():
    return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
