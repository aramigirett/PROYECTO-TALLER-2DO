from flask import Blueprint, request, jsonify, current_app as app

from app.dao.modulo_seguridad.PermisoDao import PermisoDao
from app.dao.modulo_seguridad.RolDao import RolDao
from app.rutas.modulo_seguridad.decorators import require_admin
from app.rutas.modulo_seguridad.menu_catalog import CATALOGO_MENU, MODULOS, VENTANAS_SOLO_ADMIN

permisoapi = Blueprint('permisoapi', __name__)


# -------------------------
# Roles que se pueden restringir desde la matriz (Administrador queda afuera:
# siempre ve todo, no tiene sentido togglearle nada).
# -------------------------
@permisoapi.route('/roles-restringibles', methods=['GET'])
@require_admin
def getRolesRestringibles():
    try:
        roles = [r for r in RolDao().getRoles() if r['nombre_rol'] != 'Administrador']
        return jsonify({'success': True, 'data': roles, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener roles restringibles: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Catálogo de ventanas/acciones agrupado por módulo, para dibujar la matriz
# -------------------------
@permisoapi.route('/permisos/catalogo', methods=['GET'])
@require_admin
def getCatalogoPermisos():
    try:
        por_modulo = {}
        for item in CATALOGO_MENU:
            if item.get('solo_admin'):
                continue   # exclusiva del Administrador: no se delega desde la matriz
            por_modulo.setdefault(item['modulo'], []).append({
                'ventana': item['ventana'],
                'etiqueta': item['etiqueta'],
                'acciones': item['acciones'],
            })

        data = [
            {'modulo': m['modulo'], 'ventanas': por_modulo[m['modulo']]}
            for m in MODULOS
            if m['modulo'] in por_modulo
        ]
        return jsonify({'success': True, 'data': data, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener catálogo de permisos: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Permisos otorgados a un rol (para marcar los checkboxes ya activos)
# -------------------------
@permisoapi.route('/permisos/matriz/<int:id_rol>', methods=['GET'])
@require_admin
def getMatrizRol(id_rol):
    try:
        otorgados = PermisoDao().getPermisosDeRol(id_rol)
        data = [{'ventana': ventana, 'accion': accion} for ventana, accion in sorted(otorgados)]
        return jsonify({'success': True, 'data': data, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener la matriz de permisos: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Togglear un permiso puntual: ON (otorgar)
# -------------------------
@permisoapi.route('/permisos/matriz', methods=['POST'])
@require_admin
def otorgarPermiso():
    data = request.get_json() or {}
    id_rol = data.get('id_rol')
    ventana = data.get('ventana')
    accion = data.get('accion')

    if not id_rol or not ventana or not accion:
        return jsonify({'success': False, 'error': 'Rol, ventana y acción son obligatorios.'}), 400
    if ventana in VENTANAS_SOLO_ADMIN:
        return jsonify({'success': False, 'error': 'Esa ventana es exclusiva del Administrador.'}), 400

    try:
        if PermisoDao().otorgar(id_rol, ventana, accion):
            return jsonify({'success': True, 'error': None}), 201
        return jsonify({'success': False, 'error': 'No se pudo otorgar el permiso.'}), 500
    except Exception as e:
        app.logger.error(f"Error al otorgar permiso: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Togglear un permiso puntual: OFF (revocar)
# -------------------------
@permisoapi.route('/permisos/matriz', methods=['DELETE'])
@require_admin
def revocarPermiso():
    data = request.get_json() or {}
    id_rol = data.get('id_rol')
    ventana = data.get('ventana')
    accion = data.get('accion')

    if not id_rol or not ventana or not accion:
        return jsonify({'success': False, 'error': 'Rol, ventana y acción son obligatorios.'}), 400

    try:
        if PermisoDao().revocar(id_rol, ventana, accion):
            return jsonify({'success': True, 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se pudo revocar el permiso.'}), 500
    except Exception as e:
        app.logger.error(f"Error al revocar permiso: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
