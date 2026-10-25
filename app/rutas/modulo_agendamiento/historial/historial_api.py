"""
=====================================================
MÓDULO: Historial Médico del Paciente
DESCRIPCIÓN: documentos médicos del paciente (antecedentes, alergias, medicamentos habituales, estudios y otros), con archivo adjunto opcional.
REGLAS (datos de salud):
  - Recepción y Cajero no tienen acceso. El Administrador SOLO LEE. El Médico lee, registra y anula, pero únicamente los documentos de los pacientes
    que atendió (tiene una consulta no cancelada con él): lo valida el servidor.
  - Se registra y se anula (anulación definitiva); no se modifica. El usuario que registra sale de la sesión.
  - Auditoría SIN contenido clínico: quién, cuándo, paciente, tipo de documento y si lleva archivo. Cada descarga de un adjunto queda auditada (EXPORTACION).
  - Los adjuntos se guardan en `uploads/historial_medico/` (fuera de git), con el tipo verificado por su contenido, y solo se bajan por este endpoint.
=====================================================
"""
import os
import time
from flask import Blueprint, current_app as app, jsonify, request, send_file
from werkzeug.utils import secure_filename

from app.dao.referenciales_agendamiento.historial.HistorialDao import HistorialMedicoDao
from app.rutas.modulo_agendamiento.utils import auditar, detalle_cambios, entero_id, error_interno, respuesta_error, validar_fecha
from app.rutas.modulo_seguridad.decorators import require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import id_medico_sesion
from flask import session

historialapi = Blueprint('historialapi', __name__)

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
UPLOAD_FOLDER = os.path.join(RAIZ, 'uploads', 'historial_medico')
MAX_FILE_SIZE = 5 * 1024 * 1024
TIPOS = ('antecedente', 'alergia', 'medicamento_habitual', 'estudio', 'otro')
ETIQUETA_TIPO = {'antecedente': 'Antecedente', 'alergia': 'Alergia', 'medicamento_habitual': 'Medicamento habitual', 'estudio': 'Estudio', 'otro': 'Otro'}
# extensión -> (tipo de archivo, cómo reconocer su contenido)
FIRMAS = {'pdf': ('pdf', (b'%PDF',)), 'png': ('imagen', (b'\x89PNG',)), 'jpg': ('imagen', (b'\xff\xd8\xff',)), 'jpeg': ('imagen', (b'\xff\xd8\xff',)),
          'doc': ('documento', (b'\xd0\xcf\x11\xe0',)), 'docx': ('documento', (b'PK\x03\x04',))}
ETIQ = {'nombre_paciente': 'Paciente', 'tipo': 'Tipo de documento', 'archivo': 'Archivo adjunto'}


def _auditado(h):
    return {'nombre_paciente': h['nombre_paciente'], 'tipo': ETIQUETA_TIPO.get(h['tipo_documento'], h['tipo_documento']), 'archivo': 'Sí' if h['tiene_archivo'] else 'No'}


def _acceso(id_paciente):
    """
    Quién puede tocar el historial de un paciente. Devuelve (id_medico | None, None) si puede LEER, o (None, respuesta_de_error).
    Administrador: lee todo (id_medico None). Médico: solo sus pacientes atendidos. Cualquier otro rol con permiso 'ver' (no debería existir): nada.
    """
    if session.get('nombre_rol') == 'Administrador':
        return None, None
    id_medico = id_medico_sesion()
    if not id_medico:
        return None, respuesta_error('Solo el médico que atendió al paciente puede ver su historial médico.', 403)
    if not HistorialMedicoDao().esPacienteAtendido(id_medico, id_paciente):
        return None, respuesta_error('Solo puede ver el historial de los pacientes que atendió.', 403)
    return id_medico, None


def _solo_medico(id_paciente):
    """Escribir (registrar / anular) lo hace únicamente el médico que atendió al paciente; el Administrador solo lee."""
    id_medico = id_medico_sesion()
    if not id_medico:
        return respuesta_error('Solo el médico que atendió al paciente puede registrar o anular documentos de su historial (el Administrador solo consulta).', 403)
    if not HistorialMedicoDao().esPacienteAtendido(id_medico, id_paciente):
        return respuesta_error('Solo puede registrar documentos de los pacientes que atendió.', 403)
    return None


@historialapi.route('/historial-medico/pacientes', methods=['GET'])
@require_permiso('historial', 'ver')
def getPacientes():
    """Los pacientes que la persona puede elegir en la pantalla (el médico, los que atendió)."""
    if session.get('nombre_rol') == 'Administrador':
        datos = HistorialMedicoDao().pacientesAtendidos(None)
    else:
        id_medico = id_medico_sesion()
        if not id_medico:
            return respuesta_error('Solo el médico que atendió al paciente puede ver su historial médico.', 403)
        datos = HistorialMedicoDao().pacientesAtendidos(id_medico)
    return jsonify({'success': True, 'data': datos, 'error': None}), 200


@historialapi.route('/historial-medico/paciente/<int:id_paciente>', methods=['GET'])
@require_permiso('historial', 'ver')
def getHistorialPaciente(id_paciente):
    _, error = _acceso(id_paciente)
    if error:
        return error
    tipo = request.args.get('tipo') or None
    if tipo and tipo not in TIPOS:
        return respuesta_error('Tipo de documento inválido.', 400)
    try:
        return jsonify({'success': True, 'data': HistorialMedicoDao().getHistorialByPaciente(id_paciente, tipo), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener el historial: {str(e)}")
        return error_interno()


@historialapi.route('/historial-medico/paciente/<int:id_paciente>/contadores', methods=['GET'])
@require_permiso('historial', 'ver')
def getContadores(id_paciente):
    _, error = _acceso(id_paciente)
    if error:
        return error
    c = HistorialMedicoDao().contarDocumentosPorTipo(id_paciente)
    r = {t: c.get(t, 0) for t in TIPOS}
    r['total'] = sum(r.values())
    return jsonify({'success': True, 'data': r, 'error': None}), 200


@historialapi.route('/historial-medico/<int:id_historial>', methods=['GET'])
@require_permiso('historial', 'ver')
def getHistorial(id_historial):
    h = HistorialMedicoDao().getHistorialById(id_historial)
    if not h:
        return respuesta_error('No se encontró el documento con el ID proporcionado.', 404)
    _, error = _acceso(h['id_paciente'])
    if error:
        return error
    return jsonify({'success': True, 'data': h, 'error': None}), 200


def _texto(data, campo, etiqueta, max_len, obligatorio=False):
    v = data.get(campo)
    v = v.strip() if isinstance(v, str) else ''
    if not v:
        return (None, f'El campo {etiqueta} es obligatorio y no puede estar vacío.') if obligatorio else (None, None)
    if len(v) > max_len:
        return None, f'El campo {etiqueta} no puede superar los {max_len} caracteres.'
    return v, None


@historialapi.route('/historial-medico', methods=['POST'])
@require_permiso('historial', 'nuevo')
def addHistorial():
    """Registra un documento (JSON, o FormData con un adjunto). Solo el médico que atendió al paciente."""
    if 'archivo' in request.files:
        data, archivo = request.form.to_dict(), request.files['archivo']
    else:
        data, archivo = (request.get_json(silent=True) or {}), None
    id_paciente = entero_id(data.get('id_paciente'))
    if id_paciente is None:
        return respuesta_error('Debe seleccionar el paciente.', 400, 'id_paciente')
    denegado = _solo_medico(id_paciente)
    if denegado:
        return denegado
    tipo = data.get('tipo_documento')
    if tipo not in TIPOS:
        return respuesta_error(f'Tipo de documento inválido. Debe ser uno de: {", ".join(TIPOS)}', 400, 'tipo_documento')
    d = {'id_paciente': id_paciente, 'tipo_documento': tipo}
    for campo, etiqueta, maximo, obligatorio in (('descripcion', 'descripción', 1000, True), ('tipo_alergia', 'tipo de alergia', 100, False),
                                                 ('gravedad_alergia', 'gravedad de la alergia', 50, tipo == 'alergia'),
                                                 ('nombre_medicamento', 'nombre del medicamento', 100, tipo == 'medicamento_habitual'),
                                                 ('dosis_medicamento', 'dosis del medicamento', 100, tipo == 'medicamento_habitual'),
                                                 ('frecuencia_medicamento', 'frecuencia del medicamento', 100, tipo == 'medicamento_habitual')):
        d[campo], error = _texto(data, campo, etiqueta, maximo, obligatorio)
        if error:
            return respuesta_error(error, 400, campo)
    if data.get('fecha_inicio_medicamento'):
        d['fecha_inicio_medicamento'], error = validar_fecha(data.get('fecha_inicio_medicamento'), 'fecha de inicio del medicamento')
        if error:
            return respuesta_error(error, 400, 'fecha_inicio_medicamento')
    ruta = None
    try:
        if archivo and archivo.filename:
            nombre = secure_filename(archivo.filename)
            ext = nombre.rsplit('.', 1)[1].lower() if '.' in nombre else ''
            if ext not in FIRMAS:
                return respuesta_error(f'Tipo de archivo no permitido. Extensiones válidas: {", ".join(sorted(FIRMAS))}', 400, 'archivo')
            contenido = archivo.read()
            if len(contenido) > MAX_FILE_SIZE:
                return respuesta_error('El archivo excede el tamaño máximo permitido (5 MB).', 400, 'archivo')
            if not contenido or not any(contenido.startswith(f) for f in FIRMAS[ext][1]):
                return respuesta_error('El contenido del archivo no corresponde a su extensión.', 400, 'archivo')
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            guardado = f"{int(time.time())}_{nombre}"
            ruta = os.path.join(UPLOAD_FOLDER, guardado)
            with open(ruta, 'wb') as f:
                f.write(contenido)
            d.update({'archivo_url': guardado, 'archivo_nombre': nombre, 'archivo_tipo': FIRMAS[ext][0], 'archivo_tamano': max(1, len(contenido) // 1024)})
        dao = HistorialMedicoDao()
        r = dao.guardarHistorial(d, session.get('id_usuario'))
        if isinstance(r, tuple):
            if ruta and os.path.exists(ruta):
                os.remove(ruta)
            return respuesta_error(r[2], 400, r[1])
        if r:
            h = dao.getHistorialById(r)
            auditar('historial_medico_paciente', r, 'ALTA', detalle_cambios({}, _auditado(h), ETIQ))
            return jsonify({'success': True, 'data': {'id_historial': r},
                            'mensaje': f"Documento ({_auditado(h)['tipo']}) agregado al historial de {h['nombre_paciente']}.", 'error': None}), 201
        if ruta and os.path.exists(ruta):
            os.remove(ruta)
        return respuesta_error('No se pudo guardar el documento. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al agregar documento al historial: {str(e)}")
        if ruta and os.path.exists(ruta):
            os.remove(ruta)
        return error_interno()


@historialapi.route('/historial-medico/<int:id_historial>', methods=['DELETE'])
@require_permiso('historial', 'anular')
def deleteHistorial(id_historial):
    """Anula el documento (definitivo; el registro y su archivo se conservan). Solo el médico que atendió al paciente."""
    dao = HistorialMedicoDao()
    try:
        h = dao.getHistorialById(id_historial)
        if not h:
            return respuesta_error('No se encontró el documento con el ID proporcionado.', 404)
        denegado = _solo_medico(h['id_paciente'])
        if denegado:
            return denegado
        if dao.deleteHistorial(id_historial, session.get('id_usuario')):
            auditar('historial_medico_paciente', id_historial, 'BAJA', detalle_cambios({}, _auditado(h), ETIQ))
            return jsonify({'success': True, 'mensaje': f"Documento ({_auditado(h)['tipo']}) de {h['nombre_paciente']} anulado correctamente.", 'error': None}), 200
        return respuesta_error('No se pudo anular el documento.', 404)
    except Exception as e:
        app.logger.error(f"Error al anular historial: {str(e)}")
        return error_interno()


@historialapi.route('/historial-medico/<int:id_historial>/archivo', methods=['GET'])
@require_permiso('historial', 'ver')
def descargarArchivo(id_historial):
    """Baja el adjunto (misma regla de acceso que leer el historial). Cada descarga se audita."""
    h = HistorialMedicoDao().getHistorialById(id_historial, con_ruta=True)
    if not h or not h.get('archivo_ruta'):
        return respuesta_error('El documento no tiene un archivo adjunto.', 404)
    _, error = _acceso(h['id_paciente'])
    if error:
        return error
    ruta = os.path.realpath(os.path.join(UPLOAD_FOLDER, os.path.basename(h['archivo_ruta'])))
    if not ruta.startswith(os.path.realpath(UPLOAD_FOLDER) + os.sep) or not os.path.exists(ruta):
        return respuesta_error('No se encontró el archivo en el servidor.', 404)
    auditar('historial_medico_paciente', id_historial, 'EXPORTACION', f"Descarga de archivo adjunto del historial de {h['nombre_paciente']}")
    return send_file(ruta, as_attachment=True, download_name=h['archivo_nombre'] or 'documento')
