"""
=====================================================
API: Diagnóstico
Descripción: Endpoints REST para diagnósticos médicos
=====================================================
"""

from flask import Blueprint, request, jsonify, session, current_app as app
from app.dao.referenciales_consultorio.diagnostico.DiagnosticoDao import DiagnosticoDao
from app.rutas.modulo_seguridad.decorators import require_permiso, require_login

# Crear Blueprint
diagnostico_medico_api = Blueprint('diagnostico_medico_api', __name__)

# =====================================================
# ENDPOINT: OBTENER TODOS LOS DIAGNÓSTICOS
# =====================================================
@diagnostico_medico_api.route('/diagnosticos-medicos', methods=['GET'])
@require_permiso('diagnostico', 'ver')
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
@require_permiso('diagnostico', 'ver')
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
@require_permiso('diagnostico', 'ver')
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
@require_login  # lookup: lo consumen otras pantallas
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
@require_permiso('diagnostico', 'nuevo')
def addDiagnosticoMedico():
    """
    Crea un nuevo diagnóstico médico
    
    URL: POST /api/v1/diagnosticos-medicos
    
    Body JSON:
    {
        "id_consulta_cab": 1,
        "id_tipo_diagnostico": 2,
        "descripcion_diagnostico": "Caries dental profunda",
        "pieza_dental": "18",
        "fecha_diagnostico": "2025-10-22",
        "sintomas": [1, 4],
        "observaciones": "Requiere tratamiento urgente"
    }
    Paciente y médico se derivan de la consulta (no se toman del body).
    `sintomas` es la lista de id_sintoma elegidos del referencial Síntomas.
    """
    data = request.get_json(silent=True) or {}
    diagnosticoDao = DiagnosticoDao()

    # ========== VALIDACIONES ==========
    campos_requeridos = ['id_consulta_cab', 'id_tipo_diagnostico', 'descripcion_diagnostico', 'fecha_diagnostico']

    for campo in campos_requeridos:
        if data.get(campo) in (None, ''):
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio y no puede estar vacío.'
            }), 400

    sintomas = data.get('sintomas') or []
    if not isinstance(sintomas, list) or any(isinstance(s, bool) or not isinstance(s, int) for s in sintomas):
        return jsonify({
            'success': False,
            'error': 'Los síntomas deben enviarse como una lista de IDs.'
        }), 400

    ERRORES = {
        'CONSULTA_NO_ENCONTRADA': (404, 'No se encontró la consulta seleccionada.'),
        'CONSULTA_FINALIZADA': (409, 'No se puede registrar: la consulta ya está finalizada.'),
        'SINTOMA_INVALIDO': (400, 'Alguno de los síntomas seleccionados no existe.'),
        'ERROR_INTERNO': (500, 'No se pudo guardar el diagnóstico. Consulte con el administrador.'),
    }

    try:
        resultado = diagnosticoDao.guardarDiagnostico(data, session.get('id_usuario'))

        if 'id_diagnostico' in resultado:
            return jsonify({
                'success': True,
                'data': {
                    'id_diagnostico': resultado['id_diagnostico'],
                    'codigo': resultado['codigo'],
                    'mensaje': 'Diagnóstico registrado correctamente'
                },
                'error': None
            }), 201

        codigo, mensaje = ERRORES.get(resultado.get('error'), ERRORES['ERROR_INTERNO'])
        return jsonify({'success': False, 'error': mensaje}), codigo

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
@require_permiso('diagnostico', 'anular')
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