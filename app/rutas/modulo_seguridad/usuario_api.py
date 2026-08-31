import re

from flask import Blueprint, request, jsonify, current_app as app

from app.dao.modulo_seguridad.UsuarioDao import UsuarioDao
from app.dao.modulo_seguridad.RolDao import RolDao
from app.rutas.modulo_seguridad.decorators import require_admin

usuarioapi = Blueprint('usuarioapi', __name__)

EMAIL_REGEX = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'


def _validar_persona(id_funcionario, id_medico):
    """
    Regla de negocio: un usuario se vincula a exactamente una persona,
    funcionario XOR medico (nunca ambos, nunca ninguno).
    """
    if bool(id_funcionario) == bool(id_medico):
        return "Debés seleccionar exactamente una persona: un funcionario o un médico, no ambos ni ninguno."
    return None


# -------------------------
# Roles (para el combo del formulario)
# -------------------------
@usuarioapi.route('/roles', methods=['GET'])
@require_admin
def getRoles():
    try:
        roles = RolDao().getRoles()
        return jsonify({'success': True, 'data': roles, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener roles: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Personas disponibles para vincular
# -------------------------
@usuarioapi.route('/usuarios/funcionarios-disponibles', methods=['GET'])
@require_admin
def getFuncionariosDisponibles():
    excluir_usuario = request.args.get('excluir_usuario', type=int)
    try:
        funcionarios = UsuarioDao().getFuncionariosDisponibles(excluir_usuario)
        return jsonify({'success': True, 'data': funcionarios, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener funcionarios disponibles: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


@usuarioapi.route('/usuarios/medicos-disponibles', methods=['GET'])
@require_admin
def getMedicosDisponibles():
    excluir_usuario = request.args.get('excluir_usuario', type=int)
    try:
        medicos = UsuarioDao().getMedicosDisponibles(excluir_usuario)
        return jsonify({'success': True, 'data': medicos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener médicos disponibles: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Trae todos los usuarios
# -------------------------
@usuarioapi.route('/usuarios', methods=['GET'])
@require_admin
def getUsuarios():
    try:
        usuarios = UsuarioDao().getUsuarios()
        return jsonify({'success': True, 'data': usuarios, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener todos los usuarios: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Trae un usuario por ID
# -------------------------
@usuarioapi.route('/usuarios/<int:id_usuario>', methods=['GET'])
@require_admin
def getUsuario(id_usuario):
    try:
        usuario = UsuarioDao().getUsuarioById(id_usuario)
        if usuario:
            return jsonify({'success': True, 'data': usuario, 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se encontró el usuario con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener usuario: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Agrega un nuevo usuario (Alta)
# -------------------------
@usuarioapi.route('/usuarios', methods=['POST'])
@require_admin
def addUsuario():
    data = request.get_json() or {}
    usuariodao = UsuarioDao()

    ci_ruc = (data.get('ci_ruc') or '').strip()
    password = data.get('password') or ''
    correo = (data.get('correo') or '').strip()
    id_rol = data.get('id_rol')
    id_funcionario = data.get('id_funcionario') or None
    id_medico = data.get('id_medico') or None

    if not ci_ruc or not correo or not id_rol:
        return jsonify({'success': False, 'error': 'CI/RUC, correo y rol son obligatorios.'}), 400

    if not re.match(EMAIL_REGEX, correo):
        return jsonify({'success': False, 'error': 'El correo electrónico no es válido.'}), 400

    if len(password) < 6:
        return jsonify({'success': False, 'error': 'La contraseña debe tener al menos 6 caracteres.'}), 400

    error_persona = _validar_persona(id_funcionario, id_medico)
    if error_persona:
        return jsonify({'success': False, 'error': error_persona}), 400

    try:
        if usuariodao.existeDuplicadoCiRuc(ci_ruc):
            return jsonify({'success': False, 'error': 'Ya existe un usuario con ese CI/RUC.'}), 400

        if usuariodao.existePersonaVinculada(id_funcionario, id_medico):
            return jsonify({'success': False, 'error': 'Esa persona ya tiene un usuario de acceso.'}), 400

        id_usuario = usuariodao.guardarUsuario(ci_ruc, password, correo, id_rol, id_funcionario, id_medico)
        if id_usuario:
            return jsonify({'success': True, 'data': {'id_usuario': id_usuario}, 'error': None}), 201
        return jsonify({'success': False, 'error': 'No se pudo guardar el usuario. Consulte con el administrador.'}), 500
    except Exception as e:
        app.logger.error(f"Error al agregar usuario: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Actualiza un usuario (Modificación)
# -------------------------
@usuarioapi.route('/usuarios/<int:id_usuario>', methods=['PUT'])
@require_admin
def updateUsuario(id_usuario):
    data = request.get_json() or {}
    usuariodao = UsuarioDao()

    ci_ruc = (data.get('ci_ruc') or '').strip()
    password = data.get('password') or ''
    correo = (data.get('correo') or '').strip()
    id_rol = data.get('id_rol')
    id_funcionario = data.get('id_funcionario') or None
    id_medico = data.get('id_medico') or None

    if not ci_ruc or not correo or not id_rol:
        return jsonify({'success': False, 'error': 'CI/RUC, correo y rol son obligatorios.'}), 400

    if not re.match(EMAIL_REGEX, correo):
        return jsonify({'success': False, 'error': 'El correo electrónico no es válido.'}), 400

    if password and len(password) < 6:
        return jsonify({'success': False, 'error': 'La contraseña debe tener al menos 6 caracteres.'}), 400

    error_persona = _validar_persona(id_funcionario, id_medico)
    if error_persona:
        return jsonify({'success': False, 'error': error_persona}), 400

    try:
        if not usuariodao.getUsuarioById(id_usuario):
            return jsonify({'success': False, 'error': 'No se encontró el usuario con el ID proporcionado.'}), 404

        if usuariodao.existeDuplicadoCiRuc(ci_ruc, excluir_id=id_usuario):
            return jsonify({'success': False, 'error': 'Ya existe un usuario con ese CI/RUC.'}), 400

        if usuariodao.existePersonaVinculada(id_funcionario, id_medico, excluir_id=id_usuario):
            return jsonify({'success': False, 'error': 'Esa persona ya tiene un usuario de acceso.'}), 400

        actualizado = usuariodao.updateUsuario(
            id_usuario, ci_ruc, correo, id_rol, id_funcionario, id_medico,
            password=password or None
        )
        if actualizado:
            return jsonify({'success': True, 'data': {'id_usuario': id_usuario}, 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se pudo actualizar el usuario.'}), 500
    except Exception as e:
        app.logger.error(f"Error al actualizar usuario: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Baja (desactivar) un usuario
# -------------------------
@usuarioapi.route('/usuarios/<int:id_usuario>', methods=['DELETE'])
@require_admin
def bajaUsuario(id_usuario):
    try:
        if UsuarioDao().cambiarEstado(id_usuario, False):
            return jsonify({'success': True, 'mensaje': 'Usuario dado de baja correctamente.', 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se encontró el usuario con el ID proporcionado o no se pudo dar de baja.'}), 404
    except Exception as e:
        app.logger.error(f"Error al dar de baja usuario: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Reactivar un usuario dado de baja
# -------------------------
@usuarioapi.route('/usuarios/<int:id_usuario>/reactivar', methods=['PATCH'])
@require_admin
def reactivarUsuario(id_usuario):
    try:
        if UsuarioDao().cambiarEstado(id_usuario, True):
            return jsonify({'success': True, 'mensaje': 'Usuario reactivado correctamente.', 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se encontró el usuario con el ID proporcionado o no se pudo reactivar.'}), 404
    except Exception as e:
        app.logger.error(f"Error al reactivar usuario: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
