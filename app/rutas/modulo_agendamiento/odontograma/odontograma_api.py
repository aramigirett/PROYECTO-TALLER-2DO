from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_agendamiento.odontograma.OdontogramaDao import OdontogramaDao
from datetime import date

# Crear Blueprint para la API de Odontogramas
odontogramaapi = Blueprint('odontogramaapi', __name__)

# ========================================
# HELPERS
# ========================================

def obtener_id_funcionario_actual():
    """
    Obtiene el ID del funcionario logueado desde la sesión
    TODO: Implementar según tu sistema de autenticación
    Por ahora retorna 1 como valor por defecto
    """
    # Ejemplo: return session.get('id_funcionario', 2)
    return 2  # Cambiar por tu lógica de sesión

# ========================================
# API - ESTADOS DENTALES
# ========================================

@odontogramaapi.route('/estados-dentales', methods=['GET'])
def getEstadosDentales():
    odontograma_dao = OdontogramaDao()
    try:
        estados = odontograma_dao.getEstadosDentales()
        app.logger.info(f"✅ Devolviendo {len(estados)} estados dentales")  # ✅ Log
        return jsonify({
            'success': True,
            'data': estados,
            'error': None
        }), 200
    except Exception as e:
        app.logger.error(f"❌ Error al obtener estados dentales: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al consultar los estados dentales.'
        }), 500

# ========================================
# API - ODONTOGRAMA CABECERA
# ========================================

@odontogramaapi.route('/odontogramas', methods=['GET'])
def getOdontogramas():
    """
    Obtiene todos los odontogramas
    Endpoint: GET /api/v1/odontogramas
    """
    odontograma_dao = OdontogramaDao()
    try:
        odontogramas = odontograma_dao.getOdontogramas()
        return jsonify({
            'success': True,
            'data': odontogramas,
            'error': None
        }), 200
    except Exception as e:
        app.logger.error(f"Error al obtener odontogramas: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al consultar los odontogramas.'
        }), 500

@odontogramaapi.route('/odontogramas/<int:id_odontograma>', methods=['GET'])
def getOdontogramaById(id_odontograma):
    """
    Obtiene un odontograma específico por ID con sus detalles
    Endpoint: GET /api/v1/odontogramas/{id}
    """
    odontograma_dao = OdontogramaDao()
    try:
        # Obtener cabecera
        odontograma = odontograma_dao.getOdontogramaById(id_odontograma)
        
        if not odontograma:
            return jsonify({
                'success': False,
                'error': f'No se encontró el odontograma con ID {id_odontograma}.'
            }), 404
        
        # Obtener detalles
        detalles = odontograma_dao.getDetallesPorOdontograma(id_odontograma)
        odontograma['detalles'] = detalles
        
        return jsonify({
            'success': True,
            'data': odontograma,
            'error': None
        }), 200
    except Exception as e:
        app.logger.error(f"Error al obtener odontograma {id_odontograma}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al consultar el odontograma.'
        }), 500

@odontogramaapi.route('/odontogramas/paciente/<int:id_paciente>', methods=['GET'])
def getOdontogramasByPaciente(id_paciente):
    """
    Obtiene todos los odontogramas de un paciente específico
    Endpoint: GET /api/v1/odontogramas/paciente/{id_paciente}
    """
    odontograma_dao = OdontogramaDao()
    try:
        odontogramas = odontograma_dao.getOdontogramasByPaciente(id_paciente)
        
        # Agregar detalles a cada odontograma
        for o in odontogramas:
            detalles = odontograma_dao.getDetallesPorOdontograma(o['id_odontograma'])
            o['detalles'] = detalles
        
        return jsonify({
            'success': True,
            'data': odontogramas,
            'error': None
        }), 200
    except Exception as e:
        app.logger.error(f"Error al obtener odontogramas del paciente {id_paciente}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al consultar los odontogramas del paciente.'
        }), 500

@odontogramaapi.route('/odontogramas', methods=['POST'])
def addOdontograma():
    """
    Crea un nuevo odontograma
    Endpoint: POST /api/v1/odontogramas
    Body: {
        "id_paciente": int,
        "id_medico": int,
        "fecha_registro": "YYYY-MM-DD" (opcional),
        "observaciones": string (opcional),
        "estado": "Activo" (opcional),
        "detalles": [
            {
                "diente": int o "numero_diente": int,
                "estado": int o "id_estado_dental": int,
                "superficie": string,
                "observacion": string (opcional)
            }
        ]
    }
    """
    data = request.get_json()
    app.logger.info(f"📌 Datos recibidos en addOdontograma: {data}")
    
    odontograma_dao = OdontogramaDao()
    
    # Validar campos obligatorios
    if 'id_paciente' not in data or data['id_paciente'] in (None, "", "null"):
        return jsonify({
            'success': False,
            'error': 'El campo id_paciente es obligatorio.'
        }), 400
    
    if 'id_medico' not in data or data['id_medico'] in (None, "", "null"):
        return jsonify({
            'success': False,
            'error': 'El campo id_medico es obligatorio.'
        }), 400

    try:
        # Verificar si ya existe un odontograma activo para este paciente (OPCIONAL)
        # Si quieres permitir múltiples odontogramas activos, comenta estas líneas
        if odontograma_dao.existeOdontogramaPaciente(data['id_paciente']):
            return jsonify({
                'success': False,
                'error': 'El paciente ya tiene un odontograma activo. Puede editarlo o inactivarlo antes de crear uno nuevo.'
            }), 409

        # Obtener ID del funcionario logueado
        id_funcionario = obtener_id_funcionario_actual()

        # Crear odontograma (cabecera)
        id_odontograma = odontograma_dao.guardarOdontograma(
            id_paciente=data['id_paciente'],
            id_medico=data['id_medico'],
            id_funcionario=id_funcionario,
            fecha_registro=data.get('fecha_registro', str(date.today())),
            observaciones=data.get('observaciones', ''),
            estado=data.get('estado', 'Activo')
        )
        
        if not id_odontograma:
            return jsonify({
                'success': False,
                'error': 'No se pudo crear el odontograma.'
            }), 500

        # Guardar detalles si vienen en la petición
        detalles_insertados = []
        if 'detalles' in data and isinstance(data['detalles'], list) and len(data['detalles']) > 0:
            detalles_insertados = odontograma_dao.guardarDetallesMultiples(
                id_odontograma,
                data['detalles']
            )

        return jsonify({
            'success': True,
            'data': {
                'id_odontograma': id_odontograma,
                'id_paciente': data['id_paciente'],
                'id_medico': data['id_medico'],
                'fecha_registro': data.get('fecha_registro', str(date.today())),
                'observaciones': data.get('observaciones', ''),
                'estado': data.get('estado', 'Activo'),
                'detalles_insertados': len(detalles_insertados)
            },
            'error': None
        }), 201

    except Exception as e:
        app.logger.error(f"Error al crear odontograma: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Ocurrió un error interno: {str(e)}'
        }), 500

@odontogramaapi.route('/odontogramas/<int:id_odontograma>', methods=['PUT'])
def updateOdontograma(id_odontograma):
    """
    Actualiza un odontograma existente
    Endpoint: PUT /api/v1/odontogramas/{id}
    Body: {
        "fecha_registro": "YYYY-MM-DD",
        "observaciones": string,
        "estado": "Activo|Finalizado|Inactivo",
        "detalles": [
            {
                "diente": int,
                "estado": int,
                "superficie": string,
                "observacion": string
            }
        ]
    }
    """
    data = request.get_json()
    app.logger.info(f"📌 Datos recibidos en updateOdontograma: {data}")
    
    odontograma_dao = OdontogramaDao()
    
    try:
        # Actualizar cabecera
        updated = odontograma_dao.updateOdontograma(
            id_odontograma=id_odontograma,
            fecha_registro=data.get('fecha_registro', str(date.today())),
            observaciones=data.get('observaciones', ''),
            estado=data.get('estado', 'Activo')
        )

        if not updated:
            return jsonify({
                'success': False,
                'error': 'Odontograma no encontrado.'
            }), 404

        # Manejar los detalles (si vienen)
        if 'detalles' in data and isinstance(data['detalles'], list):
            # 1. Eliminar detalles anteriores
            odontograma_dao.deleteDetallesPorOdontograma(id_odontograma)

            # 2. Insertar los nuevos detalles
            detalles_insertados = odontograma_dao.guardarDetallesMultiples(
                id_odontograma,
                data['detalles']
            )
            
            app.logger.info(f"✅ {len(detalles_insertados)} detalles actualizados")

        return jsonify({
            'success': True,
            'message': 'Odontograma actualizado correctamente',
            'error': None
        }), 200

    except Exception as e:
        app.logger.error(f"Error al actualizar odontograma {id_odontograma}: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Ocurrió un error interno: {str(e)}'
        }), 500

@odontogramaapi.route('/odontogramas/<int:id_odontograma>', methods=['DELETE'])
def deleteOdontograma(id_odontograma):
    """
    Elimina un odontograma y sus detalles
    Endpoint: DELETE /api/v1/odontogramas/{id}
    """
    odontograma_dao = OdontogramaDao()
    try:
        deleted = odontograma_dao.deleteOdontograma(id_odontograma)
        
        if deleted:
            return jsonify({
                'success': True,
                'message': f'Odontograma {id_odontograma} eliminado correctamente',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Odontograma no encontrado.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar odontograma {id_odontograma}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al eliminar el odontograma.'
        }), 500

@odontogramaapi.route('/odontogramas/<int:id_odontograma>/estado', methods=['PATCH'])
def cambiarEstadoOdontograma(id_odontograma):
    """
    Cambia el estado de un odontograma
    Endpoint: PATCH /api/v1/odontogramas/{id}/estado
    Body: {
        "estado": "Activo|Finalizado|Inactivo"
    }
    """
    data = request.get_json()
    odontograma_dao = OdontogramaDao()

    if 'estado' not in data or data['estado'] not in ['Activo', 'Finalizado', 'Inactivo']:
        return jsonify({
            'success': False,
            'error': 'El campo estado debe ser "Activo", "Finalizado" o "Inactivo".'
        }), 400

    try:
        if odontograma_dao.cambiarEstadoOdontograma(id_odontograma, data['estado']):
            return jsonify({
                'success': True,
                'message': f'Estado actualizado a {data["estado"]}.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'No se encontró el odontograma con ID {id_odontograma}.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al cambiar estado: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al cambiar el estado.'
        }), 500

# ========================================
# API - ODONTOGRAMA DETALLES
# ========================================

@odontogramaapi.route('/odontogramas/<int:id_odontograma>/detalles', methods=['GET'])
def getDetalles(id_odontograma):
    """
    Obtiene todos los detalles de un odontograma
    Endpoint: GET /api/v1/odontogramas/{id}/detalles
    """
    odontograma_dao = OdontogramaDao()
    try:
        detalles = odontograma_dao.getDetallesPorOdontograma(id_odontograma)
        return jsonify({
            'success': True,
            'data': detalles,
            'error': None
        }), 200
    except Exception as e:
        app.logger.error(f"Error al obtener detalles: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al consultar los detalles.'
        }), 500

@odontogramaapi.route('/odontogramas/<int:id_odontograma>/detalles', methods=['POST'])
def addDetalle(id_odontograma):
    """
    Agrega un detalle a un odontograma
    Endpoint: POST /api/v1/odontogramas/{id}/detalles
    Body: {
        "diente": int o "numero_diente": int,
        "estado": int o "id_estado_dental": int,
        "superficie": string,
        "observacion": string (opcional)
    }
    """
    data = request.get_json()
    odontograma_dao = OdontogramaDao()
    
    try:
        # Obtener valores con flexibilidad en nombres
        numero_diente = data.get('diente') or data.get('numero_diente')
        id_estado_dental = data.get('estado') or data.get('id_estado_dental')
        superficie = data.get('superficie', 'C')
        observacion = data.get('observacion')
        
        if not numero_diente or not id_estado_dental:
            return jsonify({
                'success': False,
                'error': 'Los campos diente y estado son obligatorios.'
            }), 400
        
        id_detalle = odontograma_dao.guardarDetalle(
            id_odontograma=id_odontograma,
            numero_diente=numero_diente,
            id_estado_dental=id_estado_dental,
            superficie=superficie,
            observacion=observacion
        )
        
        if id_detalle:
            return jsonify({
                'success': True,
                'data': {
                    'id_odontograma_detalle': id_detalle,
                    'numero_diente': numero_diente,
                    'id_estado_dental': id_estado_dental,
                    'superficie': superficie
                },
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo crear el detalle. Puede ser un registro duplicado.'
            }), 500
    except Exception as e:
        app.logger.error(f"Error al agregar detalle: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Ocurrió un error interno: {str(e)}'
        }), 500

@odontogramaapi.route('/detalles/<int:id_detalle>', methods=['PUT'])
def updateDetalle(id_detalle):
    """
    Actualiza un detalle específico
    Endpoint: PUT /api/v1/detalles/{id}
    Body: {
        "estado": int o "id_estado_dental": int,
        "superficie": string,
        "observacion": string
    }
    """
    data = request.get_json()
    odontograma_dao = OdontogramaDao()
    
    try:
        id_estado_dental = data.get('estado') or data.get('id_estado_dental')
        
        if not id_estado_dental:
            return jsonify({
                'success': False,
                'error': 'El campo estado es obligatorio.'
            }), 400
        
        updated = odontograma_dao.updateDetalle(
            id_odontograma_detalle=id_detalle,
            id_estado_dental=id_estado_dental,
            superficie=data.get('superficie', 'C'),
            observacion=data.get('observacion')
        )
        
        if updated:
            return jsonify({
                'success': True,
                'message': 'Detalle actualizado correctamente',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Detalle no encontrado.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al actualizar detalle: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno.'
        }), 500

@odontogramaapi.route('/detalles/<int:id_detalle>', methods=['DELETE'])
def deleteDetalle(id_detalle):
    """
    Elimina un detalle específico
    Endpoint: DELETE /api/v1/detalles/{id}
    """
    odontograma_dao = OdontogramaDao()
    try:
        deleted = odontograma_dao.deleteDetalle(id_detalle)
        
        if deleted:
            return jsonify({
                'success': True,
                'message': 'Detalle eliminado correctamente',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Detalle no encontrado.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar detalle: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error interno.'
        }), 500

# ========================================
# API - UTILIDADES
# ========================================

@odontogramaapi.route('/odontogramas/validar-paciente/<int:id_paciente>', methods=['GET'])
def validarPaciente(id_paciente):
    """
    Verifica si un paciente ya tiene un odontograma activo
    Endpoint: GET /api/v1/odontogramas/validar-paciente/{id_paciente}
    """
    odontograma_dao = OdontogramaDao()
    try:
        existe = odontograma_dao.existeOdontogramaPaciente(id_paciente)
        return jsonify({
            'success': True,
            'data': {
                'existe_odontograma': existe
            },
            'error': None
        }), 200
    except Exception as e:
        app.logger.error(f"Error al validar paciente: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al validar.'
        }), 500