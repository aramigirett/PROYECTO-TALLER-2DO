"""
=====================================================
Servicio: Generación de PDF de la Nota de Remisión
Descripción: arma el PDF al vuelo a partir de los datos guardados en la base (no se persiste ningún archivo).
Usa la plantilla base única `app/Services/pdf_base.py` y mantiene la separación en tres capas:
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
from app.Services.pdf_base import (
    ANCHO_UTIL,
    COLOR_FONDO_SUBTOTAL,
    COLOR_BORDE,
    COLOR_TEXTO,
    normalizar_empresa,
    codigo_item,
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

COLUMNAS_REMISION = (
    ('Cant.', 1.50 * cm, 'C'),
    ('Código', 2.20 * cm, 'L'),
    ('Descripción del bien', 7.30 * cm, 'L'),
    ('Unidad / presentación', 3.40 * cm, 'L'),
    ('Observaciones', 3.60 * cm, 'L'),
)

Y_MIN_FILAS = 2.0 * cm
ALTO_PIE_REMISION = 5.4 * cm


# ======================================================================================================================
# 1. CÁLCULO (datos)
# ======================================================================================================================
def calcular_datos_remision(remision):
    """A partir del dict de RemisionDao.getRemisionById() arma TODO lo que se imprime, ya formateado. No dibuja nada."""
    empresa = normalizar_empresa(remision.get('empresa'))
    obs_general = remision.get('observacion') or ''
    items = []
    for d in remision['detalle']:
        items.append({
            'cantidad': _miles(d['cantidad']),
            'codigo': codigo_item(d.get('id_item'), codigo=d.get('codigo'), prefijo='INS'),
            'descripcion': d['item'],
            'unidad': d.get('unidad') or d.get('presentacion') or 'Unidad',
            'observacion': d.get('observacion') or obs_general or 'Conforme a factura',
        })
    timbrado_raw = remision.get('timbrado')
    timbrado = None
    if isinstance(timbrado_raw, dict) and timbrado_raw.get('numero'):
        vig_d = _fecha(timbrado_raw.get('vigencia_desde'))
        vig_h = _fecha(timbrado_raw.get('vigencia_hasta'))
        timbrado = {
            'numero': timbrado_raw['numero'],
            'vigencia': f'{vig_d} al {vig_h}' if (vig_d and vig_h) else (timbrado_raw.get('vigencia') or ''),
        }
    return {
        'numero_remision': remision['numero_remision'],
        'anulada': remision['estado'] == 'ANULADA',
        'empresa': empresa,
        'timbrado': timbrado,
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
        'observacion': obs_general,
        'items': items,
        'total_unidades': _miles(remision['total_unidades']),
    }


# ======================================================================================================================
# 2. DIBUJO (layout)
# ======================================================================================================================
def _cabecera(c, datos, copia, primera=True):
    """Dibuja el encabezado institucional y, en la primera página de la copia, los cuadros de traslado y destinatario."""
    nombre_copia, destino = copia
    leyenda = f"DOCUMENTO DE TRASLADO · {nombre_copia} — {destino}"
    y = dibujar_encabezado(
        c,
        empresa=datos['empresa'],
        titulo='NOTA DE REMISIÓN',
        numero=datos['numero_remision'],
        leyenda=leyenda,
        timbrado=datos.get('timbrado'),
        fecha_doc=datos['fecha_emision'] if not datos.get('timbrado') else None,
    )
    if not primera:
        y = dibujar_barra_seccion(c, y, 'DETALLE DE BIENES TRASLADADOS (CONTINUACIÓN)')
        return y

    filas_traslado = [
        (('Fecha de emisión', datos['fecha_emision']), ('Motivo del traslado', datos['motivo'])),
        (('Inicio del traslado', datos['fecha_traslado']), ('Comprobante de venta', datos['comprobante'])),
        (('Dirección de salida', datos['partida']), ('Dirección de llegada', datos['llegada'])),
    ]
    y = dibujar_cuadro_datos(c, y, filas_traslado, Proporcion_izq=0.50)
    y -= 0.22 * cm

    y = dibujar_barra_seccion(c, y, 'DATOS DEL DESTINATARIO')
    filas_dest = [
        (('Nombre o razón social', datos['cliente']), ('CI/RUC', datos['ci_ruc'])),
        (('Dirección de destino', datos['llegada']), ('Emitida por', datos['emitida_por'])),
    ]
    y = dibujar_cuadro_datos(c, y, filas_dest, Proporcion_izq=0.58)
    y -= 0.22 * cm

    y = dibujar_barra_seccion(c, y, 'DETALLE DE BIENES TRASLADADOS')
    return y


def _valores_item(it):
    return [
        it['cantidad'],
        it.get('codigo') or '—',
        it['descripcion'],
        it.get('unidad') or 'Unidad',
        it.get('observacion') or 'Conforme a factura',
    ]


def _dibujar_total_y_transporte(c, datos, y):
    """Dibuja la fila de total de unidades remitidas, el cuadro de datos del transporte y las firmas."""
    # Fila destacada de total de unidades remitidas
    alto_tot = 0.68 * cm
    y_inf = y - alto_tot
    c.saveState()
    c.setFillColorRGB(*COLOR_FONDO_SUBTOTAL)
    c.setStrokeColorRGB(*COLOR_BORDE)
    c.setLineWidth(0.6)
    c.rect(MARGEN, y_inf, ANCHO_UTIL, alto_tot, stroke=1, fill=1)
    c.setFillColorRGB(*COLOR_TEXTO)
    c.setFont('Helvetica-Bold', 9.5)
    c.drawString(MARGEN + 0.3 * cm, y_inf + 0.22 * cm, 'TOTAL DE UNIDADES REMITIDAS')
    c.setFont('Helvetica-Bold', 10.5)
    c.drawRightString(DER - 0.3 * cm, y_inf + 0.22 * cm, str(datos['total_unidades']))
    c.restoreState()
    y = y_inf - 0.25 * cm

    # Bloque de datos del transporte
    y = dibujar_barra_seccion(c, y, 'DATOS DEL TRANSPORTE')
    filas_transp = [
        (('Responsable del traslado', datos['responsable']), ('Punto de partida', datos['partida'])),
    ]
    if datos.get('observacion'):
        filas_transp.append((('Observación', datos['observacion']),))
    y = dibujar_cuadro_datos(c, y, filas_transp, Proporcion_izq=0.50)

    # Firmas de entrega y recepción conforme
    y -= 1.35 * cm
    y = dibujar_firmas(
        c,
        y,
        [
            ('Firma del responsable de entrega', datos['responsable']),
            ('Firma del receptor (recibí conforme)', datos['cliente']),
        ],
    )
    return y


def _calcular_total_paginas_copia(datos, copia):
    buf_tmp = io.BytesIO()
    c_tmp = canvas.Canvas(buf_tmp, pagesize=A4)
    y = dibujar_encabezado_tabla(c_tmp, _cabecera(c_tmp, datos, copia, primera=True), COLUMNAS_REMISION)
    paginas = 1
    for it in datos['items']:
        _, alto_fila = calcular_alto_fila_tabla(_valores_item(it), COLUMNAS_REMISION)
        if y - alto_fila < Y_MIN_FILAS:
            paginas += 1
            y = dibujar_encabezado_tabla(c_tmp, _cabecera(c_tmp, datos, copia, primera=False), COLUMNAS_REMISION)
        y -= alto_fila
    if y - ALTO_PIE_REMISION < 1.45 * cm:
        paginas += 1
    return paginas


def dibujar_remision(c, datos, copia):
    """Dibuja UNA copia ('ORIGINAL' o 'DUPLICADO'); si hay muchos ítems sigue en páginas de continuación. Cierra con showPage()."""
    total_paginas = _calcular_total_paginas_copia(datos, copia)
    num_pagina = 1
    nombre_copia, destino = copia
    leyenda_pie = f"NOTA DE REMISIÓN {datos['numero_remision']} · {nombre_copia} — {destino}"

    y = dibujar_encabezado_tabla(c, _cabecera(c, datos, copia, primera=True), COLUMNAS_REMISION)
    for idx, it in enumerate(datos['items']):
        valores = _valores_item(it)
        _, alto_fila = calcular_alto_fila_tabla(valores, COLUMNAS_REMISION)
        if y - alto_fila < Y_MIN_FILAS:
            dibujar_pie_pagina(c, num_pagina, total_paginas, leyenda_pie)
            if datos['anulada']:
                dibujar_marca_agua(c, 'ANULADA')
            c.showPage()
            num_pagina += 1
            y = dibujar_encabezado_tabla(c, _cabecera(c, datos, copia, primera=False), COLUMNAS_REMISION)
        y = dibujar_fila_tabla(c, y, valores, COLUMNAS_REMISION, indice_fila=idx)

    if y - ALTO_PIE_REMISION < 1.45 * cm:
        dibujar_pie_pagina(c, num_pagina, total_paginas, leyenda_pie)
        if datos['anulada']:
            dibujar_marca_agua(c, 'ANULADA')
        c.showPage()
        num_pagina += 1
        y = _cabecera(c, datos, copia, primera=False) - 0.15 * cm

    _dibujar_total_y_transporte(c, datos, y)
    dibujar_pie_pagina(c, num_pagina, total_paginas, leyenda_pie)
    if datos['anulada']:
        dibujar_marca_agua(c, 'ANULADA')
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
