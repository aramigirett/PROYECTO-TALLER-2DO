"""
=====================================================
Servicio: Generación de PDF del Recibo de Dinero (cobro)
Descripción: arma el PDF al vuelo a partir de los datos guardados en la base (no se persiste ningún archivo).
Usa la plantilla base única `app/Services/pdf_base.py` y está dividido en tres capas:
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
from app.Services.pdf_base import (
    ANCHO_UTIL,
    COLOR_FONDO_SUBTOTAL,
    COLOR_BORDE,
    COLOR_TEXTO,
    normalizar_empresa,
    dibujar_encabezado,
    dibujar_barra_seccion,
    dibujar_cuadro_datos,
    dibujar_encabezado_tabla,
    calcular_alto_fila_tabla,
    dibujar_fila_tabla,
    dibujar_marca_agua,
    dibujar_firmas,
    dibujar_pie_pagina,
)

COPIAS = (('ORIGINAL', 'CLIENTE'), ('DUPLICADO', 'ARCHIVO'))
ETIQUETA_TIPO = {'EFECTIVO': 'Efectivo', 'TARJETA': 'Tarjeta', 'CHEQUE': 'Cheque', 'TRANSFERENCIA': 'Transferencia'}

COLUMNAS_RECIBO = (
    ('Forma de cobro', 4.20 * cm, 'L'),
    ('Modalidad', 2.60 * cm, 'C'),
    ('Detalle / Referencia', 8.20 * cm, 'L'),
    ('Monto (Gs.)', 3.00 * cm, 'R'),
)

Y_MIN_FILAS = 2.0 * cm
ALTO_PIE_RECIBO = 5.4 * cm


# ======================================================================================================================
# 1. CÁLCULO (datos)
# ======================================================================================================================
def _detalle_forma(d):
    """Texto del detalle de una forma de cobro (datos de la tarjeta, del cheque o la referencia)."""
    if d['tipo'] == 'TARJETA' and d['tarjeta']:
        t = d['tarjeta']
        tipo = 'Crédito' if t['tipo_tarjeta'] == 'CREDITO' else 'Débito'
        return (
            f"{tipo} terminada en {t['ultimos_digitos']} · Autorización {t['numero_autorizacion']} · "
            f"{t['entidad_adherida']} ({t['marca']} / {t['emisora']})"
        )
    if d['tipo'] == 'CHEQUE' and d['cheque']:
        c = d['cheque']
        return (
            f"Cheque N.º {c['numero_cheque']} · {c['emisora']} · Titular: {c['titular']} · "
            f"Emisión {_fecha(c['fecha_emision'])} · Cobro {_fecha(c['fecha_cobro'])}"
        )
    if d['tipo'] == 'TRANSFERENCIA' and d['numero_referencia']:
        return f"Referencia {d['numero_referencia']}"
    return 'Cobro en efectivo en caja'


def calcular_datos_recibo(cobro):
    """A partir del dict de CobroDao.getCobroById() arma TODO lo que se imprime, ya formateado. No dibuja nada."""
    empresa = normalizar_empresa(cobro.get('empresa'))
    return {
        'numero_recibo': cobro['numero_recibo'],
        'anulado': cobro['estado'] == 'ANULADO',
        'empresa': empresa,
        'fecha': _fecha(cobro['fecha'], con_hora=True),
        'cliente': cobro['cliente'],
        'ci_ruc': cobro['ci_ruc'],
        'cajero': cobro['cajero'],
        'concepto': f"Pago de la factura N.º {cobro['numero_factura']}",
        'observacion': cobro.get('observacion') or '',
        'formas': [
            {
                'forma': d['forma_cobro'],
                'tipo': ETIQUETA_TIPO.get(d['tipo'], d['tipo'] or ''),
                'detalle': _detalle_forma(d),
                'monto': _miles(d['monto']),
            }
            for d in cobro['detalle']
        ],
        'total': _miles(cobro['total']),
        'total_letras': monto_en_letras(int(cobro['total'])),
        'saldo_factura': _miles(max(int(cobro['saldo_despues']), 0)),
        'factura_pagada': int(cobro['saldo_despues']) <= 0,
    }


# ======================================================================================================================
# 2. DIBUJO (layout)
# ======================================================================================================================
def _cabecera(c, datos, copia, primera=True):
    nombre_copia, destino = copia
    leyenda = f"COMPROBANTE DE COBRO · {nombre_copia} — {destino}"
    y = dibujar_encabezado(
        c,
        empresa=datos['empresa'],
        titulo='RECIBO DE DINERO',
        numero=datos['numero_recibo'],
        leyenda=leyenda,
        fecha_doc=datos['fecha'],
    )
    if not primera:
        return dibujar_barra_seccion(c, y, 'DETALLE DE FORMAS DE COBRO (CONTINUACIÓN)')

    filas_recibo = [
        (('Fecha de emisión', datos['fecha']), ('Cajero', datos['cajero'])),
        (('Recibimos de', datos['cliente']), ('CI/RUC', datos['ci_ruc'])),
        (('En concepto de', datos['concepto']),),
    ]
    if datos.get('observacion'):
        filas_recibo.append((('Observación', datos['observacion']),))

    y = dibujar_cuadro_datos(c, y, filas_recibo, Proporcion_izq=0.58)
    y -= 0.24 * cm
    y = dibujar_barra_seccion(c, y, 'DETALLE DE FORMAS DE COBRO')
    return y


def _valores_forma(f):
    return [
        f['forma'],
        f.get('tipo') or '—',
        f.get('detalle') or '—',
        f['monto'],
    ]


def _dibujar_pie_recibo(c, datos, y):
    # Caja de TOTAL COBRADO
    alto_tot = 0.74 * cm
    y_inf = y - alto_tot
    c.saveState()
    c.setFillColorRGB(*COLOR_FONDO_SUBTOTAL)
    c.setStrokeColorRGB(*COLOR_BORDE)
    c.setLineWidth(0.6)
    c.rect(MARGEN, y_inf, ANCHO_UTIL, alto_tot, stroke=1, fill=1)
    c.setFillColorRGB(*COLOR_TEXTO)
    c.setFont('Helvetica-Bold', 10)
    c.drawString(MARGEN + 0.3 * cm, y_inf + 0.24 * cm, 'TOTAL COBRADO')
    c.setFont('Helvetica-Bold', 12)
    c.drawRightString(DER - 0.3 * cm, y_inf + 0.22 * cm, f"Gs. {datos['total']}")
    c.restoreState()

    y_cursor = y_inf - 0.48 * cm
    c.saveState()
    c.setFillColorRGB(*COLOR_TEXTO)
    c.setFont('Helvetica-Bold', 9)
    for linea in _partir(datos['total_letras'], 'Helvetica-Bold', 9, ANCHO_UTIL):
        c.drawString(MARGEN, y_cursor, linea)
        y_cursor -= 0.42 * cm
    c.restoreState()

    y_cursor -= 0.12 * cm
    y_cursor = dibujar_barra_seccion(c, y_cursor, 'ESTADO DEL SALDO DE LA FACTURA')
    texto_saldo = 'Gs. 0 (factura pagada)' if datos['factura_pagada'] else f"Gs. {datos['saldo_factura']}"
    y_cursor = dibujar_cuadro_datos(
        c,
        y_cursor,
        [
            (('Saldo de la factura después de este cobro', texto_saldo), ('Moneda', 'Guaraníes (Gs.)')),
        ],
        Proporcion_izq=0.64,
    )

    y_cursor -= 1.45 * cm
    y_cursor = dibujar_firmas(
        c,
        y_cursor,
        [
            ('Firma del cajero', datos['cajero']),
            ('Firma del cliente', datos['cliente']),
        ],
    )
    return y_cursor


def dibujar_recibo(c, datos, copia):
    """Dibuja UNA copia ('ORIGINAL' o 'DUPLICADO') y la cierra con showPage()."""
    nombre_copia, destino = copia
    leyenda_pie = f"RECIBO DE DINERO {datos['numero_recibo']} · {nombre_copia} — {destino}"
    num_pagina = 1
    total_paginas = 1

    y = dibujar_encabezado_tabla(c, _cabecera(c, datos, copia, primera=True), COLUMNAS_RECIBO)
    for idx, f in enumerate(datos['formas']):
        valores = _valores_forma(f)
        _, alto_fila = calcular_alto_fila_tabla(valores, COLUMNAS_RECIBO)
        if y - alto_fila < Y_MIN_FILAS:
            dibujar_pie_pagina(c, num_pagina, total_paginas, leyenda_pie)
            if datos['anulado']:
                dibujar_marca_agua(c, 'ANULADO')
            c.showPage()
            num_pagina += 1
            total_paginas += 1
            y = dibujar_encabezado_tabla(c, _cabecera(c, datos, copia, primera=False), COLUMNAS_RECIBO)
        y = dibujar_fila_tabla(c, y, valores, COLUMNAS_RECIBO, indice_fila=idx)

    if y - ALTO_PIE_RECIBO < 1.45 * cm:
        dibujar_pie_pagina(c, num_pagina, total_paginas, leyenda_pie)
        if datos['anulado']:
            dibujar_marca_agua(c, 'ANULADO')
        c.showPage()
        num_pagina += 1
        total_paginas += 1
        y = _cabecera(c, datos, copia, primera=False) - 0.15 * cm

    _dibujar_pie_recibo(c, datos, y)
    dibujar_pie_pagina(c, num_pagina, total_paginas, leyenda_pie)
    if datos['anulado']:
        dibujar_marca_agua(c, 'ANULADO')
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
