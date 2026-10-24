"""Lectura mínima de PDFs generados con ReportLab, sin librerías externas (para los tests).

Se importa con: from tests.facturacion._pdf import paginas_pdf, texto_pdf
"""
import base64
import re
import zlib


def paginas_pdf(pdf):
    """Cantidad de páginas (cuenta los objetos /Type /Page, no /Type /Pages)."""
    return len(re.findall(rb'/Type /Page(?!s)', pdf))


def texto_pdf(pdf):
    """Texto del PDF: decodifica los streams (ASCII85 + Flate) y junta las cadenas Tj. Las tildes pueden venir escapadas;
    los números, códigos y palabras sin tilde se leen tal cual."""
    textos = []
    for m in re.finditer(rb'stream\r?\n(.*?)endstream', pdf, re.S):
        datos = m.group(1).strip()
        try:
            if datos.endswith(b'~>'):
                datos = base64.a85decode(datos[:-2])
            datos = zlib.decompress(datos)
        except Exception:
            continue
        for s in re.findall(rb'\((.*?)(?<!\\)\) Tj', datos, re.S):
            textos.append(s.decode('latin-1').replace('\\(', '(').replace('\\)', ')').replace('\\\\', '\\'))
    return '\n'.join(textos)
