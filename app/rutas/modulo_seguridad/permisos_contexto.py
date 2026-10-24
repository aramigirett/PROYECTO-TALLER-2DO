from flask import g, session

from app.dao.modulo_seguridad.PermisoDao import PermisoDao
from app.rutas.modulo_seguridad.menu_catalog import VENTANAS_SOLO_ADMIN


def _permisos_del_rol():
    """
    Carga UNA sola vez por request el set de (ventana, accion) que tiene
    otorgado el rol de la sesión actual, cacheado en flask.g (no en la
    sesión, para que un cambio en la matriz de permisos aplique al toque).
    """
    if not hasattr(g, 'permisos_rol'):
        id_rol = session.get('id_rol')
        g.permisos_rol = PermisoDao().getPermisosDeRol(id_rol) if id_rol else set()
    return g.permisos_rol


def id_funcionario_sesion():
    """
    id_funcionario vinculado al usuario de la sesión, o None si el usuario es
    un Médico (vinculado a medico, no a funcionario) o no hay sesión. Se lee
    de la base en cada request (no de la sesión) y se cachea en flask.g.
    """
    if not hasattr(g, 'id_funcionario_sesion'):
        from app.dao.modulo_seguridad.UsuarioDao import UsuarioDao
        id_usuario = session.get('id_usuario')
        usuario = UsuarioDao().get_by_id(id_usuario) if id_usuario else None
        g.id_funcionario_sesion = usuario['id_funcionario'] if usuario else None
    return g.id_funcionario_sesion


def puede(ventana, accion):
    """
    True si el rol de la sesión actual puede hacer <accion> en <ventana>.
    Administrador siempre puede (bypass), sin necesidad de filas en `permisos`.
    """
    if session.get('nombre_rol') == 'Administrador':
        return True
    if ventana in VENTANAS_SOLO_ADMIN:
        return False   # ventana exclusiva del Administrador (ver menu_catalog.solo_admin)
    return (ventana, accion) in _permisos_del_rol()
