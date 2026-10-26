"""
=====================================================
Servicio: Generación de PDF de la Factura de Venta
Descripción: arma el PDF al vuelo a partir de los datos guardados en la base (no se persiste ningún archivo). Mismo
patrón que justificativo_pdf_service.py.

Está dividido en tres partes para poder mejorar el diseño sin tocar la lógica:
  1. calcular_datos_factura(venta)   -> CÁLCULO: dict con todo lo que se imprime (columnas Exentas/5%/10%, subtotales,
                                        total, total en letras, liquidación del IVA, textos ya formateados). Sin ReportLab.
  2. dibujar_factura(c, datos, copia) -> DIBUJO: solo layout sobre un canvas de ReportLab (una copia, una o más páginas).
  3. generarFacturaPdf(venta)         -> arma el PDF: ORIGINAL (cliente) y DUPLICADO (archivo tributario).
=====================================================
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.Services.numero_letras import monto_en_letras
from app.Services.telefono import formatear_telefono

COPIAS = (('ORIGINAL', 'CLIENTE'), ('DUPLICADO', 'ARCHIVO TRIBUTARIO'))


# ======================================================================================================================
# 1. CÁLCULO (datos)
# ======================================================================================================================
def _miles(n):
    return f'{int(n):,}'.replace(',', '.')


def _fecha(texto, con_hora=False):
    """'AAAA-MM-DD[ HH:MM:SS]' -> 'DD/MM/AAAA[ HH:MM]'. Devuelve el texto tal cual si no tiene ese formato."""
    if not texto:
        return ''
    try:
        dia = f'{texto[8:10]}/{texto[5:7]}/{texto[0:4]}'
        return dia + (f' {texto[11:16]}' if con_hora and len(texto) >= 16 else '')
    except (IndexError, TypeError):
        return str(texto)


def calcular_datos_factura(venta):
    """
    A partir del dict de VentaDao.getVentaById() arma TODO lo que se imprime, ya formateado. No dibuja nada.
    El precio incluye el IVA: cada renglón va en UNA sola de las columnas Exentas / 5% / 10% según su tasa.
    """
    lineas = []
    for d in venta['detalle']:
        sub = int(d['subtotal'])
        lineas.append({
            'cantidad': str(d['cantidad']),
            'descripcion': d['descripcion'],
            'precio_unitario': _miles(d['precio_unitario']),
            'exenta': _miles(sub) if d['iva'] == 0 else '',
            'gravada_5': _miles(sub) if d['iva'] == 5 else '',
            'gravada_10': _miles(sub) if d['iva'] == 10 else '',
        })
    t = venta['totales']
    iva_5, iva_10 = int(venta['iva_5']), int(venta['iva_10'])
    empresa = venta.get('empresa') or {}
    timbrado = venta['timbrado']
    return {
        'numero_factura': venta['numero_factura'],
        'anulada': venta['estado'] == 'ANULADA',
        'empresa': {
            'razon_social': empresa.get('razon_social', ''), 'ruc': empresa.get('ruc', ''),
            'direccion': empresa.get('direccion', ''), 'telefono': empresa.get('telefono', ''),
            'actividad_economica': empresa.get('actividad_economica', ''),
        },
        'timbrado': {
            'numero': timbrado['numero'],
            'vigencia': f"{_fecha(timbrado['vigencia_desde'])} al {_fecha(timbrado['vigencia_hasta'])}",
        },
        'fecha_emision': _fecha(venta['fecha'], con_hora=True),
        'condicion': 'Crédito' if venta['condicion'] == 'CREDITO' else 'Contado',
        'vencimiento': _fecha(venta.get('fecha_vencimiento')) if venta['condicion'] == 'CREDITO' else '',
        'cliente': venta['cliente'],
        'ci_ruc': venta['ci_ruc'],
        'lineas': lineas,
        'subtotales': {'exenta': _miles(t['exentas']), 'gravada_5': _miles(t['gravadas_5']), 'gravada_10': _miles(t['gravadas_10'])},
        'total': _miles(t['total']),
        'total_letras': monto_en_letras(int(t['total'])),
        'iva': {'iva_5': _miles(iva_5), 'iva_10': _miles(iva_10), 'total': _miles(iva_5 + iva_10)},
    }


# ======================================================================================================================
# 2. DIBUJO (layout)
# ======================================================================================================================
MARGEN = 1.5 * cm
ANCHO, ALTO = A4
DER = ANCHO - MARGEN
# columnas de la tabla (posición X del borde derecho de cada columna numérica)
X_CANT_DER = 2.9 * cm
X_DESC = 3.2 * cm
ANCHO_DESC = 7.6 * cm
X_PRECIO_DER = 12.9 * cm
X_EXENTA_DER = 14.9 * cm
X_G5_DER = 17.0 * cm
X_G10_DER = DER
INTERLINEADO = 0.42 * cm
ALTO_PIE = 5.6 * cm          # espacio que necesita el pie (subtotales, total, letras, IVA)
Y_MIN_FILAS = MARGEN + 1.0 * cm


def _partir(texto, fuente, tam, ancho_max):
    """Parte un texto en líneas que entren en `ancho_max`, respetando palabras (y partiendo las demasiado largas)."""
    lineas, actual = [], ''
    for palabra in str(texto).split():
        while stringWidth(palabra, fuente, tam) > ancho_max:     # palabra más ancha que la columna
            corte = len(palabra)
            while corte > 1 and stringWidth(palabra[:corte], fuente, tam) > ancho_max:
                corte -= 1
            if actual:
                lineas.append(actual); actual = ''
            lineas.append(palabra[:corte]); palabra = palabra[corte:]
        candidata = f'{actual} {palabra}'.strip()
        if stringWidth(candidata, fuente, tam) > ancho_max and actual:
            lineas.append(actual); actual = palabra
        else:
            actual = candidata
    if actual:
        lineas.append(actual)
    return lineas or ['']


def _cabecera(c, datos, copia):
    """Encabezado de cada página: empresa, timbrado, FACTURA y número, datos del cliente. Devuelve la Y siguiente."""
    nombre_copia, destino = copia
    top = ALTO - MARGEN
    c.setLineWidth(0.8)
    c.roundRect(MARGEN, top - 3.6 * cm, 10.4 * cm, 3.6 * cm, 6)
    c.roundRect(MARGEN + 10.7 * cm, top - 3.6 * cm, DER - MARGEN - 10.7 * cm, 3.6 * cm, 6)

    e = datos['empresa']
    y = top - 0.7 * cm
    c.setFont('Helvetica-Bold', 11)
    for linea in _partir(e['razon_social'], 'Helvetica-Bold', 11, 9.8 * cm):
        c.drawString(MARGEN + 0.3 * cm, y, linea); y -= 0.5 * cm
    c.setFont('Helvetica', 9)
    for texto in (f"RUC: {e['ruc']}", e['direccion'], f"Tel.: {formatear_telefono(e['telefono'])}", e['actividad_economica']):
        for linea in _partir(texto, 'Helvetica', 9, 9.8 * cm):
            c.drawString(MARGEN + 0.3 * cm, y, linea); y -= 0.42 * cm

    xc = MARGEN + 10.7 * cm + (DER - MARGEN - 10.7 * cm) / 2
    c.setFont('Helvetica', 8)
    c.drawCentredString(xc, top - 0.5 * cm, f"{nombre_copia} — {destino}")
    c.setFont('Helvetica', 9)
    c.drawCentredString(xc, top - 1.1 * cm, f"TIMBRADO N.º {datos['timbrado']['numero']}")
    c.setFont('Helvetica', 8)
    c.drawCentredString(xc, top - 1.55 * cm, f"Vigencia: {datos['timbrado']['vigencia']}")
    c.setFont('Helvetica-Bold', 16)
    c.drawCentredString(xc, top - 2.4 * cm, datos.get('titulo', 'FACTURA'))   # las notas de crédito/débito reutilizan este diseño
    c.setFont('Helvetica-Bold', 12)
    c.drawCentredString(xc, top - 3.1 * cm, datos['numero_factura'])

    y = top - 4.3 * cm
    c.setFont('Helvetica', 9.5)
    c.drawString(MARGEN, y, f"Fecha de emisión: {datos['fecha_emision']}")
    if datos.get('mostrar_condicion', True):
        condicion = datos['condicion'] + (f"  (vence {datos['vencimiento']})" if datos['vencimiento'] else '')
        c.drawString(MARGEN + 9.2 * cm, y, f"Condición de venta: {condicion}")
    y -= 0.55 * cm
    c.drawString(MARGEN, y, f"Nombre o razón social: {datos['cliente']}")
    y -= 0.55 * cm
    c.drawString(MARGEN, y, f"CI/RUC: {datos['ci_ruc']}")
    for texto in datos.get('lineas_extra', []):   # notas de crédito/débito: factura de referencia, motivo, reintegro
        for linea in _partir(texto, 'Helvetica', 9.5, DER - MARGEN):
            y -= 0.5 * cm
            c.drawString(MARGEN, y, linea)
    return y - 1.0 * cm


def _encabezado_tabla(c, y):
    c.setFont('Helvetica-Bold', 8.5)
    c.drawRightString(X_CANT_DER, y, 'Cant.')
    c.drawString(X_DESC, y, 'Descripción')
    c.drawRightString(X_PRECIO_DER, y, 'Precio unit.')
    c.drawRightString(X_EXENTA_DER, y, 'Exentas')
    c.drawRightString(X_G5_DER, y, '5%')
    c.drawRightString(X_G10_DER, y, '10%')
    c.setLineWidth(0.8)
    c.line(MARGEN, y - 0.2 * cm, DER, y - 0.2 * cm)
    return y - 0.75 * cm


def _marca_anulada(c):
    """Marca 'ANULADA' en rojo, en diagonal, translúcida (la factura anulada se puede descargar igual)."""
    c.saveState()
    c.setFillColorRGB(0.8, 0, 0)
    c.setFillAlpha(0.22)
    c.translate(ANCHO / 2, ALTO / 2)
    c.rotate(35)
    c.setFont('Helvetica-Bold', 110)
    c.drawCentredString(0, 0, 'ANULADA')
    c.restoreState()
    c.saveState()
    c.setFillColorRGB(0.8, 0, 0)
    c.setFont('Helvetica-Bold', 12)
    c.drawString(MARGEN, ALTO - MARGEN + 0.2 * cm, '*** ANULADA ***')
    c.restoreState()


def _pie(c, datos, y):
    c.setLineWidth(0.8)
    c.line(MARGEN, y, DER, y)
    y -= 0.55 * cm
    c.setFont('Helvetica-Bold', 9)
    c.drawString(X_DESC, y, 'SUBTOTALES')
    s = datos['subtotales']
    c.setFont('Helvetica', 9)
    c.drawRightString(X_EXENTA_DER, y, s['exenta'])
    c.drawRightString(X_G5_DER, y, s['gravada_5'])
    c.drawRightString(X_G10_DER, y, s['gravada_10'])
    y -= 0.75 * cm
    c.setFont('Helvetica-Bold', 11)
    c.drawString(X_DESC, y, datos.get('etiqueta_total', 'TOTAL A PAGAR'))
    c.drawRightString(DER, y, f"Gs. {datos['total']}")
    y -= 0.7 * cm
    c.setFont('Helvetica', 9)
    for linea in _partir(datos['total_letras'], 'Helvetica', 9, DER - MARGEN):
        c.drawString(MARGEN, y, linea); y -= 0.45 * cm
    y -= 0.25 * cm
    iva = datos['iva']
    c.setFont('Helvetica-Bold', 9)
    c.drawString(MARGEN, y, 'LIQUIDACIÓN DEL IVA:')
    c.setFont('Helvetica', 9)
    c.drawString(MARGEN + 4.0 * cm, y, f"(5%) {iva['iva_5']}")
    c.drawString(MARGEN + 8.0 * cm, y, f"(10%) {iva['iva_10']}")
    c.drawString(MARGEN + 12.0 * cm, y, f"TOTAL IVA: {iva['total']}")
    return y


def dibujar_factura(c, datos, copia):
    """
    Dibuja UNA copia ('ORIGINAL' o 'DUPLICADO') en el canvas: una página, o más si hay muchos renglones (cada página repite
    la cabecera; el pie va solo en la última). Termina cada página con showPage().
    """
    y = _encabezado_tabla(c, _cabecera(c, datos, copia))
    c.setFont('Helvetica', 9)
    for linea in datos['lineas']:
        partes = _partir(linea['descripcion'], 'Helvetica', 9, ANCHO_DESC)
        alto = len(partes) * INTERLINEADO
        if y - alto < Y_MIN_FILAS:                      # continúa en otra página
            if datos['anulada']:
                _marca_anulada(c)
            c.showPage()
            y = _encabezado_tabla(c, _cabecera(c, datos, copia))
        c.setFont('Helvetica', 9)
        c.drawRightString(X_CANT_DER, y, linea['cantidad'])
        for i, parte in enumerate(partes):
            c.drawString(X_DESC, y - i * INTERLINEADO, parte)
        c.drawRightString(X_PRECIO_DER, y, linea['precio_unitario'])
        c.drawRightString(X_EXENTA_DER, y, linea['exenta'])
        c.drawRightString(X_G5_DER, y, linea['gravada_5'])
        c.drawRightString(X_G10_DER, y, linea['gravada_10'])
        y -= alto + 0.12 * cm
    if y - ALTO_PIE < MARGEN:                           # el pie no entra: va en una página nueva
        if datos['anulada']:
            _marca_anulada(c)
        c.showPage()
        y = _encabezado_tabla(c, _cabecera(c, datos, copia))
    _pie(c, datos, y)
    if datos['anulada']:
        _marca_anulada(c)
    c.showPage()


# ======================================================================================================================
# 3. ARMADO
# ======================================================================================================================
def generarFacturaPdf(venta):
    """
    PDF de la factura a partir del dict de VentaDao.getVentaById(): ORIGINAL (cliente) y DUPLICADO (archivo tributario),
    una página cada uno para una factura chica. Si la venta está ANULADA lleva la marca "ANULADA" en rojo.
    Retorna los bytes del PDF.
    """
    datos = calcular_datos_factura(venta)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"Factura {datos['numero_factura']}")
    c.setAuthor(datos['empresa']['razon_social'])
    for copia in COPIAS:
        dibujar_factura(c, datos, copia)
    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
