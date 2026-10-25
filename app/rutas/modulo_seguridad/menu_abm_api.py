"""
Mantener Menú (ABM de la tabla `menu`). Solo el Administrador: las ventanas `menu`, `usuario` y `permiso` son exclusivas suyas y están protegidas. Baja lógica,
Reactivar y auditoría estructurada (módulo Seguridad). El sidebar, el buscador general y la matriz de Roles y Permisos se arman desde esta tabla.

    GET    /menus[?inactivos=1] · /menus/<id> · /menus/rutas        ('ver')
    POST   /menus ('nuevo')   PUT /menus/<id> ('editar')   DELETE /menus/<id> ('anular')   PATCH /menus/<id>/reactivar ('anular')
"""
import re

from flask import Blueprint, current_app as app, jsonify, request

from app.dao.modulo_seguridad.MenuDao import MenuDao, DUPLICADO, EN_USO, NO_EXISTE, PROTEGIDA, YA_ACTIVO
from app.rutas.modulo_facturacion.utils import auditar, detalle_cambios, entero_id, error_interno, respuesta_error, validar_texto
from app.rutas.modulo_seguridad.decorators import require_permiso

menuabmapi = Blueprint('menuabmapi', __name__)

_RE_CLAVE = re.compile(r'^[a-z][a-z0-9]{1,59}$')
_RE_ICONO = re.compile(r'^fa-[a-z0-9]+(-[a-z0-9]+)*$')
ETIQ_MENU = {'tipo_txt': 'Tipo', 'modulo': 'Módulo', 'descripcion': 'Descripción', 'clave': 'Clave', 'ruta': 'Ruta', 'icono': 'Ícono', 'orden': 'Orden',
             'visible_txt': 'Visible en el menú', 'admin_txt': 'Solo Administrador'}


def _auditado(f):
    es_ventana = f['tipo'] == 'ventana'
    return {'tipo_txt': 'Ventana' if es_ventana else 'Módulo', 'modulo': f['modulo'] if es_ventana else None, 'descripcion': f['descripcion'],
            'clave': f['clave'], 'ruta': f['ruta'], 'icono': f['icono'], 'orden': f['orden'],
            'visible_txt': ('Sí' if f['visible_en_menu'] else 'No') if es_ventana else None,
            'admin_txt': ('Sí' if f['solo_admin'] else 'No') if es_ventana else None}


def _quien(f):
    return f"{'Ventana' if f['tipo'] == 'ventana' else 'Módulo'} \"{f['descripcion']}\""


def rutas_disponibles():
    """Pantallas (GET, sin parámetros, que no son de la API) que se pueden enlazar desde el menú: [{endpoint, url}]."""
    vistas = {}
    for r in app.url_map.iter_rules():
        if r.endpoint == 'static' or 'GET' not in r.methods or (r.arguments - set(r.defaults or ())) or r.rule.startswith('/api/'):
            continue
        vistas.setdefault(r.endpoint, r.rule)
    return [{'endpoint': e, 'url': u} for e, u in sorted(vistas.items(), key=lambda x: x[1])]


def _validar(data, existente=None):
    """Valida el cuerpo del alta (existente=None) o de la modificación. Devuelve (valores, None) o (None, respuesta_de_error)."""
    if not isinstance(data, dict):
        return None, respuesta_error('Los datos enviados no son válidos.', 400)
    tipo = existente['tipo'] if existente else data.get('tipo')
    if tipo not in ('modulo', 'ventana'):
        return None, respuesta_error('Elija si es un módulo o una ventana.', 400, 'tipo')
    v = {'tipo': tipo}
    v['descripcion'], error = validar_texto(data.get('descripcion'), 'descripción', 60)
    if error:
        return None, respuesta_error(error, 400, 'descripcion')
    icono = data.get('icono').strip() if isinstance(data.get('icono'), str) else ''
    if icono and not _RE_ICONO.match(icono):
        return None, respuesta_error('El ícono debe ser una clase de FontAwesome, por ejemplo fa-users.', 400, 'icono')
    v['icono'] = icono or ('fa-circle' if tipo == 'ventana' else 'fa-folder')
    orden = data.get('orden')
    orden = 0 if orden in (0, '0') else entero_id(orden)
    if orden is None or orden > 32000:
        return None, respuesta_error('El orden debe ser un número entero de 0 a 32.000.', 400, 'orden')
    v['orden'] = orden
    if tipo == 'ventana':
        v['id_menu_padre'] = entero_id(data.get('id_menu_padre'))
        if v['id_menu_padre'] is None:
            return None, respuesta_error('Elija el módulo de la ventana.', 400, 'id_menu_padre')
        ruta = data.get('ruta').strip() if isinstance(data.get('ruta'), str) else ''
        if not ruta or ruta not in {r['endpoint'] for r in rutas_disponibles()}:
            return None, respuesta_error('Elija una pantalla existente del sistema como ruta.', 400, 'ruta')
        v['ruta'] = ruta
        for campo in ('visible_en_menu', 'solo_admin'):
            if campo in data and not isinstance(data[campo], bool):
                return None, respuesta_error('Los campos Sí / No deben ser verdadero o falso.', 400, campo)
        v['visible_en_menu'] = data.get('visible_en_menu', True)
        v['solo_admin'] = data.get('solo_admin', existente['solo_admin'] if existente else False)
        if existente is None:
            clave = data.get('clave').strip() if isinstance(data.get('clave'), str) else ''
            if not _RE_CLAVE.match(clave):
                return None, respuesta_error('La clave debe tener de 2 a 60 caracteres: minúsculas y números, empezando por una letra (ej. reportes).', 400, 'clave')
            v['clave'] = clave
    return v, None


def _conflicto(r):
    if r[0] == PROTEGIDA:
        return respuesta_error(r[1], 409)
    return respuesta_error(r[-1], 409 if r[0] in (DUPLICADO, EN_USO) else 400, r[1] if len(r) == 3 else None)


@menuabmapi.route('/menus', methods=['GET'])
@require_permiso('menu', 'ver')
def getMenus():
    try:
        filas = MenuDao().getFilas(incluir_inactivos=request.args.get('inactivos', '').lower() in ('1', 'true'))
        return jsonify({'success': True, 'data': filas, 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al listar el menú: {str(e)}")
        return error_interno()


@menuabmapi.route('/menus/rutas', methods=['GET'])
@require_permiso('menu', 'ver')
def getRutas():
    return jsonify({'success': True, 'data': rutas_disponibles(), 'error': None}), 200


@menuabmapi.route('/menus/<int:id_menu>', methods=['GET'])
@require_permiso('menu', 'ver')
def getMenu(id_menu):
    f = MenuDao().getFila(id_menu)
    if f:
        return jsonify({'success': True, 'data': f, 'error': None}), 200
    return respuesta_error('No se encontró la entrada de menú con el ID proporcionado.', 404)


@menuabmapi.route('/menus', methods=['POST'])
@require_permiso('menu', 'nuevo')
def addMenu():
    v, error = _validar(request.get_json(silent=True))
    if error:
        return error
    dao = MenuDao()
    try:
        r = dao.guardar(v)
        if isinstance(r, tuple):
            return _conflicto(r)
        if r:
            f = dao.getFila(r)
            auditar('menu', r, 'ALTA', detalle_cambios({}, _auditado(f), ETIQ_MENU))
            return jsonify({'success': True, 'data': {'id_menu': r}, 'mensaje': f'{_quien(f)} agregado correctamente.', 'error': None}), 201
        return respuesta_error('No se pudo guardar la entrada de menú. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al crear la entrada de menú: {str(e)}")
        return error_interno()


@menuabmapi.route('/menus/<int:id_menu>', methods=['PUT'])
@require_permiso('menu', 'editar')
def updateMenu(id_menu):
    dao = MenuDao()
    antes = dao.getFila(id_menu)
    if not antes or not antes['activo']:
        return respuesta_error('No se encontró la entrada de menú con el ID proporcionado.', 404)
    v, error = _validar(request.get_json(silent=True), existente=antes)
    if error:
        return error
    try:
        r = dao.actualizar(id_menu, v)
        if isinstance(r, tuple):
            return _conflicto(r)
        if r:
            nuevo = dao.getFila(id_menu)
            detalle = detalle_cambios(_auditado(antes), _auditado(nuevo), ETIQ_MENU)
            if detalle:
                auditar('menu', id_menu, 'MODIFICACION', detalle)
            return jsonify({'success': True, 'data': {'id_menu': id_menu}, 'mensaje': f'{_quien(nuevo)} actualizado correctamente.', 'error': None}), 200
        return respuesta_error('No se pudo actualizar la entrada de menú.', 404)
    except Exception as e:
        app.logger.error(f"Error al actualizar la entrada de menú: {str(e)}")
        return error_interno()


@menuabmapi.route('/menus/<int:id_menu>', methods=['DELETE'])
@require_permiso('menu', 'anular')
def deleteMenu(id_menu):
    dao = MenuDao()
    try:
        f = dao.getFila(id_menu)
        r = dao.anular(id_menu)
        if isinstance(r, tuple):
            return _conflicto(r)
        if r:
            auditar('menu', id_menu, 'BAJA', detalle_cambios({}, _auditado(f), ETIQ_MENU))
            return jsonify({'success': True, 'mensaje': f'{_quien(f)} anulado correctamente.', 'error': None}), 200
        return respuesta_error('No se encontró la entrada de menú con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al anular la entrada de menú: {str(e)}")
        return error_interno()


@menuabmapi.route('/menus/<int:id_menu>/reactivar', methods=['PATCH'])
@require_permiso('menu', 'anular')
def reactivarMenu(id_menu):
    dao = MenuDao()
    try:
        r = dao.reactivar(id_menu)
        if r == NO_EXISTE:
            return respuesta_error('No se encontró la entrada de menú con el ID proporcionado.', 404)
        if r == YA_ACTIVO:
            return respuesta_error('La entrada de menú ya está activa.', 409)
        if isinstance(r, tuple):
            return _conflicto(r)
        if r:
            f = dao.getFila(id_menu)
            auditar('menu', id_menu, 'REACTIVACION', detalle_cambios({}, _auditado(f), ETIQ_MENU))
            return jsonify({'success': True, 'data': f, 'mensaje': f'{_quien(f)} reactivado correctamente.', 'error': None}), 200
        return respuesta_error('No se pudo reactivar la entrada de menú. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al reactivar la entrada de menú: {str(e)}")
        return error_interno()
