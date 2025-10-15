"""
=====================================================
MÓDULO: Historial Médico del Paciente
DESCRIPCIÓN: API para gestionar documentos médicos del paciente
             (antecedentes, alergias, medicamentos habituales, estudios)
AUTOR: [Tu nombre]
FECHA: 2025
=====================================================
"""

# ==================== IMPORTS ====================
from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_agendamiento.historial.HistorialDao import HistorialMedicoDao
import os
import time
from werkzeug.utils import secure_filename

# ==================== CONFIGURACIÓN DEL BLUEPRINT ====================
historialapi = Blueprint('historialapi', __name__)

# ==================== CONFIGURACIÓN PARA ARCHIVOS ====================
# Carpeta donde se guardarán los archivos subidos (PDFs, imágenes, etc.)
UPLOAD_FOLDER = 'uploads/historial_medico'

# Extensiones de archivo permitidas
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}

# Tamaño máximo de archivo: 5 MB
MAX_FILE_SIZE = 5 * 1024 * 1024

def allowed_file(filename):
    """
    Verifica si la extensión del archivo está permitida
    
    Args:
        filename (str): Nombre del archivo
        
    Returns:
        bool: True si la extensión es válida, False si no
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# =====================================================
# ENDPOINT: OBTENER TODO EL HISTORIAL DE UN PACIENTE
# =====================================================
@historialapi.route('/historial-medico/paciente/<int:id_paciente>', methods=['GET'])
def getHistorialByPaciente(id_paciente):
    """
    Obtiene TODOS los documentos del historial médico de un paciente específico
    
    URL: GET /api/v1/historial-medico/paciente/5
    
    Respuesta exitosa:
    {
        "success": true,
        "data": [
            {
                "id_historial": 1,
                "tipo_documento": "alergia",
                "descripcion": "Alergia a la penicilina",
                ...
            }
        ]
    }
    """
    historialDao = HistorialMedicoDao()

    try:
        # Llamar al DAO para obtener el historial
        historial = historialDao.getHistorialByPaciente(id_paciente)

        return jsonify({
            'success': True,
            'data': historial,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener historial del paciente: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: OBTENER HISTORIAL FILTRADO POR TIPO
# =====================================================
@historialapi.route('/historial-medico/paciente/<int:id_paciente>/tipo/<string:tipo_documento>', methods=['GET'])
def getHistorialByTipo(id_paciente, tipo_documento):
    """
    Obtiene documentos filtrados por tipo (solo antecedentes, solo alergias, etc.)
    
    URL: GET /api/v1/historial-medico/paciente/5/tipo/alergia
    
    Tipos válidos:
    - antecedente
    - alergia
    - medicamento_habitual
    - estudio
    - otro
    """
    historialDao = HistorialMedicoDao()

    # Validar que el tipo de documento sea válido
    tipos_validos = ['antecedente', 'alergia', 'medicamento_habitual', 'estudio', 'otro']
    if tipo_documento not in tipos_validos:
        return jsonify({
            'success': False,
            'error': f'Tipo de documento inválido. Debe ser uno de: {", ".join(tipos_validos)}'
        }), 400

    try:
        # Obtener documentos filtrados por tipo
        historial = historialDao.getHistorialByTipo(id_paciente, tipo_documento)

        return jsonify({
            'success': True,
            'data': historial,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener historial por tipo: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: OBTENER UN DOCUMENTO ESPECÍFICO POR ID
# =====================================================
@historialapi.route('/historial-medico/<int:id_historial>', methods=['GET'])
def getHistorial(id_historial):
    """
    Obtiene los detalles de UN documento específico del historial
    
    URL: GET /api/v1/historial-medico/15
    
    Se usa para:
    - Ver detalles completos
    - Editar un documento existente
    """
    historialDao = HistorialMedicoDao()

    try:
        # Buscar el documento por su ID
        historial = historialDao.getHistorialById(id_historial)

        if historial:
            return jsonify({
                'success': True,
                'data': historial,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el documento con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener historial: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: AGREGAR NUEVO DOCUMENTO AL HISTORIAL
# =====================================================
@historialapi.route('/historial-medico', methods=['POST'])
def addHistorial():
    """
    Agrega un nuevo documento al historial médico del paciente
    
    Puede recibir:
    1. Solo JSON (sin archivo)
    2. FormData con archivo adjunto
    
    Campos obligatorios:
    - id_paciente
    - tipo_documento
    - descripcion
    
    Campos adicionales según tipo:
    - Para alergias: tipo_alergia, gravedad_alergia
    - Para medicamentos: nombre_medicamento, dosis_medicamento, frecuencia_medicamento
    """
    
    # Verificar si viene con archivo adjunto o solo datos JSON
    if 'archivo' in request.files:
        # Viene con archivo: los datos están en request.form
        data = request.form.to_dict()
        archivo = request.files['archivo']
    else:
        # Solo JSON: los datos están en request.get_json()
        data = request.get_json()
        archivo = None

    historialDao = HistorialMedicoDao()

    # ========== VALIDACIONES ==========
    
    # Validar campos obligatorios
    campos_requeridos = ['id_paciente', 'tipo_documento', 'descripcion']
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio.'
            }), 400

    # Validar que descripción no esté vacía
    if isinstance(data['descripcion'], str) and len(data['descripcion'].strip()) == 0:
        return jsonify({
            'success': False,
            'error': 'El campo descripcion no puede estar vacío.'
        }), 400

    # Validar tipo de documento
    tipos_validos = ['antecedente', 'alergia', 'medicamento_habitual', 'estudio', 'otro']
    if data['tipo_documento'] not in tipos_validos:
        return jsonify({
            'success': False,
            'error': f'Tipo de documento inválido. Debe ser uno de: {", ".join(tipos_validos)}'
        }), 400

    # Validaciones específicas para ALERGIAS
    if data['tipo_documento'] == 'alergia':
        if 'gravedad_alergia' not in data or not data['gravedad_alergia']:
            return jsonify({
                'success': False,
                'error': 'Para alergias, el campo gravedad_alergia es obligatorio.'
            }), 400

    # Validaciones específicas para MEDICAMENTOS HABITUALES
    if data['tipo_documento'] == 'medicamento_habitual':
        campos_medicamento = ['nombre_medicamento', 'dosis_medicamento', 'frecuencia_medicamento']
        for campo in campos_medicamento:
            if campo not in data or not data[campo]:
                return jsonify({
                    'success': False,
                    'error': f'Para medicamentos habituales, el campo {campo} es obligatorio.'
                }), 400

    try:
        # ========== PREPARAR DATOS PARA GUARDAR ==========
        datos_historial = {
            'id_paciente': int(data['id_paciente']),
            'tipo_documento': data['tipo_documento'],
            'descripcion': data['descripcion'].strip(),
            'tipo_alergia': data.get('tipo_alergia'),
            'gravedad_alergia': data.get('gravedad_alergia'),
            'nombre_medicamento': data.get('nombre_medicamento'),
            'dosis_medicamento': data.get('dosis_medicamento'),
            'frecuencia_medicamento': data.get('frecuencia_medicamento'),
            'fecha_inicio_medicamento': data.get('fecha_inicio_medicamento'),
            'id_usuario_registro': data.get('id_usuario_registro')
        }

        # ========== PROCESAR ARCHIVO SI EXISTE ==========
        if archivo and archivo.filename != '':
            # Validar extensión del archivo
            if not allowed_file(archivo.filename):
                return jsonify({
                    'success': False,
                    'error': f'Tipo de archivo no permitido. Extensiones válidas: {", ".join(ALLOWED_EXTENSIONS)}'
                }), 400

            # Verificar tamaño del archivo
            archivo.seek(0, os.SEEK_END)  # Ir al final del archivo
            file_size = archivo.tell()     # Obtener posición (tamaño)
            archivo.seek(0)                # Volver al inicio

            if file_size > MAX_FILE_SIZE:
                return jsonify({
                    'success': False,
                    'error': 'El archivo excede el tamaño máximo permitido (5MB).'
                }), 400

            # Crear nombre único para el archivo (timestamp + nombre original)
            filename = secure_filename(archivo.filename)  # Sanitizar nombre
            timestamp = int(time.time())                   # Timestamp actual
            unique_filename = f"{timestamp}_{filename}"    # Nombre único
            
            # Crear carpeta si no existe
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            
            # Guardar archivo en el servidor
            filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
            archivo.save(filepath)

            # Determinar tipo de archivo según extensión
            extension = filename.rsplit('.', 1)[1].lower()
            if extension == 'pdf':
                archivo_tipo = 'pdf'
            elif extension in ['jpg', 'jpeg', 'png']:
                archivo_tipo = 'imagen'
            else:
                archivo_tipo = 'documento'

            # Agregar información del archivo a los datos
            datos_historial['archivo_url'] = filepath
            datos_historial['archivo_nombre'] = filename
            datos_historial['archivo_tipo'] = archivo_tipo
            datos_historial['archivo_tamano'] = file_size // 1024  # Convertir a KB

        # ========== GUARDAR EN BASE DE DATOS ==========
        historial_id = historialDao.guardarHistorial(datos_historial)

        if historial_id is not None:
            return jsonify({
                'success': True,
                'data': {
                    'id_historial': historial_id,
                    'mensaje': 'Documento agregado correctamente al historial.'
                },
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo guardar el documento. Consulte con el administrador.'
            }), 500

    except Exception as e:
        app.logger.error(f"Error al agregar documento al historial: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: ACTUALIZAR DOCUMENTO DEL HISTORIAL
# =====================================================
@historialapi.route('/historial-medico/<int:id_historial>', methods=['PUT'])
def updateHistorial(id_historial):
    """
    Actualiza un documento existente del historial
    
    Puede actualizar:
    - Los datos del documento
    - El archivo adjunto (reemplazándolo)
    """
    
    # Verificar si viene con archivo o solo datos
    if 'archivo' in request.files:
        data = request.form.to_dict()
        archivo = request.files['archivo']
    else:
        data = request.get_json()
        archivo = None

    historialDao = HistorialMedicoDao()

    # ========== VALIDACIONES ==========
    campos_requeridos = ['tipo_documento', 'descripcion']
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio.'
            }), 400

    if isinstance(data['descripcion'], str) and len(data['descripcion'].strip()) == 0:
        return jsonify({
            'success': False,
            'error': 'El campo descripcion no puede estar vacío.'
        }), 400

    try:
        # Verificar que el documento exista
        historial_actual = historialDao.getHistorialById(id_historial)
        if not historial_actual:
            return jsonify({
                'success': False,
                'error': 'No se encontró el documento con el ID proporcionado.'
            }), 404

        # ========== PREPARAR DATOS ACTUALIZADOS ==========
        datos_historial = {
            'tipo_documento': data['tipo_documento'],
            'descripcion': data['descripcion'].strip(),
            'tipo_alergia': data.get('tipo_alergia'),
            'gravedad_alergia': data.get('gravedad_alergia'),
            'nombre_medicamento': data.get('nombre_medicamento'),
            'dosis_medicamento': data.get('dosis_medicamento'),
            'frecuencia_medicamento': data.get('frecuencia_medicamento'),
            'fecha_inicio_medicamento': data.get('fecha_inicio_medicamento'),
            'id_usuario_modificacion': data.get('id_usuario_modificacion'),
            # Mantener datos de archivo actuales (por si no se sube uno nuevo)
            'archivo_url': historial_actual.get('archivo_url'),
            'archivo_nombre': historial_actual.get('archivo_nombre'),
            'archivo_tipo': historial_actual.get('archivo_tipo'),
            'archivo_tamano': historial_actual.get('archivo_tamano')
        }

        # ========== PROCESAR NUEVO ARCHIVO SI EXISTE ==========
        if archivo and archivo.filename != '':
            # Validar archivo
            if not allowed_file(archivo.filename):
                return jsonify({
                    'success': False,
                    'error': f'Tipo de archivo no permitido.'
                }), 400

            # Eliminar archivo anterior si existe
            if historial_actual.get('archivo_url') and os.path.exists(historial_actual['archivo_url']):
                try:
                    os.remove(historial_actual['archivo_url'])
                except Exception as e:
                    app.logger.warning(f"No se pudo eliminar archivo anterior: {str(e)}")

            # Guardar nuevo archivo
            filename = secure_filename(archivo.filename)
            timestamp = int(time.time())
            unique_filename = f"{timestamp}_{filename}"
            
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
            archivo.save(filepath)

            # Determinar tipo
            extension = filename.rsplit('.', 1)[1].lower()
            archivo_tipo = 'pdf' if extension == 'pdf' else 'imagen' if extension in ['jpg', 'jpeg', 'png'] else 'documento'

            # Obtener tamaño
            archivo.seek(0, os.SEEK_END)
            file_size = archivo.tell()

            # Actualizar datos del archivo
            datos_historial['archivo_url'] = filepath
            datos_historial['archivo_nombre'] = filename
            datos_historial['archivo_tipo'] = archivo_tipo
            datos_historial['archivo_tamano'] = file_size // 1024

        # ========== ACTUALIZAR EN BASE DE DATOS ==========
        if historialDao.updateHistorial(id_historial, datos_historial):
            return jsonify({
                'success': True,
                'data': {
                    'id_historial': id_historial,
                    'mensaje': 'Documento actualizado correctamente.'
                },
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo actualizar el documento.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al actualizar historial: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: ELIMINAR (INACTIVAR) DOCUMENTO
# =====================================================
@historialapi.route('/historial-medico/<int:id_historial>', methods=['DELETE'])
def deleteHistorial(id_historial):
    """
    Elimina (inactiva) un documento del historial
    
    NOTA: No elimina físicamente el registro, solo lo marca como inactivo.
    Esto permite mantener un historial de auditoría.
    """
    historialDao = HistorialMedicoDao()

    try:
        # Intentar eliminar (inactivar)
        if historialDao.deleteHistorial(id_historial):
            return jsonify({
                'success': True,
                'mensaje': f'Documento con ID {id_historial} eliminado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el documento con el ID proporcionado o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar historial: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: OBTENER CONTADORES POR TIPO
# =====================================================
@historialapi.route('/historial-medico/paciente/<int:id_paciente>/contadores', methods=['GET'])
def getContadores(id_paciente):
    """
    Obtiene la cantidad de documentos por tipo para mostrar en los badges
    
    Respuesta:
    {
        "success": true,
        "data": {
            "antecedente": 3,
            "alergia": 2,
            "medicamento_habitual": 1,
            "estudio": 5,
            "otro": 0,
            "total": 11
        }
    }
    
    Se usa para actualizar los contadores en los tabs del frontend
    """
    historialDao = HistorialMedicoDao()

    try:
        # Obtener contadores desde el DAO
        contadores = historialDao.contarDocumentosPorTipo(id_paciente)

        # Asegurar que todos los tipos tengan un valor (0 si no hay registros)
        resultado = {
            'antecedente': contadores.get('antecedente', 0),
            'alergia': contadores.get('alergia', 0),
            'medicamento_habitual': contadores.get('medicamento_habitual', 0),
            'estudio': contadores.get('estudio', 0),
            'otro': contadores.get('otro', 0),
            'total': sum(contadores.values())
        }

        return jsonify({
            'success': True,
            'data': resultado,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener contadores: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500