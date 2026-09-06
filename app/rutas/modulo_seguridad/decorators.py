from functools import wraps

from flask import session, redirect, url_for, flash, jsonify, request


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
