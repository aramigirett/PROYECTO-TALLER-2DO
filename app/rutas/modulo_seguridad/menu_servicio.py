"""
Servicio del menú: lo que el sistema muestra y permite sale de la tabla `menu` (Mantener Menú), no del código.

  - menu_visible()       módulos y ventanas del menú lateral: solo lo ACTIVO sobre lo que el rol de la sesión tiene permiso "ver", ordenado por módulo y orden
  - buscar()             el buscador general (mismas reglas)
  - catalogo_permisos()  las filas de la matriz de Roles y Permisos (ventanas activas que no son exclusivas del Administrador)
  - ventanas_solo_admin(), acciones_de(), etiqueta_ventana()

La tabla se lee UNA vez por request (flask.g). Si la base no responde (p. ej. al dibujar una página de error) se cae al registro del código (menu_catalog) para
que un fallo nunca encadene otro. Las acciones que soporta cada ventana las define el código (los @require_permiso): una ventana creada desde la pantalla,
que el registro no conoce, solo tiene "ver".
"""
import unicodedata

from flask import g, current_app as app

from app.rutas.modulo_seguridad.menu_catalog import CATALOGO_MENU, MODULOS

_ACCIONES_CODIGO = {i['ventana']: list(i['acciones']) for i in CATALOGO_MENU}


def _desde_el_codigo():
    """Las filas activas tal como las dejaría la semilla (solo si no se puede leer la tabla)."""
    filas, orden = [], {}
    for n, m in enumerate(MODULOS, 1):
        filas.append({'id_menu': -n, 'id_menu_padre': None, 'clave': None, 'descripcion': m['modulo'], 'ruta': None, 'icono': m['icono'], 'orden': n, 'activo': True,
                      'visible_en_menu': True, 'solo_admin': False, 'protegida': False, 'modulo': m['modulo'], 'tipo': 'modulo'})
    ids = {f['descripcion']: f['id_menu'] for f in filas}
    for it in CATALOGO_MENU:
        orden[it['modulo']] = orden.get(it['modulo'], 0) + 10
        filas.append({'id_menu': 1000 + len(filas), 'id_menu_padre': ids[it['modulo']], 'clave': it['ventana'], 'descripcion': it['etiqueta'], 'ruta': it['endpoint'],
                      'icono': it['icono'], 'orden': orden[it['modulo']], 'activo': True, 'visible_en_menu': it.get('en_menu', True),
                      'solo_admin': bool(it.get('solo_admin')), 'protegida': False, 'modulo': it['modulo'], 'tipo': 'ventana'})
    return filas


def filas_activas():
    """Módulos y ventanas ACTIVOS, ordenados (una consulta por request)."""
    if not hasattr(g, 'menu_filas_activas'):
        try:
            from app.dao.modulo_seguridad.MenuDao import MenuDao
            g.menu_filas_activas = MenuDao().getFilas(incluir_inactivos=False)
        except Exception as e:
            app.logger.error(f"No se pudo leer la tabla menu; se usa el registro del código: {str(e)}")
            g.menu_filas_activas = _desde_el_codigo()
    return g.menu_filas_activas


def _ventanas_activas():
    modulos_activos = {f['id_menu'] for f in filas_activas() if f['tipo'] == 'modulo'}
    return [f for f in filas_activas() if f['tipo'] == 'ventana' and f['id_menu_padre'] in modulos_activos]


def ventanas_solo_admin():
    if not hasattr(g, 'menu_solo_admin'):
        g.menu_solo_admin = {f['clave'] for f in _ventanas_activas() if f['solo_admin']}
    return g.menu_solo_admin


def acciones_de(clave):
    """Acciones que consultan los endpoints de la ventana (definidas en el código); una ventana nueva solo tiene 'ver'."""
    return list(_ACCIONES_CODIGO.get(clave, ['ver']))


def etiqueta_ventana(clave):
    f = next((v for v in _ventanas_activas() if v['clave'] == clave), None)
    return f['descripcion'] if f else next((i['etiqueta'] for i in CATALOGO_MENU if i['ventana'] == clave), None)


def menu_visible():
    """[{modulo, icono, entradas: [{etiqueta, endpoint, icono, modulo, ventana}]}] para el rol de la sesión (solo ventanas activas con permiso 'ver')."""
    from app.rutas.modulo_seguridad.permisos_contexto import puede
    filas = filas_activas()
    rutas = app.view_functions   # una ruta que ya no existe en el código no puede romper todas las páginas
    resultado = []
    for m in (f for f in filas if f['tipo'] == 'modulo'):
        entradas = [{'etiqueta': v['descripcion'], 'endpoint': v['ruta'], 'icono': v['icono'], 'modulo': m['descripcion'], 'ventana': v['clave']}
                    for v in filas if v['id_menu_padre'] == m['id_menu'] and v['visible_en_menu'] and v['ruta'] in rutas and puede(v['clave'], 'ver')]
        if entradas:
            resultado.append({'modulo': m['descripcion'], 'icono': m['icono'], 'entradas': entradas})
    return resultado


def _normalizar(texto):
    texto = unicodedata.normalize('NFKD', (texto or '').strip().lower())
    return ''.join(c for c in texto if not unicodedata.combining(c))


def buscar(q):
    """Entradas del menú visibles para el rol cuya descripción contiene `q` (sin distinguir tildes ni mayúsculas)."""
    q = _normalizar(q)
    if not q:
        return []
    return [dict(e, modulo=m['modulo']) for m in menu_visible() for e in m['entradas'] if q in _normalizar(e['etiqueta'])]


def catalogo_permisos():
    """[{modulo, ventanas: [{ventana, etiqueta, acciones}]}] para la matriz: ventanas activas, no exclusivas del Administrador."""
    filas = filas_activas()
    resultado = []
    for m in (f for f in filas if f['tipo'] == 'modulo'):
        ventanas = [{'ventana': v['clave'], 'etiqueta': v['descripcion'], 'acciones': acciones_de(v['clave'])}
                    for v in _ventanas_activas() if v['id_menu_padre'] == m['id_menu'] and not v['solo_admin']]
        if ventanas:
            resultado.append({'modulo': m['descripcion'], 'ventanas': ventanas})
    return resultado


def ventana_para_permisos(clave):
    """La ventana activa y delegable (no exclusiva del Administrador) con esa clave, o None."""
    return next((v for v in _ventanas_activas() if v['clave'] == clave), None)
