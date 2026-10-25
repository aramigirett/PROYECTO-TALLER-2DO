"""API REST de una persona de Agendamiento (Paciente, Médico, Funcionario) con borrado lógico (Estándar de referenciales aplicado a datos maestros).
Las tres comparten esta fábrica: cada `<persona>_api.py` declara su blueprint, su ventana de permisos y su validación con `crear_api_persona()`.

Endpoints (bajo /api/v1, con la ruta que se le pase):
    GET    <ruta>                        lista los ACTIVOS (login: alimenta los buscadores de otras pantallas); `?inactivos=1` exige 'ver'.
                                         Quien no tiene 'ver' en la ventana recibe solo lo mínimo para elegir a la persona (sin datos de contacto)
    GET    <ruta>/<id>                   una persona activa (misma regla)
    POST   <ruta>                        alta ('nuevo'); la fecha de alta la pone el servidor
    PUT    <ruta>/<id>                   modificación ('editar'); sin cambios no toca la base ni audita
    DELETE <ruta>/<id>                   anulación ('anular'); 409 si tiene trabajo en curso o un usuario activo
    PATCH  <ruta>/<id>/reactivar         reactivación ('anular': quien puede anular puede reactivar); 409 si ya hay otra persona activa igual
Auditoría: solo quién, cuándo, nombre, cédula y referenciales (nombres, no IDs). Los datos de contacto (teléfono, dirección, correo,
nacimiento) nunca se guardan; si cambian queda el aviso "Datos de contacto: modificados".
"""
from flask import Blueprint, current_app as app, jsonify, request, session

from app.dao.modulo_seguridad.AuditoriaDao import AuditoriaDao
from app.dao.referenciales_agendamiento.persona_dao import DUPLICADO, INVALIDO, NO_EXISTE, YA_ACTIVO
from app.rutas.modulo_agendamiento.utils import auditar, detalle_cambios, error_interno, respuesta_error
from app.rutas.modulo_seguridad.decorators import require_login, require_permiso
from app.rutas.modulo_seguridad.permisos_contexto import puede

CONTACTO = ('fecha_nacimiento', 'telefono', 'telefono_emergencia', 'direccion', 'correo')


def crear_api_persona(*, blueprint, ventana, ruta, dao_cls, entidad, nombre, articulo, doc, validar, auditados, genero='o'):
    """
    ventana       ventana de permisos (menu_catalog)
    ruta          prefijo de URL, ej. '/pacientes'
    entidad       valor de `auditoria_cambios.entidad` (debe estar en MODULO_POR_ENTIDAD)
    nombre        ej. 'paciente'; articulo: 'el'; genero: 'o' / 'a' (para "anulado")
    doc           clave JSON y columna de la cédula ('cedula_entidad' / 'cedula')
    validar       función(data) -> (valores, None) o (None, (mensaje, campo))
    auditados     {clave de la fila: etiqueta} de lo que se audita con su valor (nombres, cédula y referenciales)
    """
    bp = Blueprint(blueprint, __name__)
    Nombre = nombre[0].upper() + nombre[1:]
    pk = dao_cls.PK
    cambia_cedula_login = bool(dao_cls.USUARIO)

    def para_auditar(fila):
        return {k: fila.get(k) for k in auditados}

    def con_contacto(anterior, nuevo):
        """Auditoría de una modificación: lo auditado que cambió + el aviso de contacto si cambió algún dato de contacto."""
        ant, nue = para_auditar(anterior), para_auditar(nuevo)
        etiquetas = dict(auditados)
        hubo = any(anterior.get(c) != nuevo.get(c) for c in CONTACTO if c in nuevo)
        ant['contacto'], nue['contacto'] = ('anteriores', 'modificados') if hubo else ('sin cambios', 'sin cambios')
        etiquetas['contacto'] = 'Datos de contacto'
        return detalle_cambios(ant, nue, etiquetas)

    def nombre_de(fila):
        return f"{fila['nombre']} {fila['apellido']}"

    def valores_a_fila(valores):
        """Los valores validados con la forma de una fila (fechas como texto) para comparar con lo guardado."""
        return {k: (str(v) if k == 'fecha_nacimiento' and v else v) for k, v in valores.items()}

    def conflicto(res):
        """Respuesta para ("DUPLICADO", campo, frase) o ("INVALIDO", columna, mensaje)."""
        if res[0] == DUPLICADO:
            return respuesta_error(f'Ya existe un {nombre} activ{genero} con {res[2]}.', 409, res[1])
        return respuesta_error(res[2], 400, res[1])

    def lectura(fila_o_lista):
        """Quien no tiene 'ver' en la ventana solo recibe lo mínimo para elegir (los buscadores de otras pantallas)."""
        if puede(ventana, 'ver'):
            return fila_o_lista
        dao = dao_cls()
        return [dao.minimo(f) for f in fila_o_lista] if isinstance(fila_o_lista, list) else dao.minimo(fila_o_lista)

    # ---------- listar ----------
    @bp.route(ruta, methods=['GET'], endpoint=f'get_{blueprint}_lista')
    @require_login
    def listar():
        incluir_inactivos = request.args.get('inactivos', '').lower() in ('1', 'true')
        if incluir_inactivos and not puede(ventana, 'ver'):
            return respuesta_error(f'No tiene permiso para ver los registros inactivos de {nombre}.', 403)
        try:
            return jsonify({'success': True, 'data': lectura(dao_cls().listar(incluir_inactivos)), 'error': None}), 200
        except Exception as e:
            app.logger.error(f"Error al listar {nombre}: {str(e)}")
            return error_interno()

    # ---------- uno ----------
    @bp.route(f'{ruta}/<int:id_registro>', methods=['GET'], endpoint=f'get_{blueprint}')
    @require_login
    def uno(id_registro):
        try:
            r = dao_cls().obtener(id_registro)
            if r:
                return jsonify({'success': True, 'data': lectura(r), 'error': None}), 200
            return respuesta_error(f'No se encontró {articulo} {nombre} con el ID proporcionado.', 404)
        except Exception as e:
            app.logger.error(f"Error al obtener {nombre}: {str(e)}")
            return error_interno()

    def _validar():
        valores, error = validar(request.get_json(silent=True))
        if error:
            return None, respuesta_error(error[0], 400, error[1])
        return valores, None

    # ---------- alta ----------
    @bp.route(ruta, methods=['POST'], endpoint=f'add_{blueprint}')
    @require_permiso(ventana, 'nuevo')
    def alta():
        valores, error = _validar()
        if error:
            return error
        dao = dao_cls()
        try:
            if cambia_cedula_login:
                donde = dao.cedulaUsadaPorOtro(valores[doc])
                if donde:
                    return respuesta_error(f"Esa cédula ya pertenece a otro {'funcionario' if donde == 'funcionario' else 'médico'}. "
                                           "La cédula es el CI/RUC de login y no puede repetirse.", 409, doc)
            dup = dao.duplicado(valores)
            if dup:
                return conflicto((DUPLICADO, *dup))
            nuevo_id = dao.guardar(valores)
            if isinstance(nuevo_id, tuple):
                return conflicto(nuevo_id)
            if nuevo_id:
                fila = dao.obtener(nuevo_id)
                auditar(entidad, nuevo_id, 'ALTA', detalle_cambios({}, para_auditar(fila), auditados))
                return jsonify({'success': True, 'data': {pk: nuevo_id},
                                'mensaje': f'{Nombre} "{nombre_de(fila)}" agregad{genero} correctamente.', 'error': None}), 201
            return respuesta_error(f'No se pudo guardar {articulo} {nombre}. Consulte con el administrador.', 500)
        except Exception as e:
            app.logger.error(f"Error al agregar {nombre}: {str(e)}")
            return error_interno()

    # ---------- modificación ----------
    @bp.route(f'{ruta}/<int:id_registro>', methods=['PUT'], endpoint=f'update_{blueprint}')
    @require_permiso(ventana, 'editar')
    def modificar(id_registro):
        body = request.get_json(silent=True)
        valores, error = _validar()
        if error:
            return error
        dao = dao_cls()
        try:
            anterior = dao.obtener(id_registro)
            if not anterior:
                return respuesta_error(f'No se encontró {articulo} {nombre} con el ID proporcionado.', 404)
            if cambia_cedula_login:
                donde = dao.cedulaUsadaPorOtro(valores[doc], excluir_funcionario=id_registro if dao.TABLA == 'funcionario' else None,
                                               excluir_medico=id_registro if dao.TABLA == 'medico' else None)
                if donde:
                    return respuesta_error(f"Esa cédula ya pertenece a otro {'funcionario' if donde == 'funcionario' else 'médico'}. "
                                           "La cédula es el CI/RUC de login y no puede repetirse.", 409, doc)
            nuevo_vals = valores_a_fila(valores)
            if all(anterior.get(c) == nuevo_vals.get(c) for c in dao.CAMPOS):
                return jsonify({'success': True, 'data': {pk: id_registro},
                                'mensaje': f'{Nombre} "{nombre_de(anterior)}" sin cambios.', 'error': None}), 200
            dup = dao.duplicado(valores, excluir_id=id_registro)
            if dup:
                return conflicto((DUPLICADO, *dup))
            # Si la persona tiene usuario, su cédula es su login: cambiarla exige confirmación
            cedula_anterior = (anterior[doc] or '').strip()
            id_usuario = dao.getUsuarioVinculado(id_registro) if cambia_cedula_login else None
            cambia_login = bool(id_usuario) and cedula_anterior != valores[doc]
            if cambia_login and not (body or {}).get('confirmar_cambio_cedula'):
                return jsonify({'success': False, 'requiere_confirmacion': True, 'cedula_anterior': cedula_anterior,
                                'cedula_nueva': valores[doc],
                                'error': 'Cambiar la cédula cambia el CI/RUC con el que esta persona inicia sesión.'}), 409
            resultado = dao.actualizar(id_registro, valores)
            if isinstance(resultado, tuple):
                return conflicto(resultado)
            if resultado:
                nuevo = dao.obtener(id_registro)
                if cambia_login:
                    AuditoriaDao().registrar_cambio_cedula(id_usuario, cedula_anterior, valores[doc], request.remote_addr, session.get('id_usuario'))
                detalle = con_contacto(anterior, nuevo)
                if detalle:
                    auditar(entidad, id_registro, 'MODIFICACION', detalle)
                return jsonify({'success': True, 'data': {pk: id_registro},
                                'mensaje': f'{Nombre} "{nombre_de(nuevo)}" actualizad{genero} correctamente.', 'error': None}), 200
            return respuesta_error(f'No se pudo actualizar {articulo} {nombre}.', 404)
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
                auditar(entidad, id_registro, 'BAJA', detalle_cambios({}, para_auditar(registro), auditados))
                return jsonify({'success': True, 'mensaje': f'{Nombre} "{nombre_de(registro)}" anulad{genero} correctamente.', 'error': None}), 200
            return respuesta_error(f'No se encontró {articulo} {nombre} con el ID proporcionado.', 404)
        except Exception as e:
            app.logger.error(f"Error al anular {nombre}: {str(e)}")
            return error_interno()

    # ---------- reactivación ----------
    @bp.route(f'{ruta}/<int:id_registro>/reactivar', methods=['PATCH'], endpoint=f'reactivar_{blueprint}')
    @require_permiso(ventana, 'anular')
    def reactivar(id_registro):
        dao = dao_cls()
        try:
            resultado = dao.reactivar(id_registro)
            if resultado == NO_EXISTE:
                return respuesta_error(f'No se encontró {articulo} {nombre} con el ID proporcionado.', 404)
            if resultado == YA_ACTIVO:
                return respuesta_error(f'{articulo.capitalize()} {nombre} ya está activ{genero}.', 409)
            if isinstance(resultado, tuple):
                if resultado[0] == DUPLICADO:
                    return respuesta_error(f'No se puede reactivar: ya existe un {nombre} activ{genero} con {resultado[2]}.', 409, resultado[1])
                return respuesta_error('No se puede reactivar: ' + resultado[2][0].lower() + resultado[2][1:], 409, resultado[1])
            if resultado:
                fila = dao.obtener(id_registro)
                auditar(entidad, id_registro, 'REACTIVACION', detalle_cambios({}, para_auditar(fila), auditados))
                return jsonify({'success': True, 'data': lectura(fila),
                                'mensaje': f'{Nombre} "{nombre_de(fila)}" reactivad{genero} correctamente.', 'error': None}), 200
            return respuesta_error(f'No se pudo reactivar {articulo} {nombre}. Consulte con el administrador.', 500)
        except Exception as e:
            app.logger.error(f"Error al reactivar {nombre}: {str(e)}")
            return error_interno()

    return bp
