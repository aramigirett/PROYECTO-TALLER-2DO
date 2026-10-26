"""
=====================================================
Servicio: Generación de PDF de la Nota de Crédito / Débito
Descripción: arma el PDF al vuelo a partir de los datos guardados en la base (no se persiste ningún archivo). Reutiliza el diseño
compartido de `pdf_base.py` y `factura_pdf_service.py`: mismas columnas Cant. / Código / Descripción / Precio unit. / Exentas / IVA 5% / IVA 10%,
recuadro de factura relacionada y motivo, pie con total, importe en letras, liquidación del IVA, firma/aclaración y copias ORIGINAL y DUPLICADO.
  1. calcular_datos_nota(nota)   -> CÁLCULO: dict puro con todo lo que se imprime (reusa calcular_datos_factura y agrega título,
                                    factura de referencia, motivo y reintegro). Sin ReportLab.
  2. dibujar_factura(c, datos, copia) (del servicio de la factura) -> DIBUJO.
  3. generarNotaPdf(nota)        -> arma el PDF: ORIGINAL (cliente) y DUPLICADO (archivo tributario).
=====================================================
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.Services.factura_pdf_service import calcular_datos_factura, dibujar_factura, _fecha, _miles, COPIAS

TITULOS = {'CREDITO': 'NOTA DE CRÉDITO', 'DEBITO': 'NOTA DE DÉBITO'}


# ======================================================================================================================
# 1. CÁLCULO (datos)
# ======================================================================================================================
def calcular_datos_nota(nota):
    """A partir del dict de NotaCreditoDebitoDao.getNotaById() arma TODO lo que se imprime, ya formateado. No dibuja nada."""
    como_venta = {
        'numero_factura': nota['numero_nota'],
        'estado': nota['estado'],
        'empresa': nota.get('empresa'),
        'timbrado': nota['timbrado'],
        'fecha': nota['fecha'],
        'condicion': 'CONTADO',
        'fecha_vencimiento': None,
        'cliente': nota['cliente'],
        'ci_ruc': nota['ci_ruc'],
        'cajero': nota.get('cajero') or '—',
        'detalle': nota['detalle'],
        'totales': nota['totales'],
        'iva_5': nota['iva_5'],
        'iva_10': nota['iva_10'],
    }
    datos = calcular_datos_factura(como_venta)
    fecha_fact_fmt = _fecha(nota.get('fecha_factura'))
    extra = [
        f"Factura de referencia: N.º {nota['numero_factura']} del {fecha_fact_fmt}",
        f"Motivo: {nota['motivo']}",
    ]
    notas_adicionales = []
    if nota['tipo_nota'] == 'CREDITO' and nota.get('es_devolucion'):
        msg_dev = 'Incluye devolución de mercadería (los ítems devueltos vuelven al stock).'
        extra.append(msg_dev)
        notas_adicionales.append(msg_dev)
    if int(nota.get('monto_reintegro') or 0) > 0:
        msg_reint = f"Reintegro en efectivo al cliente: Gs. {_miles(nota['monto_reintegro'])} (la factura ya estaba pagada)."
        extra.append(msg_reint)
        notas_adicionales.append(msg_reint)

    titulo_doc = TITULOS[nota['tipo_nota']]
    datos.update({
        'titulo': titulo_doc,
        'subtitulo_doc': 'DOCUMENTO DE AJUSTE · ',
        'etiqueta_total': 'TOTAL DE LA NOTA',
        'prefijo_letras': 'Importe en letras — ',
        'mostrar_condicion': False,
        'factura_relacionada': f"N.º {nota['numero_factura']}",
        'fecha_factura': fecha_fact_fmt,
        'titulo_motivo': f"MOTIVO DE LA {titulo_doc}",
        'motivo_nota': nota['motivo'],
        'notas_adicionales': notas_adicionales,
        'lineas_extra': extra,
        'firmas': [('Firma / aclaración del cliente', '')],
    })
    return datos


# ======================================================================================================================
# 3. ARMADO
# ======================================================================================================================
def generarNotaPdf(nota):
    """PDF de la nota a partir del dict de NotaCreditoDebitoDao.getNotaById(): ORIGINAL y DUPLICADO. Una ANULADA lleva la marca."""
    datos = calcular_datos_nota(nota)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"{datos['titulo']} {nota['numero_nota']}")
    c.setAuthor(datos['empresa']['razon_social'])
    for copia in COPIAS:
        dibujar_factura(c, datos, copia)
    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
