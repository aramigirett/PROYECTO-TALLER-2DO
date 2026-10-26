"""
=====================================================
Servicio: PDF de los documentos clínicos (Receta, Orden de Estudios, Orden de Análisis y Justificativo Médico)
Usa la plantilla base única `app/Services/pdf_base.py` (mismo encabezado con logo del sistema y datos centralizados de la clínica,
sin timbrado ni bloque de IVA).
Mantiene las tres capas:
  1. calcular_datos_documento(tipo, doc) -> CÁLCULO: dict puro (sin dibujar) con encabezado, paciente, médico, secciones y marca.
  2. dibujar_documento(c, datos)        -> DIBUJO: solo layout sobre un canvas de ReportLab (una o más páginas).
  3. generarDocumentoPdf(tipo, doc)     -> arma el archivo (bytes); se genera al vuelo, no se guarda nada en el servidor.

El PDF SÍ lleva el contenido clínico (es el documento que se entrega al paciente); la auditoría no. Un documento anulado se descarga igual, con la marca
"ANULADA" / "CANCELADA" / "ANULADO" en rojo; un justificativo PENDIENTE sale con la marca "BORRADOR" y uno emitido sin marca. El N.º de registro del médico se omite si no lo tiene.
=====================================================
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from app.Services.pdf_base import (
    MARGEN,
    ANCHO_UTIL,
    COLOR_FONDO_CAJA,
    COLOR_BORDE,
    COLOR_TEXTO,
    _partir,
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

TITULOS = {
    'receta': 'RECETA MÉDICA',
    'orden_estudio': 'ORDEN DE ESTUDIOS',
    'orden_analisis': 'ORDEN DE ANÁLISIS',
    'justificativo': 'JUSTIFICATIVO MÉDICO',
}
ETIQUETA_ESTADO = {
    'pendiente': 'Pendiente',
    'enviado': 'Enviado',
    'en_proceso': 'En proceso',
    'completado': 'Completado',
    'cancelado': 'Cancelado',
}

COLUMNAS_RECETA = (
    ('Medicamento', 7.00 * cm, 'L'),
    ('Dosis', 3.80 * cm, 'L'),
    ('Frecuencia', 3.80 * cm, 'L'),
    ('Duración', 3.40 * cm, 'L'),
)

LIMITE_INFERIOR = 2.6 * cm


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
    empresa = normalizar_empresa(doc.get('empresa'))
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
        secciones.append((
            'Reposo indicado',
            'texto',
            f"Se indica reposo por {dias} día{'' if dias == 1 else 's'} a partir del {_fecha(doc.get('fecha_justificativo'))}.",
        ))
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
        'titulo': TITULOS[tipo],
        'numero': doc.get('numero') or '',
        'fecha': _fecha(fecha),
        'estado': estado,
        'marca': marca,
        'empresa': empresa,
        'paciente': {'nombre': doc.get('nombre_paciente') or '-', 'cedula': doc.get('cedula_paciente') or '-'},
        'medico': {'linea': _medico_linea(medico), 'cedula': medico.get('cedula')},
        'secciones': secciones,
    }


# ---------------------------------------------------------------------------------------------------------------------
# DIBUJO
# ---------------------------------------------------------------------------------------------------------------------
def _cabecera(c, d, primera):
    """
    Encabezado de cada página: logo y datos de la clínica a la izquierda, recuadro con título, N.º y fecha a la derecha;
    en la primera página incluye el recuadro con los datos del paciente, médico tratante y estado (si aplica).
    """
    y = dibujar_encabezado(
        c,
        empresa=d['empresa'],
        titulo=d['titulo'],
        numero=d['numero'],
        leyenda='DOCUMENTO CLÍNICO · ORIGINAL — PACIENTE',
        timbrado=None,
        fecha_doc=d['fecha'],
        estado_doc=None,
    )
    if not primera:
        return y

    linea_medico = d['medico']['linea'] + (f"  ·  CI {d['medico']['cedula']}" if d['medico'].get('cedula') else '')
    filas_paciente = [
        (('Paciente', d['paciente']['nombre']), ('CI / Documento', d['paciente']['cedula'])),
        (('Médico tratante', linea_medico),),
    ]
    if d.get('estado'):
        filas_paciente.append((('Estado', d['estado']), ('Fecha de emisión', d['fecha'])))

    y = dibujar_cuadro_datos(c, y, filas_paciente, Proporcion_izq=0.64)
    return y - 0.3 * cm


def _dibujar_bloque_texto(c, y, lineas_bloque):
    """Dibuja un recuadro con bordes finos y fondo suave para las líneas de texto clínico."""
    interlineado = 0.42 * cm
    alto = max(len(lineas_bloque), 1) * interlineado + 0.32 * cm
    y_inf = y - alto
    c.saveState()
    c.setFillColorRGB(*COLOR_FONDO_CAJA)
    c.setStrokeColorRGB(*COLOR_BORDE)
    c.setLineWidth(0.6)
    c.rect(MARGEN, y_inf, ANCHO_UTIL, alto, stroke=1, fill=1)
    c.setFillColorRGB(*COLOR_TEXTO)
    c.setFont('Helvetica', 9.5)
    y_txt = y - 0.44 * cm
    for idx, lin in enumerate(lineas_bloque):
        c.drawString(MARGEN + 0.3 * cm, y_txt - idx * interlineado, lin)
    c.restoreState()
    return y_inf


def _dibujar_documento_interno(c, d, total_paginas=None):
    pagina = {'n': 1}
    leyenda_pie = f"{d['titulo']} {d['numero']} · Paciente: {d['paciente']['nombre']}"

    def cerrar_pagina_intermedia():
        dibujar_pie_pagina(c, pagina['n'], total_paginas, leyenda_pie)
        if d.get('marca'):
            dibujar_marca_agua(c, d['marca'])
        c.showPage()
        pagina['n'] += 1
        return _cabecera(c, d, False)

    y = _cabecera(c, d, True)

    for titulo, tipo, contenido in d['secciones']:
        if y < LIMITE_INFERIOR + 1.5 * cm:
            y = cerrar_pagina_intermedia()

        y = dibujar_barra_seccion(c, y, titulo)

        if tipo == 'texto':
            todas_lineas = []
            for parrafo in str(contenido).split('\n'):
                todas_lineas.extend(_partir(parrafo, 'Helvetica', 9.5, ANCHO_UTIL - 0.6 * cm))
            if not todas_lineas:
                todas_lineas = ['-']

            interlineado = 0.42 * cm
            idx_ini = 0
            while idx_ini < len(todas_lineas):
                espacio_disp = y - LIMITE_INFERIOR - 0.35 * cm
                max_lin_pag = max(int(espacio_disp // interlineado), 1)
                lote = todas_lineas[idx_ini:idx_ini + max_lin_pag]
                y = _dibujar_bloque_texto(c, y, lote)
                idx_ini += len(lote)
                if idx_ini < len(todas_lineas):
                    y = cerrar_pagina_intermedia()
                    y = dibujar_barra_seccion(c, y, f"{titulo} (continuación)")
        else:
            y = dibujar_encabezado_tabla(c, y, COLUMNAS_RECETA)
            filas = contenido.get('filas') or []
            if not filas:
                y = dibujar_fila_tabla(c, y, ['—', '—', '—', '—'], COLUMNAS_RECETA, indice_fila=0)
            for idx_f, fila in enumerate(filas):
                _, alto_fila = calcular_alto_fila_tabla(fila, COLUMNAS_RECETA)
                if y - alto_fila < LIMITE_INFERIOR:
                    y = cerrar_pagina_intermedia()
                    y = dibujar_barra_seccion(c, y, f"{titulo} (continuación)")
                    y = dibujar_encabezado_tabla(c, y, COLUMNAS_RECETA)
                y = dibujar_fila_tabla(c, y, fila, COLUMNAS_RECETA, indice_fila=idx_f)

        y -= 0.35 * cm

    # Firma y sello del médico al final del documento
    if y - 2.3 * cm < 1.5 * cm:
        y = cerrar_pagina_intermedia()

    y_firma = y - 1.45 * cm
    nombre_medico = d['medico']['linea'].split(' · ')[0]
    dibujar_firmas(c, y_firma, [('Firma y sello del médico', nombre_medico)])
    dibujar_pie_pagina(c, pagina['n'], total_paginas or pagina['n'], leyenda_pie)
    if d.get('marca'):
        dibujar_marca_agua(c, d['marca'])
    return pagina['n']


def dibujar_documento(c, d):
    """DIBUJO: el documento en una o más páginas (si el contenido es largo continúa con la clínica y el título repetidos). Firma y sello al final."""
    buf_tmp = io.BytesIO()
    c_tmp = canvas.Canvas(buf_tmp, pagesize=A4)
    total_paginas = _dibujar_documento_interno(c_tmp, d, total_paginas=None)
    _dibujar_documento_interno(c, d, total_paginas=total_paginas)


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
