from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_agendamiento.consultorio.ConsultorioDao import ConsultorioDao
import re

consultorioapi = Blueprint('consultorioapi', __name__)
dao = ConsultorioDao()


# ==========================================
# FUNCIONES DE VALIDACIÓN A NIVEL API
# ==========================================

def validar_correo(correo):
    """Valida formato básico de correo electrónico"""
    return bool(re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', correo))


def normalizar_telefono(telefono):
    """
    Normaliza el teléfono al formato que espera el DAO
    Ejemplos:
        "0981234567" → "595981234567"
        "098 123 4567" → "595981234567"
    """
    if not telefono:
        return None
    
    # Limpiar espacios y caracteres especiales
    telefono = telefono.strip().replace(" ", "").replace("-", "")
    
    # Quitar el + si lo tiene
    if telefono.startswith("+"):
        telefono = telefono[1:]
    
    # Si comienza con 0, quitarlo y agregar 595
    if telefono.startswith("0"):
        telefono = "595" + telefono[1:]
    # Si NO comienza con 595, agregarlo
    elif not telefono.startswith("595"):
        telefono = "595" + telefono
    
    return telefono


def validar_telefono(telefono):
    """
    Valida formato de número paraguayo
    Formato esperado: 595XXXXXXXXX (8 o 9 dígitos después del 595)
    """
    return bool(re.match(r'^595\d{8,9}$', telefono))


def validar_datos_consultorio(nombre, direccion, telefono, correo):
    """
    Valida los datos del consultorio a nivel API
    
    Returns:
        tuple: (es_valido, mensaje_error)
    """
    # Validar nombre
    if not nombre or len(nombre.strip()) < 3:
        return False, 'El nombre del consultorio debe tener al menos 3 caracteres.'
    
    # Validar dirección
    if not direccion or len(direccion.strip()) < 5:
        return False, 'La dirección debe tener al menos 5 caracteres.'
    
    # Validar correo
    if not correo or not validar_correo(correo):
        return False, 'El correo electrónico no tiene un formato válido.'
    
    # Normalizar y validar teléfono
    telefono_normalizado = normalizar_telefono(telefono)
    if not validar_telefono(telefono_normalizado):
        return False, 'El número de teléfono no es válido. Debe ser paraguayo (ej: 0981234567).'
    
    return True, None


# ==========================================
# ENDPOINTS REST
# ==========================================

@consultorioapi.route('/consultorios', methods=['GET'])
def getConsultorios():
    """
    GET /api/v1/consultorios
    Obtiene todos los consultorios
    """
    try:
        consultorios = dao.getConsultorios()
        return jsonify({'success': True, 'data': consultorios}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener consultorios: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno del servidor.'}), 500


@consultorioapi.route('/consultorios/<int:codigo>', methods=['GET'])
def getConsultorio(codigo):
    """
    GET /api/v1/consultorios/<codigo>
    Obtiene un consultorio por su código
    """
    try:
        consultorio = dao.getConsultorioById(codigo)
        if consultorio:
            return jsonify({'success': True, 'data': consultorio}), 200
        return jsonify({'success': False, 'error': 'Consultorio no encontrado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener consultorio: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno del servidor.'}), 500


@consultorioapi.route('/consultorios', methods=['POST'])
def addConsultorio():
    """
    POST /api/v1/consultorios
    Crea un nuevo consultorio
    
    Body JSON:
    {
        "nombre_consultorio": "Consultorio Central",
        "direccion": "Av. Principal 123",
        "telefono": "0981234567",
        "correo": "info@consultorio.com"
    }
    """
    data = request.get_json()

    # Validar campos obligatorios
    required_fields = ['nombre_consultorio', 'direccion', 'telefono', 'correo']
    for field in required_fields:
        if field not in data or not str(data[field]).strip():
            return jsonify({
                'success': False, 
                'error': f'El campo "{field}" es obligatorio.'
            }), 400

    nombre = data['nombre_consultorio'].strip()
    direccion = data['direccion'].strip()
    telefono = data['telefono'].strip()
    correo = data['correo'].strip()

    # Validaciones de formato a nivel API
    es_valido, mensaje_error = validar_datos_consultorio(nombre, direccion, telefono, correo)
    if not es_valido:
        return jsonify({'success': False, 'error': mensaje_error}), 400

    # Normalizar teléfono antes de enviar al DAO
    telefono = normalizar_telefono(telefono)

    try:
        codigo = dao.guardarConsultorio(nombre, direccion, telefono, correo)
        return jsonify({
            'success': True,
            'mensaje': 'Consultorio registrado correctamente.',
            'data': {
                'codigo': codigo,
                'nombre_consultorio': nombre,
                'direccion': direccion,
                'telefono': telefono,
                'correo': correo
            }
        }), 201

    except ValueError as e:
        # Errores de validación del DAO (como duplicados)
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        app.logger.error(f"Error al agregar consultorio: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno del servidor.'}), 500


@consultorioapi.route('/consultorios/<int:codigo>', methods=['PUT'])
def updateConsultorio(codigo):
    """
    PUT /api/v1/consultorios/<codigo>
    Actualiza un consultorio existente
    
    Body JSON:
    {
        "nombre_consultorio": "Consultorio Central",
        "direccion": "Av. Principal 123",
        "telefono": "0981234567",
        "correo": "info@consultorio.com"
    }
    """
    data = request.get_json()

    # Validar campos obligatorios
    required_fields = ['nombre_consultorio', 'direccion', 'telefono', 'correo']
    for field in required_fields:
        if field not in data or not str(data[field]).strip():
            return jsonify({
                'success': False, 
                'error': f'El campo "{field}" es obligatorio.'
            }), 400

    nombre = data['nombre_consultorio'].strip()
    direccion = data['direccion'].strip()
    telefono = data['telefono'].strip()
    correo = data['correo'].strip()

    # Validaciones de formato a nivel API
    es_valido, mensaje_error = validar_datos_consultorio(nombre, direccion, telefono, correo)
    if not es_valido:
        return jsonify({'success': False, 'error': mensaje_error}), 400

    # Normalizar teléfono antes de enviar al DAO
    telefono = normalizar_telefono(telefono)

    try:
        # Verificar si existe el consultorio
        consultorio_existente = dao.getConsultorioById(codigo)
        if not consultorio_existente:
            return jsonify({'success': False, 'error': 'Consultorio no encontrado.'}), 404

        # Actualizar (el DAO también valida duplicados)
        if dao.updateConsultorio(codigo, nombre, direccion, telefono, correo):
            return jsonify({
                'success': True,
                'mensaje': 'Consultorio actualizado correctamente.',
                'data': {
                    'codigo': codigo,
                    'nombre_consultorio': nombre,
                    'direccion': direccion,
                    'telefono': telefono,
                    'correo': correo
                }
            }), 200
        return jsonify({'success': False, 'error': 'No se pudo actualizar el consultorio.'}), 500

    except ValueError as e:
        # Errores de validación del DAO (como duplicados)
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        app.logger.error(f"Error al actualizar consultorio: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno del servidor.'}), 500


@consultorioapi.route('/consultorios/<int:codigo>', methods=['DELETE'])
def deleteConsultorio(codigo):
    """
    DELETE /api/v1/consultorios/<codigo>
    Elimina un consultorio
    """
    try:
        if dao.deleteConsultorio(codigo):
            return jsonify({
                'success': True, 
                'mensaje': f'Consultorio eliminado correctamente.'
            }), 200
        return jsonify({
            'success': False, 
            'error': 'Consultorio no encontrado o no se pudo eliminar.'
        }), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar consultorio: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno del servidor.'}), 500