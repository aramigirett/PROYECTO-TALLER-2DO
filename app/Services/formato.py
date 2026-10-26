"""
=====================================================
Servicio: formato de montos y cantidades
Descripción: funciones puras (sin Flask ni base de datos) para MOSTRAR montos en todo el sistema (PDFs, mensajes del servidor, Informes, filtros
Jinja). Espejo de `formatearMonto` / `limpiarMonto` de facturacion-validadores.js: si cambia una regla, cambian las dos.
  - Guaraníes sin decimales y con punto como separador de miles: 100000 -> "100.000" (con prefijo: "Gs. 100.000").
  - Las cantidades (stock, unidades) se muestran igual.
  - Para GUARDAR no hay nada que limpiar acá: el navegador manda el entero sin puntos y el servidor lo valida (validar_monto / validar_precio:
    entero >= 0, o > 0 donde corresponda).
Filtros Jinja registrados en app/__init__.py: {{ n|monto }} -> "100.000", {{ n|gs }} -> "Gs. 100.000", {{ n|cantidad }} -> "100.000".
=====================================================
"""
import re
from decimal import Decimal, InvalidOperation

_RE_AGRUPADO = re.compile(r'^-?\d{1,3}(\.\d{3})+$')


def formatear_monto(valor):
    """100000 -> '100.000'; -1500 -> '-1.500'; 1234.6 -> '1.235' (se redondea al entero); None / '' -> ''. Un texto que ya viene agrupado ('100.000')
    se devuelve igual (no se lee como el decimal 100). Un valor que no es numérico se devuelve como texto."""
    if valor is None or valor == '':
        return ''
    if isinstance(valor, str):
        t = valor.strip()
        if not t:
            return ''
        if _RE_AGRUPADO.match(t):
            return t
        try:
            valor = Decimal(t)
        except InvalidOperation:
            return valor
    try:
        n = int(Decimal(valor).quantize(Decimal(1), rounding='ROUND_HALF_UP'))
    except (InvalidOperation, ValueError, TypeError):
        return str(valor)
    return f'{n:,}'.replace(',', '.')


def formatear_gs(valor):
    """100000 -> 'Gs. 100.000'; vacío -> ''."""
    f = formatear_monto(valor)
    return f'Gs. {f}' if f != '' else ''


def formatear_cantidad(valor):
    """Cantidades (stock, unidades): igual que los montos. 1500 -> '1.500'."""
    return formatear_monto(valor)


def limpiar_monto(valor):
    """Espejo de `limpiarMonto` (JS): deja solo los dígitos, sin ceros a la izquierda ('100.000' -> '100000', '007' -> '7', '000' -> '0'); vacío -> ''.
    El servidor NO la usa para guardar (recibe el entero ya limpio y lo valida); existe para comparar JS y Python en los tests."""
    d = re.sub(r'\D', '', '' if valor is None else str(valor))
    if not d:
        return ''
    d = d.lstrip('0')
    return d or '0'
