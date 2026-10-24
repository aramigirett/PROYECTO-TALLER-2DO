from flask import Blueprint, request, jsonify, current_app as app
from app.dao.modulo_facturacion.cliente.ClienteDao import (
    ClienteDao, DUPLICADO_CI_RUC, DUPLICADO_PACIENTE, PACIENTE_INVALIDO, NO_EXISTE, YA_ACTIVO,
    MSG_MOD_CONSUMIDOR_FINAL)
from app.rutas.modulo_facturacion.utils import (
    validar_nombre, validar_ci_ruc, validar_telefono_opcional, validar_correo_opcional, entero_id,
    detalle_cambios, respuesta_error, auditar as _auditar, error_interno)
from app.rutas.modulo_seguridad.decorators import require_permiso, require_login
from app.rutas.modulo_seguridad.permisos_contexto import puede

clienteapi = Blueprint('clienteapi', __name__)

ENTIDAD = 'cliente'
ETIQUETAS = {'nombre': 'Nombre', 'apellido': 'Apellido', 'ci_ruc': 'CI/RUC', 'telefono': 'Teléfono', 'correo': 'Correo'}
MSG_DUP_CI_RUC = 'Ya existe un cliente con esa CI/RUC.'
MSG_DUP_PACIENTE = 'Ese paciente ya está registrado como cliente.'
MSG_PACIENTE = 'El paciente seleccionado no existe.'


def auditar(id_registro, accion, detalle):
    _auditar(ENTIDAD, id_registro, accion, detalle)


def validar_cliente(data):
    """Valida los campos propios del cliente (sin id_paciente). Devuelve (datos, error, campo)."""
    data = data if isinstance(data, dict) else {}
    nombre, error = validar_nombre(data.get('nombre'), 'nombre', obligatorio=True)
    if error:
        return None, error, 'nombre'
    apellido, error = validar_nombre(data.get('apellido'), 'apellido', obligatorio=False)
    if error:
        return None, error, 'apellido'
    ci_ruc, error = validar_ci_ruc(data.get('ci_ruc'))
    if error:
        return None, error, 'ci_ruc'
    telefono, error = validar_telefono_opcional(data.get('telefono'))
    if error:
        return None, error, 'telefono'
    correo, error = validar_correo_opcional(data.get('correo'))
    if error:
        return None, error, 'correo'
    return {'nombre': nombre, 'apellido': apellido, 'ci_ruc': ci_ruc, 'telefono': telefono, 'correo': correo}, None, None


def _para_detalle(d):
    """Valores legibles para la auditoría (los opcionales vacíos no se muestran como None)."""
    return {k: d.get(k) or '' for k in ETIQUETAS}


def respuesta_por_codigo(codigo):
    """Traduce los códigos de error del DAO a respuesta HTTP. None si no es un código de error."""
    if codigo == DUPLICADO_CI_RUC:
        return respuesta_error(MSG_DUP_CI_RUC, 400, 'ci_ruc')
    if codigo == DUPLICADO_PACIENTE:
        return respuesta_error(MSG_DUP_PACIENTE, 400, 'id_paciente')
    if codigo == PACIENTE_INVALIDO:
        return respuesta_error(MSG_PACIENTE, 400, 'id_paciente')
    return None


# -------------------------
# Trae los clientes. Por defecto solo activos; ?inactivos=1 incluye los anulados (requiere 'ver').
# -------------------------
@clienteapi.route('/clientes', methods=['GET'])
@require_login  # lookup: alimenta combos de otras pantallas (Pedidos de venta, Ventas)
def getClientes():
    incluir_inactivos = request.args.get('inactivos', '').lower() in ('1', 'true')
    if incluir_inactivos and not puede('cliente', 'ver'):
        return respuesta_error('No tiene permiso para ver los clientes inactivos.', 403)
    try:
        return jsonify({'success': True, 'data': ClienteDao().getClientes(incluir_inactivos), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al obtener clientes: {str(e)}")
        return error_interno()


# -------------------------
# Buscador de pacientes para el alta ("¿El cliente ya es paciente?"). Expone datos personales: exige 'nuevo'.
# -------------------------
@clienteapi.route('/clientes/pacientes', methods=['GET'])
@require_permiso('cliente', 'nuevo')
def buscarPacientes():
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return respuesta_error('Ingrese al menos 2 caracteres para buscar.', 400)
    try:
        return jsonify({'success': True, 'data': ClienteDao().buscarPacientes(q), 'error': None}), 200
    except Exception as e:
        app.logger.error(f"Error al buscar pacientes: {str(e)}")
        return error_interno()


# -------------------------
# Trae un cliente activo por ID
# -------------------------
@clienteapi.route('/clientes/<int:id_cliente>', methods=['GET'])
@require_permiso('cliente', 'ver')
def getCliente(id_cliente):
    try:
        cliente = ClienteDao().getClienteById(id_cliente)
        if cliente:
            return jsonify({'success': True, 'data': cliente, 'error': None}), 200
        return respuesta_error('No se encontró el cliente con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al obtener cliente: {str(e)}")
        return error_interno()


# -------------------------
# Agrega un cliente (manual, o desde un paciente si viene id_paciente)
# -------------------------
@clienteapi.route('/clientes', methods=['POST'])
@require_permiso('cliente', 'nuevo')
def addCliente():
    body = request.get_json(silent=True)
    datos, error, campo = validar_cliente(body)
    if error:
        return respuesta_error(error, 400, campo)

    id_paciente = None
    crudo = body.get('id_paciente') if isinstance(body, dict) else None
    if crudo not in (None, ''):
        id_paciente = entero_id(crudo)
        if id_paciente is None:
            return respuesta_error('El paciente seleccionado no es válido.', 400, 'id_paciente')

    dao = ClienteDao()
    try:
        # El paciente primero: es el mensaje más específico si coinciden los dos.
        if id_paciente is not None and dao.existePaciente(id_paciente):
            return respuesta_error(MSG_DUP_PACIENTE, 400, 'id_paciente')
        if dao.existeCiRuc(datos['ci_ruc']):
            return respuesta_error(MSG_DUP_CI_RUC, 400, 'ci_ruc')

        nuevo_id = dao.guardarCliente(id_paciente, **datos)
        rechazo = respuesta_por_codigo(nuevo_id)
        if rechazo:
            return rechazo
        if nuevo_id:
            detalle = detalle_cambios({}, _para_detalle(datos), ETIQUETAS) + \
                ('; Paciente: Sí' if id_paciente is not None else '; Paciente: No')
            auditar(nuevo_id, 'ALTA', detalle)
            return jsonify({
                'success': True, 'data': dao.getClienteById(nuevo_id),
                'mensaje': f'Cliente "{_nombre_completo(datos)}" agregado correctamente.', 'error': None
            }), 201
        return respuesta_error('No se pudo guardar el cliente. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al agregar cliente: {str(e)}")
        return error_interno()


def _nombre_completo(c):
    return f'{c["nombre"]} {c["apellido"]}'.strip() if c.get('apellido') else c['nombre']


# -------------------------
# Actualiza un cliente activo (id_paciente no se puede cambiar; el consumidor final no se modifica)
# -------------------------
@clienteapi.route('/clientes/<int:id_cliente>', methods=['PUT'])
@require_permiso('cliente', 'editar')
def updateCliente(id_cliente):
    body = request.get_json(silent=True)
    dao = ClienteDao()
    try:
        anterior = dao.getClienteById(id_cliente)
        if not anterior:
            return respuesta_error('No se encontró el cliente con el ID proporcionado.', 404)
        if anterior['es_consumidor_final']:
            return respuesta_error(MSG_MOD_CONSUMIDOR_FINAL, 409)

        datos, error, campo = validar_cliente(body)
        if error:
            return respuesta_error(error, 400, campo)

        crudo = body.get('id_paciente') if isinstance(body, dict) else None
        if crudo not in (None, '') and entero_id(crudo) != anterior['id_paciente']:
            return respuesta_error('El paciente vinculado no se puede cambiar.', 400, 'id_paciente')

        detalle = detalle_cambios(_para_detalle(anterior), _para_detalle(datos), ETIQUETAS)
        if not detalle:
            # Sin cambios: no se toca la BD ni se audita.
            return jsonify({
                'success': True, 'data': anterior,
                'mensaje': f'Cliente "{_nombre_completo(datos)}" sin cambios.', 'error': None
            }), 200

        if dao.existeCiRuc(datos['ci_ruc'], excluir_id=id_cliente):
            return respuesta_error(MSG_DUP_CI_RUC, 400, 'ci_ruc')

        resultado = dao.updateCliente(id_cliente, **datos)
        if isinstance(resultado, tuple):  # ("EN_USO", motivo): consumidor final
            return respuesta_error(resultado[1], 409)
        rechazo = respuesta_por_codigo(resultado)
        if rechazo:
            return rechazo
        if resultado:
            auditar(id_cliente, 'MODIFICACION', detalle)
            return jsonify({
                'success': True, 'data': dao.getClienteById(id_cliente),
                'mensaje': f'Cliente "{_nombre_completo(datos)}" actualizado correctamente.', 'error': None
            }), 200
        return respuesta_error('No se pudo actualizar el cliente.', 404)
    except Exception as e:
        app.logger.error(f"Error al actualizar cliente: {str(e)}")
        return error_interno()


# -------------------------
# Anula (baja lógica) un cliente
# -------------------------
@clienteapi.route('/clientes/<int:id_cliente>', methods=['DELETE'])
@require_permiso('cliente', 'anular')
def deleteCliente(id_cliente):
    dao = ClienteDao()
    try:
        registro = dao.getClienteById(id_cliente)
        resultado = dao.deleteCliente(id_cliente)
        if isinstance(resultado, tuple):  # ("EN_USO", motivo)
            return respuesta_error(resultado[1], 409)
        if resultado:
            nombre = _nombre_completo(registro) if registro else 'seleccionado'
            auditar(id_cliente, 'BAJA', f'Nombre: {nombre}; CI/RUC: {registro["ci_ruc"] if registro else ""}')
            return jsonify({'success': True, 'mensaje': f'Cliente "{nombre}" anulado correctamente.', 'error': None}), 200
        return respuesta_error('No se encontró el cliente con el ID proporcionado.', 404)
    except Exception as e:
        app.logger.error(f"Error al anular cliente: {str(e)}")
        return error_interno()


# -------------------------
# Reactiva un cliente anulado (permiso: el mismo de editar)
# -------------------------
@clienteapi.route('/clientes/<int:id_cliente>/reactivar', methods=['PATCH'])
@require_permiso('cliente', 'editar')
def reactivarCliente(id_cliente):
    dao = ClienteDao()
    try:
        resultado = dao.reactivarCliente(id_cliente)
        if resultado == NO_EXISTE:
            return respuesta_error('No se encontró el cliente con el ID proporcionado.', 404)
        if resultado == YA_ACTIVO:
            return respuesta_error('El cliente ya está activo.', 409)
        if resultado == PACIENTE_INVALIDO:
            return respuesta_error('No se puede reactivar: el paciente vinculado ya no existe.', 409)
        if resultado == DUPLICADO_CI_RUC:
            return respuesta_error('No se puede reactivar: ya existe un cliente activo con esa CI/RUC.', 409)
        if resultado == DUPLICADO_PACIENTE:
            return respuesta_error('No se puede reactivar: ese paciente ya está registrado como otro cliente activo.', 409)
        if resultado:
            cliente = dao.getClienteById(id_cliente)
            auditar(id_cliente, 'REACTIVACION', f'Nombre: {_nombre_completo(cliente)}; CI/RUC: {cliente["ci_ruc"]}')
            return jsonify({'success': True, 'data': cliente,
                            'mensaje': f'Cliente "{_nombre_completo(cliente)}" reactivado correctamente.',
                            'error': None}), 200
        return respuesta_error('No se pudo reactivar el cliente. Consulte con el administrador.', 500)
    except Exception as e:
        app.logger.error(f"Error al reactivar cliente: {str(e)}")
        return error_interno()
