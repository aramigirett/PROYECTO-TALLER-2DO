"""
=====================================================
API: Ficha Médica de Consulta
Descripción: Endpoints REST para fichas médicas
=====================================================
"""

from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_consultorio.consulta.FichaMedicaDao import FichaMedicaDao

# Crear Blueprint
fichamedicaapi = Blueprint('fichamedicaapi', __name__)

# =====================================================
# ENDPOINT: OBTENER FICHA MÉDICA DE UNA CONSULTA
# =====================================================
@fichamedicaapi.route('/ficha-medica/consulta/<int:consulta_id>', methods=['GET'])
def getFichaByConsulta(consulta_id):
    """
    Obtiene la ficha médica de una consulta específica
    
    URL: GET /api/v1/ficha-medica/consulta/5
    """
    fichaDao = FichaMedicaDao()

    try:
        ficha = fichaDao.getFichaByConsulta(consulta_id)

        if ficha:
            return jsonify({
                'success': True,
                'data': ficha,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró ficha médica para esta consulta.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener ficha médica: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: OBTENER FICHA MÉDICA POR ID
# =====================================================
@fichamedicaapi.route('/ficha-medica/<int:ficha_id>', methods=['GET'])
def getFicha(ficha_id):
    """
    Obtiene una ficha médica por su ID
    
    URL: GET /api/v1/ficha-medica/10
    """
    fichaDao = FichaMedicaDao()

    try:
        ficha = fichaDao.getFichaById(ficha_id)

        if ficha:
            return jsonify({
                'success': True,
                'data': ficha,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la ficha médica con el ID proporcionado.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al obtener ficha médica: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: CREAR NUEVA FICHA MÉDICA
# =====================================================
@fichamedicaapi.route('/ficha-medica', methods=['POST'])
def addFicha():
    """
    Crea una nueva ficha médica
    
    URL: POST /api/v1/ficha-medica
    
    Body JSON:
    {
        "id_consulta_cab": 5,
        "presion_arterial": "120/80",
        "temperatura": 36.5,
        "frecuencia_cardiaca": 72,
        "frecuencia_respiratoria": 16,
        "peso": 70.5,
        "talla": 175,
        "imc": 23.0,
        "examen_fisico_general": "...",
        "examen_bucal": "...",
        "observaciones_medico": "..."
    }
    """
    data = request.get_json()
    fichaDao = FichaMedicaDao()

    # Validación: id_consulta_cab es obligatorio
    if 'id_consulta_cab' not in data or data['id_consulta_cab'] is None:
        return jsonify({
            'success': False,
            'error': 'El campo id_consulta_cab es obligatorio.'
        }), 400

    try:
        # Verificar si ya existe una ficha para esta consulta
        ficha_existente = fichaDao.getFichaByConsulta(data['id_consulta_cab'])
        if ficha_existente:
            return jsonify({
                'success': False,
                'error': 'Ya existe una ficha médica para esta consulta. Use PUT para actualizar.'
            }), 400

        # Guardar nueva ficha
        ficha_id = fichaDao.guardarFicha(data)
        
        if ficha_id is not None:
            return jsonify({
                'success': True,
                'data': {
                    'id_ficha_medica': ficha_id,
                    'mensaje': 'Ficha médica creada correctamente'
                },
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo guardar la ficha médica.'
            }), 500

    except Exception as e:
        app.logger.error(f"Error al crear ficha médica: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: ACTUALIZAR FICHA MÉDICA
# =====================================================
@fichamedicaapi.route('/ficha-medica/<int:ficha_id>', methods=['PUT'])
def updateFicha(ficha_id):
    """
    Actualiza una ficha médica existente
    
    URL: PUT /api/v1/ficha-medica/10
    """
    data = request.get_json()
    fichaDao = FichaMedicaDao()

    try:
        if fichaDao.updateFicha(ficha_id, data):
            return jsonify({
                'success': True,
                'data': {
                    'id_ficha_medica': ficha_id,
                    'mensaje': 'Ficha médica actualizada correctamente'
                },
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo actualizar la ficha médica.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al actualizar ficha médica: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500


# =====================================================
# ENDPOINT: ELIMINAR FICHA MÉDICA
# =====================================================
@fichamedicaapi.route('/ficha-medica/<int:ficha_id>', methods=['DELETE'])
def deleteFicha(ficha_id):
    """
    Elimina una ficha médica
    
    URL: DELETE /api/v1/ficha-medica/10
    """
    fichaDao = FichaMedicaDao()

    try:
        if fichaDao.deleteFicha(ficha_id):
            return jsonify({
                'success': True,
                'mensaje': f'Ficha médica con ID {ficha_id} eliminada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No se encontró la ficha médica o no se pudo eliminar.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al eliminar ficha médica: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500
    
    # =====================================================
# ENDPOINT: OBTENER TODAS LAS FICHAS CON INFO COMPLETA
# =====================================================
@fichamedicaapi.route('/fichas-todas', methods=['GET'])
def getFichasTodas():
    """
    Obtiene todas las fichas médicas con información de consulta, paciente y médico
    
    URL: GET /api/v1/fichas-todas
    """
    from app.dao.referenciales_consultorio.consulta.FichaMedicaDao import FichaMedicaDao
    
    fichaSQL = """
    SELECT 
        fm.id_ficha_medica,
        fm.id_consulta_cab,
        cc.fecha_cita as fecha_consulta,
        CONCAT(p.nombre, ' ', p.apellido) as nombre_paciente,
        CONCAT(m.nombre, ' ', m.apellido) as nombre_medico,
        fm.presion_arterial,
        fm.temperatura,
        fm.frecuencia_cardiaca,
        fm.frecuencia_respiratoria,
        fm.peso,
        fm.talla,
        fm.imc,
        fm.examen_fisico_general,
        fm.examen_bucal,
        fm.observaciones_medico,
        fm.fecha_registro
    FROM ficha_medica_consulta fm
    INNER JOIN consultas_cab cc ON fm.id_consulta_cab = cc.id_consulta_cab
    INNER JOIN paciente p ON cc.id_paciente = p.id_paciente
    INNER JOIN medico m ON cc.id_medico = m.id_medico
    WHERE fm.activo = true AND cc.activo = true
    ORDER BY cc.fecha_cita DESC, fm.fecha_registro DESC
    """
    
    from app.conexion.Conexion import Conexion
    conexion = Conexion()
    con = conexion.getConexion()
    cur = con.cursor()
    
    try:
        cur.execute(fichaSQL)
        fichas = cur.fetchall()
        
        resultado = [{
            'id_ficha_medica': f[0],
            'id_consulta_cab': f[1],
            'fecha_consulta': f[2].isoformat() if f[2] else None,
            'nombre_paciente': f[3],
            'nombre_medico': f[4],
            'presion_arterial': f[5],
            'temperatura': float(f[6]) if f[6] else None,
            'frecuencia_cardiaca': f[7],
            'frecuencia_respiratoria': f[8],
            'peso': float(f[9]) if f[9] else None,
            'talla': float(f[10]) if f[10] else None,
            'imc': float(f[11]) if f[11] else None,
            'examen_fisico_general': f[12],
            'examen_bucal': f[13],
            'observaciones_medico': f[14],
            'fecha_registro': f[15].isoformat() if f[15] else None
        } for f in fichas]
        
        return jsonify({
            'success': True,
            'data': resultado,
            'error': None
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error al obtener fichas: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno. Consulte con el administrador.'
        }), 500
        
    finally:
        cur.close()
        con.close()