from flask import Blueprint, request, jsonify, current_app as app

from app.dao.modulo_seguridad.PermisoDao import PermisoDao
from app.dao.modulo_seguridad.RolDao import RolDao
from app.rutas.modulo_seguridad.decorators import require_admin
from app.rutas.modulo_seguridad import menu_servicio
from app.rutas.modulo_facturacion.utils import auditar, detalle_cambios


def _validar_permiso(id_rol, ventana, accion):
    """Devuelve (rol, etiqueta_ventana, None) o (None, None, mensaje): el rol existe (y no es Administrador), la ventana está en el catálogo y expone esa acción."""
    rol = next((r for r in RolDao().getRoles() if r['id_rol'] == id_rol), None)
    if rol is None:
        return None, None, 'El rol seleccionado no existe.'
    if rol['nombre_rol'] == 'Administrador':
        return None, None, 'El Administrador siempre tiene todos los permisos: no se edita.'
    item = menu_servicio.ventana_para_permisos(ventana)
    if item is None:
        return None, None, 'La ventana seleccionada no existe o está anulada.'
    if item['solo_admin']:
        return None, None, 'Esa ventana es exclusiva del Administrador.'
    if accion not in menu_servicio.acciones_de(ventana):
        return None, None, f"La ventana {item['descripcion']} no tiene la acción \"{accion}\"."
    return rol, item['descripcion'], None


def _auditar_permiso(rol, etiqueta, accion, antes, despues):
    """Un permiso otorgado o revocado queda en la auditoría (módulo Seguridad), con el rol, la ventana y la acción por nombre."""
    si_no = {True: 'Sí', False: 'No'}
    auditar('permisos', rol['id_rol'], 'MODIFICACION',
            detalle_cambios({'p': si_no[antes]}, {'p': si_no[despues]}, {'p': f"{rol['nombre_rol']} · {etiqueta} · {accion}"}))

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
        data = menu_servicio.catalogo_permisos()
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
    rol, etiqueta, error = _validar_permiso(id_rol, ventana, accion)
    if error:
        return jsonify({'success': False, 'error': error}), 400
    try:
        dao = PermisoDao()
        tenia = (ventana, accion) in dao.getPermisosDeRol(id_rol)
        if dao.otorgar(id_rol, ventana, accion):
            if not tenia:
                _auditar_permiso(rol, etiqueta, accion, False, True)
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

    rol, etiqueta, error = _validar_permiso(id_rol, ventana, accion)
    if error:
        return jsonify({'success': False, 'error': error}), 400
    try:
        dao = PermisoDao()
        tenia = (ventana, accion) in dao.getPermisosDeRol(id_rol)
        if dao.revocar(id_rol, ventana, accion):
            if tenia:
                _auditar_permiso(rol, etiqueta, accion, True, False)
            return jsonify({'success': True, 'error': None}), 200
        return jsonify({'success': False, 'error': 'No se pudo revocar el permiso.'}), 500
    except Exception as e:
        app.logger.error(f"Error al revocar permiso: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500


# -------------------------
# Guardar la matriz COMPLETA de un rol (alta de los marcados nuevos y baja de los desmarcados, en una transacción)
# -------------------------
@permisoapi.route('/permisos/matriz/<int:id_rol>', methods=['PUT'])
@require_admin
def guardarMatrizRol(id_rol):
    data = request.get_json(silent=True)
    lista = data.get('permisos') if isinstance(data, dict) else None
    if not isinstance(lista, list):
        return jsonify({'success': False, 'error': 'Los datos enviados no son válidos.'}), 400
    rol = next((r for r in RolDao().getRoles() if r['id_rol'] == id_rol), None)
    if rol is None:
        return jsonify({'success': False, 'error': 'El rol seleccionado no existe.'}), 400
    if rol['nombre_rol'] == 'Administrador':
        return jsonify({'success': False, 'error': 'El Administrador siempre tiene todos los permisos: no se edita.'}), 400
    catalogo = menu_servicio.catalogo_permisos()
    alcance = {(v['ventana'], a) for m in catalogo for v in m['ventanas'] for a in v['acciones']}      # ventanas activas y delegables, con sus acciones
    deseados = set()
    for p in lista:
        if not isinstance(p, dict) or not isinstance(p.get('ventana'), str) or not isinstance(p.get('accion'), str):
            return jsonify({'success': False, 'error': 'Los datos enviados no son válidos.'}), 400
        if (p['ventana'], p['accion']) not in alcance:
            return jsonify({'success': False, 'error': f"El permiso {p['ventana']} / {p['accion']} no existe o no se puede delegar."}), 400
        deseados.add((p['ventana'], p['accion']))
    try:
        resultado = PermisoDao().reemplazarPermisos(id_rol, deseados, alcance)
        if resultado is None:
            return jsonify({'success': False, 'error': 'El rol seleccionado no existe.'}), 400
        altas, bajas = resultado
        etiquetas = {v['ventana']: v['etiqueta'] for m in catalogo for v in m['ventanas']}
        for ventana, accion in altas:
            _auditar_permiso(rol, etiquetas.get(ventana, ventana), accion, False, True)
        for ventana, accion in bajas:
            _auditar_permiso(rol, etiquetas.get(ventana, ventana), accion, True, False)
        return jsonify({'success': True, 'data': {'otorgados': len(altas), 'revocados': len(bajas)}, 'error': None,
                        'mensaje': (f'Permisos de {rol["nombre_rol"]} guardados: {len(altas)} otorgado(s) y {len(bajas)} revocado(s).' if altas or bajas
                                    else f'Los permisos de {rol["nombre_rol"]} no tenían cambios.')}), 200
    except Exception as e:
        app.logger.error(f"Error al guardar la matriz de permisos: {str(e)}")
        return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
