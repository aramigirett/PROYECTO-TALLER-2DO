"""
=====================================================
Piezas comunes de los documentos clínicos que cuelgan de una consulta: Receta, Orden de Estudios y Orden de Análisis (y, después, el Justificativo).

Reglas compartidas:
  - Los crea y los anula SOLO el médico de la consulta, con la consulta 'programada' o 'en_proceso', revalidado dentro de la transacción con la consulta
    bloqueada (FOR UPDATE).
  - Paciente y médico se heredan de la consulta; la fecha del documento la fija el servidor.
  - Vínculos opcionales con un diagnóstico VIGENTE y con un tratamiento NO cancelado, ambos de la MISMA consulta (bloqueados FOR SHARE).
  - N.º de documento derivado del id, sin columna nueva (RCT-0000012, OES-0000005, OAN-0000003).
Dato de salud: la auditoría no recibe contenido clínico; el PDF sí lo lleva.
=====================================================
"""
ESTADOS_ABIERTOS = ('programada', 'en_proceso')

PREFIJO_RECETA = 'RCT'
PREFIJO_ORDEN_ESTUDIO = 'OES'
PREFIJO_ORDEN_ANALISIS = 'OAN'


def numero_documento(prefijo, id_documento):
    """N.º de documento visible, derivado del id (sin columna nueva): RCT-0000012."""
    return f'{prefijo}-{int(id_documento):07d}'


def bloquear_consulta(cur, id_consulta, modo='UPDATE'):
    """
    Lee (y bloquea FOR UPDATE o FOR SHARE) la consulta. Devuelve un dict o None si no existe / está anulada:
    {'estado', 'id_medico', 'id_paciente', 'paciente', 'cedula'}.
    """
    cur.execute(f"""SELECT cc.activo, cc.estado, cc.id_medico, cc.id_paciente, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad
                    FROM consultas_cab cc JOIN paciente p ON cc.id_paciente = p.id_paciente
                    WHERE cc.id_consulta_cab = %s FOR {modo} OF cc""", (id_consulta,))
    f = cur.fetchone()
    if not f or not f[0]:
        return None
    return {'estado': f[1], 'id_medico': f[2], 'id_paciente': f[3], 'paciente': f[4], 'cedula': f[5]}


def bloquear_vinculos(cur, id_consulta, id_diagnostico, id_tratamiento):
    """
    Bloquea FOR SHARE el diagnóstico y el tratamiento elegidos y verifica que sean de la misma consulta y estén vigentes.
    Devuelve None o el código de error: 'DIAGNOSTICO_INVALIDO' / 'TRATAMIENTO_INVALIDO'.
    """
    if id_diagnostico:
        cur.execute("SELECT activo, id_consulta_cab FROM diagnosticos WHERE id_diagnostico = %s FOR SHARE", (id_diagnostico,))
        f = cur.fetchone()
        if not f or not f[0] or f[1] != id_consulta:
            return 'DIAGNOSTICO_INVALIDO'
    if id_tratamiento:
        cur.execute("SELECT estado, id_consulta_cab FROM tratamientos WHERE id_tratamiento = %s FOR SHARE", (id_tratamiento,))
        f = cur.fetchone()
        if not f or f[0] == 'cancelado' or f[1] != id_consulta:
            return 'TRATAMIENTO_INVALIDO'
    return None


def datos_para_pdf(cur, id_consulta):
    """La clínica (tabla `empresa`) y el médico de la consulta (con su especialidad y N.º de registro, si los tiene) para el encabezado de los PDF."""
    cur.execute("SELECT razon_social, ruc, direccion, telefono, actividad_economica FROM empresa ORDER BY id_empresa LIMIT 1")
    e = cur.fetchone()
    empresa = {'razon_social': e[0], 'ruc': e[1], 'direccion': e[2], 'telefono': e[3], 'actividad_economica': e[4]} if e else {}
    cur.execute("""SELECT CONCAT(m.nombre, ' ', m.apellido), esp.nombre_especialidad, m.num_registro, m.cedula
                   FROM consultas_cab cc JOIN medico m ON m.id_medico = cc.id_medico
                   LEFT JOIN especialidades esp ON esp.id_especialidad = m.id_especialidad
                   WHERE cc.id_consulta_cab = %s""", (id_consulta,))
    m = cur.fetchone()
    medico = {'nombre': m[0], 'especialidad': m[1], 'registro': m[2], 'cedula': m[3]} if m else {}
    return empresa, medico
