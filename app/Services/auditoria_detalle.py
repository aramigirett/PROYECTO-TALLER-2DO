"""
=====================================================
Servicio: detalle de la auditoría de cambios
Descripción: funciones puras (sin Flask ni base de datos) que usan el registro de auditoría, la pantalla "Auditoría de Cambios",
el PDF y el CSV:
  - MODULO_POR_ENTIDAD / modulo_de(): módulo del sistema al que pertenece cada entidad auditada.
  - DetalleAuditoria: el `str` que devuelve detalle_cambios() (utils.py), con los campos que cambiaron (anteriores / nuevos)
    pegados, para que auditar() los guarde en las columnas JSONB sin que cada API tenga que cambiar.
  - estado_de_accion(): valores de ESTADO de una BAJA / REACTIVACION / CIERRE.
  - parsear_detalle(): arma anteriores / nuevos desde un texto "Campo: A -> B; ..." (solo para altas / modificaciones cuyo
    texto armó la API a mano, y para las filas viejas que no tienen JSON).
  - filas_detalle(): lo que muestran pantalla, PDF y CSV: una fila campo / valor anterior / valor nuevo por campo.
=====================================================
"""
import re
from decimal import Decimal

REFERENCIALES_FACTURACION = 'Referenciales Facturación'
MODULO_FACTURACION = 'Módulo Facturación'
MODULO_SEGURIDAD = 'Módulo Seguridad'
REFERENCIALES_CONSULTORIO = 'Referenciales Consultorio'
MODULO_CONSULTORIO = 'Módulo Consultorio'
REFERENCIALES_AGENDAMIENTO = 'Referenciales Agendamiento'
MODULO_AGENDAMIENTO = 'Módulo Agendamiento'

# Entidad (columna `entidad`) -> módulo. Una entidad que no esté acá se guarda con modulo NULL y se muestra como "Otro".
MODULO_POR_ENTIDAD = {
    'forma_cobro': REFERENCIALES_FACTURACION, 'marca_tarjeta': REFERENCIALES_FACTURACION,
    'entidad_emisora': REFERENCIALES_FACTURACION, 'entidad_adherida': REFERENCIALES_FACTURACION,
    'tipo_items': REFERENCIALES_FACTURACION, 'items': REFERENCIALES_FACTURACION, 'caja': REFERENCIALES_FACTURACION,
    'deposito': REFERENCIALES_FACTURACION, 'cliente': REFERENCIALES_FACTURACION,
    'cuenta_bancaria': REFERENCIALES_FACTURACION,
    'apertura_cierre_caja': MODULO_FACTURACION, 'pedido_venta_cab': MODULO_FACTURACION, 'venta_cab': MODULO_FACTURACION,
    'cobro_cab': MODULO_FACTURACION, 'nota_remision_cab': MODULO_FACTURACION,
    'nota_credito_debito_cab': MODULO_FACTURACION, 'arqueo_caja': MODULO_FACTURACION,
    'recaudacion_depositar': MODULO_FACTURACION,
    # Consultorio. El detalle de estas filas NUNCA lleva contenido clínico (diagnósticos, síntomas, indicaciones, medicamentos,
    # observaciones): solo quién, cuándo, paciente, N.º de documento y cambios de estado (decisión de negocio: datos de salud).
    'tipos_tratamiento': REFERENCIALES_CONSULTORIO, 'insumos': REFERENCIALES_CONSULTORIO,
    'tipo_procedimiento_medico': REFERENCIALES_CONSULTORIO, 'medicamentos': REFERENCIALES_CONSULTORIO,
    'tipo_estudio': REFERENCIALES_CONSULTORIO, 'tipo_analisis': REFERENCIALES_CONSULTORIO,
    'tipo_diagnostico': REFERENCIALES_CONSULTORIO, 'sintoma': REFERENCIALES_CONSULTORIO,
    'consultas_cab': MODULO_CONSULTORIO, 'ficha_medica_consulta': MODULO_CONSULTORIO, 'diagnosticos': MODULO_CONSULTORIO,
    'odontograma': MODULO_CONSULTORIO, 'tratamientos': MODULO_CONSULTORIO, 'sesiones_tratamiento': MODULO_CONSULTORIO,
    'recetas': MODULO_CONSULTORIO, 'orden_estudios': MODULO_CONSULTORIO, 'orden_analisis': MODULO_CONSULTORIO,
    'justificativo_medico': MODULO_CONSULTORIO,
    # Agendamiento. Datos personales: solo quién, cuándo, nombre y N.º de documento (nunca teléfono, dirección ni correo);
    # el historial médico no lleva contenido clínico.
    'ciudades': REFERENCIALES_AGENDAMIENTO, 'cargo': REFERENCIALES_AGENDAMIENTO, 'especialidades': REFERENCIALES_AGENDAMIENTO,
    'consultorio': REFERENCIALES_AGENDAMIENTO, 'dias': REFERENCIALES_AGENDAMIENTO, 'turnos': REFERENCIALES_AGENDAMIENTO,
    'disponibilidad_horaria': REFERENCIALES_AGENDAMIENTO,
    'paciente': MODULO_AGENDAMIENTO, 'medico': MODULO_AGENDAMIENTO, 'funcionario': MODULO_AGENDAMIENTO,
    'agenda_cabecera': MODULO_AGENDAMIENTO, 'agenda_detalle': MODULO_AGENDAMIENTO, 'cita_cabecera': MODULO_AGENDAMIENTO, 'cita_detalle': MODULO_AGENDAMIENTO,
    'avisos_recordatorios': MODULO_AGENDAMIENTO, 'historial_medico_paciente': MODULO_AGENDAMIENTO,
    'backup': MODULO_SEGURIDAD, 'usuarios': MODULO_SEGURIDAD, 'permisos': MODULO_SEGURIDAD, 'auditoria_cambios': MODULO_SEGURIDAD, 'auditoria_acceso': MODULO_SEGURIDAD,
}
MODULO_DESCONOCIDO = 'Otro'
MODULOS = (REFERENCIALES_FACTURACION, MODULO_FACTURACION, REFERENCIALES_CONSULTORIO, MODULO_CONSULTORIO,
           REFERENCIALES_AGENDAMIENTO, MODULO_AGENDAMIENTO, MODULO_SEGURIDAD)

# Entidades que son movimientos: su BAJA es una anulación ("Anulado") y no una baja de catálogo ("Inactivo").
ENTIDADES_MOVIMIENTO = frozenset(e for e, m in MODULO_POR_ENTIDAD.items() if m in (MODULO_FACTURACION, MODULO_CONSULTORIO)) | frozenset(
    {'agenda_cabecera', 'agenda_detalle', 'cita_cabecera', 'cita_detalle', 'avisos_recordatorios', 'historial_medico_paciente'})

ACCIONES = ('ALTA', 'MODIFICACION', 'BAJA', 'REACTIVACION', 'CIERRE', 'EXPORTACION')
# Decisión de negocio: BAJA se guarda así, pero se muestra como "Baja / Anulación".
ETIQUETA_ACCION = {'ALTA': 'Alta', 'MODIFICACION': 'Modificación', 'BAJA': 'Baja / Anulación',
                   'REACTIVACION': 'Reactivación', 'CIERRE': 'Cierre', 'EXPORTACION': 'Exportación'}


ETIQUETA_ENTIDAD = {
    'forma_cobro': 'Forma de Cobro', 'marca_tarjeta': 'Marca de Tarjeta', 'entidad_emisora': 'Entidad Emisora',
    'entidad_adherida': 'Entidad Adherida', 'tipo_items': 'Tipo de Ítems', 'items': 'Ítems', 'caja': 'Caja',
    'deposito': 'Depósito', 'cliente': 'Cliente', 'cuenta_bancaria': 'Cuenta Bancaria',
    'apertura_cierre_caja': 'Apertura y Cierre de Caja', 'pedido_venta_cab': 'Pedido de Cliente', 'venta_cab': 'Venta',
    'cobro_cab': 'Cobro', 'nota_remision_cab': 'Nota de Remisión', 'nota_credito_debito_cab': 'Nota de Crédito/Débito',
    'arqueo_caja': 'Arqueo de Caja', 'recaudacion_depositar': 'Recaudación a Depositar', 'backup': 'Copia de Seguridad', 'usuarios': 'Usuario', 'permisos': 'Permisos de un rol',
    'auditoria_cambios': 'Auditoría de Cambios', 'auditoria_acceso': 'Tablero de Accesos',
    'tipos_tratamiento': 'Tipo de Tratamiento', 'insumos': 'Tipo de Insumo', 'tipo_procedimiento_medico': 'Tipo de Procedimiento Médico',
    'medicamentos': 'Medicamento', 'tipo_estudio': 'Tipo de Estudio', 'tipo_analisis': 'Tipo de Análisis',
    'tipo_diagnostico': 'Tipo de Diagnóstico', 'sintoma': 'Síntoma', 'consultas_cab': 'Consulta',
    'ficha_medica_consulta': 'Ficha Médica', 'diagnosticos': 'Diagnóstico', 'odontograma': 'Odontograma',
    'tratamientos': 'Tratamiento', 'sesiones_tratamiento': 'Sesión de Tratamiento', 'recetas': 'Receta',
    'orden_estudios': 'Orden de Estudios', 'orden_analisis': 'Orden de Análisis', 'justificativo_medico': 'Justificativo Médico',
    'ciudades': 'Ciudad', 'cargo': 'Cargo', 'especialidades': 'Especialidad', 'consultorio': 'Consultorio', 'dias': 'Día', 'turnos': 'Turno',
    'disponibilidad_horaria': 'Disponibilidad Horaria', 'paciente': 'Paciente', 'medico': 'Médico', 'funcionario': 'Funcionario',
    'agenda_cabecera': 'Agenda', 'agenda_detalle': 'Horario de una Agenda', 'cita_cabecera': 'Cita', 'cita_detalle': 'Horario de una Cita', 'avisos_recordatorios': 'Aviso / Recordatorio',
    'historial_medico_paciente': 'Historial Médico',
}


def etiqueta_entidad(entidad):
    return ETIQUETA_ENTIDAD.get(entidad, entidad)


def modulo_de(entidad):
    """Módulo a guardar para la entidad, o None si no está en el mapa."""
    return MODULO_POR_ENTIDAD.get(entidad)


def entidades_de_modulo(modulo):
    """Entidades que pertenecen al módulo (para filtrar también las filas viejas, que tienen modulo NULL)."""
    return sorted(e for e, m in MODULO_POR_ENTIDAD.items() if m == modulo)


def etiqueta_accion(accion):
    return ETIQUETA_ACCION.get(accion, accion)


def _valor_json(v):
    """Valor serializable a JSON: números, textos y None quedan; booleanos como Sí/No; lo demás como texto."""
    if v is None or isinstance(v, (int, float, str)) and not isinstance(v, bool):
        return v
    if isinstance(v, bool):
        return 'Sí' if v else 'No'
    if isinstance(v, Decimal):
        return str(v)
    return str(v)


class DetalleAuditoria(str):
    """Texto del detalle (igual que antes) con los campos que cambiaron: `anteriores` y `nuevos` = {etiqueta: valor}.
    Si una API lo concatena o lo formatea, Python devuelve un str común y el JSON se arma con parsear_detalle()."""

    def __new__(cls, texto, anteriores, nuevos):
        obj = super().__new__(cls, texto)
        obj.anteriores = {k: _valor_json(v) for k, v in anteriores.items()}
        obj.nuevos = {k: _valor_json(v) for k, v in nuevos.items()}
        return obj


def estado_de_accion(accion, entidad):
    """(anteriores, nuevos) con el ESTADO para BAJA / REACTIVACION / CIERRE; (None, None) para las demás acciones."""
    inactivo = 'Anulado' if entidad in ENTIDADES_MOVIMIENTO else 'Inactivo'
    if accion == 'BAJA':
        return {'Estado': 'Activo'}, {'Estado': inactivo}
    if accion == 'REACTIVACION':
        return {'Estado': inactivo}, {'Estado': 'Activo'}
    if accion == 'CIERRE':
        return {'Estado': 'Abierta'}, {'Estado': 'Cerrada'}
    return None, None


_SEGMENTO = re.compile(r'^([^:;]{1,60}): (.*)$', re.S)


def parsear_detalle(texto, accion):
    """
    Intenta separar un detalle de texto en (anteriores, nuevos). Solo para ALTA ("Campo: valor; ...") y MODIFICACION
    ("Campo: A -> B; ..."). Devuelve None si el texto no tiene exactamente esa forma (un valor con "; " adentro, un campo
    repetido, un segmento sin "->" en una modificación...): mejor no mostrar campos inventados.
    """
    if accion not in ('ALTA', 'MODIFICACION') or not texto or not texto.strip():
        return None
    if texto.endswith('...'):   # algunas APIs recortan a 255 caracteres con "...": el último campo estaría incompleto
        return None
    anteriores, nuevos = {}, {}
    for segmento in texto.split('; '):
        m = _SEGMENTO.match(segmento)
        if not m:
            return None
        campo, valor = m.group(1).strip(), m.group(2)
        if not campo or campo in nuevos:
            return None
        if accion == 'MODIFICACION':
            if ' -> ' not in valor:
                return None
            ant, nue = valor.split(' -> ', 1)
            anteriores[campo], nuevos[campo] = ant, nue
        else:
            nuevos[campo] = valor
    return (anteriores, nuevos) if nuevos else None


def _texto(v):
    return '' if v is None else str(v)


def filas_detalle(fila):
    """
    Filas campo / anterior / nuevo de un registro de auditoría (dict con accion, entidad, detalle, valores_anteriores,
    valores_nuevos). Devuelve (filas, mostrar_texto): `mostrar_texto` = True cuando el texto del detalle aporta algo que
    las filas no dicen (identifica el registro de una baja, la factura de un cierre, el archivo de una exportación...).
    Usa los JSON si existen; si no (filas viejas), el parser; y si tampoco, una sola fila "Detalle" con el texto.
    """
    accion = fila.get('accion')
    detalle = fila.get('detalle') or ''
    ant, nue = fila.get('valores_anteriores'), fila.get('valores_nuevos')
    if ant is not None or nue is not None:
        ant, nue = ant or {}, nue or {}
        campos = list(nue) + [k for k in ant if k not in nue]
        filas = [{'campo': c, 'anterior': _texto(ant.get(c)), 'nuevo': _texto(nue.get(c))} for c in campos]
        return filas, accion not in ('ALTA', 'MODIFICACION') or not filas
    if accion in ('BAJA', 'REACTIVACION', 'CIERRE'):
        a, n = estado_de_accion(accion, fila.get('entidad'))
        return [{'campo': 'Estado', 'anterior': a['Estado'], 'nuevo': n['Estado']}], True
    parseado = parsear_detalle(detalle, accion)
    if parseado:
        a, n = parseado
        return [{'campo': c, 'anterior': _texto(a.get(c)), 'nuevo': _texto(n.get(c))} for c in n], False
    return ([{'campo': 'Detalle', 'anterior': '', 'nuevo': detalle}] if detalle else []), False
