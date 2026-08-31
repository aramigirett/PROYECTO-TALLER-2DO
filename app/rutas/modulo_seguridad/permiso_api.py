from flask import Blueprint, request, jsonify, current_app as app

from app.dao.modulo_seguridad.PermisoDao import PermisoDao
from app.dao.modulo_seguridad.RolDao import RolDao
from app.rutas.modulo_seguridad.decorators import require_admin

permisoapi = Blueprint('permisoapi', __name__)


# -------------------------
# Roles con cantidad de permisos (panel de solo lectura)
# -------------------------
@permisoapi.route('/roles-con-permisos', methods=['GET'])
@require_admin
def getRolesConPermisos():
    try:
        roles = RolDao().getRolesConConteoPermisos()
        return jsonify({'success': True, 'data': roles, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener roles con permisos: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Trae todos los permisos
# -------------------------
@permisoapi.route('/permisos', methods=['GET'])
@require_admin
def getPermisos():
    try:
        permisos = PermisoDao().getPermisos()
        return jsonify({'success': True, 'data': permisos, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener todos los permisos: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Trae un permiso por ID
# -------------------------
@permisoapi.route('/permisos/<int:id_permiso>', methods=['GET'])
@require_admin
def getPermiso(id_permiso):
    try:
        permiso = PermisoDao().getPermisoById(id_permiso)
        if permiso:
            return jsonify({'success': True, 'data': permiso, 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se encontró el permiso con el ID proporcionado.'}), 404
    except Exception as e:
        app.logger.error(f"Error al obtener permiso: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Agrega un nuevo permiso (Alta)
# -------------------------
@permisoapi.route('/permisos', methods=['POST'])
@require_admin
def addPermiso():
    data = request.get_json() or {}
    permisodao = PermisoDao()

    nombre_permiso = (data.get('nombre_permiso') or '').strip()
    descripcion = (data.get('descripcion') or '').strip() or None
    id_rol = data.get('id_rol')

    if not nombre_permiso or not id_rol:
        return jsonify({'success': False, 'error': 'El nombre del permiso y el rol son obligatorios.'}), 400

    try:
        if permisodao.existeDuplicado(id_rol, nombre_permiso):
            return jsonify({'success': False, 'error': 'Ese rol ya tiene un permiso con ese nombre.'}), 400

        id_permiso = permisodao.guardarPermiso(nombre_permiso, descripcion, id_rol)
        if id_permiso:
            return jsonify({'success': True, 'data': {'id_permiso': id_permiso}, 'error': None}), 201
        return jsonify({'success': False, 'error': 'No se pudo guardar el permiso. Consulte con el administrador.'}), 500
    except Exception as e:
        app.logger.error(f"Error al agregar permiso: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Actualiza un permiso (Modificación)
# -------------------------
@permisoapi.route('/permisos/<int:id_permiso>', methods=['PUT'])
@require_admin
def updatePermiso(id_permiso):
    data = request.get_json() or {}
    permisodao = PermisoDao()

    nombre_permiso = (data.get('nombre_permiso') or '').strip()
    descripcion = (data.get('descripcion') or '').strip() or None
    id_rol = data.get('id_rol')

    if not nombre_permiso or not id_rol:
        return jsonify({'success': False, 'error': 'El nombre del permiso y el rol son obligatorios.'}), 400

    try:
        if not permisodao.getPermisoById(id_permiso):
            return jsonify({'success': False, 'error': 'No se encontró el permiso con el ID proporcionado.'}), 404

        if permisodao.existeDuplicado(id_rol, nombre_permiso, excluir_id=id_permiso):
            return jsonify({'success': False, 'error': 'Ese rol ya tiene un permiso con ese nombre.'}), 400

        if permisodao.updatePermiso(id_permiso, nombre_permiso, descripcion, id_rol):
            return jsonify({'success': True, 'data': {'id_permiso': id_permiso}, 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se pudo actualizar el permiso.'}), 500
    except Exception as e:
        app.logger.error(f"Error al actualizar permiso: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Elimina un permiso (Baja física)
# -------------------------
@permisoapi.route('/permisos/<int:id_permiso>', methods=['DELETE'])
@require_admin
def deletePermiso(id_permiso):
    try:
        if PermisoDao().deletePermiso(id_permiso):
            return jsonify({'success': True, 'mensaje': f'Permiso con ID {id_permiso} eliminado correctamente.', 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se encontró el permiso con el ID proporcionado o no se pudo eliminar.'}), 404
    except Exception as e:
        app.logger.error(f"Error al eliminar permiso: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
