import re

from flask import Blueprint, request, jsonify, session, current_app as app

from app.dao.modulo_seguridad.UsuarioDao import UsuarioDao
from app.dao.modulo_seguridad.AuditoriaDao import AuditoriaDao
from app.dao.modulo_seguridad.RolDao import RolDao
from app.rutas.modulo_seguridad.decorators import require_permiso
from app.rutas.modulo_seguridad.password_policy import validar_password_compleja
from app.rutas.modulo_facturacion.utils import auditar, detalle_cambios, respuesta_error, error_interno

usuarioapi = Blueprint('usuarioapi', __name__)

EMAIL_REGEX = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'

NOTA_FUENTE = "Se edita en Funcionario/Médico."

# Auditoría de Usuarios: persona, CI/RUC (su login) y rol. NUNCA la contraseña ni el código 2FA: un cambio de contraseña solo deja "modificada".
ETIQ_USUARIO = {'nombre_completo': 'Persona', 'ci_ruc': 'CI/RUC', 'nombre_rol': 'Rol', 'password': 'Contraseña'}


def _auditado(u):
    return {k: u.get(k) for k in ('nombre_completo', 'ci_ruc', 'nombre_rol')}


def _nombre(u):
    return f"{u['nombre_completo']} ({u['ci_ruc']})"


def _validar_persona(id_funcionario, id_medico):
    """
    Regla de negocio: un usuario se vincula a exactamente una persona,
    funcionario XOR medico (nunca ambos, nunca ninguno).
    """
    if bool(id_funcionario) == bool(id_medico):
        return "Debés seleccionar exactamente una persona: un funcionario o un médico, no ambos ni ninguno."
    return None


def _validar_datos_persona(usuariodao, id_funcionario, id_medico):
    """
    CI/RUC (login) y correo (2FA, alertas, recuperación) salen de la persona
    vinculada, no se guardan en usuarios. Por eso la persona tiene que existir
    y tener ambos cargados antes de vincularle un usuario.
    """
    datos = usuariodao.getDatosPersona(id_funcionario, id_medico)
    if datos is None:
        return "La persona seleccionada no existe."
    if not datos['ci_ruc']:
        return f"La persona seleccionada no tiene cédula registrada. {NOTA_FUENTE}"
    if not datos['correo']:
        return (f"La persona seleccionada no tiene correo registrado: sin correo no puede "
                f"recibir el código de verificación. {NOTA_FUENTE}")
    if not re.match(EMAIL_REGEX, datos['correo']):
        return f"El correo registrado de la persona no es válido. {NOTA_FUENTE}"
    return None


# -------------------------
# Roles (para el combo del formulario)
# -------------------------
@usuarioapi.route('/roles', methods=['GET'])
@require_permiso('usuario', 'ver')
def getRoles():
    try:
        roles = RolDao().getRoles()
        return jsonify({'success': True, 'data': roles, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener roles: {str(e)}")
        return error_interno()


# -------------------------
# Personas disponibles para vincular
# -------------------------
@usuarioapi.route('/usuarios/funcionarios-disponibles', methods=['GET'])
@require_permiso('usuario', 'ver')
def getFuncionariosDisponibles():
    excluir_usuario = request.args.get('excluir_usuario', type=int)
    try:
        funcionarios = UsuarioDao().getFuncionariosDisponibles(excluir_usuario)
        return jsonify({'success': True, 'data': funcionarios, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener funcionarios disponibles: {str(e)}")
        return error_interno()


@usuarioapi.route('/usuarios/medicos-disponibles', methods=['GET'])
@require_permiso('usuario', 'ver')
def getMedicosDisponibles():
    excluir_usuario = request.args.get('excluir_usuario', type=int)
    try:
        medicos = UsuarioDao().getMedicosDisponibles(excluir_usuario)
        return jsonify({'success': True, 'data': medicos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener médicos disponibles: {str(e)}")
        return error_interno()


# -------------------------
# Trae todos los usuarios
# -------------------------
@usuarioapi.route('/usuarios', methods=['GET'])
@require_permiso('usuario', 'ver')
def getUsuarios():
    try:
        usuarios = UsuarioDao().getUsuarios()
        return jsonify({'success': True, 'data': usuarios, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener todos los usuarios: {str(e)}")
        return error_interno()


# -------------------------
# Trae un usuario por ID
# -------------------------
@usuarioapi.route('/usuarios/<int:id_usuario>', methods=['GET'])
@require_permiso('usuario', 'ver')
def getUsuario(id_usuario):
    try:
        usuario = UsuarioDao().getUsuarioById(id_usuario)
        if usuario:
            return jsonify({'success': True, 'data': usuario, 'error': None}), 200
        return respuesta_error('No se encontró el usuario con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al obtener usuario: {str(e)}")
        return error_interno()


# -------------------------
# Agrega un nuevo usuario (Alta)
# -------------------------
@usuarioapi.route('/usuarios', methods=['POST'])
@require_permiso('usuario', 'nuevo')
def addUsuario():
    data = request.get_json() or {}
    usuariodao = UsuarioDao()

    password = data.get('password') or ''
    id_rol = data.get('id_rol')
    id_funcionario = data.get('id_funcionario') or None
    id_medico = data.get('id_medico') or None

    if not id_rol:
        return respuesta_error('El rol es obligatorio.', 400, 'id_rol', tipo='obligatorio')

    error_password = validar_password_compleja(password)
    if error_password:
        return respuesta_error(error_password, 400, 'password')

    error_persona = _validar_persona(id_funcionario, id_medico)
    if error_persona:
        return respuesta_error(error_persona, 400, 'persona', tipo='obligatorio')

    try:
        error_datos = _validar_datos_persona(usuariodao, id_funcionario, id_medico)
        if error_datos:
            return respuesta_error(error_datos, 400, 'persona')

        if usuariodao.existePersonaVinculada(id_funcionario, id_medico):
            return respuesta_error('Esa persona ya tiene un usuario de acceso.', 400, 'persona', tipo='duplicado')

        id_usuario = usuariodao.guardarUsuario(password, id_rol, id_funcionario, id_medico)
        if isinstance(id_usuario, tuple):  # ("PERSONA_INACTIVA", mensaje)
            return respuesta_error(id_usuario[1], 400, 'persona', tipo='estado')
        if id_usuario:
            nuevo = usuariodao.getUsuarioById(id_usuario)
            auditar('usuarios', id_usuario, 'ALTA', detalle_cambios({}, _auditado(nuevo), ETIQ_USUARIO))
            return jsonify({'success': True, 'data': {'id_usuario': id_usuario}, 'mensaje': f'Usuario de {_nombre(nuevo)} agregado correctamente.', 'error': None}), 201
        return respuesta_error('No se pudo guardar el usuario. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al agregar usuario: {str(e)}")
        return error_interno()


# -------------------------
# Actualiza un usuario (Modificación)
# -------------------------
@usuarioapi.route('/usuarios/<int:id_usuario>', methods=['PUT'])
@require_permiso('usuario', 'editar')
def updateUsuario(id_usuario):
    data = request.get_json() or {}
    usuariodao = UsuarioDao()

    password = data.get('password') or ''
    id_rol = data.get('id_rol')
    id_funcionario = data.get('id_funcionario') or None
    id_medico = data.get('id_medico') or None

    if not id_rol:
        return respuesta_error('El rol es obligatorio.', 400, 'id_rol', tipo='obligatorio')

    error_password = validar_password_compleja(password) if password else None
    if error_password:
        return respuesta_error(error_password, 400, 'password')

    error_persona = _validar_persona(id_funcionario, id_medico)
    if error_persona:
        return respuesta_error(error_persona, 400, 'persona', tipo='obligatorio')

    try:
        actual = usuariodao.getUsuarioById(id_usuario)
        if not actual:
            return respuesta_error('No se encontró el usuario con el ID proporcionado.', 404)

        # Los datos de la persona solo se exigen si se la cambia: editar el rol de
        # un usuario no debe bloquearse por un dato de una persona ya vinculada.
        if (id_funcionario != actual['id_funcionario']) or (id_medico != actual['id_medico']):
            error_datos = _validar_datos_persona(usuariodao, id_funcionario, id_medico)
            if error_datos:
                return respuesta_error(error_datos, 400, 'persona')

        if usuariodao.existePersonaVinculada(id_funcionario, id_medico, excluir_id=id_usuario):
            return respuesta_error('Esa persona ya tiene un usuario de acceso.', 400, 'persona', tipo='duplicado')

        actualizado = usuariodao.updateUsuario(
            id_usuario, id_rol, id_funcionario, id_medico,
            password=password or None
        )
        if isinstance(actualizado, tuple):  # ("PERSONA_INACTIVA", mensaje)
            return respuesta_error(actualizado[1], 400, 'persona', tipo='estado')
        if actualizado:
            nuevo = usuariodao.getUsuarioById(id_usuario)
            ant, nue = _auditado(actual), _auditado(nuevo)
            ant['password'], nue['password'] = ('anterior', 'modificada') if password else ('sin cambios', 'sin cambios')
            detalle = detalle_cambios(ant, nue, ETIQ_USUARIO)
            if detalle:
                auditar('usuarios', id_usuario, 'MODIFICACION', detalle)
            return jsonify({'success': True, 'data': {'id_usuario': id_usuario}, 'mensaje': f'Usuario de {_nombre(nuevo)} actualizado correctamente.', 'error': None}), 200
        return respuesta_error('No se pudo actualizar el usuario.', 500)
    except Exception as e:
        app.logger.error(f"Error al actualizar usuario: {str(e)}")
        return error_interno()


# -------------------------
# Baja (desactivar) un usuario
# -------------------------
@usuarioapi.route('/usuarios/<int:id_usuario>', methods=['DELETE'])
@require_permiso('usuario', 'anular')
def bajaUsuario(id_usuario):
    try:
        dao = UsuarioDao()
        u = dao.getUsuarioById(id_usuario)
        if not u:
            return respuesta_error('No se encontró el usuario con el ID proporcionado.', 404)
        if id_usuario == session.get('id_usuario'):
            return respuesta_error('No puede anular su propio usuario.', 409)
        if u['nombre_rol'] == 'Administrador' and u['activo'] and dao.contarAdministradoresActivos() <= 1:
            return respuesta_error('No se puede anular el único Administrador activo: el sistema quedaría sin acceso de administración.', 409)
        if dao.cambiarEstado(id_usuario, False):
            auditar('usuarios', id_usuario, 'BAJA', detalle_cambios({}, _auditado(u), ETIQ_USUARIO))
            return jsonify({'success': True, 'mensaje': f'Usuario de {_nombre(u)} dado de baja correctamente.', 'error': None}), 200
        return respuesta_error('No se pudo dar de baja el usuario.', 404)
    except Exception as e:
        app.logger.error(f"Error al dar de baja usuario: {str(e)}")
        return error_interno()


# -------------------------
# Desbloquear una cuenta bloqueada por intentos fallidos
# -------------------------
@usuarioapi.route('/usuarios/<int:id_usuario>/desbloquear', methods=['PATCH'])
@require_permiso('usuario', 'desbloquear')
def desbloquearUsuario(id_usuario):
    try:
        usuariodao = UsuarioDao()
        usuario = usuariodao.getUsuarioById(id_usuario)
        if not usuario:
            return respuesta_error('No se encontró el usuario con el ID proporcionado.', 404)

        if not usuariodao.desbloquear(id_usuario):
            return respuesta_error('El usuario no está bloqueado.', 409)

        AuditoriaDao().registrar(id_usuario, usuario['ci_ruc'], 'DESBLOQUEADO', request.remote_addr, 'DESBLOQUEO_ADMIN',
                                  id_usuario_actor=session.get('id_usuario'))
        auditar('usuarios', id_usuario, 'MODIFICACION', detalle_cambios({'c': 'bloqueada'}, {'c': 'desbloqueada'}, {'c': f'Cuenta de {_nombre(usuario)}'}))
        app.logger.info(f"Usuario {usuario['ci_ruc']} desbloqueado por {session.get('ci_ruc')}")
        return jsonify({'success': True, 'mensaje': 'Usuario desbloqueado correctamente.', 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al desbloquear usuario: {str(e)}")
        return error_interno()


# -------------------------
# Reactivar un usuario dado de baja
# -------------------------
@usuarioapi.route('/usuarios/<int:id_usuario>/reactivar', methods=['PATCH'])
@require_permiso('usuario', 'anular')
def reactivarUsuario(id_usuario):
    try:
        dao = UsuarioDao()
        u = dao.getUsuarioById(id_usuario)
        resultado = dao.cambiarEstado(id_usuario, True)
        if isinstance(resultado, tuple):  # ("PERSONA_INACTIVA", mensaje)
            return respuesta_error('No se puede reactivar el usuario: ' + resultado[1][0].lower() + resultado[1][1:], 409)
        if resultado:
            auditar('usuarios', id_usuario, 'REACTIVACION', detalle_cambios({}, _auditado(u), ETIQ_USUARIO))
            return jsonify({'success': True, 'mensaje': f'Usuario de {_nombre(u)} reactivado correctamente.', 'error': None}), 200
        return respuesta_error('No se encontró el usuario con el ID proporcionado o no se pudo reactivar.', 404)
    except Exception as e:
        app.logger.error(f"Error al reactivar usuario: {str(e)}")
        return error_interno()
