"""
=====================================================
Servicio: Generación de PDF del Recibo de Dinero (cobro)
Descripción: arma el PDF al vuelo a partir de los datos guardados en la base (no se persiste ningún archivo). Reutiliza el
patrón y los helpers de factura_pdf_service.py y está dividido igual, para poder mejorar el diseño sin tocar la lógica:
  1. calcular_datos_recibo(cobro)    -> CÁLCULO: dict puro con todo lo que se imprime (formas de cobro con su detalle, total,
                                        total en letras, saldo de la factura después del cobro). Sin ReportLab.
  2. dibujar_recibo(c, datos, copia) -> DIBUJO: solo layout sobre un canvas de ReportLab.
  3. generarReciboPdf(cobro)         -> arma el PDF: ORIGINAL (cliente) y DUPLICADO (archivo).
=====================================================
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from app.Services.numero_letras import monto_en_letras
from app.Services.factura_pdf_service import _partir, _miles, _fecha, MARGEN, ANCHO, ALTO, DER
from app.Services.telefono import formatear_telefono

COPIAS = (('ORIGINAL', 'CLIENTE'), ('DUPLICADO', 'ARCHIVO'))
ETIQUETA_TIPO = {'EFECTIVO': 'Efectivo', 'TARJETA': 'Tarjeta', 'CHEQUE': 'Cheque', 'TRANSFERENCIA': 'Transferencia'}


# ======================================================================================================================
# 1. CÁLCULO (datos)
# ======================================================================================================================
def _detalle_forma(d):
    """Texto del detalle de una forma de cobro (datos de la tarjeta, del cheque o la referencia)."""
    if d['tipo'] == 'TARJETA' and d['tarjeta']:
        t = d['tarjeta']
        tipo = 'Crédito' if t['tipo_tarjeta'] == 'CREDITO' else 'Débito'
        return (f"{tipo} terminada en {t['ultimos_digitos']} · Autorización {t['numero_autorizacion']} · "
                f"{t['entidad_adherida']} ({t['marca']} / {t['emisora']})")
    if d['tipo'] == 'CHEQUE' and d['cheque']:
        c = d['cheque']
        return (f"Cheque N.º {c['numero_cheque']} · {c['emisora']} · Titular: {c['titular']} · "
                f"Emisión {_fecha(c['fecha_emision'])} · Cobro {_fecha(c['fecha_cobro'])}")
    if d['tipo'] == 'TRANSFERENCIA' and d['numero_referencia']:
        return f"Referencia {d['numero_referencia']}"
    return ''


def calcular_datos_recibo(cobro):
    """A partir del dict de CobroDao.getCobroById() arma TODO lo que se imprime, ya formateado. No dibuja nada."""
    empresa = cobro.get('empresa') or {}
    return {
        'numero_recibo': cobro['numero_recibo'],
        'anulado': cobro['estado'] == 'ANULADO',
        'empresa': {k: empresa.get(k, '') for k in ('razon_social', 'ruc', 'direccion', 'telefono', 'actividad_economica')},
        'fecha': _fecha(cobro['fecha'], con_hora=True),
        'cliente': cobro['cliente'],
        'ci_ruc': cobro['ci_ruc'],
        'cajero': cobro['cajero'],
        'concepto': f"Pago de la factura N.º {cobro['numero_factura']}",
        'observacion': cobro.get('observacion') or '',
        'formas': [{'forma': d['forma_cobro'], 'tipo': ETIQUETA_TIPO.get(d['tipo'], d['tipo'] or ''),
                    'detalle': _detalle_forma(d), 'monto': _miles(d['monto'])} for d in cobro['detalle']],
        'total': _miles(cobro['total']),
        'total_letras': monto_en_letras(int(cobro['total'])),
        'saldo_factura': _miles(max(int(cobro['saldo_despues']), 0)),
        'factura_pagada': int(cobro['saldo_despues']) <= 0,
    }


# ======================================================================================================================
# 2. DIBUJO (layout)
# ======================================================================================================================
X_FORMA = MARGEN
X_DETALLE = 5.2 * cm
ANCHO_DETALLE = 10.0 * cm
INTERLINEADO = 0.42 * cm


def _marca_anulado(c):
    c.saveState()
    c.setFillColorRGB(0.8, 0, 0)
    c.setFillAlpha(0.22)
    c.translate(ANCHO / 2, ALTO / 2)
    c.rotate(35)
    c.setFont('Helvetica-Bold', 110)
    c.drawCentredString(0, 0, 'ANULADO')
    c.restoreState()
    c.saveState()
    c.setFillColorRGB(0.8, 0, 0)
    c.setFont('Helvetica-Bold', 12)
    c.drawString(MARGEN, ALTO - MARGEN + 0.2 * cm, '*** ANULADO ***')
    c.restoreState()


def dibujar_recibo(c, datos, copia):
    """Dibuja UNA copia ('ORIGINAL' o 'DUPLICADO') en una página y la cierra con showPage()."""
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
    c.setFont('Helvetica-Bold', 15)
    c.drawCentredString(xc, top - 1.6 * cm, 'RECIBO DE DINERO')
    c.setFont('Helvetica-Bold', 12)
    c.drawCentredString(xc, top - 2.4 * cm, datos['numero_recibo'])

    y = top - 4.2 * cm
    c.setFont('Helvetica', 10)
    c.drawString(MARGEN, y, f"Fecha: {datos['fecha']}")
    c.drawRightString(DER, y, f"Cajero: {datos['cajero']}")
    y -= 0.65 * cm
    c.drawString(MARGEN, y, f"Recibimos de: {datos['cliente']}   (CI/RUC: {datos['ci_ruc']})")
    y -= 0.65 * cm
    c.drawString(MARGEN, y, f"En concepto de: {datos['concepto']}")
    if datos['observacion']:
        y -= 0.65 * cm
        for linea in _partir('Observación: ' + datos['observacion'], 'Helvetica', 10, DER - MARGEN):
            c.drawString(MARGEN, y, linea); y -= 0.5 * cm
        y += 0.5 * cm
    y -= 1.0 * cm

    c.setFont('Helvetica-Bold', 8.5)
    c.drawString(X_FORMA, y, 'Forma de cobro')
    c.drawString(X_DETALLE, y, 'Detalle')
    c.drawRightString(DER, y, 'Monto (Gs.)')
    c.setLineWidth(0.8)
    c.line(MARGEN, y - 0.2 * cm, DER, y - 0.2 * cm)
    y -= 0.8 * cm
    c.setFont('Helvetica', 9)
    for f in datos['formas']:
        partes = _partir(f['detalle'], 'Helvetica', 8, ANCHO_DETALLE) if f['detalle'] else ['']
        c.setFont('Helvetica', 9)
        c.drawString(X_FORMA, y, f['forma'][:26])
        c.drawRightString(DER, y, f['monto'])
        c.setFont('Helvetica', 8)
        for i, p in enumerate(partes):
            c.drawString(X_DETALLE, y - i * INTERLINEADO, p)
        y -= max(len(partes), 1) * INTERLINEADO + 0.25 * cm

    c.line(MARGEN, y, DER, y)
    y -= 0.8 * cm
    c.setFont('Helvetica-Bold', 12)
    c.drawString(X_DETALLE, y, 'TOTAL COBRADO')
    c.drawRightString(DER, y, f"Gs. {datos['total']}")
    y -= 0.8 * cm
    c.setFont('Helvetica', 9.5)
    for linea in _partir(datos['total_letras'], 'Helvetica', 9.5, DER - MARGEN):
        c.drawString(MARGEN, y, linea); y -= 0.45 * cm
    y -= 0.4 * cm
    c.setFont('Helvetica', 9.5)
    c.drawString(MARGEN, y, 'Saldo de la factura después de este cobro: ' + ('Gs. 0 (factura pagada)' if datos['factura_pagada'] else f"Gs. {datos['saldo_factura']}"))

    y -= 3.0 * cm
    c.line(MARGEN + 1.0 * cm, y, MARGEN + 6.5 * cm, y)
    c.line(DER - 6.5 * cm, y, DER - 1.0 * cm, y)
    c.setFont('Helvetica', 8.5)
    c.drawCentredString(MARGEN + 3.75 * cm, y - 0.45 * cm, 'Firma del cajero')
    c.drawCentredString(DER - 3.75 * cm, y - 0.45 * cm, 'Firma del cliente')
    if datos['anulado']:
        _marca_anulado(c)
    c.showPage()


# ======================================================================================================================
# 3. ARMADO
# ======================================================================================================================
def generarReciboPdf(cobro):
    """PDF del recibo a partir del dict de CobroDao.getCobroById(): ORIGINAL y DUPLICADO. Un cobro ANULADO lleva la marca."""
    datos = calcular_datos_recibo(cobro)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"Recibo {datos['numero_recibo']}")
    c.setAuthor(datos['empresa']['razon_social'])
    for copia in COPIAS:
        dibujar_recibo(c, datos, copia)
    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
