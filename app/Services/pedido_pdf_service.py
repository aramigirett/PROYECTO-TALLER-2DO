"""
=====================================================
Servicio: Generación de PDF para el Pedido de Cliente
Descripción: Arma el PDF al vuelo a partir de los datos guardados en la base (no se persiste ningún archivo).
Usa la plantilla base única `app/Services/pdf_base.py` (logo del sistema, datos centralizados de la clínica,
recuadro de datos del pedido, tabla de 7 columnas con encabezado `#0e7c86`, subtotales, monto en letras y liquidación del IVA).
=====================================================
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from app.Services.formato import formatear_gs as _gs   # 'Gs. 100.000' (helper único: app/Services/formato.py)
from app.Services.formato import formatear_monto as _miles
from app.Services.numero_letras import monto_en_letras
from app.Services.factura_pdf_service import COLUMNAS_FACTURA
from app.Services.pdf_base import (
    _fecha,
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
    dibujar_pie_pagina,
)

Y_MIN_FILAS = 2.0 * cm
ALTO_PIE_PEDIDO = 4.6 * cm


def calcular_datos_pedido(pedido):
    """A partir del dict de PedidoClienteDao.getPedidoById() arma todos los datos formateados para el PDF."""
    empresa = normalizar_empresa(pedido.get('empresa'))
    lineas = []
    for d in pedido.get('detalle', []):
        sub = int(d.get('subtotal') or 0)
        iva_tasa = int(d.get('iva') or 0)
        lineas.append({
            'cantidad': str(d.get('cantidad') or 0),
            'codigo': codigo_item(d.get('id_item'), d.get('id_tratamiento'), d.get('codigo'), prefijo='INS'),
            'descripcion': str(d.get('item') or d.get('descripcion') or ''),
            'precio_unitario': _miles(d.get('precio_unitario') or 0),
            'exenta': _miles(sub) if iva_tasa == 0 else '',
            'gravada_5': _miles(sub) if iva_tasa == 5 else '',
            'gravada_10': _miles(sub) if iva_tasa == 10 else '',
        })
    t = pedido.get('totales') or {}
    total_num = int(t.get('total', pedido.get('total', 0)) or 0)
    id_ped = pedido.get('id_pedido')
    try:
        numero_fmt = f"{int(id_ped):06d}"
    except (ValueError, TypeError):
        numero_fmt = str(id_ped or '')

    return {
        'id_pedido': id_ped,
        'numero_pedido': numero_fmt,
        'estado': pedido.get('estado') or 'CONFIRMADO',
        'anulado': (pedido.get('estado') == 'ANULADO'),
        'empresa': empresa,
        'fecha_pedido': _fecha(pedido.get('fecha_pedido') or '', con_hora=True),
        'cliente': pedido.get('cliente') or '-',
        'ci_ruc': pedido.get('ci_ruc') or '-',
        'cajero': pedido.get('cajero') or '-',
        'observacion': pedido.get('observacion') or '',
        'lineas': lineas,
        'subtotales': {
            'exenta': _miles(t.get('exentas', 0)),
            'gravada_5': _miles(t.get('gravadas_5', 0)),
            'gravada_10': _miles(t.get('gravadas_10', 0)),
        },
        'total': _miles(total_num),
        'total_gs': _gs(total_num),
        'total_letras': monto_en_letras(total_num),
        'iva': {
            'iva_5': _miles(t.get('iva_5', 0)),
            'iva_10': _miles(t.get('iva_10', 0)),
            'total': _miles(t.get('total_iva', 0)),
        },
    }


def _cabecera_pedido(c, datos, primera=True):
    y = dibujar_encabezado(
        c,
        empresa=datos['empresa'],
        titulo='PEDIDO DE CLIENTE',
        numero=datos['numero_pedido'],
        leyenda='ORDEN DE PEDIDO · ORIGINAL — CLIENTE',
        fecha_doc=datos['fecha_pedido'],
        estado_doc=datos['estado'],
    )
    if not primera:
        return dibujar_barra_seccion(c, y, 'DETALLE DEL PEDIDO (CONTINUACIÓN)')

    filas = [
        (('Fecha de emisión', datos['fecha_pedido']), ('Estado del pedido', datos['estado'])),
        (('Cliente', datos['cliente']), ('CI/RUC', datos['ci_ruc'])),
        (('Atendido por (Cajero)', datos['cajero']), ('Pedido N.º', str(datos['id_pedido']))),
    ]
    if datos.get('observacion'):
        filas.append((('Observación', datos['observacion']),))

    y = dibujar_cuadro_datos(c, y, filas, Proporcion_izq=0.56)
    y -= 0.25 * cm
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


def _calcular_total_paginas(datos):
    buf_tmp = io.BytesIO()
    c_tmp = canvas.Canvas(buf_tmp, pagesize=A4)
    y = dibujar_encabezado_tabla(c_tmp, _cabecera_pedido(c_tmp, datos, primera=True), COLUMNAS_FACTURA)
    paginas = 1
    for linea in datos['lineas']:
        _, alto_fila = calcular_alto_fila_tabla(_valores_fila(linea), COLUMNAS_FACTURA)
        if y - alto_fila < Y_MIN_FILAS:
            paginas += 1
            y = dibujar_encabezado_tabla(c_tmp, _cabecera_pedido(c_tmp, datos, primera=False), COLUMNAS_FACTURA)
        y -= alto_fila
    if y - ALTO_PIE_PEDIDO < 1.45 * cm:
        paginas += 1
    return paginas


def generarPedidoPdf(pedido):
    """
    Genera el PDF de un pedido a partir del dict de PedidoClienteDao.getPedidoById(). Un pedido ANULADO se marca
    visiblemente (no se bloquea la descarga: sirve de respaldo). Retorna los bytes del PDF.
    """
    datos = calcular_datos_pedido(pedido)
    total_paginas = _calcular_total_paginas(datos)
    num_pagina = 1
    leyenda_pie = f"PEDIDO DE CLIENTE N.º {datos['numero_pedido']} · ORIGINAL — CLIENTE"

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"Pedido de Cliente {datos['numero_pedido']}")
    c.setAuthor(datos['empresa']['razon_social'])

    y = dibujar_encabezado_tabla(c, _cabecera_pedido(c, datos, primera=True), COLUMNAS_FACTURA)
    for idx, linea in enumerate(datos['lineas']):
        valores = _valores_fila(linea)
        _, alto_fila = calcular_alto_fila_tabla(valores, COLUMNAS_FACTURA)
        if y - alto_fila < Y_MIN_FILAS:
            dibujar_pie_pagina(c, num_pagina, total_paginas, leyenda_pie)
            if datos['anulado']:
                dibujar_marca_agua(c, 'ANULADO')
            c.showPage()
            num_pagina += 1
            y = dibujar_encabezado_tabla(c, _cabecera_pedido(c, datos, primera=False), COLUMNAS_FACTURA)
        y = dibujar_fila_tabla(c, y, valores, COLUMNAS_FACTURA, indice_fila=idx)

    if y - ALTO_PIE_PEDIDO < 1.45 * cm:
        dibujar_pie_pagina(c, num_pagina, total_paginas, leyenda_pie)
        if datos['anulado']:
            dibujar_marca_agua(c, 'ANULADO')
        c.showPage()
        num_pagina += 1
        y = dibujar_encabezado_tabla(c, _cabecera_pedido(c, datos, primera=False), COLUMNAS_FACTURA)

    dibujar_totales_iva(
        c,
        y - 0.15 * cm,
        subtotales=datos['subtotales'],
        total=datos['total'],
        total_letras=datos['total_letras'],
        iva=datos['iva'],
        etiqueta_total='TOTAL DEL PEDIDO',
    )
    dibujar_pie_pagina(c, num_pagina, total_paginas, leyenda_pie)
    if datos['anulado']:
        dibujar_marca_agua(c, 'ANULADO')

    c.showPage()
    c.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
