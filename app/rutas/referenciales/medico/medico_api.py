from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.medico.MedicoDao import MedicoDao

medicoapi = Blueprint('medicoapi', __name__)

# Trae todos los medicos
@medicoapi.route('/medicos', methods=['GET'])
def getMedicos():
    medicodao = MedicoDao()

    try:
        medicos = medicodao.getMedicos()

        return jsonify({
            'success': True,
            'data': medicos,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener todos los medicos: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@medicoapi.route('/medicos/<int:medico_id>', methods=['GET'])
def getMedico(medico_id):
    medicodao = MedicoDao()

    try:
        medico = medicodao.getMedicoById(medico_id)

        if medico:
            return jsonify({
                'success': True,
                'data': medico,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el medico con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener el medico: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

#Agrega un nuevo medico
@medicoapi.route('/medicos', methods=['POST'])
def addMedico():
    data = request.get_json()
    medicodao = MedicoDao()

    # Validar que el JSON no esté vacío y tenga las propiedades necesarias
    campos_requeridos = ['id_paciente','matricula']

    # Verificar si faltan campos o son vacíos
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None or len(data[campo].strip()) == 0:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        #print("hola")
        id_paciente = data['id_paciente']
        matricula = data['matricula'].upper()

        medico_id = medicodao.guardarMedico(id_paciente, matricula)
        if medico_id is not None:
            return jsonify({
                'success': True,
                'data': {'id_medico': medico_id,'id_paciente': id_paciente, 'matricula': matricula},
                'error': None
            }), 201
        else:
            return jsonify({'success': False, 'error': 'No se pudo guardar el medico. Consulte con el administrador.'}), 500
    except Exception as e:
        app.logger.error(f"Error al agregar medico: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@medicoapi.route('/medicos/<int:medico_id>', methods=['PUT'])
def updateMedico(medico_id):
    data = request.get_json()
    medicodao = MedicoDao()
    #print(medico_id)
    # Validar que el JSON no esté vacío y tenga las propiedades necesarias
    campos_requeridos = ['id_paciente','matricula' ]

    # Verificar si faltan campos o son vacíos
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None or len(data[campo].strip()) == 0:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        id_paciente = data['id_paciente']
        matricula = data['matricula'].upper()

        if medicodao.updateMedico(medico_id, id_paciente, matricula):
            return jsonify({
                'success': True,
                'data': {'id_medico': medico_id, 'id_paciente': id_paciente, 'matricula': matricula},
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el medico con el ID proporcionado o no se pudo actualizar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar medico: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@medicoapi.route('/medicos/<int:medico_id>', methods=['DELETE'])
def deleteMedico(medico_id):
    medicodao = MedicoDao()

    try:
        if medicodao.deleteMedico(medico_id):
            return jsonify({
                'success': True,
                'mensaje': f'Medico con ID {medico_id} eliminado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el medico con el ID proporcionado o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar medico: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500
