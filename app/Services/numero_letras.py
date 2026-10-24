"""
=====================================================
Servicio: Número a letras (guaraníes)
Descripción: convierte un entero (0 a 999.999.999.999) en su texto en español, en mayúsculas, para el
"SON GUARANÍES: ..." de la factura. Función pura, sin dependencias.

Convenciones: el número solo termina en "UNO" (1 -> UNO, 101 -> CIENTO UNO); delante de MIL/MILLÓN/MILLONES se apocopa
(21.000 -> VEINTIÚN MIL, 1.000.000 -> UN MILLÓN, 31.000.000 -> TREINTA Y UN MILLONES); 1.000 -> MIL; 100 -> CIEN.
=====================================================
"""

MAXIMO = 999_999_999_999

_UNIDADES = ['', 'UNO', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE']
_ESPECIALES = {10: 'DIEZ', 11: 'ONCE', 12: 'DOCE', 13: 'TRECE', 14: 'CATORCE', 15: 'QUINCE', 16: 'DIECISÉIS',
               17: 'DIECISIETE', 18: 'DIECIOCHO', 19: 'DIECINUEVE', 20: 'VEINTE', 22: 'VEINTIDÓS', 23: 'VEINTITRÉS',
               24: 'VEINTICUATRO', 25: 'VEINTICINCO', 26: 'VEINTISÉIS', 27: 'VEINTISIETE', 28: 'VEINTIOCHO',
               29: 'VEINTINUEVE'}
_DECENAS = {3: 'TREINTA', 4: 'CUARENTA', 5: 'CINCUENTA', 6: 'SESENTA', 7: 'SETENTA', 8: 'OCHENTA', 9: 'NOVENTA'}
_CENTENAS = {1: 'CIENTO', 2: 'DOSCIENTOS', 3: 'TRESCIENTOS', 4: 'CUATROCIENTOS', 5: 'QUINIENTOS', 6: 'SEISCIENTOS',
             7: 'SETECIENTOS', 8: 'OCHOCIENTOS', 9: 'NOVECIENTOS'}


def _menor_cien(n, apocope):
    """0 < n < 100. `apocope`: 1 -> UN y 21 -> VEINTIÚN (cuando va delante de MIL/MILLONES)."""
    if n < 10:
        return 'UN' if (n == 1 and apocope) else _UNIDADES[n]
    if n == 21:
        return 'VEINTIÚN' if apocope else 'VEINTIUNO'
    if n in _ESPECIALES:
        return _ESPECIALES[n]
    decena, unidad = divmod(n, 10)
    return _DECENAS[decena] + (' Y ' + _menor_cien(unidad, apocope) if unidad else '')


def _menor_mil(n, apocope):
    """0 <= n < 1000."""
    if n == 0:
        return ''
    if n == 100:
        return 'CIEN'
    centena, resto = divmod(n, 100)
    partes = []
    if centena:
        partes.append(_CENTENAS[centena])
    if resto:
        partes.append(_menor_cien(resto, apocope))
    return ' '.join(partes)


def _menor_millon(n, apocope):
    """0 <= n < 1.000.000."""
    if n == 0:
        return ''
    miles, resto = divmod(n, 1000)
    partes = []
    if miles == 1:
        partes.append('MIL')
    elif miles:
        partes.append(_menor_mil(miles, True) + ' MIL')
    if resto:
        partes.append(_menor_mil(resto, apocope))
    return ' '.join(partes)


def numero_a_letras(n):
    """Entero 0..999.999.999.999 -> texto en mayúsculas. ValueError si no es un entero en ese rango."""
    if isinstance(n, bool) or not isinstance(n, int):
        raise ValueError('El número debe ser un entero.')
    if n < 0 or n > MAXIMO:
        raise ValueError(f'El número debe estar entre 0 y {MAXIMO:,}'.replace(',', '.') + '.')
    if n == 0:
        return 'CERO'
    millones, resto = divmod(n, 1_000_000)
    partes = []
    if millones == 1:
        partes.append('UN MILLÓN')
    elif millones:
        partes.append(_menor_millon(millones, True) + ' MILLONES')
    if resto:
        partes.append(_menor_millon(resto, False))
    return ' '.join(partes)


def monto_en_letras(n):
    """Guaraníes para la factura: 200000 -> 'SON GUARANÍES: DOSCIENTOS MIL.'"""
    return f'SON GUARANÍES: {numero_a_letras(int(n))}.'
