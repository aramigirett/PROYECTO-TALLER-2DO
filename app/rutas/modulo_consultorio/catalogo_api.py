"""API REST de un referencial de Consultorio (Estándar de referenciales). Los 6 referenciales con borrado lógico comparten
esta fábrica: cada `<entidad>_api.py` declara su blueprint, su ventana de permisos y sus validaciones con `crear_api_catalogo()`.

Endpoints (todos bajo /api/v1, con la ruta que se le pase):
    GET    <ruta>                        lista los ACTIVOS (login: alimenta combos de otras pantallas); `?inactivos=1` exige 'ver'
    GET    <ruta>/<id>                   uno activo ('ver')
    POST   <ruta>                        alta ('nuevo')
    PUT    <ruta>/<id>                   modificación ('editar'); sin cambios no toca la base ni audita
    DELETE <ruta>/<id>                   anulación ('anular'); 409 si está en uso
    PATCH  <ruta>/<id>/reactivar         reactivación ('editar'); 409 si ya hay otro activo igual
Cada alta, modificación, baja y reactivación queda en `auditoria_cambios` (formato estructurado, con nombres y no IDs).
"""
from flask import Blueprint, current_app as app, jsonify, request

from app.dao.referenciales_consultorio.CatalogoDao import DUPLICADO, NO_EXISTE, YA_ACTIVO
from app.rutas.modulo_consultorio.utils import auditar, detalle_cambios, error_interno, respuesta_error
from app.rutas.modulo_seguridad.decorators import require_login, require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import puede


class Campo:
    """Un campo editable (además del texto único). `validar(data)` devuelve (valor, mensaje_de_error)."""

    def __init__(self, clave, etiqueta, validar):
        self.clave, self.etiqueta, self.validar = clave, etiqueta, validar


def crear_api_catalogo(*, blueprint, ventana, ruta, dao_cls, entidad, nombre, clave, etiqueta_clave, clave_frase, validar_clave, extras=(), femenino=False):
    """
    blueprint/ventana  nombre del Blueprint y ventana de permisos (menu_catalog)
    ruta               prefijo de URL, ej. '/tipos-insumo'
    entidad            valor de `auditoria_cambios.entidad` (debe estar en MODULO_POR_ENTIDAD)
    nombre             ej. 'tipo de insumo' (para los mensajes)
    clave              nombre JSON del texto único ('descripcion' / 'nombre_comercial'); etiqueta_clave: cómo se muestra
    clave_frase        ej. 'esa descripción' / 'ese nombre comercial' (mensaje de duplicado)
    validar_clave      función(data) -> (valor, error)
    extras             lista de Campo (precio, iva, presentación...)
    femenino           True si el nombre es femenino (ciudad, especialidad): ajusta artículos y participios de los mensajes
    """
    bp = Blueprint(blueprint, __name__)
    campos = [Campo(clave, etiqueta_clave, validar_clave), *extras]
    etiquetas = {c.clave: c.etiqueta for c in campos}
    Nombre = nombre[0].upper() + nombre[1:]
    art, Art, un, otro, sfx = ('la', 'La', 'una', 'otra', 'a') if femenino else ('el', 'El', 'un', 'otro', 'o')

    def pk_de(dao):
        return dao.PK

    def validar(data):
        """Valida todos los campos (el texto único primero). Devuelve (valores, None) o (None, respuesta_de_error)."""
        if not isinstance(data, dict):
            return None, respuesta_error('Los datos enviados no son válidos.', 400)
        valores = {}
        for c in campos:
            valor, error = c.validar(data)
            if error:
                return None, respuesta_error(error, 400, c.clave)
            valores[c.clave] = valor
        return valores, None

    def datos(dao, id_registro, valores):
        return {pk_de(dao): id_registro, **valores}

    def registrar(id_registro, accion, detalle):
        auditar(entidad, id_registro, accion, detalle)

    def duplicado_de(dao, valores, excluir_id=None):
        """(campo, frase) del duplicado entre los activos, o None. Un DAO con varios campos únicos (Consultorio: nombre y correo)
        declara `duplicado()` y devuelve 'nombre' o 'correo'; el resto compara solo el texto único."""
        if hasattr(dao, 'duplicado'):
            campo = dao.duplicado(valores, excluir_id)
            if campo:
                return ('correo', 'ese correo') if campo == 'correo' else (clave, clave_frase)
            return None
        return (clave, clave_frase) if dao.existeDuplicado(valores[clave], excluir_id) else None

    def a_tupla(valores):
        return tuple(valores[c.clave] for c in campos)

    # ---------- listar ----------
    @bp.route(ruta, methods=['GET'], endpoint=f'get_{blueprint}_lista')
    @require_login  # lookup: alimenta combos de otras pantallas
    def listar():
        incluir_inactivos = request.args.get('inactivos', '').lower() in ('1', 'true')
        if incluir_inactivos and not puede(ventana, 'ver'):
            return respuesta_error(f'No tiene permiso para ver los registros inactivos de {nombre}.', 403)
        try:
            return jsonify({'success': True, 'data': dao_cls().listar(incluir_inactivos), 'error': None}), 200
        except Exception as e:
            app.logger.error(f"Error al listar {nombre}: {str(e)}")
            return error_interno()

    # ---------- uno ----------
    @bp.route(f'{ruta}/<int:id_registro>', methods=['GET'], endpoint=f'get_{blueprint}')
    @require_permiso(ventana, 'ver')
    def uno(id_registro):
        try:
            r = dao_cls().obtener(id_registro)
            if r:
                return jsonify({'success': True, 'data': r, 'error': None}), 200
            return respuesta_error(f'No se encontró {art} {nombre} con el ID proporcionado.', 404)
        except Exception as e:
            app.logger.error(f"Error al obtener {nombre}: {str(e)}")
            return error_interno()

    # ---------- alta ----------
    @bp.route(ruta, methods=['POST'], endpoint=f'add_{blueprint}')
    @require_permiso(ventana, 'nuevo')
    def alta():
        valores, error = validar(request.get_json(silent=True))
        if error:
            return error
        dao = dao_cls()
        try:
            dup = duplicado_de(dao, valores)
            if dup:
                return respuesta_error(f'Ya existe {un} {nombre} activ{sfx} con {dup[1]}.', 400, dup[0])
            nuevo_id = dao.guardar(*a_tupla(valores))
            if nuevo_id == DUPLICADO:
                return respuesta_error(f'Ya existe {un} {nombre} activ{sfx} con {clave_frase}.', 400, clave)
            if nuevo_id:
                registrar(nuevo_id, 'ALTA', detalle_cambios({}, valores, etiquetas))
                return jsonify({'success': True, 'data': datos(dao, nuevo_id, valores),
                                'mensaje': f'{Nombre} "{valores[clave]}" agregad{sfx} correctamente.', 'error': None}), 201
            return respuesta_error(f'No se pudo guardar {art} {nombre}. Consulte con el administrador.', 500)
        except Exception as e:
            app.logger.error(f"Error al agregar {nombre}: {str(e)}")
            return error_interno()

    # ---------- modificación ----------
    @bp.route(f'{ruta}/<int:id_registro>', methods=['PUT'], endpoint=f'update_{blueprint}')
    @require_permiso(ventana, 'editar')
    def modificar(id_registro):
        valores, error = validar(request.get_json(silent=True))
        if error:
            return error
        dao = dao_cls()
        try:
            anterior = dao.obtener(id_registro)
            if not anterior:
                return respuesta_error(f'No se encontró {art} {nombre} con el ID proporcionado.', 404)
            if all(anterior.get(c.clave) == valores[c.clave] for c in campos):
                # Sin cambios: no se toca la base ni se audita.
                return jsonify({'success': True, 'data': datos(dao, id_registro, valores),
                                'mensaje': f'{Nombre} "{valores[clave]}" sin cambios.', 'error': None}), 200
            dup = duplicado_de(dao, valores, id_registro)
            if dup:
                return respuesta_error(f'Ya existe {otro} {nombre} activ{sfx} con {dup[1]}.', 400, dup[0])
            resultado = dao.actualizar(id_registro, *a_tupla(valores))
            if resultado == DUPLICADO:
                return respuesta_error(f'Ya existe {otro} {nombre} activ{sfx} con {clave_frase}.', 400, clave)
            if resultado:
                registrar(id_registro, 'MODIFICACION', detalle_cambios(anterior, valores, etiquetas))
                return jsonify({'success': True, 'data': datos(dao, id_registro, valores),
                                'mensaje': f'{Nombre} "{valores[clave]}" actualizad{sfx} correctamente.', 'error': None}), 200
            return respuesta_error(f'No se pudo actualizar {art} {nombre}.', 404)
        except Exception as e:
            app.logger.error(f"Error al actualizar {nombre}: {str(e)}")
            return error_interno()

    # ---------- anulación ----------
    @bp.route(f'{ruta}/<int:id_registro>', methods=['DELETE'], endpoint=f'delete_{blueprint}')
    @require_permiso(ventana, 'anular')
    def anular(id_registro):
        dao = dao_cls()
        try:
            registro = dao.obtener(id_registro)
            resultado = dao.anular(id_registro)
            if isinstance(resultado, tuple):  # ("EN_USO", motivo)
                return respuesta_error(resultado[1], 409)
            if resultado:
                texto = registro[clave] if registro else 'seleccionado'
                registrar(id_registro, 'BAJA', f'{etiqueta_clave}: {texto}')
                return jsonify({'success': True, 'mensaje': f'{Nombre} "{texto}" anulad{sfx} correctamente.', 'error': None}), 200
            return respuesta_error(f'No se encontró {art} {nombre} con el ID proporcionado.', 404)
        except Exception as e:
            app.logger.error(f"Error al anular {nombre}: {str(e)}")
            return error_interno()

    # ---------- reactivación (permiso: el mismo de editar) ----------
    @bp.route(f'{ruta}/<int:id_registro>/reactivar', methods=['PATCH'], endpoint=f'reactivar_{blueprint}')
    @require_permiso(ventana, 'editar')
    def reactivar(id_registro):
        dao = dao_cls()
        try:
            resultado = dao.reactivar(id_registro)
            if resultado == NO_EXISTE:
                return respuesta_error(f'No se encontró {art} {nombre} con el ID proporcionado.', 404)
            if resultado == YA_ACTIVO:
                return respuesta_error(f'{Art} {nombre} ya está activ{sfx}.', 409)
            if resultado == DUPLICADO:
                return respuesta_error(f'No se puede reactivar: ya existe {un} {nombre} activ{sfx} con {clave_frase}.', 409)
            if resultado:
                obj = dao.obtener(id_registro)
                registrar(id_registro, 'REACTIVACION', f'{etiqueta_clave}: {obj[clave]}')
                return jsonify({'success': True, 'data': obj, 'mensaje': f'{Nombre} "{obj[clave]}" reactivad{sfx} correctamente.',
                                'error': None}), 200
            return respuesta_error(f'No se pudo reactivar {art} {nombre}. Consulte con el administrador.', 500)
        except Exception as e:
            app.logger.error(f"Error al reactivar {nombre}: {str(e)}")
            return error_interno()

    return bp
