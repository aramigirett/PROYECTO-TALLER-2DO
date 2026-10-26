"""Helper central de errores de validación de OdontoClinic.

Estandariza todos los avisos de validación del sistema en 5 tipos:
  1. 'obligatorio' (⚠ "Atención"): El campo "X" es obligatorio.
  2. 'caracteres'  (✗ "Error")   : El campo "X" contiene caracteres no permitidos. Use solo <lo que admite>.
  3. 'duplicado'   (✗ "Error")   : Ya existe <entidad> "VALOR".
  4. 'rango'       (✗ "Error")   : Valor fuera de lo permitido (fechas, montos, saldos, rangos).
  5. 'estado'      (⚠ "Atención"): Operación no permitida en este momento (por el estado del registro).

El servidor devuelve siempre `{success: False, tipo, campo, mensaje, error}` y el cliente lo presenta con
`window.AvisoValidacion` (en `base_tabler.html` y `facturacion-validadores.js`).
"""

TIPO_OBLIGATORIO = 'obligatorio'
TIPO_CARACTERES = 'caracteres'
TIPO_DUPLICADO = 'duplicado'
TIPO_RANGO = 'rango'
TIPO_ESTADO = 'estado'

TIPOS_VALIDACION = (
    TIPO_OBLIGATORIO,
    TIPO_CARACTERES,
    TIPO_DUPLICADO,
    TIPO_RANGO,
    TIPO_ESTADO,
)

META_TIPOS = {
    TIPO_OBLIGATORIO: {'icono': 'warning', 'titulo': 'Atención'},
    TIPO_CARACTERES:  {'icono': 'error',   'titulo': 'Error'},
    TIPO_DUPLICADO:   {'icono': 'error',   'titulo': 'Error'},
    TIPO_RANGO:       {'icono': 'error',   'titulo': 'Error'},
    TIPO_ESTADO:      {'icono': 'warning', 'titulo': 'Atención'},
}

REGLAS_CARACTERES = {
    'simple':   'letras, números y espacios',
    'catalogo': 'letras, números, espacios y puntos',
    'entidad':  'letras, números, espacios, puntos y guiones',
}


def msg_obligatorio(etiqueta):
    """Tipo 1 (⚠ Atención): El campo "X" es obligatorio."""
    return f'El campo "{etiqueta}" es obligatorio.'


def msg_caracteres(etiqueta, admite=REGLAS_CARACTERES['simple']):
    """Tipo 2 (✗ Error): El campo "X" contiene caracteres no permitidos. Use solo <lo que admite>."""
    return f'El campo "{etiqueta}" contiene caracteres no permitidos. Use solo {admite}.'


def msg_duplicado(entidad, valor):
    """Tipo 3 (✗ Error): Ya existe <entidad> "VALOR"."""
    return f'Ya existe {entidad} "{valor}".'


def msg_rango(mensaje):
    """Tipo 4 (✗ Error): Valor fuera de lo permitido (fechas, montos, saldos)."""
    return mensaje


def msg_estado(mensaje):
    """Tipo 5 (⚠ Atención): Operación no permitida en este momento por el estado del registro."""
    return mensaje


_PATRONES_DUPLICADO = (
    'ya existe',
    'duplicad',
    'ya pertenece a otro',
    'ya tiene un usuario',
    'ya está registrado como',
    'se superpone',
    'no puede repetirse',
    'está repetid',
    'no repita',
    'ya está registrado en el odontograma',
    'ya tiene una consulta registrada',
    'ya tiene un odontograma',
)

_PATRONES_ESTADO = (
    'ya está anulad',
    'ya está activ',
    'ya está cerrad',
    'ya fue cerrad',
    'ya fue facturad',
    'ya fue depositad',
    'ya está depositad',
    'ya está pagad',
    'ya está finalizad',
    'ya está completad',
    'ya está emitid',
    'está anulad',
    'está cancelad',
    'está inactiv',
    'inactivos:',
    'no está abiert',
    'ya no está abiert',
    'debe abrir la caja',
    'debe cerrar la apertura',
    'ya está abierta por otro',
    'no admite',
    'no se puede anular',
    'no es posible anular',
    'no se puede emitir',
    'no se puede cancelar',
    'no se puede finalizar',
    'no se puede pasar',
    'no se puede reactivar',
    'ya no se puede',
    'no está en estado',
    'tiene citas',
    'tiene ventas',
    'tiene cobros',
    'tiene movimientos',
    'tiene sesiones',
    'tiene datos clínicos',
    'tiene un tratamiento',
    'tiene ítems',
    'tiene cuentas',
    'propio usuario',
    'único administrador',
    'no está bloqueado',
    'no puede arquear su propia caja',
    'stock insuficiente',
    'cupo disponible',
)

_PATRONES_OBLIGATORIO = (
    'es obligatorio',
    'es obligatoria',
    'son obligatori',
    'debe seleccionar',
    'debe elegir',
    'debe indicar',
    'debe ingresar',
    'debe agregar al menos',
    'indique las fechas',
    'elija ',
    'seleccione ',
    'faltan parámetros',
    'debe tener al menos un dato',
    'necesita su ',
    'debe tener dosis',
)

_PATRONES_CARACTERES = (
    'caracteres no permitidos',
    'solo puede contener',
    'use solo',
)


def inferir_tipo_error(mensaje, status=400):
    """Clasifica un mensaje de error en uno de los 5 tipos estándar."""
    m = (mensaje or '').strip().lower()
    if any(p in m for p in _PATRONES_DUPLICADO):
        return TIPO_DUPLICADO
    if status == 409 or any(p in m for p in _PATRONES_ESTADO):
        return TIPO_ESTADO
    if any(p in m for p in _PATRONES_OBLIGATORIO):
        return TIPO_OBLIGATORIO
    if any(p in m for p in _PATRONES_CARACTERES):
        return TIPO_CARACTERES
    return TIPO_RANGO


def construir_cuerpo_error(mensaje, campo=None, tipo=None, status=400, **extra):
    """Construye el diccionario JSON estándar `{success: False, tipo, campo, mensaje, error, ...}`."""
    tipo_resuelto = tipo if tipo in TIPOS_VALIDACION else inferir_tipo_error(mensaje, status)
    cuerpo = {
        'success': False,
        'tipo': tipo_resuelto,
        'campo': campo,
        'mensaje': mensaje,
        'error': mensaje,
    }
    if extra:
        cuerpo.update(extra)
    return cuerpo
