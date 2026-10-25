"""Validadores clínicos de Consultorio (Ficha Médica).

OJO: estas reglas están duplicadas en app/static/js/consultorio-validadores.js para avisar en el formulario antes de enviar. Si cambia
una regla (o un rango), cambiar los dos archivos y la restricción de la base (chk_ficha_rangos / chk_ficha_presion en
app/dao/referenciales_consultorio/schema_consultorio_etapa3.sql). El servidor valida SIEMPRE; el IMC lo calcula el servidor.

Rangos aprobados: temperatura 30–45 °C; frecuencia cardíaca 20–250 lpm; frecuencia respiratoria 5–80 rpm; presión sistólica 50–300 y
diastólica 30–200 mmHg con sistólica > diastólica; peso 1–500 kg; talla 30–250 cm. No se admite una ficha sin ningún dato.
"""
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

RANGOS = {
    'temperatura': (Decimal(30), Decimal(45)),
    'frecuencia_cardiaca': (20, 250),
    'frecuencia_respiratoria': (5, 80),
    'peso': (Decimal(1), Decimal(500)),
    'talla': (Decimal(30), Decimal(250)),
}
PRESION_SISTOLICA = (50, 300)
PRESION_DIASTOLICA = (30, 200)
MAX_TEXTO = 2000
CAMPOS_TEXTO = {
    'examen_fisico_general': 'El examen físico general',
    'examen_bucal': 'El examen bucal',
    'observaciones_medico': 'Las observaciones del médico',
}
# Los campos que cuentan como "dato" (el IMC se calcula, no se carga)
CAMPOS_DATO = ('presion_arterial', 'temperatura', 'frecuencia_cardiaca', 'frecuencia_respiratoria', 'peso', 'talla',
               'examen_fisico_general', 'examen_bucal', 'observaciones_medico')

_RE_NUMERO = re.compile(r'^\d+([.,]\d+)?$')
_RE_ENTERO = re.compile(r'^\d+$')
_RE_PRESION = re.compile(r'^(\d{2,3})\s*/\s*(\d{2,3})$')
_RE_CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')   # se permiten salto de línea y tabulación en los textos largos


def _vacio(valor):
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _decimal(valor, minimo, maximo, mensaje):
    """(Decimal|None, error). Hasta 2 decimales (coma o punto), dentro del rango."""
    if _vacio(valor):
        return None, None
    if isinstance(valor, bool):
        return None, mensaje
    texto = str(valor).strip()
    if isinstance(valor, float):
        texto = repr(valor)
    if not _RE_NUMERO.match(texto):
        return None, mensaje
    try:
        n = Decimal(texto.replace(',', '.'))
    except InvalidOperation:
        return None, mensaje
    if n.as_tuple().exponent < -2 or not minimo <= n <= maximo:
        return None, mensaje
    return n, None


def _entero(valor, minimo, maximo, mensaje):
    if _vacio(valor):
        return None, None
    if isinstance(valor, bool) or (isinstance(valor, float) and valor != int(valor)):
        return None, mensaje
    texto = str(int(valor)) if isinstance(valor, float) else str(valor).strip()
    if not _RE_ENTERO.match(texto):
        return None, mensaje
    n = int(texto)
    return (n, None) if minimo <= n <= maximo else (None, mensaje)


def calcular_imc(peso, talla_cm):
    """IMC = peso / (talla en metros)², 2 decimales (mitad hacia arriba). None si falta el peso o la talla."""
    if peso is None or talla_cm is None:
        return None
    metros = Decimal(talla_cm) / Decimal(100)
    return (Decimal(peso) / (metros * metros)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def validar_presion(valor):
    """(texto 'SSS/DDD'|None, error)."""
    if _vacio(valor):
        return None, None
    if not isinstance(valor, str):
        return None, 'La presión arterial debe tener el formato sistólica/diastólica (ej.: 120/80).'
    m = _RE_PRESION.match(valor.strip())
    if not m:
        return None, 'La presión arterial debe tener el formato sistólica/diastólica (ej.: 120/80).'
    sis, dia = int(m.group(1)), int(m.group(2))
    if not PRESION_SISTOLICA[0] <= sis <= PRESION_SISTOLICA[1]:
        return None, f'La presión sistólica debe estar entre {PRESION_SISTOLICA[0]} y {PRESION_SISTOLICA[1]} mmHg.'
    if not PRESION_DIASTOLICA[0] <= dia <= PRESION_DIASTOLICA[1]:
        return None, f'La presión diastólica debe estar entre {PRESION_DIASTOLICA[0]} y {PRESION_DIASTOLICA[1]} mmHg.'
    if sis <= dia:
        return None, 'La presión sistólica debe ser mayor que la diastólica.'
    return f'{sis}/{dia}', None


def validar_texto_clinico(valor, campo):
    """Texto largo opcional. (texto|None, error)."""
    if _vacio(valor):
        return None, None
    if not isinstance(valor, str):
        return None, f'{CAMPOS_TEXTO[campo]} debe ser un texto.'
    texto = valor.strip()
    if len(texto) > MAX_TEXTO:
        return None, f'{CAMPOS_TEXTO[campo]} no puede superar los {MAX_TEXTO} caracteres.'
    if _RE_CONTROL.search(texto):
        return None, f'{CAMPOS_TEXTO[campo]} contiene caracteres no permitidos.'
    return texto, None


def validar_ficha(data):
    """
    Valida los datos de una ficha médica. Devuelve (valores, None, None) o (None, mensaje, campo).
    `valores` trae las 9 claves de CAMPOS_DATO (None = sin dato) más `imc` (calculado acá; el que mande el navegador se ignora).
    """
    if not isinstance(data, dict):
        return None, 'Los datos enviados no son válidos.', None
    v = {}
    v['presion_arterial'], e = validar_presion(data.get('presion_arterial'))
    if e:
        return None, e, 'presion_arterial'
    v['temperatura'], e = _decimal(data.get('temperatura'), *RANGOS['temperatura'],
                                   'La temperatura debe ser un número entre 30 y 45 (°C), con hasta 2 decimales.')
    if e:
        return None, e, 'temperatura'
    v['frecuencia_cardiaca'], e = _entero(data.get('frecuencia_cardiaca'), *RANGOS['frecuencia_cardiaca'],
                                          'La frecuencia cardíaca debe ser un número entero entre 20 y 250 (lpm).')
    if e:
        return None, e, 'frecuencia_cardiaca'
    v['frecuencia_respiratoria'], e = _entero(data.get('frecuencia_respiratoria'), *RANGOS['frecuencia_respiratoria'],
                                              'La frecuencia respiratoria debe ser un número entero entre 5 y 80 (rpm).')
    if e:
        return None, e, 'frecuencia_respiratoria'
    v['peso'], e = _decimal(data.get('peso'), *RANGOS['peso'], 'El peso debe ser un número entre 1 y 500 (kg), con hasta 2 decimales.')
    if e:
        return None, e, 'peso'
    v['talla'], e = _decimal(data.get('talla'), *RANGOS['talla'], 'La talla debe ser un número entre 30 y 250 (cm), con hasta 2 decimales.')
    if e:
        return None, e, 'talla'
    for campo in CAMPOS_TEXTO:
        v[campo], e = validar_texto_clinico(data.get(campo), campo)
        if e:
            return None, e, campo
    if all(v[c] is None for c in CAMPOS_DATO):
        return None, 'La ficha debe tener al menos un dato.', 'ficha'
    v['imc'] = calcular_imc(v['peso'], v['talla'])
    return v, None, None
