from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_agendamiento.cita.CitaDao import CitaDao
from datetime import time

# Crear Blueprint para la API de Citas
citaapi = Blueprint('citaapi', __name__)

# ========================================
# HELPERS
# ========================================

def serialize_time(obj):
    """Convierte objetos time de Python en string formato HH:MM:SS"""
    if isinstance(obj, time):
        return obj.strftime('%H:%M:%S')
    return obj

def obtener_id_funcionario_actual():
    """Obtiene el ID del funcionario logueado"""
    return 2

# ========================================
# API - ESTADOS DE CITA
# ========================================

@citaapi.route('/estados-cita', methods=['GET'])
def getEstadosCita():
    citadao = CitaDao()
    try:
        estados = citadao.getEstadosCita()
        return jsonify({
            'success': True,
            'data': estados,
            'error': None
        }), 200
    except Exception as e:
        app.logger.error(f"Error al obtener estados de cita: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al consultar los estados.'
        }), 500

# ========================================
# API - CITA CABECERA
# ========================================

@citaapi.route('/citas-cabecera', methods=['GET'])
def getCitasCabecera():
    citadao = CitaDao()
    try:
        cabeceras = citadao.getCitasCabecera()
        return jsonify({
            'success': True,
            'data': cabeceras,
            'error': None
        }), 200
    except Exception as e:
        app.logger.error(f"Error al obtener cabeceras de citas: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al consultar las citas.'
        }), 500

@citaapi.route('/citas-cabecera/<int:id_cita_cabecera>', methods=['GET'])
def getCitaCabeceraById(id_cita_cabecera):
    citadao = CitaDao()
    try:
        cabecera = citadao.getCitaCabeceraById(id_cita_cabecera)
        if cabecera:
            return jsonify({
                'success': True,
                'data': cabecera,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'No se encontró la cita con ID {id_cita_cabecera}.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al obtener cabecera {id_cita_cabecera}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al consultar la cita.'
        }), 500

@citaapi.route('/citas-cabecera', methods=['POST'])
def addCitaCabecera():
    data = request.get_json()
    citadao = CitaDao()

    campos_requeridos = ['id_paciente', 'id_agenda_cabecera']
    for campo in campos_requeridos:
        if campo not in data or data[campo] in (None, "", "null"):
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio.'
            }), 400

    try:
        id_funcionario = obtener_id_funcionario_actual()
        cabecera_id = citadao.guardarCitaCabecera(
            data['id_paciente'],
            data['id_agenda_cabecera'],
            id_funcionario,
            data.get('observaciones')
        )

        if cabecera_id:
            return jsonify({
                'success': True,
                'data': {
                    'id_cita_cabecera': cabecera_id,
                    'id_paciente': data['id_paciente'],
                    'id_agenda_cabecera': data['id_agenda_cabecera'],
                    'observaciones': data.get('observaciones')
                },
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo crear la cabecera de cita.'
            }), 500

    except Exception as e:
        app.logger.error(f"Error al crear cabecera: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al guardar la cita.'
        }), 500

@citaapi.route('/citas-cabecera/<int:id_cita_cabecera>', methods=['PUT'])
def updateCitaCabecera(id_cita_cabecera):
    data = request.get_json()
    citadao = CitaDao()

    campos_requeridos = ['id_paciente', 'id_agenda_cabecera']
    for campo in campos_requeridos:
        if campo not in data or data[campo] in (None, "", "null"):
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio.'
            }), 400

    try:
        exito = citadao.updateCitaCabecera(
            id_cita_cabecera,
            data['id_paciente'],
            data['id_agenda_cabecera'],
            data.get('observaciones')
        )

        if exito:
            return jsonify({
                'success': True,
                'data': {
                    'id_cita_cabecera': id_cita_cabecera,
                    'id_paciente': data['id_paciente'],
                    'id_agenda_cabecera': data['id_agenda_cabecera'],
                    'observaciones': data.get('observaciones')
                },
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'No se encontró la cita con ID {id_cita_cabecera}.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al actualizar cabecera {id_cita_cabecera}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al actualizar la cita.'
        }), 500

@citaapi.route('/citas-cabecera/<int:id_cita_cabecera>', methods=['DELETE'])
def deleteCitaCabecera(id_cita_cabecera):
    citadao = CitaDao()
    try:
        if citadao.deleteCitaCabecera(id_cita_cabecera):
            return jsonify({
                'success': True,
                'mensaje': f'Cita con ID {id_cita_cabecera} eliminada correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'No se encontró la cita con ID {id_cita_cabecera}.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar cabecera {id_cita_cabecera}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al eliminar la cita.'
        }), 500

@citaapi.route('/citas-cabecera/<int:id_cita_cabecera>/estado', methods=['PATCH'])
def cambiarEstadoCabecera(id_cita_cabecera):
    data = request.get_json()
    citadao = CitaDao()

    if 'estado' not in data or data['estado'] not in ['Activo', 'Inactivo']:
        return jsonify({
            'success': False,
            'error': 'El campo estado debe ser "Activo" o "Inactivo".'
        }), 400

    try:
        if citadao.cambiarEstadoCabecera(id_cita_cabecera, data['estado']):
            return jsonify({
                'success': True,
                'mensaje': f'Estado actualizado a {data["estado"]}.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'No se encontró la cita con ID {id_cita_cabecera}.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al cambiar estado: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al cambiar el estado.'
        }), 500

# ========================================
# API - CITA DETALLE
# ========================================

@citaapi.route('/citas-detalle/cabecera/<int:id_cita_cabecera>', methods=['GET'])
def getDetallesPorCabecera(id_cita_cabecera):
    citadao = CitaDao()
    try:
        detalles = citadao.getDetallesPorCabecera(id_cita_cabecera)
        
        for detalle in detalles:
            if 'hora_cita' in detalle:
                detalle['hora_cita'] = serialize_time(detalle['hora_cita'])
            if 'hora_inicio' in detalle:
                detalle['hora_inicio'] = serialize_time(detalle['hora_inicio'])
            if 'hora_fin' in detalle:
                detalle['hora_fin'] = serialize_time(detalle['hora_fin'])
        
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

@citaapi.route('/citas-detalle/<int:id_cita_detalle>', methods=['GET'])
def getDetalleById(id_cita_detalle):
    citadao = CitaDao()
    try:
        detalle = citadao.getDetalleById(id_cita_detalle)
        if detalle:
            if 'hora_cita' in detalle:
                detalle['hora_cita'] = serialize_time(detalle['hora_cita'])
            
            return jsonify({
                'success': True,
                'data': detalle,
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'No se encontró el detalle con ID {id_cita_detalle}.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al obtener detalle {id_cita_detalle}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al consultar el detalle.'
        }), 500

@citaapi.route('/citas-detalle', methods=['POST'])
def addCitaDetalle():
    data = request.get_json()
    citadao = CitaDao()

    campos_requeridos = ['id_cita_cabecera', 'id_agenda_detalle', 'fecha_cita', 
                         'hora_cita', 'motivo_consulta', 'id_estado_cita']
    for campo in campos_requeridos:
        if campo not in data or data[campo] in (None, "", "null"):
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio.'
            }), 400

    try:
        detalle_id = citadao.guardarCitaDetalle(
            data['id_cita_cabecera'],
            data['id_agenda_detalle'],
            data['fecha_cita'],
            data['hora_cita'],
            data['motivo_consulta'],
            data['id_estado_cita']
        )

        if detalle_id == "SIN_CUPOS":
            return jsonify({
                'success': False,
                'error': 'No hay cupos disponibles en este horario.'
            }), 409

        if detalle_id:
            return jsonify({
                'success': True,
                'data': {
                    'id_cita_detalle': detalle_id,
                    'id_cita_cabecera': data['id_cita_cabecera'],
                    'id_agenda_detalle': data['id_agenda_detalle'],
                    'fecha_cita': data['fecha_cita'],
                    'hora_cita': data['hora_cita'],
                    'motivo_consulta': data['motivo_consulta'],
                    'id_estado_cita': data['id_estado_cita']
                },
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo crear el detalle de cita.'
            }), 500

    except Exception as e:
        app.logger.error(f"Error al crear detalle: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al guardar el detalle.'
        }), 500

@citaapi.route('/citas-detalle/<int:id_cita_detalle>', methods=['PUT'])
def updateCitaDetalle(id_cita_detalle):
    data = request.get_json()
    citadao = CitaDao()

    campos_requeridos = ['id_agenda_detalle', 'fecha_cita', 'hora_cita', 
                         'motivo_consulta', 'id_estado_cita']
    for campo in campos_requeridos:
        if campo not in data or data[campo] in (None, "", "null"):
            return jsonify({
                'success': False,
                'error': f'El campo {campo} es obligatorio.'
            }), 400

    try:
        exito = citadao.updateCitaDetalle(
            id_cita_detalle,
            data['id_agenda_detalle'],
            data['fecha_cita'],
            data['hora_cita'],
            data['motivo_consulta'],
            data['id_estado_cita']
        )

        if exito == "SIN_CUPOS":
            return jsonify({
                'success': False,
                'error': 'No hay cupos disponibles en este horario.'
            }), 409

        if exito:
            return jsonify({
                'success': True,
                'data': {
                    'id_cita_detalle': id_cita_detalle,
                    'id_agenda_detalle': data['id_agenda_detalle'],
                    'fecha_cita': data['fecha_cita'],
                    'hora_cita': data['hora_cita'],
                    'motivo_consulta': data['motivo_consulta'],
                    'id_estado_cita': data['id_estado_cita']
                },
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'No se encontró el detalle con ID {id_cita_detalle}.'
            }), 404

    except Exception as e:
        app.logger.error(f"Error al actualizar detalle {id_cita_detalle}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al actualizar el detalle.'
        }), 500

@citaapi.route('/citas-detalle/<int:id_cita_detalle>', methods=['DELETE'])
def deleteCitaDetalle(id_cita_detalle):
    citadao = CitaDao()
    try:
        if citadao.deleteCitaDetalle(id_cita_detalle):
            return jsonify({
                'success': True,
                'mensaje': f'Detalle con ID {id_cita_detalle} eliminado correctamente.',
                'error': None
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'No se encontró el detalle con ID {id_cita_detalle}.'
            }), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar detalle {id_cita_detalle}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al eliminar el detalle.'
        }), 500

# ========================================
# API - UTILIDADES
# ========================================

@citaapi.route('/agenda-detalle/cupos/<int:id_agenda_detalle>', methods=['GET'])
def verificarCupos(id_agenda_detalle):
    citadao = CitaDao()
    try:
        cupos = citadao.verificarCuposDisponibles(id_agenda_detalle)
        return jsonify({
            'success': True,
            'data': {
                'id_agenda_detalle': id_agenda_detalle,
                'cupos_disponibles': cupos
            },
            'error': None
        }), 200
    except Exception as e:
        app.logger.error(f"Error al verificar cupos: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Ocurrió un error al verificar los cupos.'
        }), 500

# ========================================
# NUEVO ENDPOINT: Obtener citas del paciente
# ========================================

@citaapi.route('/citas/paciente/<int:id_paciente>', methods=['GET'])
def obtener_citas_paciente(id_paciente):
    """Obtiene citas confirmadas del paciente para avisos"""
    citadao = CitaDao()
    try:
        citas = citadao.obtenerCitasPacienteConfirmadas(id_paciente)
        
        return jsonify(
            success=True,
            data=citas,
            cantidad=len(citas) if citas else 0
        ), 200
            
    except Exception as e:
        app.logger.error(f"Error en obtener_citas_paciente: {e}")
        return jsonify(
            success=False,
            error=str(e)
        ), 500