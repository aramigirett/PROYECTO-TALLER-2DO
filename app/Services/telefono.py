"""
=====================================================
Servicio: teléfonos (formato nacional paraguayo)
Descripción: funciones puras (sin Flask ni base de datos) para el manejo de teléfonos de todo el sistema. Espejo en facturacion-validadores.js
(normalizarTelefono / telefono / formatearTelefono / aWhatsapp: si cambia una regla, cambian las dos).
  - Se GUARDA en formato nacional: solo dígitos y con el 0 inicial.
      Celular:    ^09\\d{8}$       se muestra "0984 818 035"
      Línea baja: ^0[2-8]\\d{7,8}$  se muestra "021 339 8423" (código de área + número)
  - El usuario puede escribir con o sin espacios (y con guiones): se limpia al guardar y se formatea al mostrar.
  - Para WhatsApp solo sirven los celulares: se convierte al enviar (se quita el 0 y se antepone 595).
=====================================================
"""
import re

_RE_CELULAR = re.compile(r'^09\d{8}$')
_RE_LINEA_BAJA = re.compile(r'^0[2-8]\d{7,8}$')
_RE_ESCRITURA = re.compile(r'^[0-9 \-]+$')      # lo que el usuario puede escribir: dígitos, espacios y guiones

MENSAJE_INVALIDO = 'Ingrese un celular (09XX XXX XXX) o una línea baja con código de área (021 XXX XXXX).'
MENSAJE_OBLIGATORIO = 'El campo teléfono es obligatorio y no puede estar vacío.'


def solo_digitos(valor):
    """Texto con espacios y guiones quitados (None si no es texto). No toca ningún otro carácter: un '+' o una letra siguen ahí y lo invalidan."""
    if not isinstance(valor, str):
        return None
    return valor.strip().replace(' ', '').replace('-', '')


def es_celular(valor):
    return isinstance(valor, str) and bool(_RE_CELULAR.match(valor))


def es_linea_baja(valor):
    return isinstance(valor, str) and bool(_RE_LINEA_BAJA.match(valor))


def es_valido(valor):
    """True si `valor` YA está en el formato guardado (solo dígitos con el 0 inicial) y es celular o línea baja."""
    return es_celular(valor) or es_linea_baja(valor)


def normalizar_telefono(valor):
    """Lo que se guarda: solo dígitos con el 0 inicial. Devuelve None si el texto es vacío o no es un teléfono válido."""
    if not isinstance(valor, str) or not _RE_ESCRITURA.match(valor.strip() or 'x'):
        return None
    t = solo_digitos(valor)
    return t if es_valido(t) else None


def validar_telefono(valor, obligatorio=True):
    """Devuelve (telefono_para_guardar, error). Vacío: error si es obligatorio y (None, None) si no."""
    if not isinstance(valor, str) or not valor.strip():
        return (None, MENSAJE_OBLIGATORIO) if obligatorio else (None, None)
    t = normalizar_telefono(valor)
    return (t, None) if t else (None, MENSAJE_INVALIDO)


def formatear_telefono(valor):
    """Para mostrar: celular '0984 818 035', línea baja '021 339 8423' (9 dígitos: '021 600 600'). Un valor que no cumple el formato (dato viejo)
    se devuelve tal cual, y None / vacío como ''."""
    if valor is None:
        return ''
    t = str(valor).strip()
    if es_celular(t):
        return f'{t[:4]} {t[4:7]} {t[7:]}'
    if es_linea_baja(t):
        resto = t[3:]
        return f'{t[:3]} {resto[:3]} {resto[3:]}'
    return t


def a_whatsapp(valor):
    """Número para WhatsApp: celular 0984818035 -> 595984818035. Una línea baja (o algo inválido) devuelve None: no se envía por WhatsApp."""
    t = normalizar_telefono(valor) if isinstance(valor, str) else None
    return '595' + t[1:] if es_celular(t) else None
