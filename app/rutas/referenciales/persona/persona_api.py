from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.persona.PersonaDao import PersonaDao

persapi = Blueprint('persapi', __name__)

# Trae todas las personas
@persapi.route('/personas', methods=['GET'])
def getPersonas():
    personadao = PersonaDao()

    try:
        personas = personadao.getPersonas()

        return jsonify({
            'success': True,
            'data': personas,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener todas las personas: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@persapi.route('/personas/<int:persona_id>', methods=['GET'])
def getPersona(persona_id):
    personadao = PersonaDao()

    try:
        persona = personadao.getPersonaById(persona_id)

        if persona:
            return jsonify({
                'success': True,
                'data': persona,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la persona con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener persona: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Agrega una nueva persona
@persapi.route('/personas', methods=['POST'])
def addPersona():
    data = request.get_json()
    personadao = PersonaDao()

    # Validar que el JSON no esté vacío y tenga las propiedades necesarias
    campos_requeridos = ['nombre', 'apellido', 'fechanacimiento', 'cedula', 'sexo', 'telefono', 'id_ciudad', 'id_pais', 'id_nacionalidad']

    # Verificar si faltan campos o son vacíos
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None or len(data[campo].strip()) == 0:
            return jsonify({
                            'success': False,
                            'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
                            }), 400

    try:
        nombre = data['nombre'].strip().upper()  # Quita espacios y convierte a mayúsculas
        apellido = data['apellido'].strip().upper()
        fechanacimiento = data['fechanacimiento']  # Suponiendo que ya está en formato correcto
        cedula = data['cedula'].strip()  # Elimina espacios en blanco
        sexo = data['sexo']  # Verifica si ya es booleano o un string limpio
        telefono = data['telefono'].strip()  # Elimina espacios si es una cadena
        id_ciudad = int(data['id_ciudad'])  # Convierte a entero si aplica
        id_pais = int(data['id_pais'])  # Convierte a entero si aplica
        id_nacionalidad = int(data['id_nacionalidad'])  # Sin coma para evitar una tupla

        persona_id = personadao.guardarPersona(nombre, apellido, fechanacimiento, cedula, sexo, telefono, id_ciudad, id_pais, id_nacionalidad)
        if persona_id is not None:
            return jsonify({
                'success': True,
                'data': {'id': persona_id, 'nombre': nombre, 'apellido': apellido, 'fechanacimiento': fechanacimiento, 'cedula': cedula, 'sexo': sexo, 'telefono': telefono, 'id_ciudad': id_ciudad, 'id_pais': id_pais, 'id_nacionalidad': id_nacionalidad},
                'error': None
            }), 201
        else:
            return jsonify({ 'success': False, 'error': 'No se pudo guardar persona. Consulte con el administrador.' }), 500
    except Exception as e:
        app.logger.error(f"Error al agregar persona: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@persapi.route('/personas/<int:persona_id>', methods=['PUT'])
def updatePersona(persona_id):
    data = request.get_json()
    personadao = PersonaDao()

    # Validar que el JSON no esté vacío y tenga las propiedades necesarias
    campos_requeridos = ['nombre', 'apellido', 'fechanacimiento', 'cedula', 'sexo', 'telefono', 'id_ciudad', 'id_pais', 'id_nacionalidad']

    # Verificar si faltan campos o son vacíos
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None or len(data[campo].strip()) == 0:
            return jsonify({
                            'success': False,
                            'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
                            }), 400
        
    try:
        nombre = data['nombre'].strip().upper()  # Quita espacios y convierte a mayúsculas
        apellido = data['apellido'].strip().upper()
        fechanacimiento = data['fechanacimiento']  # Suponiendo que ya está en formato correcto
        cedula = data['cedula'].strip()  # Elimina espacios en blanco
        sexo = data['sexo']  # Verifica si ya es booleano o un string limpio
        telefono = data['telefono'].strip()  # Elimina espacios si es una cadena
        id_ciudad = int(data['id_ciudad'])  # Convierte a entero si aplica
        id_pais = int(data['id_pais'])  # Convierte a entero si aplica
        id_nacionalidad = int(data['id_nacionalidad'])  # Sin coma para evitar una tupla

        if personadao.updatePersona(persona_id, nombre.upper(), apellido.upper(), fechanacimiento, cedula, sexo, telefono, id_ciudad, id_pais, id_nacionalidad):
            return jsonify({
                'success': True,
                'data': {'id': persona_id, 'nombre': nombre, 'apellido': apellido, 'fechanacimiento': fechanacimiento, 'cedula': cedula, 'sexo': sexo, 'telefono': telefono, 'id_ciudad': id_ciudad, 'id_pais': id_pais, 'id_nacionalidad': id_nacionalidad},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la persona con el ID proporcionado o no se pudo actualizar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar persona: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@persapi.route('/personas/<int:persona_id>', methods=['DELETE'])
def deletePersona(persona_id):
    personadao = PersonaDao()

    try:
        # Usar el retorno de eliminarPersona para determinar el éxito
        if personadao.deletePersona(persona_id):
            return jsonify({
                'success': True,
                'mensaje': f'Persona con ID {persona_id} eliminada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la persona con el ID proporcionado o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar persona: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500