from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales.historia_clinica.HistoriaClinicaDao import HistoriaClinicaDao

histocliapi = Blueprint('histocliapi', __name__)

@histocliapi.route('/historiaclinica', methods=['GET'])
def getHistoriasClinicas():
    histoclidao = HistoriaClinicaDao()

    try:
        historiasclinicas = histoclidao.getHistoriasClinicas()

        return jsonify({
            'success': True,
            'data': historiasclinicas,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener todas las historias clinicas: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@histocliapi.route('/historiasclinicas/<int:historiaclinica_id>', methods=['GET'])
def getHistoriaClinica(historiaclinica_id):
    histoclidao = HistoriaClinicaDao()

    try:
        historiaclinica = histoclidao.getHistoriaClinicaById(historiaclinica_id)

        if historiaclinica:
            return jsonify({
                'success': True,
                'data': historiaclinica,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el historial clínico con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener historia clinica: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

# Agrega una nueva Historia Clínica
@histocliapi.route('/historiasclinicas', methods=['POST'])
def addHistoriaClinica():
    data = request.get_json()
    histoclidao = HistoriaClinicaDao()

    # Validar que el JSON tenga las propiedades necesarias
    campos_requeridos = ['motivo_consulta', 'antecedentes_medicos', 'antecedentes_psicologicos', 'historia_familiar']

    # Verificar si faltan campos o son vacíos
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None or len(data[campo].strip()) == 0:
            return jsonify({
                            'success': False,
                            'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
                            }), 400

    try:
        motivo_consulta = data['motivo_consulta']
        antecedentes_medicos = data['antecedentes_medicos']
        antecedentes_psicologicos = data['antecedentes_psicologicos']
        historia_familiar = data['historia_familiar']

        historiaclinica_id = histoclidao.guardarHistoriaClinica(motivo_consulta, antecedentes_medicos, antecedentes_psicologicos, historia_familiar)
        
        if historiaclinica_id is not None:
            return jsonify({
                'success': True,
                'data': {
                    'id': historiaclinica_id,
                    'motivo_consulta': motivo_consulta,
                    'antecedentes_medicos': antecedentes_medicos,
                    'antecedentes_psicologicos': antecedentes_psicologicos,
                    'historia_familiar': historia_familiar
                },
                'error': None
            }), 201
        else:
            return jsonify({ 'success': False, 'error': 'No se pudo guardar la Historia Clínica. Consulte con el administrador.' }), 500
    except Exception as e:
        app.logger.error(f"Error al agregar Historia Clinica: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@histocliapi.route('/historiasclinicas/<int:historiaclinica_id>', methods=['PUT'])
def updateHistoriaClinica(historiaclinica_id):
    data = request.get_json()
    histoclidao = HistoriaClinicaDao()

    # Validar que el JSON tenga las propiedades necesarias
    campos_requeridos = ['motivo_consulta', 'antecedentes_medicos', 'antecedentes_psicologicos', 'historia_familiar']

    # Verificar si faltan campos o son vacíos
    for campo in campos_requeridos:
        if campo not in data or data[campo] is None or len(data[campo].strip()) == 0:
            return jsonify({
                            'success': False,
                            'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
                            }), 400

    motivo_consulta = data['motivo_consulta']
    antecedentes_medicos = data['antecedentes_medicos']
    antecedentes_psicologicos = data['antecedentes_psicologicos']
    historia_familiar = data['historia_familiar']

    try:
        if histoclidao.updateHistoriaClinica(historiaclinica_id, motivo_consulta, antecedentes_medicos, antecedentes_psicologicos, historia_familiar):
            return jsonify({
                'success': True,
                'data': {
                    'id': historiaclinica_id,
                    'motivo_consulta': motivo_consulta,
                    'antecedentes_medicos': antecedentes_medicos,
                    'antecedentes_psicologicos': antecedentes_psicologicos,
                    'historia_familiar': historia_familiar
                },
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el historial clínico con el ID proporcionado o no se pudo actualizar.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar Historia Clinica: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500

@histocliapi.route('/historiasclinicas/<int:historiaclinica_id>', methods=['DELETE'])
def deleteHistoriaClinica(historiaclinica_id):
    histoclidao = HistoriaClinicaDao()

    try:
        if histoclidao.deleteHistoriaClinica(historiaclinica_id):
            return jsonify({
                'success': True,
                'mensaje': f'Historia Clínica con ID {historiaclinica_id} eliminada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el historial clínico con el ID proporcionado o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar Historia Clinica: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500