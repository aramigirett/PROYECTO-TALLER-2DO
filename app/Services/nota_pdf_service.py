"""
=====================================================
Servicio: Generación de PDF de la Nota de Crédito / Débito
Descripción: arma el PDF al vuelo a partir de los datos guardados en la base (no se persiste ningún archivo). Reutiliza el diseño
de la factura (factura_pdf_service.py): mismas columnas Exentas / 5% / 10%, pie con total, total en letras y liquidación del IVA, y
copias ORIGINAL y DUPLICADO. Dividido igual, para poder mejorar el diseño sin tocar la lógica:
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
    como_venta = {   # la nota se imprime con el mismo diseño de la factura: se la presenta con la forma que ese cálculo espera
        'numero_factura': nota['numero_nota'], 'estado': nota['estado'], 'empresa': nota.get('empresa'), 'timbrado': nota['timbrado'],
        'fecha': nota['fecha'], 'condicion': 'CONTADO', 'fecha_vencimiento': None, 'cliente': nota['cliente'], 'ci_ruc': nota['ci_ruc'],
        'detalle': nota['detalle'], 'totales': nota['totales'], 'iva_5': nota['iva_5'], 'iva_10': nota['iva_10'],
    }
    datos = calcular_datos_factura(como_venta)
    extra = [f"Factura de referencia: N.º {nota['numero_factura']} del {_fecha(nota['fecha_factura'])}", f"Motivo: {nota['motivo']}"]
    if nota['tipo_nota'] == 'CREDITO' and nota['es_devolucion']:
        extra.append('Incluye devolución de mercadería (los ítems devueltos vuelven al stock).')
    if nota['monto_reintegro'] > 0:
        extra.append(f"Reintegro en efectivo al cliente: Gs. {_miles(nota['monto_reintegro'])} (la factura ya estaba pagada).")
    datos.update({
        'titulo': TITULOS[nota['tipo_nota']],
        'etiqueta_total': 'TOTAL DE LA NOTA',
        'mostrar_condicion': False,
        'lineas_extra': extra,
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
