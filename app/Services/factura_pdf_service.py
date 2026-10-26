"""
=====================================================
Servicio: Generación de PDF de la Factura de Venta
Descripción: arma el PDF al vuelo a partir de los datos guardados en la base (no se persiste ningún archivo).
Usa la plantilla base única `app/Services/pdf_base.py` (logo del sistema, datos centralizados de la empresa,
recuadros con bordes, encabezado de tabla sombreado en `#0e7c86`, subtotales, monto en letras y liquidación del IVA).

Está dividido en tres partes para mantener separado el cálculo del diseño:
  1. calcular_datos_factura(venta)   -> CÁLCULO: dict con todo lo que se imprime (columnas Exentas/5%/10%, subtotales,
                                        total, total en letras, liquidación del IVA, textos ya formateados). Sin ReportLab.
  2. dibujar_factura(c, datos, copia) -> DIBUJO: solo layout sobre un canvas de ReportLab (una copia, una o más páginas).
  3. generarFacturaPdf(venta)         -> arma el PDF: ORIGINAL (cliente) y DUPLICADO (archivo tributario).
=====================================================
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from app.Services.formato import formatear_monto as _miles   # '100.000' (helper único: app/Services/formato.py)
from app.Services.numero_letras import monto_en_letras
from app.Services.telefono import formatear_telefono
from app.Services.pdf_base import (
    ANCHO,
    ALTO,
    MARGEN,
    DER,
    _fecha,
    _partir,
    normalizar_empresa,
    codigo_item,
    dibujar_encabezado,
    dibujar_barra_seccion,
    dibujar_cuadro_datos,
    dibujar_encabezado_tabla,
    calcular_alto_fila_tabla,
    dibujar_fila_tabla,
    dibujar_totales_iva,
    dibujar_marca_agua,
    dibujar_firmas,
    dibujar_pie_pagina,
)

COPIAS = (('ORIGINAL', 'CLIENTE'), ('DUPLICADO', 'ARCHIVO TRIBUTARIO'))

COLUMNAS_FACTURA = (
    ('Cant.', 1.35 * cm, 'C'),
    ('Código', 2.05 * cm, 'L'),
    ('Descripción', 6.40 * cm, 'L'),
    ('Precio unit.', 2.20 * cm, 'R'),
    ('Exentas', 2.00 * cm, 'R'),
    ('IVA 5%', 2.00 * cm, 'R'),
    ('IVA 10%', 2.00 * cm, 'R'),
)

Y_MIN_FILAS = 2.0 * cm


# ======================================================================================================================
# 1. CÁLCULO (datos)
# ======================================================================================================================
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
            'codigo': codigo_item(d.get('id_item'), d.get('id_tratamiento'), d.get('codigo'), prefijo='INS'),
            'descripcion': d['descripcion'],
            'precio_unitario': _miles(d['precio_unitario']),
            'exenta': _miles(sub) if d['iva'] == 0 else '',
            'gravada_5': _miles(sub) if d['iva'] == 5 else '',
            'gravada_10': _miles(sub) if d['iva'] == 10 else '',
        })
    t = venta['totales']
    iva_5, iva_10 = int(venta['iva_5']), int(venta['iva_10'])
    empresa = normalizar_empresa(venta.get('empresa'))
    timbrado = venta['timbrado']
    tel_cli = formatear_telefono(venta.get('telefono_cliente') or venta.get('telefono') or '')
    return {
        'numero_factura': venta['numero_factura'],
        'anulada': venta['estado'] == 'ANULADA',
        'empresa': empresa,
        'timbrado': {
            'numero': timbrado['numero'],
            'vigencia': f"{_fecha(timbrado['vigencia_desde'])} al {_fecha(timbrado['vigencia_hasta'])}",
        },
        'fecha_emision': _fecha(venta['fecha'], con_hora=True),
        'condicion': 'Crédito' if venta['condicion'] == 'CREDITO' else 'Contado',
        'vencimiento': _fecha(venta.get('fecha_vencimiento')) if venta['condicion'] == 'CREDITO' else '',
        'cliente': venta['cliente'],
        'ci_ruc': venta['ci_ruc'],
        'direccion_cliente': venta.get('direccion_cliente') or venta.get('direccion') or 'Asunción',
        'telefono_cliente': tel_cli or '—',
        'cajero': venta.get('cajero') or '—',
        'lineas': lineas,
        'subtotales': {
            'exenta': _miles(t['exentas']),
            'gravada_5': _miles(t['gravadas_5']),
            'gravada_10': _miles(t['gravadas_10']),
        },
        'total': _miles(t['total']),
        'total_letras': monto_en_letras(int(t['total'])),
        'iva': {'iva_5': _miles(iva_5), 'iva_10': _miles(iva_10), 'total': _miles(iva_5 + iva_10)},
    }


# ======================================================================================================================
# 2. DIBUJO (layout)
# ======================================================================================================================
def _cabecera(c, datos, copia):
    """
    Encabezado de página: logo + empresa a la izquierda, recuadro de documento/timbrado a la derecha,
    recuadro de datos del cliente/operación y (en notas de crédito/débito) barra y cuadro de motivo.
    Devuelve la coordenada `y` donde empieza la tabla de detalle.
    """
    nombre_copia, destino = copia
    titulo = datos.get('titulo', 'FACTURA')
    subtitulo_doc = datos.get('subtitulo_doc', '')
    leyenda = f"{subtitulo_doc}{nombre_copia} — {destino}"

    y = dibujar_encabezado(
        c,
        empresa=datos['empresa'],
        titulo=titulo,
        numero=datos['numero_factura'],
        leyenda=leyenda,
        timbrado=datos['timbrado'],
    )

    if datos.get('mostrar_condicion', True):
        condicion = datos['condicion'] + (f" (vence {datos['vencimiento']})" if datos.get('vencimiento') else '')
        filas_cliente = [
            (('Fecha de emisión', datos['fecha_emision']), ('Condición de venta', condicion)),
            (('Nombre o razón social', datos['cliente']), ('CI/RUC', datos['ci_ruc'])),
            (
                ('Dirección', datos.get('direccion_cliente') or 'Asunción'),
                ('Teléfono', datos.get('telefono_cliente') or '—'),
            ),
        ]
        y = dibujar_cuadro_datos(c, y, filas_cliente, Proporcion_izq=0.56)
        return y - 0.25 * cm

    # Diseño específico para Nota de Crédito / Nota de Débito (sin incluir la palabra "Condición")
    fact_rel = datos.get('factura_relacionada') or ''
    fecha_fact = datos.get('fecha_factura') or '—'
    filas_nota = [
        (('Fecha de emisión', datos['fecha_emision']), ('Factura relacionada', fact_rel)),
        (('Cliente', datos['cliente']), ('CI/RUC', datos['ci_ruc'])),
        (('Fecha de factura', fecha_fact), ('Cajero', datos.get('cajero') or '—')),
    ]
    y = dibujar_cuadro_datos(c, y, filas_nota, Proporcion_izq=0.54)
    y -= 0.22 * cm

    titulo_motivo = datos.get('titulo_motivo') or f"MOTIVO DE LA {titulo}"
    y = dibujar_barra_seccion(c, y, titulo_motivo)

    filas_motivo = []
    if datos.get('motivo_nota'):
        filas_motivo.append((('Motivo', datos['motivo_nota']),))
        for extra_txt in datos.get('notas_adicionales', []):
            filas_motivo.append((('', extra_txt),))
    else:
        for extra_txt in datos.get('lineas_extra', []):
            filas_motivo.append((('', extra_txt),))

    y = dibujar_cuadro_datos(c, y, filas_motivo)
    y -= 0.22 * cm
    y = dibujar_barra_seccion(c, y, 'DETALLE DEL AJUSTE')
    return y


def _valores_fila(linea):
    return [
        linea['cantidad'],
        linea.get('codigo') or '—',
        linea['descripcion'],
        linea['precio_unitario'],
        linea['exenta'] or '—',
        linea['gravada_5'] or '—',
        linea['gravada_10'] or '—',
    ]


def _pie(c, datos, y):
    """Dibuja subtotales, total, monto en letras, liquidación del IVA y firmas opcionales."""
    y = dibujar_totales_iva(
        c,
        y,
        subtotales=datos['subtotales'],
        total=datos['total'],
        total_letras=datos['total_letras'],
        iva=datos['iva'],
        etiqueta_total=datos.get('etiqueta_total', 'TOTAL A PAGAR'),
        prefijo_letras=datos.get('prefijo_letras', ''),
    )
    if datos.get('firmas'):
        y -= 1.15 * cm
        y = dibujar_firmas(c, y, datos['firmas'])
    return y


def _calcular_total_paginas_copia(datos, copia):
    """Simula la paginación en un canvas temporal para conocer el total exacto de páginas de la copia."""
    buf_tmp = io.BytesIO()
    c_tmp = canvas.Canvas(buf_tmp, pagesize=A4)
    y = dibujar_encabezado_tabla(c_tmp, _cabecera(c_tmp, datos, copia), COLUMNAS_FACTURA)
    paginas = 1
    for linea in datos['lineas']:
        _, alto_fila = calcular_alto_fila_tabla(_valores_fila(linea), COLUMNAS_FACTURA)
        if y - alto_fila < Y_MIN_FILAS:
            paginas += 1
            y = dibujar_encabezado_tabla(c_tmp, _cabecera(c_tmp, datos, copia), COLUMNAS_FACTURA)
        y -= alto_fila
    alto_pie = 5.8 * cm if datos.get('firmas') else 4.5 * cm
    if y - alto_pie < 1.45 * cm:
        paginas += 1
    return paginas


def dibujar_factura(c, datos, copia):
    """
    Dibuja UNA copia ('ORIGINAL' o 'DUPLICADO') en el canvas: una página, o más si hay muchos renglones (cada página repite
    la cabecera; el pie va solo en la última). Termina cada página con showPage().
    """
    total_paginas = _calcular_total_paginas_copia(datos, copia)
    num_pagina = 1
    nombre_copia, destino = copia
    leyenda_pie = f"{datos.get('titulo', 'FACTURA')} {datos['numero_factura']} · {nombre_copia} — {destino}"

    y = dibujar_encabezado_tabla(c, _cabecera(c, datos, copia), COLUMNAS_FACTURA)
    for idx, linea in enumerate(datos['lineas']):
        valores = _valores_fila(linea)
        _, alto_fila = calcular_alto_fila_tabla(valores, COLUMNAS_FACTURA)
        if y - alto_fila < Y_MIN_FILAS:
            dibujar_pie_pagina(c, num_pagina, total_paginas, leyenda_pie)
            if datos['anulada']:
                dibujar_marca_agua(c, 'ANULADA')
            c.showPage()
            num_pagina += 1
            y = dibujar_encabezado_tabla(c, _cabecera(c, datos, copia), COLUMNAS_FACTURA)
        y = dibujar_fila_tabla(c, y, valores, COLUMNAS_FACTURA, indice_fila=idx)

    alto_pie = 5.8 * cm if datos.get('firmas') else 4.5 * cm
    if y - alto_pie < 1.45 * cm:
        dibujar_pie_pagina(c, num_pagina, total_paginas, leyenda_pie)
        if datos['anulada']:
            dibujar_marca_agua(c, 'ANULADA')
        c.showPage()
        num_pagina += 1
        y = dibujar_encabezado_tabla(c, _cabecera(c, datos, copia), COLUMNAS_FACTURA)

    _pie(c, datos, y - 0.15 * cm)
    dibujar_pie_pagina(c, num_pagina, total_paginas, leyenda_pie)
    if datos['anulada']:
        dibujar_marca_agua(c, 'ANULADA')
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
