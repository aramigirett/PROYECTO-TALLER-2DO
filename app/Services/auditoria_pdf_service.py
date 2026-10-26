"""
=====================================================
Servicio: PDF e informes de la auditoría (Auditoría de Cambios y Tablero de Accesos)
Descripción: arma al vuelo, a partir de las filas ya filtradas, un informe tabular en A4 apaisado con el mismo estilo que la
factura (cuadro de la empresa, título, trazo fino, Helvetica). Mismo patrón que factura_pdf_service.py:
  1. calcular_datos_informe(...)  -> CÁLCULO: dict puro con todo lo que se imprime (filtros aplicados, fecha de emisión, usuario
                                     que lo genera, columnas y filas ya formateadas). Sin ReportLab.
  2. dibujar_informe(c, datos)    -> DIBUJO: solo layout; reparte las filas en páginas y repite el encabezado de la tabla.
  3. generarInformePdf(datos)     -> arma el PDF.
  Además, el CSV (`generar_csv`, con BOM UTF-8 para que Excel abra bien las tildes) y los armadores de filas de cada informe
  (`datos_auditoria_cambios`, `datos_auditoria_accesos`), también puros.
=====================================================
"""
import csv
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from app.Services.auditoria_detalle import etiqueta_accion, filas_detalle
from app.Services.factura_pdf_service import _partir
from app.Services.telefono import formatear_telefono

ANCHO, ALTO = landscape(A4)
MARGEN = 1.5 * cm
DER = ANCHO - MARGEN
INTERLINEADO = 0.38 * cm
TAM = 7.5
MAX_LINEAS_FILA = 14          # una fila más larga se corta con "…" (el texto completo está en el CSV)
Y_MIN = MARGEN + 0.8 * cm


# ======================================================================================================================
# 1. CÁLCULO (datos)
# ======================================================================================================================
def _fecha_hora(texto):
    """'AAAA-MM-DD HH:MM:SS' -> 'DD/MM/AAAA HH:MM:SS'."""
    t = str(texto or '')
    return f'{t[8:10]}/{t[5:7]}/{t[0:4]} {t[11:19]}' if len(t) >= 19 else t


def _fecha(texto):
    t = str(texto or '')
    return f'{t[8:10]}/{t[5:7]}/{t[0:4]}' if len(t) >= 10 else t


def calcular_datos_informe(titulo, empresa, filtros, columnas, filas, emitido_por, emitido=None, aviso=''):
    """
    titulo: texto del informe. empresa: dict (razon_social, ruc, direccion, telefono) o None. filtros: lista de
    (etiqueta, valor) YA legibles. columnas: lista de (encabezado, ancho relativo, alineación 'L' | 'R'). filas: lista de
    listas de texto. emitido_por: nombre del usuario que lo genera. aviso: texto opcional (p. ej. "se muestran las primeras
    5.000 filas").
    """
    emitido = emitido or datetime.now()
    e = empresa or {}
    total_rel = sum(c[1] for c in columnas)
    ancho_util = DER - MARGEN
    return {
        'titulo': titulo,
        'empresa': {k: e.get(k, '') for k in ('razon_social', 'ruc', 'direccion', 'telefono')},
        'filtros': [(k, v) for k, v in filtros],
        'emitido': emitido.strftime('%d/%m/%Y %H:%M'),
        'emitido_por': emitido_por or '',
        'aviso': aviso,
        'columnas': [{'titulo': c[0], 'ancho': ancho_util * c[1] / total_rel, 'alinea': c[2]} for c in columnas],
        'filas': [[str(v) if v is not None else '' for v in fila] for fila in filas],
    }


def _detalle_en_linea(fila):
    """Campo: anterior -> nuevo por campo, en una línea (para el PDF y el CSV)."""
    filas, mostrar_texto = filas_detalle(fila)
    partes = []
    for f in filas:
        if f['campo'] == 'Detalle' and not f['anterior']:
            partes.append(f['nuevo'])
        elif f['anterior'] and f['nuevo']:
            partes.append(f"{f['campo']}: {f['anterior']} → {f['nuevo']}")
        elif f['anterior']:
            partes.append(f"{f['campo']}: {f['anterior']} →")
        else:
            partes.append(f"{f['campo']}: {f['nuevo']}")
    if mostrar_texto and fila.get('detalle') and fila['accion'] in ('BAJA', 'REACTIVACION', 'CIERRE', 'EXPORTACION'):
        partes.append(fila['detalle'])
    return '; '.join(p for p in partes if p)


def datos_auditoria_cambios(filas, filtros, empresa, emitido_por, total, recortado, tope):
    """Informe "Auditoría de Cambios". `filtros` = lista de (etiqueta, valor) ya legibles."""
    aviso = (f'Se exportaron las {tope:,} filas más recientes de {total:,} que cumplen el filtro; '
             f'acote las fechas para ver el resto.'.replace(',', '.')) if recortado else ''
    columnas = [('Fecha y hora', 2.3, 'L'), ('Usuario', 2.6, 'L'), ('IP', 1.6, 'L'), ('Módulo', 2.2, 'L'),
                ('Entidad', 2.6, 'L'), ('ID', 0.8, 'R'), ('Acción', 1.8, 'L'), ('Detalle', 8.0, 'L')]
    cuerpo = [[_fecha_hora(f['fecha_hora']), f['usuario'] or '(sistema)', f['ip'] or '', f['modulo'], f['entidad_etiqueta'],
               f['id_registro'], etiqueta_accion(f['accion']), _detalle_en_linea(f)] for f in filas]
    return calcular_datos_informe('AUDITORÍA DE CAMBIOS', empresa, filtros, columnas, cuerpo, emitido_por, aviso=aviso)


def datos_auditoria_accesos(intentos, filtros, empresa, emitido_por, total, recortado, tope):
    """Informe "Tablero de Accesos" (intentos de acceso)."""
    aviso = (f'Se exportaron los {tope:,} intentos más recientes de {total:,} que cumplen el filtro; '
             f'acote las fechas para ver el resto.'.replace(',', '.')) if recortado else ''
    columnas = [('Fecha y hora', 2.3, 'L'), ('CI/RUC ingresado', 2.2, 'L'), ('Acción', 2.0, 'L'), ('Resultado', 3.0, 'L'),
                ('IP', 2.0, 'L'), ('País', 0.8, 'L'), ('Realizado por', 2.0, 'L')]
    cuerpo = [[_fecha_hora(i['fecha_hora']), i['ci_ruc_ingresado'], i['accion'], i['resultado'], i['ip'] or '',
               i['pais_detectado'] or '', i['actor_ci_ruc'] or ''] for i in intentos]
    return calcular_datos_informe('TABLERO DE ACCESOS — INTENTOS DE ACCESO', empresa, filtros, columnas, cuerpo,
                                  emitido_por, aviso=aviso)


# ======================================================================================================================
# 2. DIBUJO (layout)
# ======================================================================================================================
def _cabecera_primera(c, d, top):
    """Cuadro de la empresa a la izquierda y título a la derecha (como la factura). Devuelve la Y siguiente."""
    c.setLineWidth(0.8)
    ancho_emp = 11.0 * cm
    c.roundRect(MARGEN, top - 2.6 * cm, ancho_emp, 2.6 * cm, 6)
    c.roundRect(MARGEN + ancho_emp + 0.3 * cm, top - 2.6 * cm, DER - MARGEN - ancho_emp - 0.3 * cm, 2.6 * cm, 6)
    e = d['empresa']
    y = top - 0.65 * cm
    c.setFont('Helvetica-Bold', 11)
    for linea in _partir(e['razon_social'], 'Helvetica-Bold', 11, ancho_emp - 0.6 * cm):
        c.drawString(MARGEN + 0.3 * cm, y, linea); y -= 0.5 * cm
    c.setFont('Helvetica', 9)
    for texto in (f"RUC: {e['ruc']}", e['direccion'], f"Tel.: {formatear_telefono(e['telefono'])}"):
        for linea in _partir(texto, 'Helvetica', 9, ancho_emp - 0.6 * cm):
            c.drawString(MARGEN + 0.3 * cm, y, linea); y -= 0.42 * cm
    xc = MARGEN + ancho_emp + 0.3 * cm + (DER - MARGEN - ancho_emp - 0.3 * cm) / 2
    c.setFont('Helvetica-Bold', 13)
    for i, linea in enumerate(_partir(d['titulo'], 'Helvetica-Bold', 13, DER - MARGEN - ancho_emp - 0.9 * cm)):
        c.drawCentredString(xc, top - 1.1 * cm - i * 0.55 * cm, linea)
    c.setFont('Helvetica', 8)
    c.drawCentredString(xc, top - 2.2 * cm, f"Emitido el {d['emitido']} por {d['emitido_por']}")
    y = top - 3.3 * cm
    c.setFont('Helvetica-Bold', 9)
    c.drawString(MARGEN, y, 'Filtros aplicados:')
    c.setFont('Helvetica', 9)
    texto = '   |   '.join(f'{k}: {v}' for k, v in d['filtros']) or 'ninguno'
    for linea in _partir(texto, 'Helvetica', 9, DER - MARGEN - 3.1 * cm):
        c.drawString(MARGEN + 3.1 * cm, y, linea); y -= 0.42 * cm
    if d['aviso']:
        c.setFont('Helvetica-Bold', 8.5)
        c.setFillColorRGB(0.7, 0.3, 0)
        for linea in _partir(d['aviso'], 'Helvetica-Bold', 8.5, DER - MARGEN):
            c.drawString(MARGEN, y, linea); y -= 0.4 * cm
        c.setFillColorRGB(0, 0, 0)
    return y - 0.3 * cm


def _encabezado_tabla(c, d, y):
    c.setFont('Helvetica-Bold', 8)
    x = MARGEN
    for col in d['columnas']:
        if col['alinea'] == 'R':
            c.drawRightString(x + col['ancho'] - 0.1 * cm, y, col['titulo'])
        else:
            c.drawString(x + 0.1 * cm, y, col['titulo'])
        x += col['ancho']
    c.setLineWidth(0.8)
    c.line(MARGEN, y - 0.2 * cm, DER, y - 0.2 * cm)
    return y - 0.65 * cm


def _lineas_fila(d, fila):
    """Por columna, las líneas de texto que caben en su ancho (con tope de MAX_LINEAS_FILA)."""
    cols = []
    for col, valor in zip(d['columnas'], fila):
        lineas = _partir(valor, 'Helvetica', TAM, col['ancho'] - 0.25 * cm) or ['']
        if len(lineas) > MAX_LINEAS_FILA:
            lineas = lineas[:MAX_LINEAS_FILA]
            lineas[-1] = lineas[-1][:max(0, len(lineas[-1]) - 1)] + '…'
        cols.append(lineas)
    return cols


def dibujar_informe(c, d):
    """Dibuja todas las páginas del informe sobre el canvas (repite el encabezado de la tabla y numera las páginas)."""
    pagina = 1
    top = ALTO - MARGEN
    y = _cabecera_primera(c, d, top)
    y = _encabezado_tabla(c, d, y)
    if not d['filas']:
        c.setFont('Helvetica-Oblique', 9)
        c.drawString(MARGEN, y, 'No hay registros para los filtros indicados.')
    for fila in d['filas']:
        cols = _lineas_fila(d, fila)
        alto = max(len(l) for l in cols) * INTERLINEADO + 0.15 * cm
        if y - alto < Y_MIN:
            _pie(c, pagina)
            c.showPage()
            pagina += 1
            c.setFont('Helvetica', 8)
            c.drawString(MARGEN, ALTO - MARGEN, f"{d['titulo']} (continuación)")
            y = _encabezado_tabla(c, d, ALTO - MARGEN - 0.7 * cm)
        c.setFont('Helvetica', TAM)
        x = MARGEN
        for col, lineas in zip(d['columnas'], cols):
            for i, linea in enumerate(lineas):
                if col['alinea'] == 'R':
                    c.drawRightString(x + col['ancho'] - 0.1 * cm, y - i * INTERLINEADO, linea)
                else:
                    c.drawString(x + 0.1 * cm, y - i * INTERLINEADO, linea)
            x += col['ancho']
        y -= alto
        c.setLineWidth(0.25)
        c.line(MARGEN, y + 0.1 * cm, DER, y + 0.1 * cm)
    c.setFont('Helvetica-Bold', 8.5)
    c.drawString(MARGEN, max(y - 0.5 * cm, Y_MIN - 0.3 * cm), f"Total de registros en este informe: {len(d['filas']):,}".replace(',', '.'))
    _pie(c, pagina)
    c.showPage()


def _pie(c, pagina):
    c.setFont('Helvetica', 7.5)
    c.drawString(MARGEN, MARGEN - 0.2 * cm, 'Informe de solo lectura. La auditoría no se puede modificar ni eliminar.')
    c.drawRightString(DER, MARGEN - 0.2 * cm, f'Página {pagina}')


# ======================================================================================================================
# 3. ARMADO
# ======================================================================================================================
def generarInformePdf(datos):
    """Bytes del PDF del informe (datos = calcular_datos_informe / datos_auditoria_*)."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    c.setTitle(datos['titulo'])
    c.setAuthor(datos['empresa']['razon_social'])
    dibujar_informe(c, datos)
    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def generar_csv(datos, encabezado_extra=()):
    """Bytes del CSV (UTF-8 con BOM, separador ';' como espera Excel en configuración regional hispana): primero los filtros
    aplicados y la emisión, luego la tabla completa (sin recortar el texto)."""
    salida = io.StringIO()
    w = csv.writer(salida, delimiter=';', lineterminator='\r\n')
    w.writerow([datos['titulo']])
    w.writerow(['Emitido', datos['emitido'], 'Por', datos['emitido_por']])
    for k, v in datos['filtros']:
        w.writerow(['Filtro', k, v])
    if datos['aviso']:
        w.writerow(['Aviso', datos['aviso']])
    for fila in encabezado_extra:
        w.writerow(fila)
    w.writerow([])
    w.writerow([c['titulo'] for c in datos['columnas']])
    for fila in datos['filas']:
        w.writerow([_csv_seguro(v) for v in fila])
    return ('﻿' + salida.getvalue()).encode('utf-8')


def _csv_seguro(valor):
    """Evita la inyección de fórmulas al abrir en Excel: un texto que empieza con = + - @ se antepone con una comilla."""
    v = str(valor)
    return "'" + v if v[:1] in ('=', '+', '-', '@') else v
