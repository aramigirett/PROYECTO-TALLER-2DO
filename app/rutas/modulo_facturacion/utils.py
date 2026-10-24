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
MAX_UBICACION = 100
MAX_NOMBRE = 80
MAX_OBSERVACION = 200
TELEFONO_MIN_LARGO = 6
TELEFONO_MAX_LARGO = 20
TELEFONO_MIN_DIGITOS = 6
MAX_PRECIO = 999_999_999_999   # NUMERIC(12,0)
MAX_CANTIDAD = 2_147_483_647   # INTEGER
IVA_VALIDOS = (0, 5, 10)

_RE_DESCRIPCION = re.compile(r'^[A-ZÁÉÍÓÚÜÑ0-9][A-ZÁÉÍÓÚÜÑ0-9 .\-/]*$')
_RE_DESCRIPCION_AMPLIADA = re.compile(r'^[A-ZÁÉÍÓÚÜÑ0-9][A-ZÁÉÍÓÚÜÑ0-9 .\-/,%()+&]*$')
_RE_NOMBRE = re.compile(r"^[A-ZÁÉÍÓÚÜÑ0-9][A-ZÁÉÍÓÚÜÑ0-9 .,\-&'/()]*$")
_RE_CEDULA = re.compile(r'^\d{5,10}$')
_RE_RUC = re.compile(r'^(\d{5,10})-(\d)$')
_RE_CONTROL = re.compile(r'[\x00-\x1f\x7f]')
_RE_TELEFONO = re.compile(r'^\+?[0-9][0-9 \-]*$')
_RE_CORREO = re.compile(r'^[a-z0-9._%+\-]+@[a-z0-9\-]+(\.[a-z0-9\-]+)*\.[a-z]{2,}$')


def _como_texto(valor):
    """Colapsa espacios (incluye saltos de línea) y recorta. None/no-str => ''."""
    if not isinstance(valor, str):
        return ''
    return re.sub(r'\s+', ' ', valor).strip()


def normalizar_descripcion(data, max_len=MAX_DESCRIPCION, ampliada=False):
    """
    Devuelve (descripcion, error). Quita espacios sobrantes y pasa a mayúsculas.
    `ampliada=True` (ej. Ítems) acepta además los símbolos , % ( ) + &
    """
    descripcion = _como_texto(data.get('descripcion') if isinstance(data, dict) else None).upper()
    if not descripcion:
        return None, 'El campo descripción es obligatorio y no puede estar vacío.'
    if len(descripcion) > max_len:
        return None, f'La descripción no puede superar los {max_len} caracteres.'
    if not (_RE_DESCRIPCION_AMPLIADA if ampliada else _RE_DESCRIPCION).match(descripcion):
        return None, ('La descripción solo puede contener letras, números, espacios y los símbolos . - / , % ( ) + &'
                      if ampliada else
                      'La descripción solo puede contener letras, números, espacios y los símbolos . - /')
    return descripcion, None


def validar_texto(valor, nombre, max_len, mayusculas=False):
    """Texto libre obligatorio (ej. dirección, ubicación). Devuelve (texto, error).
    `mayusculas=True` guarda el texto en mayúsculas."""
    texto = _como_texto(valor)
    if mayusculas:
        texto = texto.upper()
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


def _entero_estricto(valor):
    """int, o texto de solo dígitos -> int. Rechaza bool, float, vacío y cualquier otra cosa (None)."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str) and re.fullmatch(r'-?\d+', valor.strip()):
        return int(valor.strip())
    return None


def _miles(n):
    return f'{n:,}'.replace(',', '.')


def entero_id(valor):
    """ID entero positivo (int o texto numérico). None si no es válido."""
    n = _entero_estricto(valor)
    return n if n is not None and n > 0 else None


def validar_precio(valor):
    """Guaraníes: entero mayor a 0, hasta 12 dígitos (sin decimales). Devuelve (precio, error)."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None, 'El campo precio es obligatorio y no puede estar vacío.'
    n = _entero_estricto(valor)
    if n is None:
        return None, 'El precio debe ser un número entero (guaraníes, sin decimales).'
    if n <= 0:
        return None, 'El precio debe ser mayor a 0.'
    if n > MAX_PRECIO:
        return None, f'El precio no puede superar {_miles(MAX_PRECIO)}.'
    return n, None


def validar_monto(valor):
    """Guaraníes: entero MAYOR O IGUAL a 0 (puede ser 0), hasta 12 dígitos. Devuelve (monto, error).
    Distinto de validar_precio, que exige mayor a 0."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None, 'El campo monto es obligatorio y no puede estar vacío.'
    n = _entero_estricto(valor)
    if n is None:
        return None, 'El monto debe ser un número entero (guaraníes, sin decimales).'
    if n < 0:
        return None, 'El monto no puede ser negativo.'
    if n > MAX_PRECIO:
        return None, f'El monto no puede superar {_miles(MAX_PRECIO)}.'
    return n, None


def validar_iva(valor):
    """Solo 0 (exenta), 5 o 10. Devuelve (iva, error)."""
    n = _entero_estricto(valor)
    if n not in IVA_VALIDOS:
        return None, 'El IVA debe ser Exenta (0), 5% o 10%.'
    return n, None


def validar_cantidad(valor):
    """Entero de 0 en adelante. Devuelve (cantidad, error)."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None, 'El campo cantidad es obligatorio (use 0 si no hay stock).'
    n = _entero_estricto(valor)
    if n is None:
        return None, 'La cantidad debe ser un número entero.'
    if n < 0:
        return None, 'La cantidad no puede ser negativa.'
    if n > MAX_CANTIDAD:
        return None, f'La cantidad no puede superar {_miles(MAX_CANTIDAD)}.'
    return n, None


def validar_cantidad_positiva(valor):
    """Cantidad de un renglón de pedido: entero MAYOR a 0. Un único mensaje para cualquier valor inválido
    (distinto de validar_cantidad, que acepta 0 para el stock). Devuelve (cantidad, error)."""
    n = _entero_estricto(valor)
    if n is None or n <= 0:
        return None, 'La cantidad debe ser un número entero mayor a 0.'
    if n > MAX_CANTIDAD:
        return None, f'La cantidad no puede superar {_miles(MAX_CANTIDAD)}.'
    return n, None


def validar_observacion(valor):
    """Observación opcional (hasta 200 caracteres, texto libre). Vacío => (None, None). Devuelve (texto, error)."""
    if valor is None:
        return None, None
    if not isinstance(valor, str):
        return None, 'La observación debe ser un texto.'
    texto = _como_texto(valor)
    if not texto:
        return None, None
    if len(texto) > MAX_OBSERVACION:
        return None, f'La observación no puede superar los {MAX_OBSERVACION} caracteres.'
    if _RE_CONTROL.search(texto):
        return None, 'La observación contiene caracteres no permitidos.'
    return texto, None


def validar_booleano(valor, nombre):
    """Solo true/false reales (JSON). Devuelve (bool, error)."""
    if not isinstance(valor, bool):
        return None, f'El campo "{nombre}" debe ser Sí o No.'
    return valor, None


def calcular_dv_ruc(base, base_max=11):
    """Dígito verificador del RUC paraguayo (SET): módulo 11, base máxima 11.
    Se recorre la base de derecha a izquierda con pesos 2, 3, ... (vuelve a 2 al pasar de base_max)."""
    k = 2
    total = 0
    for digito in reversed(str(base)):
        if k > base_max:
            k = 2
        total += int(digito) * k
        k += 1
    resto = total % 11
    return 11 - resto if resto > 1 else 0


def validar_ci_ruc(valor):
    """
    Obligatorio. Cédula: solo dígitos, de 5 a 10 (sin verificador). RUC: dígitos, guion y un dígito
    verificador (ej. 80012345-0), cuyo verificador se valida con calcular_dv_ruc. Devuelve (ci_ruc, error).
    """
    texto = _como_texto(valor)
    if not texto:
        return None, 'El campo CI/RUC es obligatorio y no puede estar vacío.'
    if texto.isdigit():
        if not _RE_CEDULA.match(texto):
            return None, 'La cédula debe tener entre 5 y 10 dígitos.'
        return texto, None
    ruc = _RE_RUC.match(texto)
    if not ruc:
        return None, 'La CI/RUC no es válida: use una cédula (5 a 10 dígitos) o un RUC con verificador (ej. 80012345-0).'
    if int(ruc.group(2)) != calcular_dv_ruc(ruc.group(1)):
        return None, 'El dígito verificador del RUC no es válido.'
    return texto, None


def validar_nombre(valor, etiqueta, obligatorio=True, max_len=MAX_NOMBRE):
    """
    Nombre o razón social (también apellido, opcional). Mayúsculas; letras, números, espacios y . , - & ' / ( ).
    Devuelve (texto | None, error); un opcional vacío da (None, None).
    """
    texto = _como_texto(valor).upper()
    if not texto:
        if obligatorio:
            return None, f'El campo {etiqueta} es obligatorio y no puede estar vacío.'
        return None, None
    if len(texto) > max_len:
        return None, f'El campo {etiqueta} no puede superar los {max_len} caracteres.'
    if not _RE_NOMBRE.match(texto):
        return None, f"El campo {etiqueta} solo puede contener letras, números, espacios y los símbolos . , - & ' / ( )"
    return texto, None


def validar_telefono_opcional(valor):
    """Opcional: vacío => (None, None); si se carga, aplica validar_telefono."""
    if not _como_texto(valor):
        return None, None
    return validar_telefono(valor)


def validar_correo_opcional(valor):
    """Opcional: vacío => (None, None); si se carga, aplica validar_correo."""
    if not _como_texto(valor):
        return None, None
    return validar_correo(valor)


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
