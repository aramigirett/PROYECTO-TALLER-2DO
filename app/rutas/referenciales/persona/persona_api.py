from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.persona.PersonaDao import PersonaDao

personaapi = Blueprint('personaapi', __name__)

@personaapi.route('/personas', methods=['GET'])
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
        app.logger.error(f"Error al obtener todos los pacientes: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


@personaapi.route('/personas/<int:persona_id>', methods=['GET'])
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
                'error': 'No se encontró el paciente con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener el paciente: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


@personaapi.route('/personas', methods=['POST'])
def addPersona():
    data = request.get_json()
    personadao = PersonaDao()

    # Validar que el JSON tenga las propiedades necesarias
    campos_requeridos = ['id_paciente','fecha_nacimiento']

    # Verificar si faltan campos o son vacíos
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        id_paciente = data['id_paciente']
        fecha_nacimiento = data['fecha_nacimiento']  # Formato esperado: YYYY-MM-DD

        persona_id = personadao.guardarPersona(id_paciente,fecha_nacimiento)
        if persona_id is not None:
            return jsonify({
                'success': True,
                'data': {'id_persona': persona_id, 'id_paciente': id_paciente, 'fecha_nacimiento': fecha_nacimiento},
                'error': None
            }), 201
        else:
            return jsonify({'success': False, 'error': 'No se pudo guardar el paciente. Consulte con el administrador.'}), 500

    except Exception as e:
        print("aaa")
        app.logger.error(f"Error al agregar paciente: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


@personaapi.route('/personas/<int:persona_id>', methods=['PUT'])
def updatePersona(persona_id):
    data = request.get_json()
    personadao = PersonaDao()

    # Validar que el JSON tenga las propiedades necesarias
    campos_requeridos = ['id_paciente','fecha_nacimiento' ]

    # Verificar si faltan campos o son vacíos
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        id_paciente = data['id_paciente']
        fecha_nacimiento = data['fecha_nacimiento']  # Formato esperado: YYYY-MM-DD

        if personadao.updatePersona(persona_id, id_paciente, fecha_nacimiento,):
            return jsonify({
                'success': True,
                'data': {'id_persona': persona_id, 'id_persona': persona_id,'id_paciente': id_paciente, 'fecha_nacimiento': fecha_nacimiento},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el paciente con el ID proporcionado o no se pudo actualizar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al actualizar paciente: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


@personaapi.route('/personas/<int:persona_id>', methods=['DELETE'])
def deletePersona(persona_id):
    personadao = PersonaDao()

    try:
        if personadao.deletePersona(persona_id):
            return jsonify({
                'success': True,
                'mensaje': f'Paciente con ID {persona_id} eliminado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el paciente con el ID proporcionado o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar paciente: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500
