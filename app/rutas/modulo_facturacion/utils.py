"""Helpers compartidos por las APIs de los referenciales de Facturación."""
import re
from flask import jsonify, request, session
from app.dao.modulo_facturacion.AuditoriaCambiosDao import AuditoriaCambiosDao

MAX_DESCRIPCION = 60


def normalizar_descripcion(data):
    """Devuelve (descripcion, error). Quita espacios sobrantes y pasa a mayúsculas."""
    if not data or not isinstance(data.get('descripcion'), str):
        return None, 'El campo descripción es obligatorio y no puede estar vacío.'
    descripcion = re.sub(r'\s+', ' ', data['descripcion']).strip().upper()
    if not descripcion:
        return None, 'El campo descripción es obligatorio y no puede estar vacío.'
    if len(descripcion) > MAX_DESCRIPCION:
        return None, f'La descripción no puede superar los {MAX_DESCRIPCION} caracteres.'
    if not re.match(r'^[A-ZÁÉÍÓÚÜÑ0-9][A-ZÁÉÍÓÚÜÑ0-9 .\-/]*$', descripcion):
        return None, 'La descripción solo puede contener letras, números, espacios y los símbolos . - /'
    return descripcion, None


def auditar(entidad, id_registro, accion, detalle):
    """Registra en auditoria_cambios. id_usuario e ip salen de la sesión y del request, nunca del cliente."""
    AuditoriaCambiosDao().registrar(session.get('id_usuario'), entidad, id_registro,
                                    accion, detalle, request.remote_addr)


def error_interno():
    return jsonify({'success': False, 'error': 'Ocurrió un error interno. Consulte con el administrador.'}), 500
