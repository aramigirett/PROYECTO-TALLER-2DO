"""
=====================================================
Servicio: Generación de PDF para el Pedido de Cliente
Descripción: Arma el PDF al vuelo a partir de los datos guardados en la base
(no se persiste ningún archivo). Mismo patrón que justificativo_pdf_service.py.
=====================================================
"""
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


def _gs(n):
    return 'Gs. ' + f'{int(n):,}'.replace(',', '.')


def _recortar(texto, largo):
    texto = str(texto or '')
    return texto if len(texto) <= largo else texto[:largo - 1] + '…'


def _wrap(texto, ancho_max):
    lineas, actual = [], ''
    for palabra in str(texto or '').split():
        candidata = f'{actual} {palabra}'.strip()
        if len(candidata) > ancho_max and actual:
            lineas.append(actual)
            actual = palabra
        else:
            actual = candidata
    if actual:
        lineas.append(actual)
    return lineas or ['-']


def generarPedidoPdf(pedido):
    """
    Genera el PDF de un pedido a partir del dict de PedidoClienteDao.getPedidoById(). Un pedido ANULADO se marca
    visiblemente (no se bloquea la descarga: sirve de respaldo). Retorna los bytes del PDF.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    ancho, alto = A4
    izq, der = 2 * cm, ancho - 2 * cm
    x_cant, x_precio, x_iva, x_sub = 11.2 * cm, 14.2 * cm, 15.6 * cm, der

    def encabezado_tabla(y):
        c.setFont("Helvetica-Bold", 9)
        c.drawString(izq, y, "Ítem")
        c.drawRightString(x_cant, y, "Cant.")
        c.drawRightString(x_precio, y, "Precio")
        c.drawRightString(x_iva, y, "IVA")
        c.drawRightString(x_sub, y, "Subtotal")
        c.line(izq, y - 0.2 * cm, der, y - 0.2 * cm)
        return y - 0.8 * cm

    y = alto - 2.5 * cm
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(ancho / 2, y, f"PEDIDO DE CLIENTE N.º {pedido['id_pedido']}")
    y -= 1 * cm

    if pedido.get('estado') == 'ANULADO':
        c.setFillColorRGB(0.8, 0, 0)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(ancho / 2, y, "*** ANULADO ***")
        c.setFillColorRGB(0, 0, 0)
        y -= 1 * cm

    c.setFont("Helvetica", 10)
    fecha = pedido.get('fecha_pedido') or ''
    try:
        fecha = datetime.strptime(fecha, '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
    except ValueError:
        pass
    for linea in (f"Fecha: {fecha}", f"Cliente: {pedido.get('cliente', '-')}",
                  f"CI/RUC: {pedido.get('ci_ruc', '-')}", f"Cajero: {pedido.get('cajero', '-')}",
                  f"Estado: {pedido.get('estado', '-')}"):
        c.drawString(izq, y, linea)
        y -= 0.6 * cm
    if pedido.get('observacion'):
        for i, linea in enumerate(_wrap(pedido['observacion'], 95)):
            c.drawString(izq, y, ('Observación: ' if i == 0 else '') + linea if i == 0 else '    ' + linea)
            y -= 0.5 * cm
    y -= 0.4 * cm
    y = encabezado_tabla(y)

    c.setFont("Helvetica", 9)
    for d in pedido.get('detalle', []):
        if y < 6 * cm:
            c.showPage()
            y = encabezado_tabla(alto - 2.5 * cm)
            c.setFont("Helvetica", 9)
        c.drawString(izq, y, _recortar(d['item'], 48))
        c.drawRightString(x_cant, y, str(d['cantidad']))
        c.drawRightString(x_precio, y, _gs(d['precio_unitario']))
        c.drawRightString(x_iva, y, 'Exenta' if d['iva'] == 0 else f"{d['iva']}%")
        c.drawRightString(x_sub, y, _gs(d['subtotal']))
        y -= 0.55 * cm

    if y < 6 * cm:
        c.showPage()
        y = alto - 2.5 * cm
    t = pedido.get('totales') or {}
    y -= 0.2 * cm
    c.line(izq, y, der, y)
    y -= 0.7 * cm
    c.setFont("Helvetica", 10)
    for etiqueta, valor in (("Exentas", t.get('exentas', 0)), ("Gravadas 5%", t.get('gravadas_5', 0)),
                            ("Gravadas 10%", t.get('gravadas_10', 0))):
        c.drawString(11 * cm, y, etiqueta)
        c.drawRightString(der, y, _gs(valor))
        y -= 0.55 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(11 * cm, y, "TOTAL")
    c.drawRightString(der, y, _gs(t.get('total', pedido.get('total', 0))))
    y -= 0.9 * cm
    c.setFont("Helvetica", 9)
    c.drawString(11 * cm, y, "IVA liquidado (precios con IVA incluido)")
    y -= 0.5 * cm
    for etiqueta, valor in (("IVA 5%", t.get('iva_5', 0)), ("IVA 10%", t.get('iva_10', 0)),
                            ("Total IVA", t.get('total_iva', 0))):
        c.drawString(11 * cm, y, etiqueta)
        c.drawRightString(der, y, _gs(valor))
        y -= 0.45 * cm

    c.showPage()
    c.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
