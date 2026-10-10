from functools import wraps

from flask import session, redirect, url_for, flash, jsonify, request

from app.rutas.modulo_seguridad.permisos_contexto import puede


def require_admin(view_func):
    """
    Restringe una vista al rol Administrador. Para rutas de API (bajo
    /api/v1) responde JSON con 401/403; para rutas de vista redirige.
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
            flash('Acceso restringido al rol Administrador.', 'danger')
            return redirect(url_for('vista.vistaIndex'))

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
    criterio de respuesta que require_admin: 401/403 JSON en /api/, redirect
    con flash en vistas.
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
                flash('No tiene permiso para acceder a esta pantalla.', 'danger')
                return redirect(url_for('vista.vistaIndex'))

            return view_func(*args, **kwargs)
        return wrapper
    return decorador
