"""
=====================================================
Servicio: Generación de PDF del Arqueo de Caja
Descripción: arma el PDF al vuelo a partir de los datos guardados en la base (no se persiste ningún archivo). Reutiliza el patrón y los
helpers de factura_pdf_service.py (igual que recibo_pdf_service.py) y está dividido igual, para poder mejorar el diseño sin tocar la lógica:
  1. calcular_datos_arqueo(arqueo)    -> CÁLCULO: dict puro con todo lo que se imprime (formas con sistema / contado / diferencia, resultado,
                                         recaudación a depositar). Sin ReportLab.
  2. dibujar_arqueo(c, datos, copia)  -> DIBUJO: solo layout sobre un canvas de ReportLab.
  3. generarArqueoPdf(arqueo)         -> arma el PDF: ORIGINAL y DUPLICADO.
=====================================================
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from app.Services.factura_pdf_service import _partir, _miles, _fecha, MARGEN, ANCHO, ALTO, DER

COPIAS = (('ORIGINAL', 'ARCHIVO'), ('DUPLICADO', 'CAJERO'))
ETIQUETA_TIPO = {'EFECTIVO': 'Efectivo', 'TARJETA': 'Tarjeta', 'CHEQUE': 'Cheque', 'TRANSFERENCIA': 'Transferencia'}
ETIQUETA_RESULTADO = {'CUADRA': 'LA CAJA CUADRA', 'SOBRANTE': 'SOBRANTE', 'FALTANTE': 'FALTANTE'}


# ======================================================================================================================
# 1. CÁLCULO (datos)
# ======================================================================================================================
def _signo(n):
    n = int(n)
    return ('+' if n > 0 else ('-' if n < 0 else '')) + _miles(abs(n))


def calcular_datos_arqueo(arqueo):
    """A partir del dict de ArqueoDao.getArqueoById() arma TODO lo que se imprime, ya formateado. No dibuja nada."""
    empresa = arqueo.get('empresa') or {}
    rec = arqueo.get('recaudacion')
    return {
        'numero': f"Arqueo N.º {arqueo['id_arqueo']}",
        'anulado': arqueo['estado'] == 'ANULADO',
        'empresa': {k: empresa.get(k, '') for k in ('razon_social', 'ruc', 'direccion', 'telefono', 'actividad_economica')},
        'fecha': _fecha(arqueo['fecha_arqueo'], con_hora=True),
        'caja': arqueo['caja'],
        'cajero': arqueo['cajero'],
        'arqueador': arqueo['arqueador'],
        'apertura': f"{_fecha(arqueo['fecha_apertura'], con_hora=True)}  —  cierre {_fecha(arqueo['fecha_cierre'], con_hora=True)}",
        'fondo': _miles(arqueo['monto_apertura']),
        'formas': [{'forma': d['forma_cobro'], 'tipo': ETIQUETA_TIPO.get(d['tipo'], d['tipo'] or ''), 'sistema': _miles(d['monto_sistema']),
                    'contado': _miles(d['monto_contado']), 'diferencia': _signo(d['diferencia']) if d['diferencia'] else '0'} for d in arqueo['detalle']],
        'total_sistema': _miles(arqueo['total_sistema']),
        'total_contado': _miles(arqueo['total_contado']),
        'total_diferencia': _signo(arqueo['diferencia']) if arqueo['diferencia'] else '0',
        'resultado': ETIQUETA_RESULTADO.get(arqueo['resultado'], arqueo['resultado']),
        'observacion': arqueo.get('observacion') or '',
        'recaudacion': None if not rec else {
            'efectivo': _miles(rec['monto_efectivo']), 'cheque': _miles(rec['monto_cheque']), 'total': _miles(rec['total']), 'estado': rec['estado'],
            'deposito': (f"Depositada el {_fecha(rec['fecha_deposito'])} en {rec['cuenta']} (boleta {rec['numero_boleta']})" if rec['estado'] == 'DEPOSITADA' else ''),
        },
    }


# ======================================================================================================================
# 2. DIBUJO (layout)
# ======================================================================================================================
X_FORMA = MARGEN
X_SISTEMA = 10.2 * cm
X_CONTADO = 13.8 * cm
X_DIF = DER


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


def dibujar_arqueo(c, datos, copia):
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
    for texto in (f"RUC: {e['ruc']}", e['direccion'], f"Tel.: {e['telefono']}"):
        for linea in _partir(texto, 'Helvetica', 9, 9.8 * cm):
            c.drawString(MARGEN + 0.3 * cm, y, linea); y -= 0.42 * cm
    xc = MARGEN + 10.7 * cm + (DER - MARGEN - 10.7 * cm) / 2
    c.setFont('Helvetica', 8)
    c.drawCentredString(xc, top - 0.5 * cm, f"{nombre_copia} — {destino}")
    c.setFont('Helvetica-Bold', 15)
    c.drawCentredString(xc, top - 1.6 * cm, 'ARQUEO DE CAJA')
    c.setFont('Helvetica-Bold', 12)
    c.drawCentredString(xc, top - 2.4 * cm, datos['numero'])

    y = top - 4.2 * cm
    for etiqueta, valor in (('Fecha del arqueo', datos['fecha']), ('Caja', datos['caja']), ('Cajero', datos['cajero']),
                            ('Apertura', datos['apertura']), ('Fondo inicial', 'Gs. ' + datos['fondo']), ('Arqueado por', datos['arqueador'])):
        c.setFont('Helvetica-Bold', 9.5)
        c.drawString(MARGEN, y, etiqueta + ':')
        c.setFont('Helvetica', 9.5)
        c.drawString(MARGEN + 3.6 * cm, y, valor)
        y -= 0.55 * cm
    y -= 0.6 * cm

    c.setFont('Helvetica-Bold', 8.5)
    c.drawString(X_FORMA, y, 'Forma de cobro')
    c.drawRightString(X_SISTEMA, y, 'Sistema (Gs.)')
    c.drawRightString(X_CONTADO, y, 'Contado (Gs.)')
    c.drawRightString(X_DIF, y, 'Diferencia (Gs.)')
    c.setLineWidth(0.8)
    c.line(MARGEN, y - 0.2 * cm, DER, y - 0.2 * cm)
    y -= 0.8 * cm
    c.setFont('Helvetica', 9)
    for f in datos['formas']:
        c.drawString(X_FORMA, y, f['forma'][:34])
        c.drawRightString(X_SISTEMA, y, f['sistema'])
        c.drawRightString(X_CONTADO, y, f['contado'])
        c.drawRightString(X_DIF, y, f['diferencia'])
        y -= 0.55 * cm
    c.line(MARGEN, y + 0.2 * cm, DER, y + 0.2 * cm)
    y -= 0.35 * cm
    c.setFont('Helvetica-Bold', 10)
    c.drawString(X_FORMA, y, 'TOTAL')
    c.drawRightString(X_SISTEMA, y, datos['total_sistema'])
    c.drawRightString(X_CONTADO, y, datos['total_contado'])
    c.drawRightString(X_DIF, y, datos['total_diferencia'])
    y -= 0.9 * cm
    c.setFont('Helvetica-Bold', 11)
    c.drawString(MARGEN, y, 'Resultado: ' + datos['resultado'])
    y -= 0.7 * cm
    if datos['observacion']:
        c.setFont('Helvetica-Bold', 9.5)
        c.drawString(MARGEN, y, 'Observación:')
        c.setFont('Helvetica', 9.5)
        for linea in _partir(datos['observacion'], 'Helvetica', 9.5, DER - MARGEN - 3.0 * cm):
            c.drawString(MARGEN + 3.0 * cm, y, linea); y -= 0.45 * cm
        y -= 0.3 * cm

    y -= 0.3 * cm
    c.setFont('Helvetica-Bold', 10)
    c.drawString(MARGEN, y, 'RECAUDACIÓN A DEPOSITAR')
    y -= 0.6 * cm
    c.setFont('Helvetica', 9.5)
    r = datos['recaudacion']
    if r is None:
        c.drawString(MARGEN, y, 'No hay recaudación a depositar (sin efectivo sobre el fondo inicial ni cheques).')
    else:
        c.drawString(MARGEN, y, f"Efectivo: Gs. {r['efectivo']}      Cheques: Gs. {r['cheque']}      Total: Gs. {r['total']}      Estado: {r['estado']}")
        if r['deposito']:
            y -= 0.5 * cm
            for linea in _partir(r['deposito'], 'Helvetica', 9.5, DER - MARGEN):
                c.drawString(MARGEN, y, linea); y -= 0.45 * cm
    y -= 3.0 * cm
    c.line(MARGEN + 1.0 * cm, y, MARGEN + 6.5 * cm, y)
    c.line(DER - 6.5 * cm, y, DER - 1.0 * cm, y)
    c.setFont('Helvetica', 8.5)
    c.drawCentredString(MARGEN + 3.75 * cm, y - 0.45 * cm, 'Firma de quien arquea')
    c.drawCentredString(DER - 3.75 * cm, y - 0.45 * cm, 'Firma del cajero')
    if datos['anulado']:
        _marca_anulado(c)
    c.showPage()


# ======================================================================================================================
# 3. ARMADO
# ======================================================================================================================
def generarArqueoPdf(arqueo):
    """PDF del arqueo a partir del dict de ArqueoDao.getArqueoById(): ORIGINAL y DUPLICADO. Un arqueo ANULADO lleva la marca."""
    datos = calcular_datos_arqueo(arqueo)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"Arqueo de caja {datos['numero']}")
    c.setAuthor(datos['empresa']['razon_social'])
    for copia in COPIAS:
        dibujar_arqueo(c, datos, copia)
    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
