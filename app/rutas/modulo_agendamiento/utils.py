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
    validar_correo, validar_telefono, validar_texto,
)

DIAS_VALIDOS = ('LUNES', 'MARTES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'SABADO', 'DOMINGO')
MAX_CUPOS = 1000


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


FECHA_NACIMIENTO_MINIMA = datetime(1900, 1, 1).date()


def validar_fecha_nacimiento(valor):
    """Fecha de nacimiento AAAA-MM-DD, obligatoria, no futura y desde 1900. Devuelve (date, error)."""
    fecha, error = validar_fecha(valor, 'fecha de nacimiento')
    if error:
        return None, error
    if fecha > datetime.now().date():
        return None, 'La fecha de nacimiento no puede ser futura.'
    if fecha < FECHA_NACIMIENTO_MINIMA:
        return None, 'La fecha de nacimiento no es válida.'
    return fecha, None


def validar_persona(data, doc, con_emergencia=False, con_registro=False, padres=()):
    """
    Valida los datos de un paciente, médico o funcionario. `doc` = clave JSON de la cédula ('cedula_entidad' / 'cedula'); `padres` =
    [(clave JSON, etiqueta)] de los referenciales (id_ciudad, id_especialidad, id_cargo). Devuelve (valores, None) o
    (None, (mensaje, campo)); `valores` usa las mismas claves que las columnas del DAO.
    """
    from app.rutas.modulo_facturacion.utils import MAX_DIRECCION as _MD, validar_ci_ruc, validar_codigo, validar_nombre, validar_telefono
    if not isinstance(data, dict):
        return None, ('Los datos enviados no son válidos.', None)
    v = {}
    pasos = [
        ('nombre', lambda x: validar_nombre(x, 'nombre', True)),
        ('apellido', lambda x: validar_nombre(x, 'apellido', True)),
        (doc, validar_ci_ruc),
        ('fecha_nacimiento', validar_fecha_nacimiento),
        ('telefono', validar_telefono),
    ]
    if con_emergencia:
        pasos.append(('telefono_emergencia', lambda x: _con_etiqueta(validar_telefono(x), 'teléfono de emergencia')))
    pasos += [('direccion', lambda x: validar_texto(x, 'dirección', _MD)), ('correo', validar_correo)]
    if con_registro:
        pasos.append(('num_registro', lambda x: validar_codigo(x, 'N.º de registro', 30, True)))
    for clave, f in pasos:
        valor, error = f(data.get(clave))
        if error:
            return None, (error, clave)
        v[clave] = valor
    for clave, etiqueta in padres:
        v[clave] = entero_id(data.get(clave))
        if v[clave] is None:
            return None, (f'El campo {etiqueta} es obligatorio.', clave)
    return v, None


def _con_etiqueta(resultado, etiqueta):
    valor, error = resultado
    return valor, (error.replace('teléfono', etiqueta, 1) if error else None)
