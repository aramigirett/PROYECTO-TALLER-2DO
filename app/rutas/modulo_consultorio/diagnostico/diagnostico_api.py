"""
=====================================================
API: Diagnóstico
Descripción: Endpoints REST para diagnósticos médicos
=====================================================
"""

from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_consultorio.diagnostico.DiagnosticoDao import DiagnosticoDao

# Crear Blueprint
diagnostico_medico_api = Blueprint('diagnostico_medico_api', __name__)

# =====================================================
# ENDPOINT: OBTENER TODOS LOS DIAGNÓSTICOS
# =====================================================
@diagnostico_medico_api.route('/diagnosticos-medicos', methods=['GET'])
def getDiagnosticosMedicos():
    """
    Obtiene todos los diagnósticos médicos
    
    URL: GET /api/v1/diagnosticos-medicos
    """
    diagnosticoDao = DiagnosticoDao()

    try:
        diagnosticos = diagnosticoDao.getDiagnosticos()

        return jsonify({
            'success': True,
            'data': diagnosticos,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener diagnósticos: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: OBTENER UN DIAGNÓSTICO POR ID
# =====================================================
@diagnostico_medico_api.route('/diagnosticos-medicos/<int:diagnostico_id>', methods=['GET'])
def getDiagnosticoMedico(diagnostico_id):
    """
    Obtiene un diagnóstico específico por ID
    
    URL: GET /api/v1/diagnosticos-medicos/5
    """
    diagnosticoDao = DiagnosticoDao()

    try:
        diagnostico = diagnosticoDao.getDiagnosticoById(diagnostico_id)

        if diagnostico:
            return jsonify({
                'success': True,
                'data': diagnostico,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el diagnóstico con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener diagnóstico: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: OBTENER DIAGNÓSTICOS DE UN PACIENTE
# =====================================================
@diagnostico_medico_api.route('/diagnosticos-medicos/paciente/<int:paciente_id>', methods=['GET'])
def getDiagnosticosByPaciente(paciente_id):
    """
    Obtiene todos los diagnósticos de un paciente
    
    URL: GET /api/v1/diagnosticos-medicos/paciente/5
    """
    diagnosticoDao = DiagnosticoDao()

    try:
        diagnosticos = diagnosticoDao.getDiagnosticosByPaciente(paciente_id)

        return jsonify({
            'success': True,
            'data': diagnosticos,
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al obtener diagnósticos del paciente: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: OBTENER DIAGNÓSTICOS DE UNA CONSULTA (para Gestionar Tratamientos)
# =====================================================
@diagnostico_medico_api.route('/diagnosticos-medicos/consulta/<int:id_consulta_cab>', methods=['GET'])
def getDiagnosticosByConsulta(id_consulta_cab):
    """
    Obtiene los diagnósticos vinculados a una consulta específica.

    URL: GET /api/v1/diagnosticos-medicos/consulta/5
    """
    diagnosticoDao = DiagnosticoDao()

    try:
        diagnosticos = diagnosticoDao.getDiagnosticosByConsulta(id_consulta_cab)
        return jsonify({
            'success': True,
            'data': diagnosticos,
            'error': None
        }), 200
    except Exception as e:
        app.logger.error(f"Error al obtener diagnósticos de la consulta: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: AGREGAR NUEVO DIAGNÓSTICO
# =====================================================
@diagnostico_medico_api.route('/diagnosticos-medicos', methods=['POST'])
def addDiagnosticoMedico():
    """
    Crea un nuevo diagnóstico médico
    
    URL: POST /api/v1/diagnosticos-medicos
    
    Body JSON:
    {
        "id_consulta_detalle": 1,
        "id_paciente": 5,
        "id_medico": 3,
        "id_tipo_diagnostico": 2,
        "descripcion_diagnostico": "Caries dental profunda",
        "pieza_dental": "18",
        "fecha_diagnostico": "2025-10-22",
        "sintomas": "Dolor intenso al masticar",
        "observaciones": "Requiere tratamiento urgente"
    }
    """
    data = request.get_json()
    diagnosticoDao = DiagnosticoDao()

    # ========== VALIDACIONES ==========
    campos_requeridos = ['id_paciente', 'id_medico', 'id_tipo_diagnostico', 'descripcion_diagnostico', 'fecha_diagnostico']

    for campo in campos_requeridos:
        if campo not in data or data[campo] is None:
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    try:
        # Guardar diagnóstico
        diagnostico_id = diagnosticoDao.guardarDiagnostico(data)
        
        if diagnostico_id is not None:
            return jsonify({
                'success': True,
                'data': {
                    'id_diagnostico': diagnostico_id,
                    'mensaje': 'Diagnóstico registrado correctamente'
                },
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo guardar el diagnóstico. Consulte con el administrador.'
            }), 500

    except Exception as e:
        app.logger.error(f"Error al agregar diagnóstico: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: ANULAR DIAGNÓSTICO (baja lógica)
# =====================================================
@diagnostico_medico_api.route('/diagnosticos-medicos/<int:diagnostico_id>', methods=['DELETE'])
def deleteDiagnosticoMedico(diagnostico_id):
    """
    Anula (baja lógica) un diagnóstico. Se bloquea si tiene un Tratamiento
    asociado, o si la consulta a la que pertenece ya está finalizada.

    URL: DELETE /api/v1/diagnosticos-medicos/5
    """
    diagnosticoDao = DiagnosticoDao()

    try:
        registro = diagnosticoDao.getDiagnosticoById(diagnostico_id)
        resultado = diagnosticoDao.deleteDiagnostico(diagnostico_id)

        if resultado == "EN_USO":
            return jsonify({
                'success': False,
                'error': 'No se puede anular: este diagnóstico tiene un tratamiento asociado.'
            }), 409

        if resultado == "CONSULTA_FINALIZADA":
            return jsonify({
                'success': False,
                'error': 'No se puede anular: la consulta asociada ya está finalizada.'
            }), 409

        if resultado:
            codigo = registro['codigo'] if registro else 'seleccionado'
            return jsonify({
                'success': True,
                'mensaje': f'Diagnóstico {codigo} anulado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró el diagnóstico con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al anular diagnóstico: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500