from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_consultorio.sintomas.SintomasDao import SintomaDao
import re

def descripcion_valida(texto: str) -> bool:
    """
    Valida que la descripción solo contenga letras, números, acentos, ñ y espacios.
    Compatible con cualquier versión de Python.
    """
    if not texto:
        return False
    texto = texto.strip()
    patron = r'^[A-Za-z0-9ÁÉÍÓÚÑáéíóúñ\s]+$'
    return re.match(patron, texto) is not None

def descripcion_valida(texto: str) -> bool:
        """
         Valida que la descripción solo contenga letras, acentos, ñ y espacios (sin números).
         """
        if not texto:
         return False
        texto = texto.strip()
        patron = r'^[A-Za-zÁÉÍÓÚÑáéíóúñ\s]+$'  # SIN números
        return re.match(patron, texto) is not None

sintomaapi = Blueprint('sintomaapi', __name__)

# Trae todos los síntomas
@sintomaapi.route('/sintomas', methods=['GET'])
def getSintomas():
    sdao = SintomaDao()
    try:
        sintomas = sdao.getSintomas()
        return jsonify({
            'success': True,
            'data': sintomas,
            'error': None
        }), 200
    except Exception as e:
        app.logger.error(f"Error al obtener todos los síntomas: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Ocurrió un error interno: {str(e)}'
        }), 500

# Trae un síntoma por ID
@sintomaapi.route('/sintomas/<int:id_sintoma>', methods=['GET'])
def getSintoma(id_sintoma):
    sdao = SintomaDao()
    try:
        sintoma = sdao.getSintomaById(id_sintoma)
        if sintoma:
            return jsonify({
                'success': True,
                'data': sintoma,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el síntoma con el ID proporcionado.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al obtener síntoma: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Ocurrió un error interno: {str(e)}'
        }), 500

# Agrega un nuevo síntoma
@sintomaapi.route('/sintomas', methods=['POST'])
def addSintoma():
    data = request.get_json()
    sdao = SintomaDao()

    if 'descripcion_sintoma' not in data or not data['descripcion_sintoma'].strip():
        return jsonify({
            'success': False,
            'error': 'El campo descripcion_sintoma es obligatorio y no puede estar vacío.'
        }), 400

    descripcion = data['descripcion_sintoma'].strip()
    if not descripcion_valida(descripcion):
        return jsonify({
            'success': False,
            'error': 'La descripción solo puede contener letras y espacios.'
        }), 400

    try:
        if sdao.sintomaExiste(descripcion):
            return jsonify({
                'success': False,
                'error': f'El síntoma "{descripcion}" ya existe.'
            }), 409

        id_sintoma = sdao.guardarSintoma(descripcion)
        if id_sintoma:
            return jsonify({
                'success': True,
                'data': {'id_sintoma': id_sintoma, 'descripcion_sintoma': descripcion},
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo guardar el síntoma. Consulte con el administrador.'
            }), 500

    except Exception as e:
        app.logger.error(f"Error al agregar síntoma: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Ocurrió un error interno: {str(e)}'
        }), 500

# Actualiza un síntoma
@sintomaapi.route('/sintomas/<int:id_sintoma>', methods=['PUT'])
def updateSintoma(id_sintoma):
    data = request.get_json()
    sdao = SintomaDao()

    if 'descripcion_sintoma' not in data or not data['descripcion_sintoma'].strip():
        return jsonify({
            'success': False,
            'error': 'El campo descripcion_sintoma es obligatorio y no puede estar vacío.'
        }), 400

    descripcion = data['descripcion_sintoma'].strip()
    if not descripcion_valida(descripcion):
        return jsonify({
            'success': False,
            'error': 'La descripción solo puede contener letras, números y espacios.'
        }), 400

    try:
        if sdao.updateSintoma(id_sintoma, descripcion):
            return jsonify({
                'success': True,
                'data': {'id_sintoma': id_sintoma, 'descripcion_sintoma': descripcion},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'La descripción ya está en uso o el ID no existe.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al actualizar síntoma: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Ocurrió un error interno: {str(e)}'
        }), 500

# Elimina un síntoma
@sintomaapi.route('/sintomas/<int:id_sintoma>', methods=['DELETE'])
def deleteSintoma(id_sintoma):
    sdao = SintomaDao()
    try:
        if sdao.deleteSintoma(id_sintoma):
            return jsonify({
                'success': True,
                'mensaje': f'Síntoma con ID {id_sintoma} eliminado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el síntoma con el ID proporcionado o no se pudo eliminar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar síntoma: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Ocurrió un error interno: {str(e)}'
        }), 500