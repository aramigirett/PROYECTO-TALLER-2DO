from flask import Blueprint, request, jsonify, current_app as app
from app.dao.referenciales_agendamiento.agenda.AgendaCabeceraDao import AgendaCabeceraDao
from app.dao.referenciales_agendamiento.agenda.AgendaDetalleDao import AgendaDetalleDao
from app.dao.referenciales_agendamiento.disponibilidad_horaria.DisponibilidadHorariaDao import DisponibilidadDao
from datetime import datetime

agendaapi = Blueprint('agendaapi', __name__)

# ================================================================
# ENDPOINTS DE AGENDA CABECERA
# ================================================================

# 🔹 Obtener todas las cabeceras
@agendaapi.route('/agenda/cabeceras', methods=['GET'])
def getCabeceras():
    dao = AgendaCabeceraDao()
    try:
        cabeceras = dao.getCabeceras()
        return jsonify({'success': True, 'data': cabeceras, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener cabeceras: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# 🔹 Obtener cabecera por ID
@agendaapi.route('/agenda/cabeceras/<int:id_cabecera>', methods=['GET'])
def getCabecera(id_cabecera):
    dao = AgendaCabeceraDao()
    try:
        cabecera = dao.getCabeceraById(id_cabecera)
        if cabecera:
            return jsonify({'success': True, 'data': cabecera, 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se encontró la cabecera'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener cabecera: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# 🔹 Crear nueva cabecera
@agendaapi.route('/agenda/cabeceras', methods=['POST'])
def addCabecera():
    data = request.get_json()
    dao = AgendaCabeceraDao()

    # Validar campos requeridos
    campos_requeridos = ['id_medico', 'id_especialidad', 'id_consultorio', 'fecha_agenda', 'estado', 'id_funcionario']
    for campo in campos_requeridos:
        if campo not in data or not data[campo]:
            return jsonify({'success': False, 'error': f'El campo {campo} es obligatorio'}), 400

    try:
        # Normalizar fecha
        fecha_agenda = datetime.strptime(data['fecha_agenda'], "%Y-%m-%d").date()

        # Validar estado
        if data['estado'] not in ['Activo', 'Inactivo']:
            return jsonify({'success': False, 'error': 'Estado debe ser Activo o Inactivo'}), 400

        # Guardar cabecera
        new_id = dao.guardarCabecera(
            data['id_medico'],
            data['id_especialidad'],
            data['id_consultorio'],
            fecha_agenda,
            data['estado'],
            data['id_funcionario'],
            data.get('observaciones')
        )

        if new_id:
            return jsonify({
                'success': True, 
                'data': {'id_agenda_cabecera': new_id}, 
                'error': None
            }), 201
        
        # Si retorna False, es porque ya existe
        return jsonify({
            'success': False, 
            'error': 'Ya existe una agenda para este médico en esta fecha'
        }), 409

    except ValueError as ve:
        return jsonify({'success': False, 'error': f'Error en formato de datos: {str(ve)}'}), 400
    except Exception as e:
        app.logger.error(f"Error al crear cabecera: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# 🔹 Actualizar cabecera
@agendaapi.route('/agenda/cabeceras/<int:id_cabecera>', methods=['PUT'])
def updateCabecera(id_cabecera):
    data = request.get_json()
    dao = AgendaCabeceraDao()

    campos_requeridos = ['id_medico', 'id_especialidad', 'id_consultorio', 'fecha_agenda', 'estado', 'id_funcionario']
    for campo in campos_requeridos:
        if campo not in data or not data[campo]:
            return jsonify({'success': False, 'error': f'El campo {campo} es obligatorio'}), 400

    try:
        fecha_agenda = datetime.strptime(data['fecha_agenda'], "%Y-%m-%d").date()

        if data['estado'] not in ['Activo', 'Inactivo']:
            return jsonify({'success': False, 'error': 'Estado debe ser Activo o Inactivo'}), 400

        exito = dao.updateCabecera(
            id_cabecera,
            data['id_medico'],
            data['id_especialidad'],
            data['id_consultorio'],
            fecha_agenda,
            data['estado'],
            data['id_funcionario'],
            data.get('observaciones')
        )

        if exito:
            return jsonify({'success': True, 'data': {'id_agenda_cabecera': id_cabecera}, 'error': None}), 200
        
        return jsonify({'success': False, 'error': 'No se pudo actualizar o ya existe otra agenda igual'}), 404

    except ValueError as ve:
        return jsonify({'success': False, 'error': f'Error en formato: {str(ve)}'}), 400
    except Exception as e:
        app.logger.error(f"Error al actualizar cabecera: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# 🔹 Anular cabecera (baja lógica; en cascada anula también sus detalles)
@agendaapi.route('/agenda/cabeceras/<int:id_cabecera>', methods=['DELETE'])
def deleteCabecera(id_cabecera):
    dao = AgendaCabeceraDao()
    try:
        exito = dao.deleteCabecera(id_cabecera)
        if exito:
            return jsonify({
                'success': True, 
                'mensaje': f'Cabecera {id_cabecera} y sus detalles eliminados', 
                'error': None
            }), 200
        return jsonify({'success': False, 'error': 'No se encontró o no se pudo eliminar'}), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar cabecera: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# 🔹 Cambiar estado de cabecera
@agendaapi.route('/agenda/cabeceras/<int:id_cabecera>/estado', methods=['PATCH'])
def cambiarEstadoCabecera(id_cabecera):
    data = request.get_json()
    dao = AgendaCabeceraDao()

    if 'estado' not in data or data['estado'] not in ['Activo', 'Inactivo']:
        return jsonify({'success': False, 'error': 'Estado debe ser Activo o Inactivo'}), 400

    try:
        exito = dao.cambiarEstado(id_cabecera, data['estado'])
        if exito:
            return jsonify({'success': True, 'data': {'nuevo_estado': data['estado']}, 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se pudo cambiar el estado'}), 404
    except Exception as e:
        app.logger.error(f"Error al cambiar estado: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# ================================================================
# ENDPOINTS DE AGENDA DETALLE
# ================================================================

# 🔹 Obtener detalles de una cabecera
@agendaapi.route('/agenda/cabeceras/<int:id_cabecera>/detalles', methods=['GET'])
def getDetalles(id_cabecera):
    dao = AgendaDetalleDao()
    try:
        detalles = dao.getDetallesPorCabecera(id_cabecera)
        return jsonify({'success': True, 'data': detalles, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener detalles: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# 🔹 Obtener un detalle específico
@agendaapi.route('/agenda/detalles/<int:id_detalle>', methods=['GET'])
def getDetalle(id_detalle):
    dao = AgendaDetalleDao()
    try:
        detalle = dao.getDetalleById(id_detalle)
        if detalle:
            return jsonify({'success': True, 'data': detalle, 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se encontró el detalle'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener detalle: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# 🔹 Agregar detalles (uno o varios) a una cabecera
@agendaapi.route('/agenda/cabeceras/<int:id_cabecera>/detalles', methods=['POST'])
def addDetalles(id_cabecera):
    data = request.get_json()
    detalle_dao = AgendaDetalleDao()
    disp_dao = DisponibilidadDao()

    # Espera un array de IDs de disponibilidades
    if 'ids_disponibilidades' not in data or not isinstance(data['ids_disponibilidades'], list):
        return jsonify({'success': False, 'error': 'Debe enviar ids_disponibilidades como array'}), 400

    if not data['ids_disponibilidades']:
        return jsonify({'success': False, 'error': 'Debe seleccionar al menos una disponibilidad'}), 400

    try:
        # Validar que la cabecera existe
        cabecera_dao = AgendaCabeceraDao()
        cabecera = cabecera_dao.getCabeceraById(id_cabecera)
        if not cabecera:
            return jsonify({'success': False, 'error': f'No existe la cabecera {id_cabecera}'}), 404

        # Obtener las disponibilidades y crear detalles
        ids_creados = []
        errores = []

        for id_disp in data['ids_disponibilidades']:
            # Obtener disponibilidad
            disponibilidad = disp_dao.getDisponibilidadById(id_disp)
            if not disponibilidad:
                errores.append(f"Disponibilidad {id_disp} no existe")
                continue

            # Intentar crear detalle
            detalle_id = detalle_dao.guardarDetalle(id_cabecera, disponibilidad)
            if detalle_id:
                ids_creados.append(detalle_id)
            else:
                errores.append(f"Disponibilidad {id_disp} ya está publicada o hubo un error")

        # Retornar resultado
        if ids_creados:
            return jsonify({
                'success': True,
                'data': {
                    'ids_creados': ids_creados,
                    'cantidad': len(ids_creados),
                    'errores': errores if errores else None
                },
                'error': None
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': f"No se pudo crear ningún detalle. Errores: {', '.join(errores)}"
            }), 400

    except Exception as e:
        app.logger.error(f"Error al agregar detalles: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# 🔹 Eliminar un detalle específico
@agendaapi.route('/agenda/detalles/<int:id_detalle>', methods=['DELETE'])
def deleteDetalle(id_detalle):
    dao = AgendaDetalleDao()
    try:
        exito = dao.deleteDetalle(id_detalle)
        if exito == "TIENE_CITAS_ACTIVAS":
            return jsonify({
                'success': False,
                'error': 'No se puede anular: este horario tiene citas activas asociadas.'
            }), 409
        if exito:
            return jsonify({'success': True, 'mensaje': f'Detalle {id_detalle} anulado', 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se encontró o no se pudo anular'}), 404
    except Exception as e:
        app.logger.error(f"Error al anular detalle: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# 🔹 Actualizar cupos disponibles de un detalle
@agendaapi.route('/agenda/detalles/<int:id_detalle>/cupos', methods=['PATCH'])
def actualizarCupos(id_detalle):
    data = request.get_json()
    dao = AgendaDetalleDao()

    if 'cupos_disponibles' not in data:
        return jsonify({'success': False, 'error': 'Debe enviar cupos_disponibles'}), 400

    try:
        nuevos_cupos = int(data['cupos_disponibles'])
        if nuevos_cupos < 0:
            return jsonify({'success': False, 'error': 'Los cupos no pueden ser negativos'}), 400

        exito = dao.actualizarCuposDisponibles(id_detalle, nuevos_cupos)
        if exito:
            return jsonify({'success': True, 'data': {'cupos_disponibles': nuevos_cupos}, 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se pudo actualizar'}), 404

    except ValueError:
        return jsonify({'success': False, 'error': 'cupos_disponibles debe ser un número'}), 400
    except Exception as e:
        app.logger.error(f"Error al actualizar cupos: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500


# 🔹 Cambiar estado de detalle
@agendaapi.route('/agenda/detalles/<int:id_detalle>/estado', methods=['PATCH'])
def cambiarEstadoDetalle(id_detalle):
    data = request.get_json()
    dao = AgendaDetalleDao()

    if 'estado_detalle' not in data or data['estado_detalle'] not in ['Disponible', 'Agotado', 'Cancelado']:
        return jsonify({'success': False, 'error': 'Estado debe ser Disponible, Agotado o Cancelado'}), 400

    try:
        exito = dao.cambiarEstadoDetalle(id_detalle, data['estado_detalle'])
        if exito:
            return jsonify({'success': True, 'data': {'nuevo_estado': data['estado_detalle']}, 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se pudo cambiar el estado'}), 404
    except Exception as e:
        app.logger.error(f"Error al cambiar estado detalle: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno'}), 500