from flask import g, session

from app.dao.modulo_seguridad.PermisoDao import PermisoDao


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


def puede(ventana, accion):
    """
    True si el rol de la sesión actual puede hacer <accion> en <ventana>.
    Administrador siempre puede (bypass), sin necesidad de filas en `permisos`.
    """
    if session.get('nombre_rol') == 'Administrador':
        return True
    return (ventana, accion) in _permisos_del_rol()
