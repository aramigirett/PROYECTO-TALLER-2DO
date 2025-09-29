from app.dao.referenciales.avisosRecordatorios.AvisosRecordatoriosDao import AvisoRecordatorioDao
# app/rutas/referenciales/avisosRecordatorios/AvisosRecordatorios_api.py
from flask import Blueprint, jsonify, request, current_app as app
from app.rutas.referenciales.avisosRecordatorios.notificador import enviar_whatsapp

avisoapi = Blueprint('avisoapi', __name__, url_prefix='/api/v1')

dao = AvisoRecordatorioDao()

# =========================
# Listar todos los avisos
# =========================
@avisoapi.route('/avisos', methods=['GET'])
def listar_avisos():
    try:
        avisos = dao.getAvisos()
        return jsonify(success=True, data=avisos)
    except Exception as e:
        app.logger.error(f"Error en listar_avisos: {e}")
        return jsonify(success=False, error=str(e))


# =========================
# Obtener aviso por ID
# =========================
@avisoapi.route('/avisos/<int:id_aviso>', methods=['GET'])
def get_aviso(id_aviso):
    try:
        aviso = dao.getAvisoById(id_aviso)
        if aviso:
            return jsonify(success=True, data=aviso)
        return jsonify(success=False, error="Aviso no encontrado")
    except Exception as e:
        app.logger.error(f"Error en get_aviso: {e}")
        return jsonify(success=False, error=str(e))


# =========================
# Crear aviso
# =========================
@avisoapi.route('/avisos', methods=['POST'])
def crear_aviso():
    data = request.get_json()
    try:
        # Validación mínima
        required_fields = ["id_paciente", "id_medico", "id_consultorio",
                           "fecha_cita", "hora_cita", "hora_recordatorio",
                           "forma_envio", "mensaje"]
        for f in required_fields:
            if f not in data or not str(data[f]).strip():
                return jsonify(success=False, error=f"El campo {f} es obligatorio"), 400

        id_aviso = dao.addAviso(data)
        if id_aviso:
            # 🚀 Si la forma de envío es WhatsApp, disparamos la notificación
            if data.get("forma_envio", "").lower() == "whatsapp":
                numero = data.get("telefono", None)
                mensaje = data.get("mensaje", "")
                if numero:
                    enviar_whatsapp(numero, mensaje)

            return jsonify(success=True, mensaje="Aviso creado", id=id_aviso)
        return jsonify(success=False, error="No se pudo crear aviso")
    except Exception as e:
        app.logger.error(f"Error en crear_aviso: {e}")
        return jsonify(success=False, error=str(e))


# =========================
# Actualizar aviso
# =========================
@avisoapi.route('/avisos/<int:id_aviso>', methods=['PUT'])
def actualizar_aviso(id_aviso):
    data = request.get_json()
    try:
        if dao.updateAviso(id_aviso, data):
            return jsonify(success=True, mensaje="Aviso actualizado")
        return jsonify(success=False, error="No se pudo actualizar aviso")
    except Exception as e:
        app.logger.error(f"Error en actualizar_aviso: {e}")
        return jsonify(success=False, error=str(e))


# =========================
# Eliminar aviso
# =========================
@avisoapi.route('/avisos/<int:id_aviso>', methods=['DELETE'])
def eliminar_aviso(id_aviso):
    try:
        if dao.deleteAviso(id_aviso):
            return jsonify(success=True, mensaje="Aviso eliminado")
        return jsonify(success=False, error="No se pudo eliminar aviso")
    except Exception as e:
        app.logger.error(f"Error en eliminar_aviso: {e}")
        return jsonify(success=False, error=str(e))