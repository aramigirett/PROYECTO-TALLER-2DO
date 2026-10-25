from functools import wraps

from flask import session, redirect, url_for, jsonify, request, abort, g

from app.rutas.modulo_seguridad.permisos_contexto import puede


def require_admin(view_func):
    """
    Restringe una vista al rol Administrador. Para rutas de API (bajo
    /api/v1) responde JSON con 401/403; para rutas de vista redirige al login
    (sin sesión) o muestra la página 403 propia.
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        es_api = request.path.startswith('/api/')

        if not session.get('id_usuario'):
            if es_api:
                return jsonify({'success': False, 'error': 'No autenticado.'}), 401
            return redirect(url_for('seguridad.login'))

        if session.get('nombre_rol') != 'Administrador':
            if es_api:
                return jsonify({'success': False, 'error': 'Acceso restringido al rol Administrador.'}), 403
            # Vista: página 403 propia (ver app/rutas/errores.py)
            abort(403)

        return view_func(*args, **kwargs)
    return wrapper


def require_login(view_func):
    """
    Exige solamente que haya una sesión iniciada (cualquier rol). Para rutas
    de API (bajo /api/v1) responde JSON 401; para rutas de vista redirige al
    login.
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get('id_usuario'):
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'No autenticado.'}), 401
            return redirect(url_for('seguridad.login'))
        return view_func(*args, **kwargs)
    return wrapper


def require_permiso(ventana, accion):
    """
    Restringe una vista/endpoint a los roles que tengan <accion> otorgada
    sobre <ventana> en la matriz de Roles y Permisos (tabla `permisos`).
    Administrador siempre pasa (bypass, ver permisos_contexto.puede). Mismo
    criterio de respuesta que require_admin: 401/403 JSON en /api/, página 403
    en vistas.
    """
    def decorador(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            es_api = request.path.startswith('/api/')

            if not session.get('id_usuario'):
                if es_api:
                    return jsonify({'success': False, 'error': 'No autenticado.'}), 401
                return redirect(url_for('seguridad.login'))

            if not puede(ventana, accion):
                if es_api:
                    return jsonify({'success': False, 'error': 'No tiene permiso para realizar esta acción.'}), 403
                # Vista: página 403 propia; g.ventana_denegada le dice cuál intentó abrir
                g.ventana_denegada = ventana
                abort(403)

            return view_func(*args, **kwargs)
        return wrapper
    return decorador


def require_algun_permiso(*pares):
    """
    Como require_permiso, pero basta con tener CUALQUIERA de los pares (ventana, acción). Sirve para los lookups que varias ventanas
    comparten (ej. los diagnósticos de una consulta, que usan Tratamiento, Receta, Órdenes y Justificativo): no basta con tener sesión.
    """
    def decorador(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            es_api = request.path.startswith('/api/')

            if not session.get('id_usuario'):
                if es_api:
                    return jsonify({'success': False, 'error': 'No autenticado.'}), 401
                return redirect(url_for('seguridad.login'))

            if not any(puede(ventana, accion) for ventana, accion in pares):
                if es_api:
                    return jsonify({'success': False, 'error': 'No tiene permiso para realizar esta acción.'}), 403
                g.ventana_denegada = pares[0][0]
                abort(403)

            return view_func(*args, **kwargs)
        return wrapper
    return decorador
