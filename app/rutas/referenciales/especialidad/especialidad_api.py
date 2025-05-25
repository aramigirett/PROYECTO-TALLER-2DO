from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.especialidad.EspecialidadDao import EspecialidadDao

especiapi = Blueprint('especiapi', __name__)

# Trae todas las especialidades
@especiapi.route('/especialidades', methods=['GET'])
def getEspecialidades():
    especialidaddao = EspecialidadDao()
    try:
        especialidades = especialidaddao.getEspecialidades()
        return jsonify({
            'success': True,
            'data': especialidades,
            'error': None
        }), 200
    except Exception as e:
        app.logger.error(f"Error al obtener todas las especialidades: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@especiapi.route('/especialidades/<int:id_especialidad>', methods=['GET'])
def getEspecialidad(id_especialidad):
    especialidaddao = EspecialidadDao()
    try:
        especialidad = especialidaddao.getEspecialidadById(id_especialidad)
        if especialidad:
            return jsonify({
                'success': True,
                'data': especialidad,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la especialidad con el ID proporcionado.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al obtener especialidad: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Agrega una nueva especialidad
@especiapi.route('/especialidades', methods=['POST'])
def addEspecialidad():
    data = request.get_json()
    especialidaddao = EspecialidadDao()
    campos_requeridos = ['nombre_especialidad']
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None or len(data[campo].strip()) == 0:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400
    try:
        nombre_especialidad = data['nombre_especialidad'].upper()
        id_especialidad = especialidaddao.guardarEspecialidad(nombre_especialidad)
        if id_especialidad is not None:
            return jsonify({
                'success': True,
                'data': {'id': id_especialidad, 'nombre_especialidad': nombre_especialidad},
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo guardar la especialidad. Consulte con el administrador.'
            }), 500
    except Exception as e:
        app.logger.error(f"Error al agregar especialidad: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@especiapi.route('/especialidades/<int:id_especialidad>', methods=['PUT'])
def updateEspecialidad(id_especialidad):
    data = request.get_json()
    especialidaddao = EspecialidadDao()
    campos_requeridos = ['nombre_especialidad']
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None or len(data[campo].strip()) == 0:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400
    nombre_especialidad = data['nombre_especialidad']
    try:
        if especialidaddao.updateEspecialidad(id_especialidad, nombre_especialidad.upper()):
            return jsonify({
                'success': True,
                'data': {'id': id_especialidad, 'nombre_especialidad': nombre_especialidad},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la especialidad con el ID proporcionado o no se pudo actualizar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar especialidad: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@especiapi.route('/especialidades/<int:id_especialidad>', methods=['DELETE'])
def deleteEspecialidad(id_especialidad):
    especialidaddao = EspecialidadDao()
    try:
        if especialidaddao.deleteEspecialidad(id_especialidad):
            return jsonify({
                'success': True,
                'mensaje': f'Especialidad con ID {id_especialidad} eliminada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la especialidad con el ID proporcionado o no se pudo eliminar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar especialidad: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500
