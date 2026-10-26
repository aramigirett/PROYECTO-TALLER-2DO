"""
=====================================================
Servicio base compartido de PDFs para el cliente (OdontoClinic)
Descripción:
  Única plantilla visual para todos los documentos PDF que se entregan al cliente / paciente:
    - Facturación: Factura de Venta, Nota de Crédito, Nota de Débito, Nota de Remisión, Recibo de Dinero y Pedido de Cliente.
    - Consultorio: Receta Médica, Orden de Estudios, Orden de Análisis y Justificativo Médico.

  Centraliza:
    1. Configuración por defecto de la clínica (`EMPRESA_POR_DEFECTO` y `normalizar_empresa`) y ruta única del logo
       principal del sistema (`app/static/img/logo_sistema.png`).
    2. Paleta corporativa (primario `#0e7c86`, azul marino `#16324f` para barras de sección, grises neutros de bordes y fondos),
       tipografía Helvetica y geometría A4.
    3. Componentes reutilizables de dibujo en ReportLab:
       - `dibujar_encabezado`: bloque izquierdo con logo y datos de la empresa; recuadro derecho con título del documento,
         N.º, leyenda (ORIGINAL — CLIENTE / DOCUMENTO DE TRASLADO / DOCUMENTO DE AJUSTE / etc.) y timbrado + vigencia cuando aplica.
       - `dibujar_cuadro_datos`: recuadro con bordes finos y filas en 1 o 2 columnas con ajuste automático de líneas.
       - `dibujar_barra_seccion`: franja azul marino con título en blanco y mayúsculas.
       - `dibujar_encabezado_tabla` y `dibujar_fila_tabla`: tabla con encabezado sombreado en color primario (`#0e7c86`)
         y celdas con bordes finos y salto de línea automático.
       - `dibujar_totales_iva`: cuadro de subtotales (Exentas, IVA 5%, IVA 10%, Total destacado), monto en letras y
         bloque de Liquidación del IVA (5%, 10%, Total IVA y Moneda).
       - `dibujar_marca_agua`: marca diagonal translúcida (`ANULADA`, `ANULADO`, `CANCELADA`, `BORRADOR`).
       - `dibujar_firmas` y `dibujar_pie_pagina`: líneas de firma/aclaración y numeración de página (`Página X de Y`).
=====================================================
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth

from app.Services.formato import formatear_monto as _miles, formatear_gs as _gs
from app.Services.telefono import formatear_telefono

# ── Geometría A4 ──────────────────────────────────────────────────────────────────────────────────────────────────────
ANCHO, ALTO = A4
MARGEN = 1.5 * cm
DER = ANCHO - MARGEN
ANCHO_UTIL = DER - MARGEN

# ── Paleta corporativa OdontoClinic ───────────────────────────────────────────────────────────────────────────────────
COLOR_PRIMARIO = (14 / 255, 124 / 255, 134 / 255)        # #0e7c86 — acento principal del sistema y encabezado de tablas
COLOR_SECCION = (22 / 255, 50 / 255, 79 / 255)           # #16324f — barras de sección (Liquidación IVA, Destinatario, etc.)
COLOR_TEXTO = (30 / 255, 41 / 255, 59 / 255)             # #1e293b — texto principal oscuro
COLOR_MUTED = (71 / 255, 85 / 255, 105 / 255)            # #475569 — texto secundario / etiquetas
COLOR_BORDE = (203 / 255, 213 / 255, 225 / 255)          # #cbd5e1 — bordes finos de tablas y recuadros
COLOR_FONDO_CAJA = (248 / 255, 250 / 255, 252 / 255)     # #f8fafc — fondo suave de recuadros de datos
COLOR_FONDO_SUBTOTAL = (236 / 255, 243 / 255, 248 / 255) # #ecf3f8 — encabezado de caja de subtotales
COLOR_FONDO_LOGO = (238 / 255, 249 / 255, 250 / 255)     # #eef9fa — recuadro suave del logo
COLOR_FILA_PAR = (251 / 255, 253 / 255, 254 / 255)       # #fbfdfe — cebra muy sutil para filas de tabla

# ── Logo y configuración centralizada de la clínica ───────────────────────────────────────────────────────────────────
RUTA_LOGO = Path(__file__).resolve().parents[1] / 'static' / 'img' / 'logo_sistema.png'

EMPRESA_POR_DEFECTO = {
    'razon_social': 'CLÍNICA ODONTOLÓGICA ODONTOCLINIC S.A.',
    'ruc': '80099999-1',
    'direccion': 'Avda. Mcal. López 1234 · Asunción',
    'telefono': '021600600',
    'actividad_economica': 'Servicios odontológicos',
}


def normalizar_empresa(empresa=None):
    """
    Devuelve un dict completo con los datos de la clínica (`razon_social`, `ruc`, `direccion`, `telefono`,
    `actividad_economica`). Toma los valores provistos por el DAO (tabla `empresa`) y completa cualquier clave faltante
    o vacía desde `EMPRESA_POR_DEFECTO`.
    """
    src = empresa if isinstance(empresa, dict) else {}
    return {
        clave: (str(src.get(clave)).strip() if src.get(clave) not in (None, '') else valor_defecto)
        for clave, valor_defecto in EMPRESA_POR_DEFECTO.items()
    }


def _fecha(texto, con_hora=False):
    """'AAAA-MM-DD[ HH:MM:SS]' -> 'DD/MM/AAAA[ HH:MM]'. Devuelve el texto tal cual si no tiene ese formato."""
    if not texto:
        return ''
    t = str(texto).strip()
    try:
        if len(t) >= 10 and t[4] == '-' and t[7] == '-':
            dia = f'{t[8:10]}/{t[5:7]}/{t[0:4]}'
            return dia + (f' {t[11:16]}' if con_hora and len(t) >= 16 else '')
    except (IndexError, TypeError):
        pass
    return t


def _partir(texto, fuente, tam, ancho_max):
    """Parte un texto en líneas que entren en `ancho_max`, respetando palabras y cortando palabras más largas que la columna."""
    if texto is None:
        return ['']
    lineas_finales = []
    for parrafo in str(texto).split('\n'):
        actual = ''
        for palabra in parrafo.split():
            while stringWidth(palabra, fuente, tam) > ancho_max:
                corte = len(palabra)
                while corte > 1 and stringWidth(palabra[:corte], fuente, tam) > ancho_max:
                    corte -= 1
                if actual:
                    lineas_finales.append(actual)
                    actual = ''
                lineas_finales.append(palabra[:corte])
                palabra = palabra[corte:]
            candidata = f'{actual} {palabra}'.strip()
            if stringWidth(candidata, fuente, tam) > ancho_max and actual:
                lineas_finales.append(actual)
                actual = palabra
            else:
                actual = candidata
        if actual or not parrafo.strip():
            lineas_finales.append(actual)
    return lineas_finales or ['']


def codigo_item(id_item=None, id_tratamiento=None, codigo=None, prefijo='ITM'):
    """Genera un código legible para la columna Código a partir de los IDs reales del renglón."""
    if codigo:
        return str(codigo)
    if id_item is not None:
        try:
            return f'{prefijo}-{int(id_item):03d}'
        except (ValueError, TypeError):
            return str(id_item)
    if id_tratamiento is not None:
        try:
            return f'TRT-{int(id_tratamiento):03d}'
        except (ValueError, TypeError):
            return str(id_tratamiento)
    return '—'


# ======================================================================================================================
# 1. ENCABEZADO COMPARTIDO (Logo + Empresa a la izquierda · Recuadro del documento a la derecha)
# ======================================================================================================================
def dibujar_encabezado(c, empresa, titulo, numero, leyenda='', timbrado=None, fecha_doc=None, estado_doc=None):
    """
    Dibuja el encabezado institucional en la parte superior de la hoja A4:
      - Bloque izquierdo: recuadro con `logo_sistema.png` y datos de la clínica (razón social, RUC, dirección, teléfono, rubro).
      - Bloque derecho: título del comprobante/documento, N.º formateado, leyenda (ORIGINAL — CLIENTE / DOCUMENTO DE TRASLADO /
        DOCUMENTO DE AJUSTE) y datos de timbrado/vigencia (o Fecha/Estado en documentos clínicos).
      - Línea divisoria horizontal en color primario `#0e7c86`.
    Devuelve la coordenada `y` donde debe comenzar el siguiente bloque.
    """
    e = normalizar_empresa(empresa)
    top = ALTO - MARGEN
    alto_cab = 2.55 * cm
    y_base = top - alto_cab

    # 1.1 Recuadro e imagen del logo (izquierda)
    lado_logo = 2.55 * cm
    c.saveState()
    c.setFillColorRGB(*COLOR_FONDO_LOGO)
    c.setStrokeColorRGB(*COLOR_PRIMARIO)
    c.setLineWidth(0.9)
    c.rect(MARGEN, y_base, lado_logo, alto_cab, stroke=1, fill=1)
    if RUTA_LOGO.is_file():
        try:
            c.drawImage(
                str(RUTA_LOGO),
                MARGEN + 0.12 * cm,
                y_base + 0.12 * cm,
                width=lado_logo - 0.24 * cm,
                height=alto_cab - 0.24 * cm,
                preserveAspectRatio=True,
                anchor='c',
                mask='auto',
            )
        except Exception:
            c.setFillColorRGB(*COLOR_PRIMARIO)
            c.setFont('Helvetica-Bold', 11)
            c.drawCentredString(MARGEN + lado_logo / 2, y_base + alto_cab / 2 - 4, 'LOGO')
    else:
        c.setFillColorRGB(*COLOR_PRIMARIO)
        c.setFont('Helvetica-Bold', 11)
        c.drawCentredString(MARGEN + lado_logo / 2, y_base + alto_cab / 2 - 4, 'LOGO')
    c.restoreState()

    # 1.2 Datos de la empresa (al lado del logo)
    x_emp = MARGEN + lado_logo + 0.35 * cm
    ancho_emp = 8.1 * cm
    y_emp = top - 0.42 * cm

    c.saveState()
    c.setFillColorRGB(*COLOR_TEXTO)
    c.setFont('Helvetica-Bold', 10.5)
    for lin in _partir(e['razon_social'], 'Helvetica-Bold', 10.5, ancho_emp)[:2]:
        c.drawString(x_emp, y_emp, lin)
        y_emp -= 0.42 * cm

    c.setFillColorRGB(*COLOR_MUTED)
    c.setFont('Helvetica', 8.5)
    if e.get('ruc'):
        c.drawString(x_emp, y_emp, f"RUC: {e['ruc']}")
        y_emp -= 0.38 * cm

    tel_fmt = formatear_telefono(e.get('telefono', ''))
    dir_txt = e.get('direccion', '')
    linea_dir_tel = ' · '.join(x for x in (dir_txt, f"Tel.: {tel_fmt}" if tel_fmt else '') if x)
    for lin in _partir(linea_dir_tel, 'Helvetica', 8.5, ancho_emp)[:2]:
        c.drawString(x_emp, y_emp, lin)
        y_emp -= 0.38 * cm

    if e.get('actividad_economica'):
        for lin in _partir(e['actividad_economica'], 'Helvetica', 8.5, ancho_emp)[:1]:
            c.drawString(x_emp, y_emp, lin)
            y_emp -= 0.38 * cm
    c.restoreState()

    # 1.3 Bloque derecho (tipo de documento, N.º, leyenda y timbrado / fecha)
    x_doc = MARGEN + 11.15 * cm
    ancho_doc = DER - x_doc
    c.saveState()
    c.setFillColorRGB(*COLOR_FONDO_CAJA)
    c.setStrokeColorRGB(*COLOR_BORDE)
    c.setLineWidth(0.7)
    c.rect(x_doc, y_base, ancho_doc, alto_cab, stroke=1, fill=1)
    # Franja superior de acento en el recuadro del documento
    c.setFillColorRGB(*COLOR_PRIMARIO)
    c.rect(x_doc, top - 0.12 * cm, ancho_doc, 0.12 * cm, stroke=0, fill=1)

    x_in = x_doc + 0.3 * cm
    x_der_in = DER - 0.3 * cm
    y_doc = top - 0.58 * cm

    # Título del documento (ajustando tamaño si es largo)
    tam_titulo = 14.5
    while tam_titulo > 9.5 and stringWidth(titulo, 'Helvetica-Bold', tam_titulo) > (ancho_doc - 0.5 * cm):
        tam_titulo -= 0.5
    c.setFillColorRGB(*COLOR_TEXTO)
    c.setFont('Helvetica-Bold', tam_titulo)
    c.drawRightString(x_der_in, y_doc, titulo)
    y_doc -= 0.46 * cm

    # Número del comprobante / documento
    num_str = str(numero or '').strip()
    if num_str and not num_str.upper().startswith('N.º') and not num_str.upper().startswith('Nº'):
        texto_num = f'N.º {num_str}'
    else:
        texto_num = num_str
    c.setFont('Helvetica-Bold', 9.5)
    c.setFillColorRGB(*COLOR_TEXTO)
    c.drawString(x_in, y_doc, texto_num)
    y_doc -= 0.38 * cm

    # Leyenda / Copia (ORIGINAL — CLIENTE, DOCUMENTO DE TRASLADO, DOCUMENTO DE AJUSTE, etc.)
    if leyenda:
        tam_ley = 8.0
        while tam_ley > 6.2 and stringWidth(leyenda, 'Helvetica', tam_ley) > (ancho_doc - 0.55 * cm):
            tam_ley -= 0.25
        c.setFont('Helvetica', tam_ley)
        c.setFillColorRGB(*COLOR_MUTED)
        c.drawString(x_in, y_doc, leyenda)
        y_doc -= 0.38 * cm

    # Timbrado y vigencia (documentos fiscales) o Fecha/Estado (documentos clínicos y otros)
    if timbrado and timbrado.get('numero'):
        c.setFont('Helvetica-Bold', 8)
        c.setFillColorRGB(*COLOR_MUTED)
        c.drawString(x_in, y_doc, f"TIMBRADO: {timbrado['numero']}")
        y_doc -= 0.36 * cm
        if timbrado.get('vigencia'):
            c.setFont('Helvetica', 8)
            c.drawString(x_in, y_doc, f"Vigencia: {timbrado['vigencia']}")
            y_doc -= 0.36 * cm
    else:
        if fecha_doc:
            c.setFont('Helvetica', 8.5)
            c.setFillColorRGB(*COLOR_MUTED)
            c.drawString(x_in, y_doc, f'Fecha: {fecha_doc}')
            y_doc -= 0.36 * cm
        if estado_doc:
            c.setFont('Helvetica', 8.5)
            c.setFillColorRGB(*COLOR_MUTED)
            c.drawString(x_in, y_doc, f'Estado: {estado_doc}')
            y_doc -= 0.36 * cm
    c.restoreState()

    # 1.4 Línea horizontal de separación en color primario
    y_linea = y_base - 0.25 * cm
    c.saveState()
    c.setStrokeColorRGB(*COLOR_PRIMARIO)
    c.setLineWidth(1.5)
    c.line(MARGEN, y_linea, DER, y_linea)
    c.restoreState()

    return y_linea - 0.28 * cm


# ======================================================================================================================
# 2. RECUADROS DE DATOS Y BARRAS DE SECCIÓN
# ======================================================================================================================
def dibujar_barra_seccion(c, y, titulo):
    """
    Dibuja una barra horizontal azul marino (`#16324f`) con texto blanco en negrita (como `LIQUIDACIÓN DEL IVA`,
    `DATOS DEL DESTINATARIO`, `DETALLE DE BIENES TRASLADADOS`, `MOTIVO DE LA NOTA DE CRÉDITO`, etc.).
    Devuelve la coordenada `y` debajo de la barra.
    """
    alto = 0.6 * cm
    y_inf = y - alto
    c.saveState()
    c.setFillColorRGB(*COLOR_SECCION)
    c.rect(MARGEN, y_inf, ANCHO_UTIL, alto, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont('Helvetica-Bold', 8.5)
    c.drawString(MARGEN + 0.25 * cm, y_inf + 0.19 * cm, str(titulo).upper())
    c.restoreState()
    return y_inf


def dibujar_cuadro_datos(c, y, filas, Proporcion_izq=0.52):
    """
    Dibuja un recuadro con bordes finos y fondo suave dividido en filas.
    Cada elemento de `filas` puede ser:
      - Una tupla de 2 celdas: `((etiqueta_izq, valor_izq), (etiqueta_der, valor_der))`
      - Una tupla de 1 celda de ancho completo: `((etiqueta, valor),)`
    Ajusta automáticamente el alto de cada fila si algún texto ocupa más de una línea.
    Devuelve la coordenada `y` debajo del recuadro.
    """
    if not filas:
        return y
    x_medio = MARGEN + ANCHO_UTIL * Proporcion_izq
    pad_x = 0.25 * cm
    interlineado = 0.38 * cm

    # Precalcular líneas y alturas por fila
    alturas = []
    lineas_por_fila = []
    for fila in filas:
        if len(fila) == 1:
            etq, val = fila[0]
            texto = f'{etq}: {val}' if etq else str(val or '')
            partes = _partir(texto, 'Helvetica', 8.5, ANCHO_UTIL - 2 * pad_x)
            lineas_por_fila.append([(etq, val, partes, MARGEN, ANCHO_UTIL)])
            alturas.append(max(len(partes), 1) * interlineado + 0.22 * cm)
        else:
            (etq1, val1), (etq2, val2) = fila[0], fila[1]
            ancho1 = (x_medio - MARGEN) - 2 * pad_x
            ancho2 = (DER - x_medio) - 2 * pad_x
            t1 = f'{etq1}: {val1}' if etq1 else str(val1 or '')
            t2 = f'{etq2}: {val2}' if etq2 else str(val2 or '')
            p1 = _partir(t1, 'Helvetica', 8.5, ancho1)
            p2 = _partir(t2, 'Helvetica', 8.5, ancho2) if (etq2 or val2) else ['']
            lineas_por_fila.append([
                (etq1, val1, p1, MARGEN, x_medio - MARGEN),
                (etq2, val2, p2, x_medio, DER - x_medio),
            ])
            alturas.append(max(len(p1), len(p2), 1) * interlineado + 0.22 * cm)

    alto_total = sum(alturas)
    y_inf = y - alto_total

    c.saveState()
    c.setFillColorRGB(*COLOR_FONDO_CAJA)
    c.setStrokeColorRGB(*COLOR_BORDE)
    c.setLineWidth(0.6)
    c.rect(MARGEN, y_inf, ANCHO_UTIL, alto_total, stroke=1, fill=1)

    y_cursor = y
    for celdas, alto_f in zip(lineas_por_fila, alturas):
        y_sig = y_cursor - alto_f
        # Línea horizontal inferior de la fila
        if y_sig > y_inf + 0.01 * cm:
            c.setStrokeColorRGB(*COLOR_BORDE)
            c.setLineWidth(0.5)
            c.line(MARGEN, y_sig, DER, y_sig)
        # Divisor vertical si hay 2 columnas
        if len(celdas) == 2:
            c.setStrokeColorRGB(*COLOR_BORDE)
            c.setLineWidth(0.5)
            c.line(x_medio, y_sig, x_medio, y_cursor)

        for etq, val, partes, x_celda, ancho_celda in celdas:
            if not etq and not val:
                continue
            y_txt = y_cursor - 0.4 * cm
            # Dibujamos también la cadena combinada o etiqueta + valor legibles para que tanto visualmente como en texto_pdf quede limpio
            if etq:
                etq_str = f'{etq}: '
                ancho_etq = stringWidth(etq_str, 'Helvetica-Bold', 8.5)
                primera_completa = partes[0]
                valor_primera = primera_completa[len(etq_str):] if primera_completa.startswith(etq_str) else str(val or '')
                if len(partes) == 1 and ancho_etq + stringWidth(valor_primera, 'Helvetica', 8.5) <= (ancho_celda - 2 * pad_x):
                    c.setFillColorRGB(*COLOR_TEXTO)
                    c.setFont('Helvetica-Bold', 8.5)
                    c.drawString(x_celda + pad_x, y_txt, etq_str)
                    c.setFillColorRGB(*COLOR_TEXTO)
                    c.setFont('Helvetica', 8.5)
                    c.drawString(x_celda + pad_x + ancho_etq, y_txt, valor_primera)
                else:
                    c.setFillColorRGB(*COLOR_TEXTO)
                    c.setFont('Helvetica-Bold', 8.5)
                    c.drawString(x_celda + pad_x, y_txt, etq_str)
                    c.setFont('Helvetica', 8.5)
                    resto_primera = primera_completa[len(etq_str):] if primera_completa.startswith(etq_str) else primera_completa
                    c.drawString(x_celda + pad_x + ancho_etq, y_txt, resto_primera)
                    for idx_l, lin_extra in enumerate(partes[1:], start=1):
                        c.drawString(x_celda + pad_x, y_txt - idx_l * interlineado, lin_extra)
            else:
                c.setFillColorRGB(*COLOR_TEXTO)
                c.setFont('Helvetica', 8.5)
                for idx_l, lin in enumerate(partes):
                    c.drawString(x_celda + pad_x, y_txt - idx_l * interlineado, lin)

        y_cursor = y_sig

    c.restoreState()
    return y_inf


# ======================================================================================================================
# 3. TABLAS DE DETALLE CON ENCABEZADO SOMBREADO (#0e7c86) Y BORDES FINOS
# ======================================================================================================================
def dibujar_encabezado_tabla(c, y, columnas):
    """
    Dibuja el encabezado sombreado en color primario (`#0e7c86`) de una tabla.
    `columnas`: lista de dicts o tuplas `(titulo, ancho_cm_o_pts, alineacion)` donde `alineacion` es `'L'`, `'R'` o `'C'`.
    Devuelve la coordenada `y` (borde inferior del encabezado, donde empieza la primera fila).
    """
    alto = 0.66 * cm
    y_inf = y - alto
    c.saveState()
    c.setFillColorRGB(*COLOR_PRIMARIO)
    c.setStrokeColorRGB(*COLOR_PRIMARIO)
    c.setLineWidth(0.7)
    c.rect(MARGEN, y_inf, ANCHO_UTIL, alto, stroke=1, fill=1)

    c.setFont('Helvetica-Bold', 8.5)
    c.setFillColorRGB(1, 1, 1)
    c.setStrokeColorRGB(1, 1, 1)
    c.setLineWidth(0.4)

    x_actual = MARGEN
    for idx, (titulo, ancho_col, alin) in enumerate(columnas):
        if idx > 0:
            c.line(x_actual, y_inf, x_actual, y)
        y_texto = y_inf + 0.21 * cm
        if alin == 'R':
            c.drawRightString(x_actual + ancho_col - 0.2 * cm, y_texto, titulo)
        elif alin == 'C':
            c.drawCentredString(x_actual + ancho_col / 2, y_texto, titulo)
        else:
            c.drawString(x_actual + 0.2 * cm, y_texto, titulo)
        x_actual += ancho_col

    c.restoreState()
    return y_inf


def calcular_alto_fila_tabla(valores, columnas, tam_fuente=8.5, interlineado=0.38 * cm):
    """Calcula las líneas partidas por celda y el alto total de una fila de tabla."""
    celdas_partidas = []
    max_lineas = 1
    for valor, (_, ancho_col, _) in zip(valores, columnas):
        texto = '' if valor is None else str(valor)
        partes = _partir(texto, 'Helvetica', tam_fuente, max(ancho_col - 0.36 * cm, 0.8 * cm))
        celdas_partidas.append(partes)
        if len(partes) > max_lineas:
            max_lineas = len(partes)
    alto = max_lineas * interlineado + 0.22 * cm
    return celdas_partidas, alto


def dibujar_fila_tabla(c, y, valores, columnas, indice_fila=0, tam_fuente=8.5, interlineado=0.38 * cm, negrita=False):
    """
    Dibuja una fila de la tabla con bordes finos y ajuste multilínea.
    Devuelve la nueva coordenada `y` (borde inferior de la fila).
    """
    celdas_partidas, alto = calcular_alto_fila_tabla(valores, columnas, tam_fuente, interlineado)
    y_inf = y - alto
    fuente = 'Helvetica-Bold' if negrita else 'Helvetica'

    c.saveState()
    if indice_fila % 2 == 1 and not negrita:
        c.setFillColorRGB(*COLOR_FILA_PAR)
    else:
        c.setFillColorRGB(1, 1, 1)
    c.setStrokeColorRGB(*COLOR_BORDE)
    c.setLineWidth(0.5)
    c.rect(MARGEN, y_inf, ANCHO_UTIL, alto, stroke=1, fill=1)

    c.setFillColorRGB(*COLOR_TEXTO)
    c.setFont(fuente, tam_fuente)
    x_actual = MARGEN
    for idx, (partes, (_, ancho_col, alin)) in enumerate(zip(celdas_partidas, columnas)):
        if idx > 0:
            c.line(x_actual, y_inf, x_actual, y)
        y_txt = y - 0.39 * cm
        for i_lin, linea in enumerate(partes):
            yl = y_txt - i_lin * interlineado
            if alin == 'R':
                c.drawRightString(x_actual + ancho_col - 0.2 * cm, yl, linea)
            elif alin == 'C':
                c.drawCentredString(x_actual + ancho_col / 2, yl, linea)
            else:
                c.drawString(x_actual + 0.2 * cm, yl, linea)
        x_actual += ancho_col

    c.restoreState()
    return y_inf


# ======================================================================================================================
# 4. BLOQUE DE SUBTOTALES, TOTAL EN LETRAS Y LIQUIDACIÓN DEL IVA
# ======================================================================================================================
def dibujar_totales_iva(c, y, subtotales, total, total_letras, iva, etiqueta_total='TOTAL A PAGAR', prefijo_letras=''):
    """
    Dibuja el bloque inferior de comprobantes fiscales (Factura, Nota de Crédito, Nota de Débito, Pedido):
      1. Cuadro de 4 columnas: `SUBTOTAL EXENTAS` | `SUBTOTAL IVA 5%` | `SUBTOTAL IVA 10%` | `etiqueta_total` (`TOTAL A PAGAR` / `TOTAL DE LA NOTA`).
      2. Renglón con el monto en letras (`Son guaraníes: ...` / `Importe en letras: ...`).
      3. Barra azul marino `LIQUIDACIÓN DEL IVA` y grilla 2x2 (`IVA 5%`, `IVA 10%`, `Total IVA`, `Moneda: Guaraníes (Gs.)`).
    Devuelve la coordenada `y` final.
    """
    c.saveState()
    ancho_col = ANCHO_UTIL / 4.0
    alto_cab = 0.52 * cm
    alto_val = 0.72 * cm

    # 4.1 Encabezado de subtotales
    y_cab_inf = y - alto_cab
    c.setFillColorRGB(*COLOR_FONDO_SUBTOTAL)
    c.setStrokeColorRGB(*COLOR_BORDE)
    c.setLineWidth(0.6)
    c.rect(MARGEN, y_cab_inf, ANCHO_UTIL, alto_cab, stroke=1, fill=1)

    titulos_sub = ('SUBTOTAL EXENTAS', 'SUBTOTAL IVA 5%', 'SUBTOTAL IVA 10%', etiqueta_total)
    c.setFont('Helvetica-Bold', 8)
    c.setFillColorRGB(*COLOR_MUTED)
    for idx, t_col in enumerate(titulos_sub):
        x_c = MARGEN + idx * ancho_col
        if idx > 0:
            c.line(x_c, y_cab_inf, x_c, y)
        c.drawString(x_c + 0.22 * cm, y_cab_inf + 0.17 * cm, t_col)

    # 4.2 Valores de subtotales y total destacado
    y_val_inf = y_cab_inf - alto_val
    c.setFillColorRGB(1, 1, 1)
    c.rect(MARGEN, y_val_inf, ANCHO_UTIL, alto_val, stroke=1, fill=1)

    vals_sub = (
        f"Gs. {subtotales.get('exenta') or '0'}",
        f"Gs. {subtotales.get('gravada_5') or '0'}",
        f"Gs. {subtotales.get('gravada_10') or '0'}",
    )
    c.setFillColorRGB(*COLOR_TEXTO)
    c.setFont('Helvetica', 9.5)
    for idx, v_col in enumerate(vals_sub):
        x_c = MARGEN + idx * ancho_col
        if idx > 0:
            c.line(x_c, y_val_inf, x_c, y_cab_inf)
        c.drawString(x_c + 0.22 * cm, y_val_inf + 0.24 * cm, v_col)

    # 4ta columna: TOTAL destacado a la derecha
    x_tot = MARGEN + 3 * ancho_col
    c.line(x_tot, y_val_inf, x_tot, y_cab_inf)
    c.setFont('Helvetica-Bold', 11.5)
    c.setFillColorRGB(*COLOR_TEXTO)
    c.drawRightString(DER - 0.25 * cm, y_val_inf + 0.22 * cm, f"Gs. {total}")

    # 4.3 Monto en letras
    y_cursor = y_val_inf - 0.46 * cm
    texto_letras = f"{prefijo_letras}{total_letras}" if prefijo_letras else str(total_letras or '')
    c.setFont('Helvetica-Bold', 8.8)
    c.setFillColorRGB(*COLOR_TEXTO)
    for lin in _partir(texto_letras, 'Helvetica-Bold', 8.8, ANCHO_UTIL):
        c.drawString(MARGEN, y_cursor, lin)
        y_cursor -= 0.4 * cm

    # 4.4 Liquidación del IVA
    y_cursor -= 0.1 * cm
    y_cursor = dibujar_barra_seccion(c, y_cursor, 'LIQUIDACIÓN DEL IVA')
    y_cursor = dibujar_cuadro_datos(
        c,
        y_cursor,
        [
            (('IVA 5%', f"Gs. {iva.get('iva_5') or '0'}"), ('IVA 10%', f"Gs. {iva.get('iva_10') or '0'}")),
            (('Total IVA', f"Gs. {iva.get('total') or '0'}"), ('Moneda', 'Guaraníes (Gs.)')),
        ],
        Proporcion_izq=0.5,
    )
    c.restoreState()
    return y_cursor


# ======================================================================================================================
# 5. MARCA DE AGUA, FIRMAS Y PIE DE PÁGINA
# ======================================================================================================================
def dibujar_marca_agua(c, texto='ANULADA'):
    """Dibuja la marca diagonal translúcida (`ANULADA`, `ANULADO`, `CANCELADA`, `BORRADOR`) y el aviso superior."""
    if not texto:
        return
    c.saveState()
    if texto == 'BORRADOR':
        c.setFillColorRGB(0.45, 0.45, 0.45)
    else:
        c.setFillColorRGB(0.8, 0.05, 0.05)
    try:
        c.setFillAlpha(0.18)
    except Exception:
        pass
    c.translate(ANCHO / 2, ALTO / 2)
    c.rotate(35)
    c.setFont('Helvetica-Bold', 96)
    c.drawCentredString(0, 0, texto)
    c.restoreState()

    c.saveState()
    if texto == 'BORRADOR':
        c.setFillColorRGB(0.45, 0.45, 0.45)
    else:
        c.setFillColorRGB(0.8, 0.05, 0.05)
    c.setFont('Helvetica-Bold', 10.5)
    c.drawString(MARGEN, ALTO - MARGEN + 0.18 * cm, f'*** {texto} ***')
    c.restoreState()


def dibujar_firmas(c, y, firmas):
    """
    Dibuja 1 o 2 líneas de firma y aclaración centradas en su columna.
    `firmas`: lista de tuplas `(etiqueta_principal, subtitulo_opcional)`.
    Devuelve la coordenada `y` debajo de las firmas.
    """
    if not firmas:
        return y
    c.saveState()
    c.setStrokeColorRGB(*COLOR_MUTED)
    c.setLineWidth(0.7)
    c.setFillColorRGB(*COLOR_TEXTO)

    if len(firmas) == 1:
        etq, sub = firmas[0]
        xc = ANCHO / 2
        c.line(xc - 4.2 * cm, y, xc + 4.2 * cm, y)
        c.setFont('Helvetica-Bold', 8.5)
        c.drawCentredString(xc, y - 0.42 * cm, etq)
        if sub:
            c.setFont('Helvetica', 8.5)
            c.setFillColorRGB(*COLOR_MUTED)
            c.drawCentredString(xc, y - 0.82 * cm, sub)
        c.restoreState()
        return y - 1.0 * cm

    # 2 firmas (izquierda y derecha)
    izq_c = MARGEN + 4.2 * cm
    der_c = DER - 4.2 * cm
    for xc, (etq, sub) in zip((izq_c, der_c), firmas[:2]):
        c.setStrokeColorRGB(*COLOR_MUTED)
        c.line(xc - 3.6 * cm, y, xc + 3.6 * cm, y)
        c.setFillColorRGB(*COLOR_TEXTO)
        c.setFont('Helvetica-Bold', 8.5)
        c.drawCentredString(xc, y - 0.42 * cm, etq)
        if sub:
            c.setFont('Helvetica', 8)
            c.setFillColorRGB(*COLOR_MUTED)
            c.drawCentredString(xc, y - 0.8 * cm, sub)
    c.restoreState()
    return y - 0.95 * cm


def dibujar_pie_pagina(c, num_pagina=1, total_paginas=1, leyenda_pie=''):
    """Dibuja la línea inferior del pie de página con la numeración `Página X de Y`."""
    y_pie = 0.95 * cm
    c.saveState()
    c.setStrokeColorRGB(*COLOR_BORDE)
    c.setLineWidth(0.5)
    c.line(MARGEN, y_pie + 0.32 * cm, DER, y_pie + 0.32 * cm)
    c.setFillColorRGB(*COLOR_MUTED)
    c.setFont('Helvetica', 7.8)
    if leyenda_pie:
        c.drawString(MARGEN, y_pie, leyenda_pie)
    texto_pag = f'Página {num_pagina} de {total_paginas}' if total_paginas else f'Página {num_pagina}'
    c.drawRightString(DER, y_pie, texto_pag)
    c.restoreState()
