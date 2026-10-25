"""Validadores clínicos de Consultorio (Ficha Médica).

OJO: estas reglas están duplicadas en app/static/js/consultorio-validadores.js para avisar en el formulario antes de enviar. Si cambia
una regla (o un rango), cambiar los dos archivos y la restricción de la base (chk_ficha_rangos / chk_ficha_presion en
app/dao/referenciales_consultorio/schema_consultorio_etapa3.sql). El servidor valida SIEMPRE; el IMC lo calcula el servidor.

Rangos aprobados: temperatura 30–45 °C; frecuencia cardíaca 20–250 lpm; frecuencia respiratoria 5–80 rpm; presión sistólica 50–300 y
diastólica 30–200 mmHg con sistólica > diastólica; peso 1–500 kg; talla 30–250 cm. No se admite una ficha sin ningún dato.
"""
import datetime
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


# ====================================================================================================================================
# Etapa 4: Diagnóstico y Odontograma
# ====================================================================================================================================
# Nomenclatura FDI: permanentes 11-18, 21-28, 31-38, 41-48; temporales 51-55, 61-65, 71-75, 81-85 (también en chk_detalle_pieza_fdi y
# chk_diagnostico_pieza_fdi de la base y en consultorio-validadores.js).
FDI_PERMANENTES = [c * 10 + n for c in (1, 2, 3, 4) for n in range(1, 9)]
FDI_TEMPORALES = [c * 10 + n for c in (5, 6, 7, 8) for n in range(1, 6)]
FDI_VALIDAS = frozenset(FDI_PERMANENTES + FDI_TEMPORALES)
MSG_PIEZA = ('La pieza dental debe ser un número FDI válido (permanentes 11–18, 21–28, 31–38, 41–48; '
             'temporales 51–55, 61–65, 71–75, 81–85).')
SUPERFICIES = ('O', 'V', 'L', 'M', 'D', 'T')   # T = pieza completa
NOMBRE_SUPERFICIE = {'O': 'oclusal / incisal', 'V': 'vestibular', 'L': 'lingual / palatina', 'M': 'mesial', 'D': 'distal', 'T': 'pieza completa'}
MAX_DESCRIPCION_DX = 1000
MAX_OBSERVACIONES_DX = 2000


def validar_pieza_fdi(valor, obligatoria=False):
    """(número FDI como int|None, error). Acepta un entero o un texto numérico ("18")."""
    if _vacio(valor):
        return (None, MSG_PIEZA) if obligatoria else (None, None)
    if isinstance(valor, bool) or (isinstance(valor, float) and valor != int(valor)):
        return None, MSG_PIEZA
    texto = str(int(valor)) if isinstance(valor, float) else str(valor).strip()
    if not _RE_ENTERO.match(texto) or int(texto) not in FDI_VALIDAS:
        return None, MSG_PIEZA
    return int(texto), None


def validar_superficie(valor):
    """(letra|None, error)."""
    if not isinstance(valor, str) or valor.strip().upper() not in SUPERFICIES:
        return None, 'La superficie debe ser O (oclusal / incisal), V (vestibular), L (lingual / palatina), M (mesial), D (distal) o T (pieza completa).'
    return valor.strip().upper(), None


def validar_diagnostico(data):
    """
    Valida los datos de un diagnóstico (lo que el navegador puede definir). Devuelve (valores, None, None) o (None, mensaje, campo).
    id_tipo_diagnostico: entero positivo. sintomas: lista de ids, AL MENOS UNO, sin repetidos. descripción: obligatoria (hasta 1.000).
    pieza dental: opcional, FDI válida. observaciones: opcionales (hasta 2.000). Paciente, médico, consulta y fecha NO se toman del navegador.
    """
    if not isinstance(data, dict):
        return None, 'Los datos enviados no son válidos.', None
    v = {}
    tipo = data.get('id_tipo_diagnostico')
    if _vacio(tipo):
        return None, 'El tipo de diagnóstico es obligatorio.', 'id_tipo_diagnostico'
    if isinstance(tipo, bool) or not _RE_ENTERO.match(str(tipo).strip()) or int(str(tipo).strip()) <= 0:
        return None, 'El tipo de diagnóstico no es válido.', 'id_tipo_diagnostico'
    v['id_tipo_diagnostico'] = int(str(tipo).strip())

    sintomas = data.get('sintomas')
    if not isinstance(sintomas, list) or not sintomas:
        return None, 'Debe elegir al menos un síntoma.', 'sintomas'
    ids = []
    for s in sintomas:
        if isinstance(s, bool) or not _RE_ENTERO.match(str(s).strip()) or int(str(s).strip()) <= 0:
            return None, 'Los síntomas deben enviarse como una lista de IDs.', 'sintomas'
        ids.append(int(str(s).strip()))
    v['sintomas'] = sorted(set(ids))

    descripcion = data.get('descripcion_diagnostico')
    if _vacio(descripcion) or not isinstance(descripcion, str):
        return None, 'La descripción del diagnóstico es obligatoria.', 'descripcion_diagnostico'
    descripcion = descripcion.strip()
    if len(descripcion) > MAX_DESCRIPCION_DX:
        return None, f'La descripción no puede superar los {MAX_DESCRIPCION_DX} caracteres.', 'descripcion_diagnostico'
    if _RE_CONTROL.search(descripcion):
        return None, 'La descripción contiene caracteres no permitidos.', 'descripcion_diagnostico'
    v['descripcion_diagnostico'] = descripcion

    v['pieza_dental'], e = validar_pieza_fdi(data.get('pieza_dental'))
    if e:
        return None, e, 'pieza_dental'
    observaciones = data.get('observaciones')
    if _vacio(observaciones):
        v['observaciones'] = None
    else:
        if not isinstance(observaciones, str):
            return None, 'Las observaciones deben ser un texto.', 'observaciones'
        observaciones = observaciones.strip()
        if len(observaciones) > MAX_OBSERVACIONES_DX:
            return None, f'Las observaciones no pueden superar los {MAX_OBSERVACIONES_DX} caracteres.', 'observaciones'
        if _RE_CONTROL.search(observaciones):
            return None, 'Las observaciones contienen caracteres no permitidos.', 'observaciones'
        v['observaciones'] = observaciones
    return v, None, None


# ---------------------------------------------------------------------------------------------------------------------
# Etapa 5: Tratamiento y Sesiones (espejo en consultorio-validadores.js: tratamiento / sesion)
# ---------------------------------------------------------------------------------------------------------------------
MAX_DESCRIPCION_TRAT = 1000
MAX_DESCRIPCION_SESION = 1000
MAX_OBSERVACIONES_SESION = 2000
CANTIDAD_INSUMO = (1, 999)
_RE_FECHA = re.compile(r'^(\d{4})-(\d{2})-(\d{2})$')


def _fecha_iso(valor):
    """(texto AAAA-MM-DD | None, error). Una fecha real del calendario, escrita así."""
    if not isinstance(valor, str) or not _RE_FECHA.match(valor.strip()):
        return None, 'inválida'
    texto = valor.strip()
    try:
        datetime.date.fromisoformat(texto)
    except ValueError:
        return None, 'inválida'
    return texto, None


def _id_positivo(valor):
    if isinstance(valor, (bool, float)):
        return None
    texto = str(valor).strip()
    return int(texto) if _RE_ENTERO.match(texto) and int(texto) > 0 else None


def _texto_largo(valor, maximo, obligatorio, vacio_msg, largo_msg, control_msg):
    """(texto|None, error)."""
    if _vacio(valor):
        return (None, vacio_msg) if obligatorio else (None, None)
    if not isinstance(valor, str):
        return None, vacio_msg
    texto = valor.strip()
    if len(texto) > maximo:
        return None, largo_msg
    if _RE_CONTROL.search(texto):
        return None, control_msg
    return texto, None


def validar_tratamiento(data, hoy=None):
    """
    Valida los datos de un tratamiento (lo que el navegador puede definir). Devuelve (valores, None, None) o (None, mensaje, campo).
    id_tipo_tratamiento: entero positivo, obligatorio. descripcion_tratamiento: obligatoria (hasta 1.000). fecha_tratamiento: opcional (sin dato = hoy),
    no puede ser futura. id_diagnostico: opcional, entero positivo. Paciente, médico, consultorio, consulta y estado NO se toman del navegador.
    `hoy` es 'AAAA-MM-DD' (el servidor pasa su fecha).
    """
    if not isinstance(data, dict):
        return None, 'Los datos enviados no son válidos.', None
    hoy = hoy or datetime.date.today().isoformat()
    v = {}
    tipo = data.get('id_tipo_tratamiento')
    if _vacio(tipo):
        return None, 'El tipo de tratamiento es obligatorio.', 'id_tipo_tratamiento'
    v['id_tipo_tratamiento'] = _id_positivo(tipo)
    if v['id_tipo_tratamiento'] is None:
        return None, 'El tipo de tratamiento no es válido.', 'id_tipo_tratamiento'
    descripcion, e = _texto_largo(data.get('descripcion_tratamiento'), MAX_DESCRIPCION_TRAT, True, 'La descripción del tratamiento es obligatoria.',
                                  f'La descripción no puede superar los {MAX_DESCRIPCION_TRAT} caracteres.', 'La descripción contiene caracteres no permitidos.')
    if e:
        return None, e, 'descripcion_tratamiento'
    v['descripcion_tratamiento'] = descripcion
    fecha = data.get('fecha_tratamiento')
    if _vacio(fecha):
        v['fecha_tratamiento'] = hoy
    else:
        texto, e = _fecha_iso(fecha)
        if e:
            return None, 'La fecha del tratamiento no es válida (AAAA-MM-DD).', 'fecha_tratamiento'
        if texto > hoy:
            return None, 'La fecha del tratamiento no puede ser futura.', 'fecha_tratamiento'
        v['fecha_tratamiento'] = texto
    diagnostico = data.get('id_diagnostico')
    if _vacio(diagnostico):
        v['id_diagnostico'] = None
    else:
        v['id_diagnostico'] = _id_positivo(diagnostico)
        if v['id_diagnostico'] is None:
            return None, 'El diagnóstico no es válido.', 'id_diagnostico'
    return v, None, None


def validar_sesion(data, hoy=None):
    """
    Valida los datos de una sesión de tratamiento. Devuelve (valores, None, None) o (None, mensaje, campo).
    procedimientos: lista de ids de tipo de procedimiento, AL MENOS UNO (los repetidos se unifican). descripcion_procedimiento: obligatoria (hasta 1.000).
    observaciones: opcionales (hasta 2.000). proxima_cita: opcional, no anterior a hoy. insumos: lista (puede estar vacía) de {id_insumo, cantidad 1–999},
    sin repetir el mismo insumo. La fecha de la sesión la pone el servidor; consulta y tratamiento se validan en el DAO.
    """
    if not isinstance(data, dict):
        return None, 'Los datos enviados no son válidos.', None
    hoy = hoy or datetime.date.today().isoformat()
    v = {}
    procedimientos = data.get('procedimientos')
    if not isinstance(procedimientos, list) or not procedimientos:
        return None, 'Debe elegir al menos un procedimiento.', 'procedimientos'
    ids = []
    for p in procedimientos:
        i = _id_positivo(p)
        if i is None:
            return None, 'Los procedimientos deben enviarse como una lista de IDs.', 'procedimientos'
        ids.append(i)
    v['procedimientos'] = sorted(set(ids))
    descripcion, e = _texto_largo(data.get('descripcion_procedimiento'), MAX_DESCRIPCION_SESION, True, 'La descripción de la sesión es obligatoria.',
                                  f'La descripción no puede superar los {MAX_DESCRIPCION_SESION} caracteres.', 'La descripción contiene caracteres no permitidos.')
    if e:
        return None, e, 'descripcion_procedimiento'
    v['descripcion_procedimiento'] = descripcion
    observaciones, e = _texto_largo(data.get('observaciones'), MAX_OBSERVACIONES_SESION, False, 'Las observaciones deben ser un texto.',
                                    f'Las observaciones no pueden superar los {MAX_OBSERVACIONES_SESION} caracteres.', 'Las observaciones contienen caracteres no permitidos.')
    if e:
        return None, e, 'observaciones'
    v['observaciones'] = observaciones
    proxima = data.get('proxima_cita')
    if _vacio(proxima):
        v['proxima_cita'] = None
    else:
        texto, e = _fecha_iso(proxima)
        if e:
            return None, 'La próxima cita no es válida (AAAA-MM-DD).', 'proxima_cita'
        if texto < hoy:
            return None, 'La próxima cita no puede ser anterior a hoy.', 'proxima_cita'
        v['proxima_cita'] = texto
    insumos = data.get('insumos')
    if insumos is None:
        insumos = []
    if not isinstance(insumos, list):
        return None, 'Los insumos deben enviarse como una lista.', 'insumos'
    vistos, lista = set(), []
    msg_cantidad = f'La cantidad de cada insumo debe ser un número entero de {CANTIDAD_INSUMO[0]} a {CANTIDAD_INSUMO[1]}.'
    for item in insumos:
        if not isinstance(item, dict) or _id_positivo(item.get('id_insumo')) is None:
            return None, 'Cada insumo necesita su tipo de insumo.', 'insumos'
        n = _id_positivo(item.get('cantidad'))
        if n is None or not CANTIDAD_INSUMO[0] <= n <= CANTIDAD_INSUMO[1]:
            return None, msg_cantidad, 'insumos'
        i = _id_positivo(item['id_insumo'])
        if i in vistos:
            return None, 'No repita el mismo insumo: sume las cantidades en un solo renglón.', 'insumos'
        vistos.add(i)
        lista.append({'id_insumo': i, 'cantidad': n})
    v['insumos'] = sorted(lista, key=lambda x: x['id_insumo'])
    return v, None, None


# ---------------------------------------------------------------------------------------------------------------------
# Etapa 6: Receta y Órdenes de Estudio / de Análisis (espejo en consultorio-validadores.js: receta / ordenEstudio / ordenAnalisis)
# ---------------------------------------------------------------------------------------------------------------------
MAX_INDICACIONES_RECETA = 2000
MAX_TEXTO_MEDICAMENTO = 100
MAX_MOTIVO_ORDEN = 1000
MAX_INDICACIONES_ORDEN = 2000


def _vinculos(data, v):
    """Diagnóstico y tratamiento opcionales (enteros positivos). Devuelve (mensaje, campo) o (None, None)."""
    for campo, etiqueta in (('id_diagnostico', 'El diagnóstico'), ('id_tratamiento', 'El tratamiento')):
        valor = data.get(campo)
        if _vacio(valor):
            v[campo] = None
        else:
            v[campo] = _id_positivo(valor)
            if v[campo] is None:
                return f'{etiqueta} no es válido.', campo
    return None, None


def validar_receta(data):
    """
    Valida los datos de una receta (lo que el navegador puede definir). Devuelve (valores, None, None) o (None, mensaje, campo).
    indicaciones_generales: obligatorias (hasta 2.000). medicamentos: lista de {id_medicamento, dosis, frecuencia, duracion}, AL MENOS UNO, sin repetir el mismo
    medicamento; dosis, frecuencia y duración obligatorias (hasta 100). id_diagnostico / id_tratamiento: opcionales. Paciente, médico, consulta y fecha NO se toman del navegador.
    """
    if not isinstance(data, dict):
        return None, 'Los datos enviados no son válidos.', None
    v = {}
    texto, e = _texto_largo(data.get('indicaciones_generales'), MAX_INDICACIONES_RECETA, True, 'Las indicaciones generales son obligatorias.',
                            f'Las indicaciones generales no pueden superar los {MAX_INDICACIONES_RECETA} caracteres.', 'Las indicaciones generales contienen caracteres no permitidos.')
    if e:
        return None, e, 'indicaciones_generales'
    v['indicaciones_generales'] = texto
    medicamentos = data.get('medicamentos')
    if not isinstance(medicamentos, list) or not medicamentos:
        return None, 'Debe agregar al menos un medicamento.', 'medicamentos'
    vistos, lista = set(), []
    for item in medicamentos:
        if not isinstance(item, dict) or _id_positivo(item.get('id_medicamento')) is None:
            return None, 'Cada medicamento necesita su medicamento.', 'medicamentos'
        fila = {'id_medicamento': _id_positivo(item['id_medicamento'])}
        for campo in ('dosis', 'frecuencia', 'duracion'):
            valor = item.get(campo)
            if _vacio(valor) or not isinstance(valor, str):
                return None, 'Cada medicamento debe tener dosis, frecuencia y duración.', 'medicamentos'
            valor = valor.strip()
            if len(valor) > MAX_TEXTO_MEDICAMENTO:
                return None, f'La dosis, la frecuencia y la duración no pueden superar los {MAX_TEXTO_MEDICAMENTO} caracteres.', 'medicamentos'
            if _RE_CONTROL.search(valor):
                return None, 'La dosis, la frecuencia y la duración contienen caracteres no permitidos.', 'medicamentos'
            fila[campo] = valor
        if fila['id_medicamento'] in vistos:
            return None, 'No repita el mismo medicamento.', 'medicamentos'
        vistos.add(fila['id_medicamento'])
        lista.append(fila)
    v['medicamentos'] = sorted(lista, key=lambda x: x['id_medicamento'])
    mensaje, campo = _vinculos(data, v)
    if mensaje:
        return None, mensaje, campo
    return v, None, None


def _validar_orden(data, campo_tipo, etiqueta_tipo):
    if not isinstance(data, dict):
        return None, 'Los datos enviados no son válidos.', None
    v = {}
    tipo = data.get(campo_tipo)
    if _vacio(tipo):
        return None, f'El {etiqueta_tipo} es obligatorio.', campo_tipo
    v[campo_tipo] = _id_positivo(tipo)
    if v[campo_tipo] is None:
        return None, f'El {etiqueta_tipo} no es válido.', campo_tipo
    motivo, e = _texto_largo(data.get('motivo_orden'), MAX_MOTIVO_ORDEN, True, 'El motivo de la orden es obligatorio.',
                             f'El motivo no puede superar los {MAX_MOTIVO_ORDEN} caracteres.', 'El motivo contiene caracteres no permitidos.')
    if e:
        return None, e, 'motivo_orden'
    v['motivo_orden'] = motivo
    indicaciones, e = _texto_largo(data.get('indicaciones'), MAX_INDICACIONES_ORDEN, False, 'Las indicaciones deben ser un texto.',
                                   f'Las indicaciones no pueden superar los {MAX_INDICACIONES_ORDEN} caracteres.', 'Las indicaciones contienen caracteres no permitidos.')
    if e:
        return None, e, 'indicaciones'
    v['indicaciones'] = indicaciones
    mensaje, campo = _vinculos(data, v)
    if mensaje:
        return None, mensaje, campo
    return v, None, None


def validar_orden_estudio(data):
    """Orden de estudio: tipo de estudio y motivo obligatorios, indicaciones y vínculos (diagnóstico, tratamiento) opcionales."""
    return _validar_orden(data, 'id_tipo_estudio', 'tipo de estudio')


def validar_orden_analisis(data):
    """Orden de análisis: tipo de análisis y motivo obligatorios, indicaciones y vínculos (diagnóstico, tratamiento) opcionales."""
    return _validar_orden(data, 'id_tipo_analisis', 'tipo de análisis')
