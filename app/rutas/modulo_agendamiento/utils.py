"""Helpers compartidos por las APIs de Agendamiento (referenciales, personas y movimientos).

Reutiliza los de Facturación (misma auditoría estructurada, mismos validadores): las reglas viven en
app/rutas/modulo_facturacion/utils.py y su espejo en app/static/js/facturacion-validadores.js. Las reglas propias de Agendamiento
(día de la semana, teléfono paraguayo del consultorio, horario y cupos de una disponibilidad) están acá y tienen su par en el mismo
archivo JS. Si cambia una regla, cambiar los dos.

AUDITORÍA DE AGENDAMIENTO: el detalle que se guarda en `auditoria_cambios` lleva NOMBRES, no IDs. De las personas (paciente, médico,
funcionario) solo se audita quién, cuándo, el nombre y el N.º de documento: nunca teléfono, dirección ni correo. El historial médico
no lleva contenido clínico. Las entidades auditadas se declaran en app/Services/auditoria_detalle.py (MODULO_POR_ENTIDAD).
"""
import re
import unicodedata
from datetime import datetime

from app.rutas.modulo_facturacion.utils import (  # noqa: F401  (se reexportan para las APIs de Agendamiento)
    MAX_DIRECCION, _como_texto, auditar, detalle_cambios, entero_id, error_interno, normalizar_descripcion, respuesta_error,
    validar_correo, validar_texto,
)

DIAS_VALIDOS = ('LUNES', 'MARTES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'SABADO', 'DOMINGO')
MAX_CUPOS = 1000
_RE_TELEFONO_PY = re.compile(r'^595\d{8,9}$')


def _sin_tildes(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')


def validar_dia(data, campo='descripcion'):
    """
    Día de la semana: solo uno de los 7 nombres válidos (el CHECK de la base los conserva). Se pasa a mayúsculas y se acepta con tilde
    (MIÉRCOLES, SÁBADO), que se guarda sin ella. Devuelve (nombre, error).
    """
    texto = _sin_tildes(_como_texto(data.get(campo) if isinstance(data, dict) else None)).upper()
    if not texto:
        return None, 'El campo día es obligatorio y no puede estar vacío.'
    if texto not in DIAS_VALIDOS:
        return None, 'El día debe ser uno de los días de la semana: Lunes, Martes, Miércoles, Jueves, Viernes, Sábado o Domingo.'
    return texto, None


def normalizar_telefono_py(valor):
    """0981 123 456 -> 595981123456 (acepta +595..., 0..., o el número sin prefijo). Vacío => None."""
    if not isinstance(valor, str):
        return None
    t = valor.strip().replace(' ', '').replace('-', '')
    if not t:
        return None
    if t.startswith('+'):
        t = t[1:]
    if t.startswith('0'):
        return '595' + t[1:]
    return t if t.startswith('595') else '595' + t


def validar_telefono_py(valor):
    """Teléfono paraguayo obligatorio (consultorio): se guarda como 595XXXXXXXXX (8 o 9 dígitos tras el 595). Devuelve (telefono, error)."""
    if not _como_texto(valor):
        return None, 'El campo teléfono es obligatorio y no puede estar vacío.'
    t = normalizar_telefono_py(valor)
    if not t or not _RE_TELEFONO_PY.match(t):
        return None, 'El número de teléfono no es válido. Debe ser paraguayo (ej.: 0981234567).'
    return t, None


def validar_hora(valor, nombre):
    """Hora HH:MM o HH:MM:SS. Devuelve (datetime.time, error)."""
    texto = valor.strip() if isinstance(valor, str) else ''
    if not texto:
        return None, f'El campo {nombre} es obligatorio y no puede estar vacío.'
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(texto, fmt).time(), None
        except ValueError:
            pass
    return None, f'El campo {nombre} no es una hora válida (use HH:MM).'


def validar_fecha(valor, nombre):
    """Fecha AAAA-MM-DD. Devuelve (datetime.date, error)."""
    texto = valor.strip() if isinstance(valor, str) else ''
    if not texto:
        return None, f'El campo {nombre} es obligatorio y no puede estar vacío.'
    try:
        return datetime.strptime(texto, '%Y-%m-%d').date(), None
    except ValueError:
        return None, f'El campo {nombre} no es una fecha válida.'


def validar_horario(inicio, fin):
    """La hora de fin debe ser posterior a la de inicio. Devuelve error o None."""
    if fin <= inicio:
        return 'La hora de fin debe ser posterior a la hora de inicio.'
    return None


def validar_cupos(valor):
    """Cupos de una disponibilidad: entero de 1 a MAX_CUPOS. Devuelve (int, error)."""
    if isinstance(valor, bool) or isinstance(valor, float):
        return None, 'Los cupos deben ser un número entero.'
    if isinstance(valor, str):
        t = valor.strip()
        if not re.fullmatch(r'\d+', t):
            return None, 'Los cupos deben ser un número entero.'
        valor = int(t)
    if not isinstance(valor, int):
        return None, 'Los cupos deben ser un número entero.'
    if valor < 1 or valor > MAX_CUPOS:
        return None, f'Los cupos deben estar entre 1 y {MAX_CUPOS}.'
    return valor, None
