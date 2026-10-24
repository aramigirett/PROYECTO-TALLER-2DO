from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_agendamiento.odontograma.OdontogramaDao import OdontogramaDao
from datetime import date
from app.conexion.Conexion import Conexion
from app.rutas.modulo_seguridad.decorators import require_permiso, require_login

# Crear Blueprint para la API de Odontogramas
odontogramaapi = Blueprint('odontogramaapi', __name__)

# ========================================
# API - ESTADOS DENTALES
# ========================================

@odontogramaapi.route('/estados-dentales', methods=['GET'])
@require_login  # lookup: lo consumen otras pantallas
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
@require_permiso('odontograma', 'ver')
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
@require_permiso('odontograma', 'ver')
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
                'error': 'No se encontró el odontograma indicado.'
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
@require_permiso('odontograma', 'ver')
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
@require_permiso('odontograma', 'nuevo')
def addOdontograma():
    """
    Crea un nuevo odontograma
    Endpoint: POST /api/v1/odontogramas
    Body: {
        "id_consulta_cab": int,
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
    
    # Validar campos obligatorios: el odontograma cuelga de una Consulta (paciente y
    # médico se derivan de ella; lo que mande el navegador para eso se ignora)
    data = data or {}
    try:
        id_consulta_cab = int(data.get('id_consulta_cab'))
    except (TypeError, ValueError):
        return jsonify({
            'success': False,
            'error': 'El campo id_consulta_cab es obligatorio: el odontograma se registra desde una Consulta.'
        }), 400

    ERRORES = {
        'CONSULTA_NO_ENCONTRADA': (404, 'No se encontró la consulta seleccionada.'),
        'CONSULTA_FINALIZADA': (409, 'No se puede registrar: la consulta ya está finalizada.'),
        'YA_EXISTE': (409, 'Esta consulta ya tiene un odontograma. Puede editarlo o anularlo antes de crear uno nuevo.'),
        'ERROR_INTERNO': (500, 'No se pudo crear el odontograma.'),
    }

    try:
        resultado = odontograma_dao.guardarOdontograma(
            id_consulta_cab=id_consulta_cab,
            fecha_registro=data.get('fecha_registro') or str(date.today()),
            observaciones=data.get('observaciones', ''),
            estado=data.get('estado', 'Activo')
        )

        if 'id_odontograma' not in resultado:
            codigo, mensaje = ERRORES.get(resultado.get('error'), ERRORES['ERROR_INTERNO'])
            return jsonify({'success': False, 'error': mensaje}), codigo
        id_odontograma = resultado['id_odontograma']

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
                'id_consulta_cab': id_consulta_cab,
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
@require_permiso('odontograma', 'editar')
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
@require_permiso('odontograma', 'anular')
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
@require_permiso('odontograma', 'anular')
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
                'error': 'No se encontró el odontograma indicado.'
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
@require_permiso('odontograma', 'ver')
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
@require_permiso('odontograma', 'nuevo')
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
@require_permiso('odontograma', 'editar')
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
@require_permiso('odontograma', 'editar')
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

@odontogramaapi.route('/odontogramas/validar-consulta/<int:id_consulta_cab>', methods=['GET'])
@require_permiso('odontograma', 'ver')
def validarConsulta(id_consulta_cab):
    """
    Verifica si una consulta ya tiene un odontograma vigente (uno por consulta)
    Endpoint: GET /api/v1/odontogramas/validar-consulta/{id_consulta_cab}
    """
    odontograma_dao = OdontogramaDao()
    try:
        existe = odontograma_dao.existeOdontogramaConsulta(id_consulta_cab)
        return jsonify({
            'success': True,
            'data': {
                'existe_odontograma': existe
            },
            'error': None
        }), 200
    except Exception as e:
        app.logger.error(f"Error al validar consulta: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al validar.'
        }), 500


@odontogramaapi.route('/odontogramas/precarga/<int:id_consulta_cab>', methods=['GET'])
@require_permiso('odontograma', 'nuevo')
def getPrecarga(id_consulta_cab):
    """
    Estado del odontograma vigente del paciente de la consulta (el de su última
    consulta anterior), para precargar el odontograma nuevo.
    Endpoint: GET /api/v1/odontogramas/precarga/{id_consulta_cab}
    data = {'detalles': [...], 'fecha_registro': ...} o {'detalles': []} si no hay previo.
    """
    odontograma_dao = OdontogramaDao()
    try:
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_paciente FROM consultas_cab WHERE id_consulta_cab = %s AND activo = true",
                        (id_consulta_cab,))
            fila = cur.fetchone()
        finally:
            cur.close()
            con.close()
        if not fila:
            return jsonify({'success': False, 'error': 'No se encontró la consulta seleccionada.'}), 404
        previo = odontograma_dao.getOdontogramaVigentePaciente(fila[0], excluir_consulta=id_consulta_cab)
        data = ({'detalles': previo['detalles'], 'fecha_registro': previo['fecha_registro']}
                if previo else {'detalles': []})
        return jsonify({'success': True, 'data': data, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener la precarga del odontograma: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error al consultar el odontograma previo.'}), 500
