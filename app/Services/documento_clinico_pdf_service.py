"""
=====================================================
Servicio: PDF de los documentos clínicos (Receta, Orden de Estudios, Orden de Análisis y Justificativo Médico)
Mismo patrón que la factura, el recibo y el arqueo:
  1. calcular_datos_documento(tipo, doc) -> CÁLCULO: dict puro (sin dibujar) con encabezado, paciente, médico, secciones y marca.
  2. dibujar_documento(c, datos)        -> DIBUJO: solo layout sobre un canvas de ReportLab (una o más páginas). Para mejorar el diseño se toca esto.
  3. generarDocumentoPdf(tipo, doc)     -> arma el archivo (bytes); se genera al vuelo, no se guarda nada en el servidor.

El PDF SÍ lleva el contenido clínico (es el documento que se entrega al paciente); la auditoría no. Un documento anulado se descarga igual, con la marca
"ANULADA" / "CANCELADA" / "ANULADO" en rojo; un justificativo PENDIENTE sale con la marca "BORRADOR" y uno emitido sin marca. El N.º de registro del médico se omite si no lo tiene (no hay columna nueva).
=====================================================
"""
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas
from app.Services.telefono import formatear_telefono

MARGEN = 2 * cm
TITULOS = {'receta': 'RECETA MÉDICA', 'orden_estudio': 'ORDEN DE ESTUDIOS', 'orden_analisis': 'ORDEN DE ANÁLISIS', 'justificativo': 'JUSTIFICATIVO MÉDICO'}
ETIQUETA_ESTADO = {'pendiente': 'Pendiente', 'enviado': 'Enviado', 'en_proceso': 'En proceso', 'completado': 'Completado', 'cancelado': 'Cancelado'}


def _fecha(texto):
    """AAAA-MM-DD (o con hora) -> DD/MM/AAAA."""
    t = (texto or '')[:10]
    return f'{t[8:10]}/{t[5:7]}/{t[0:4]}' if len(t) == 10 else (texto or '')


def _medico_linea(medico):
    partes = [medico.get('nombre') or '-']
    if medico.get('especialidad'):
        partes.append(medico['especialidad'])
    if medico.get('registro'):
        partes.append(f"Registro N.º {medico['registro']}")
    return ' · '.join(partes)


def calcular_datos_documento(tipo, doc):
    """
    CÁLCULO (sin dibujar). `tipo`: 'receta' | 'orden_estudio' | 'orden_analisis' | 'justificativo'; `doc`: el dict de getParaPdf() del DAO (con 'empresa' y 'medico').
    Devuelve un dict: titulo, numero, fecha, empresa, paciente (nombre, cedula), medico (linea, cedula), marca ('ANULADA' | 'CANCELADA' | 'ANULADO' | 'BORRADOR' | None),
    estado (solo órdenes) y secciones: lista de (titulo, 'texto', str) o (titulo, 'tabla', {'columnas': [...], 'filas': [[...]]}).
    """
    empresa = doc.get('empresa') or {}
    medico = doc.get('medico') or {}
    secciones, marca, estado = [], None, None
    if tipo == 'receta':
        filas = []
        for m in doc.get('medicamentos') or []:
            nombre = m.get('nombre_comercial') or ''
            if m.get('presentacion'):
                nombre += f" ({m['presentacion']})"
            filas.append([nombre, m.get('dosis') or '', m.get('frecuencia') or '', m.get('duracion') or ''])
        secciones.append(('Medicamentos', 'tabla', {'columnas': ['Medicamento', 'Dosis', 'Frecuencia', 'Duración'], 'filas': filas}))
        secciones.append(('Indicaciones generales', 'texto', doc.get('indicaciones_generales') or '-'))
        if not doc.get('activo', True):
            marca = 'ANULADA'
        fecha = doc.get('fecha_receta')
    elif tipo == 'justificativo':
        dias = doc.get('dias_reposo')
        secciones.append(('Reposo indicado', 'texto', f"Se indica reposo por {dias} día{'' if dias == 1 else 's'} a partir del {_fecha(doc.get('fecha_justificativo'))}."))
        secciones.append(('Recomendaciones', 'texto', doc.get('recomendaciones') or '-'))
        marca = {'pendiente': 'BORRADOR', 'anulado': 'ANULADO'}.get(doc.get('estado'))
        fecha = doc.get('fecha_justificativo')
    else:
        secciones.append(('Estudio solicitado' if tipo == 'orden_estudio' else 'Análisis solicitado', 'texto', doc.get('tipo') or '-'))
        secciones.append(('Motivo de la orden', 'texto', doc.get('motivo_orden') or '-'))
        secciones.append(('Indicaciones', 'texto', doc.get('indicaciones') or '-'))
        estado = ETIQUETA_ESTADO.get(doc.get('estado'), doc.get('estado') or '')
        if doc.get('estado') == 'cancelado':
            marca = 'CANCELADA'
        fecha = doc.get('fecha_orden')
    return {
        'titulo': TITULOS[tipo], 'numero': doc.get('numero') or '', 'fecha': _fecha(fecha), 'estado': estado, 'marca': marca,
        'empresa': {'razon_social': empresa.get('razon_social', ''), 'ruc': empresa.get('ruc', ''), 'direccion': empresa.get('direccion', ''),
                    'telefono': empresa.get('telefono', '')},
        'paciente': {'nombre': doc.get('nombre_paciente') or '-', 'cedula': doc.get('cedula_paciente') or '-'},
        'medico': {'linea': _medico_linea(medico), 'cedula': medico.get('cedula')},
        'secciones': secciones,
    }


# ---------------------------------------------------------------------------------------------------------------------
# DIBUJO
# ---------------------------------------------------------------------------------------------------------------------
def _marca(c, texto):
    ancho, alto = A4
    c.saveState()
    c.setFillColorRGB(0.85, 0.1, 0.1, alpha=0.18)
    c.setFont('Helvetica-Bold', 80)
    c.translate(ancho / 2, alto / 2)
    c.rotate(35)
    c.drawCentredString(0, 0, texto)
    c.restoreState()


def _cabecera(c, d, primera):
    """Encabezado de cada página: la clínica y, en la primera, el título, el N.º, la fecha y los datos del paciente y del médico. Devuelve la Y siguiente."""
    ancho, alto = A4
    y = alto - MARGEN
    e = d['empresa']
    c.setFont('Helvetica-Bold', 13)
    c.drawString(MARGEN, y, e['razon_social'] or '')
    c.setFont('Helvetica', 8.5)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.drawString(MARGEN, y - 0.45 * cm, ' · '.join(x for x in (f"RUC {e['ruc']}" if e['ruc'] else '', e['direccion'], f"Tel. {formatear_telefono(e['telefono'])}" if e['telefono'] else '') if x))
    c.setFillColorRGB(0, 0, 0)
    c.setStrokeColorRGB(0.6, 0.6, 0.6)
    c.line(MARGEN, y - 0.8 * cm, ancho - MARGEN, y - 0.8 * cm)
    y -= 1.9 * cm
    c.setFont('Helvetica-Bold', 16)
    c.drawString(MARGEN, y, d['titulo'])
    c.setFont('Helvetica-Bold', 10)
    c.drawRightString(ancho - MARGEN, y + 0.1 * cm, f"N.º {d['numero']}")
    c.setFont('Helvetica', 9.5)
    c.drawRightString(ancho - MARGEN, y - 0.4 * cm, f"Fecha: {d['fecha']}")
    y -= 0.9 * cm
    if not primera:
        return y
    c.setFont('Helvetica-Bold', 9.5)
    c.drawString(MARGEN, y, 'Paciente:')
    c.drawString(MARGEN, y - 0.55 * cm, 'Médico:')
    c.setFont('Helvetica', 9.5)
    c.drawString(MARGEN + 1.9 * cm, y, f"{d['paciente']['nombre']}  ·  CI {d['paciente']['cedula']}")
    linea = d['medico']['linea'] + (f"  ·  CI {d['medico']['cedula']}" if d['medico'].get('cedula') else '')
    c.drawString(MARGEN + 1.9 * cm, y - 0.55 * cm, linea)
    if d.get('estado'):
        c.setFont('Helvetica-Bold', 9.5)
        c.drawString(MARGEN, y - 1.1 * cm, 'Estado:')
        c.setFont('Helvetica', 9.5)
        c.drawString(MARGEN + 1.9 * cm, y - 1.1 * cm, d['estado'])
        y -= 0.55 * cm
    c.line(MARGEN, y - 1.0 * cm, ancho - MARGEN, y - 1.0 * cm)
    return y - 1.8 * cm


def dibujar_documento(c, d):
    """DIBUJO: el documento en una o más páginas (si el contenido es largo continúa con la clínica y el título repetidos). Firma y sello al final."""
    ancho, _ = A4
    limite = 3.5 * cm
    pagina = {'n': 1}

    def nueva():
        c.showPage()
        pagina['n'] += 1
        if d['marca']:
            _marca(c, d['marca'])
        return _cabecera(c, d, False)

    if d['marca']:
        _marca(c, d['marca'])
    y = _cabecera(c, d, True)
    for titulo, tipo, contenido in d['secciones']:
        if y < limite + 1.5 * cm:
            y = nueva()
        c.setFont('Helvetica-Bold', 11)
        c.drawString(MARGEN, y, titulo)
        y -= 0.65 * cm
        if tipo == 'texto':
            c.setFont('Helvetica', 10)
            for parrafo in str(contenido).split('\n'):
                for linea in simpleSplit(parrafo, 'Helvetica', 10, ancho - 2 * MARGEN) or ['']:
                    if y < limite:
                        y = nueva(); c.setFont('Helvetica', 10)
                    c.drawString(MARGEN, y, linea)
                    y -= 0.5 * cm
        else:
            cols = contenido['columnas']
            x = [MARGEN, MARGEN + 7.2 * cm, MARGEN + 11.2 * cm, MARGEN + 14.4 * cm]
            anchos = [6.9 * cm, 3.7 * cm, 3.0 * cm, ancho - 2 * MARGEN - 14.4 * cm]

            def encabezado(y0):
                c.setFont('Helvetica-Bold', 9)
                c.setFillColorRGB(0.93, 0.93, 0.93)
                c.rect(MARGEN, y0 - 0.2 * cm, ancho - 2 * MARGEN, 0.65 * cm, stroke=0, fill=1)
                c.setFillColorRGB(0, 0, 0)
                for xi, nombre in zip(x, cols):
                    c.drawString(xi + 0.1 * cm, y0, nombre)
                return y0 - 0.75 * cm
            y = encabezado(y)
            for fila in contenido['filas']:
                partidas = [simpleSplit(str(v), 'Helvetica', 9.5, a - 0.2 * cm) or [''] for v, a in zip(fila, anchos)]
                alto_fila = max(len(p) for p in partidas) * 0.45 * cm + 0.2 * cm
                if y - alto_fila < limite:
                    y = nueva(); y = encabezado(y)
                c.setFont('Helvetica', 9.5)
                for xi, lineas in zip(x, partidas):
                    for k, linea in enumerate(lineas):
                        c.drawString(xi + 0.1 * cm, y - k * 0.45 * cm, linea)
                y -= alto_fila
                c.setStrokeColorRGB(0.85, 0.85, 0.85)
                c.line(MARGEN, y + 0.25 * cm, ancho - MARGEN, y + 0.25 * cm)
        y -= 0.5 * cm
    y -= 1.5 * cm
    if y < 2.5 * cm:
        y = nueva() - 1 * cm
    c.setStrokeColorRGB(0, 0, 0)
    c.line(ancho / 2 - 4.5 * cm, y, ancho / 2 + 4.5 * cm, y)
    c.setFont('Helvetica', 9)
    c.drawCentredString(ancho / 2, y - 0.5 * cm, 'Firma y sello del médico')
    c.drawCentredString(ancho / 2, y - 0.95 * cm, d['medico']['linea'].split(' · ')[0])


def generarDocumentoPdf(tipo, doc):
    """Arma el PDF (bytes) del documento a partir del dict de getParaPdf()."""
    datos = calcular_datos_documento(tipo, doc)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"{datos['titulo']} {datos['numero']}")
    c.setAuthor(datos['empresa']['razon_social'] or 'Odontoclinic')
    dibujar_documento(c, datos)
    c.showPage()
    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
