"""
=====================================================
Servicio: Generación de PDF para Justificativo Médico
Descripción: Arma el PDF al vuelo a partir de los datos ya guardados en
la base (no se persiste ningún archivo en el servidor).
=====================================================
"""
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


def generarJustificativoPdf(justificativo):
    """
    Genera el PDF de un justificativo médico a partir del dict devuelto por
    JustificativoMedicoDao.getJustificativoById(). Si el justificativo está
    'anulado', se marca visiblemente "ANULADO" en el documento (no se
    bloquea la descarga: sirve como respaldo/auditoría).

    Retorna los bytes del PDF.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    ancho, alto = A4

    y = alto - 3 * cm

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(ancho / 2, y, "JUSTIFICATIVO MÉDICO")
    y -= 1.2 * cm

    if justificativo.get('estado') == 'anulado':
        c.setFillColorRGB(0.8, 0, 0)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(ancho / 2, y, "*** ANULADO ***")
        c.setFillColorRGB(0, 0, 0)
        y -= 1.2 * cm

    c.setFont("Helvetica", 10)
    fecha_emision = datetime.now().strftime('%d/%m/%Y')
    c.drawRightString(ancho - 2.5 * cm, alto - 2 * cm, f"Fecha de emisión: {fecha_emision}")

    y -= 0.5 * cm
    c.line(2.5 * cm, y, ancho - 2.5 * cm, y)
    y -= 1 * cm

    c.setFont("Helvetica", 11)
    lineas = [
        f"Paciente: {justificativo.get('nombre_paciente', '-')}",
        f"Cédula del paciente: {justificativo.get('cedula_paciente', '-')}",
        f"Médico tratante: {justificativo.get('nombre_medico', '-')}",
        f"Cédula del médico: {justificativo.get('cedula_medico', '-')}",
        f"Fecha del justificativo: {justificativo.get('fecha_justificativo', '-')}",
        f"Días de reposo indicados: {justificativo.get('dias_reposo', '-')}",
    ]
    for linea in lineas:
        c.drawString(2.5 * cm, y, linea)
        y -= 0.8 * cm

    y -= 0.4 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2.5 * cm, y, "Recomendaciones:")
    y -= 0.7 * cm

    c.setFont("Helvetica", 10)
    recomendaciones = justificativo.get('recomendaciones') or '-'
    for linea in _wrapTexto(recomendaciones, 90):
        c.drawString(2.5 * cm, y, linea)
        y -= 0.6 * cm

    y -= 2 * cm
    c.line(ancho / 2 - 4 * cm, y, ancho / 2 + 4 * cm, y)
    y -= 0.5 * cm
    c.setFont("Helvetica", 9)
    c.drawCentredString(ancho / 2, y, "Firma y sello del médico tratante")

    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def _wrapTexto(texto, ancho_max):
    """Parte un texto largo en líneas de a lo sumo `ancho_max` caracteres, respetando palabras."""
    palabras = texto.split()
    lineas = []
    linea_actual = ""
    for palabra in palabras:
        candidata = f"{linea_actual} {palabra}".strip()
        if len(candidata) > ancho_max:
            lineas.append(linea_actual)
            linea_actual = palabra
        else:
            linea_actual = candidata
    if linea_actual:
        lineas.append(linea_actual)
    return lineas or ['-']
