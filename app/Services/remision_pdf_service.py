"""
=====================================================
Servicio: Generación de PDF de la Nota de Remisión
Descripción: arma el PDF al vuelo a partir de los datos guardados en la base (no se persiste ningún archivo). Reutiliza el
patrón y los helpers de factura_pdf_service.py (igual que recibo_pdf_service.py) y está dividido igual, para poder mejorar el
diseño sin tocar la lógica:
  1. calcular_datos_remision(remision)    -> CÁLCULO: dict puro con todo lo que se imprime. Sin ReportLab.
  2. dibujar_remision(c, datos, copia)    -> DIBUJO: solo layout sobre un canvas de ReportLab (una copia, con las páginas de
                                             continuación que hagan falta si hay muchos ítems).
  3. generarRemisionPdf(remision)         -> arma el PDF: ORIGINAL (cliente) y DUPLICADO (archivo).
=====================================================
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from app.Services.factura_pdf_service import _partir, _miles, _fecha, MARGEN, ANCHO, ALTO, DER
from app.Services.telefono import formatear_telefono

COPIAS = (('ORIGINAL', 'CLIENTE'), ('DUPLICADO', 'ARCHIVO'))


# ======================================================================================================================
# 1. CÁLCULO (datos)
# ======================================================================================================================
def calcular_datos_remision(remision):
    """A partir del dict de RemisionDao.getRemisionById() arma TODO lo que se imprime, ya formateado. No dibuja nada."""
    empresa = remision.get('empresa') or {}
    return {
        'numero_remision': remision['numero_remision'],
        'anulada': remision['estado'] == 'ANULADA',
        'empresa': {k: empresa.get(k, '') for k in ('razon_social', 'ruc', 'direccion', 'telefono', 'actividad_economica')},
        'fecha_emision': _fecha(remision['fecha_emision'], con_hora=True),
        'fecha_traslado': _fecha(remision['fecha_traslado']),
        'motivo': remision['motivo_traslado'],
        'comprobante': f"Factura N.º {remision['numero_factura']}",
        'cliente': remision['cliente'],
        'ci_ruc': remision['ci_ruc'],
        'partida': f"{remision['deposito']} — {remision['ubicacion_deposito']}",
        'llegada': remision['direccion_llegada'],
        'responsable': remision['responsable_traslado'],
        'emitida_por': remision['usuario'],
        'observacion': remision.get('observacion') or '',
        'items': [{'cantidad': _miles(d['cantidad']), 'descripcion': d['item']} for d in remision['detalle']],
        'total_unidades': _miles(remision['total_unidades']),
    }


# ======================================================================================================================
# 2. DIBUJO (layout)
# ======================================================================================================================
X_CANTIDAD = MARGEN
X_DESCRIPCION = 3.6 * cm
ANCHO_DESCRIPCION = DER - X_DESCRIPCION
INTERLINEADO = 0.45 * cm
ALTO_FIRMAS = 4.2 * cm   # espacio que necesita el pie (total y firmas) en la última página


def _marca_anulada(c):
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


def _cabecera(c, datos, copia):
    """Recuadros de empresa y título; devuelve la Y donde sigue el contenido."""
    nombre_copia, destino = copia
    top = ALTO - MARGEN
    c.setLineWidth(0.8)
    c.roundRect(MARGEN, top - 3.2 * cm, 10.4 * cm, 3.2 * cm, 6)
    c.roundRect(MARGEN + 10.7 * cm, top - 3.2 * cm, DER - MARGEN - 10.7 * cm, 3.2 * cm, 6)
    e = datos['empresa']
    y = top - 0.7 * cm
    c.setFont('Helvetica-Bold', 11)
    for linea in _partir(e['razon_social'], 'Helvetica-Bold', 11, 9.8 * cm):
        c.drawString(MARGEN + 0.3 * cm, y, linea); y -= 0.5 * cm
    c.setFont('Helvetica', 9)
    for texto in (f"RUC: {e['ruc']}", e['direccion'], f"Tel.: {formatear_telefono(e['telefono'])}"):
        for linea in _partir(texto, 'Helvetica', 9, 9.8 * cm):
            c.drawString(MARGEN + 0.3 * cm, y, linea); y -= 0.42 * cm
    xc = MARGEN + 10.7 * cm + (DER - MARGEN - 10.7 * cm) / 2
    c.setFont('Helvetica', 8)
    c.drawCentredString(xc, top - 0.5 * cm, f"{nombre_copia} — {destino}")
    c.setFont('Helvetica-Bold', 14)
    c.drawCentredString(xc, top - 1.6 * cm, 'NOTA DE REMISIÓN')
    c.setFont('Helvetica-Bold', 12)
    c.drawCentredString(xc, top - 2.4 * cm, datos['numero_remision'])
    return top - 4.2 * cm


def _encabezado_tabla(c, y):
    c.setFont('Helvetica-Bold', 8.5)
    c.drawString(X_CANTIDAD, y, 'Cantidad')
    c.drawString(X_DESCRIPCION, y, 'Descripción del ítem')
    c.setLineWidth(0.8)
    c.line(MARGEN, y - 0.2 * cm, DER, y - 0.2 * cm)
    return y - 0.8 * cm


def dibujar_remision(c, datos, copia):
    """Dibuja UNA copia ('ORIGINAL' o 'DUPLICADO'); si hay muchos ítems sigue en páginas de continuación. Cierra con showPage()."""
    y = _cabecera(c, datos, copia)
    c.setFont('Helvetica', 10)
    c.drawString(MARGEN, y, f"Fecha de emisión: {datos['fecha_emision']}")
    c.drawRightString(DER, y, f"Fecha de traslado: {datos['fecha_traslado']}")
    renglones = [('Motivo del traslado', datos['motivo']), ('Comprobante de venta', datos['comprobante']),
                 ('Destinatario', f"{datos['cliente']}   (CI/RUC: {datos['ci_ruc']})"),
                 ('Punto de partida', datos['partida']), ('Punto de llegada', datos['llegada']),
                 ('Responsable del traslado', datos['responsable'])]
    if datos['observacion']:
        renglones.append(('Observación', datos['observacion']))
    for etiqueta, valor in renglones:
        y -= 0.62 * cm
        c.setFont('Helvetica-Bold', 9.5)
        c.drawString(MARGEN, y, etiqueta + ':')
        c.setFont('Helvetica', 9.5)
        partes = _partir(valor, 'Helvetica', 9.5, DER - 6.4 * cm)
        for i, p in enumerate(partes):
            c.drawString(6.4 * cm, y - i * 0.45 * cm, p)
        y -= (len(partes) - 1) * 0.45 * cm
    y -= 1.0 * cm

    y = _encabezado_tabla(c, y)
    for it in datos['items']:
        partes = _partir(it['descripcion'], 'Helvetica', 9, ANCHO_DESCRIPCION)
        if y - len(partes) * INTERLINEADO < MARGEN + 1.0 * cm:   # no entra: continúa en otra página
            c.setFont('Helvetica', 8)
            c.drawRightString(DER, MARGEN - 0.2 * cm, '(continúa en la página siguiente)')
            if datos['anulada']:
                _marca_anulada(c)
            c.showPage()
            y = _encabezado_tabla(c, _cabecera(c, datos, copia))
        c.setFont('Helvetica', 9)
        c.drawString(X_CANTIDAD + 0.4 * cm, y, it['cantidad'])
        for i, p in enumerate(partes):
            c.drawString(X_DESCRIPCION, y - i * INTERLINEADO, p)
        y -= len(partes) * INTERLINEADO + 0.12 * cm

    if y - ALTO_FIRMAS < MARGEN:   # el pie no entra: va en una página nueva
        if datos['anulada']:
            _marca_anulada(c)
        c.showPage()
        y = _cabecera(c, datos, copia)
    c.setLineWidth(0.8)
    c.line(MARGEN, y, DER, y)
    y -= 0.7 * cm
    c.setFont('Helvetica-Bold', 10.5)
    c.drawString(X_DESCRIPCION, y, 'TOTAL DE UNIDADES REMITIDAS')
    c.drawRightString(DER, y, datos['total_unidades'])
    y -= 2.4 * cm
    c.line(MARGEN + 1.0 * cm, y, MARGEN + 6.5 * cm, y)
    c.line(DER - 6.5 * cm, y, DER - 1.0 * cm, y)
    c.setFont('Helvetica', 8.5)
    c.drawCentredString(MARGEN + 3.75 * cm, y - 0.45 * cm, 'Firma del responsable del traslado')
    c.drawCentredString(DER - 3.75 * cm, y - 0.45 * cm, 'Recibí conforme (cliente)')
    if datos['anulada']:
        _marca_anulada(c)
    c.showPage()


# ======================================================================================================================
# 3. ARMADO
# ======================================================================================================================
def generarRemisionPdf(remision):
    """PDF de la remisión a partir del dict de RemisionDao.getRemisionById(): ORIGINAL y DUPLICADO. Una ANULADA lleva la marca."""
    datos = calcular_datos_remision(remision)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"Nota de Remisión {datos['numero_remision']}")
    c.setAuthor(datos['empresa']['razon_social'])
    for copia in COPIAS:
        dibujar_remision(c, datos, copia)
    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
