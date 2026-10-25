# Data Access Object - DAO
"""Informes (solo lectura). Cada pestaña devuelve el mismo formato, que usan la pantalla y las exportaciones:

    {'kpis':     [{'clave', 'titulo', 'valor', 'formato'}],                       formato: 'num' | 'gs' | 'pct'
     'graficos': [{'id', 'titulo', 'tipo', 'categorias', 'series': [{'nombre', 'datos'}]}],   tipo: 'line' | 'bar' | 'donut'
     'tablas':   [{'id', 'titulo', 'columnas': [{'campo', 'titulo', 'tipo'}], 'filas': [{campo: valor}]}]}   tipo: 'texto' | 'num' | 'gs' | 'pct'

Todo sale de las vistas v_inf_* (migración 03). Los filtros viajan como parámetros: desde / hasta (inclusivos), id_medico y condicion.
Consultorio no trae nombres de pacientes ni contenido clínico (las vistas ya no lo exponen)."""
from decimal import Decimal

from app.conexion.Conexion import Conexion

TOPE_FILAS = 5000     # filas máximas por tabla


def _num(v):
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    return v


def _pct(parte, total):
    return round(parte * 100.0 / total, 1) if total else 0.0


def _dia(d):
    return d.strftime('%d/%m/%Y') if d else ''


def _kpi(clave, titulo, valor, formato='num'):
    return {'clave': clave, 'titulo': titulo, 'valor': _num(valor), 'formato': formato}


def _col(campo, titulo, tipo='texto'):
    return {'campo': campo, 'titulo': titulo, 'tipo': tipo}


def _tabla(id_, titulo, columnas, filas):
    return {'id': id_, 'titulo': titulo, 'columnas': columnas, 'filas': filas}


class InformesDao:

    # ---------------------------------------------------------------------------------------------------------------
    # Utilidades
    # ---------------------------------------------------------------------------------------------------------------
    def _consultar(self, sql, params=()):
        """Filas (tuplas) de un SELECT; abre y cierra su propia conexión."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            cur.close()
            con.close()

    @staticmethod
    def _medico(f, columna='id_medico'):
        return (f" AND {columna} = %s", [f['id_medico']]) if f.get('id_medico') else ("", [])

    @staticmethod
    def _condicion(f):
        return (" AND condicion = %s", [f['condicion']]) if f.get('condicion') else ("", [])

    @staticmethod
    def _dias(f):
        return (f['hasta'] - f['desde']).days + 1

    def get_medicos(self):
        """Médicos activos para el filtro (id y nombre)."""
        filas = self._consultar("SELECT id_medico, nombre || ' ' || apellido FROM medico WHERE activo ORDER BY apellido, nombre")
        return [{'id_medico': r[0], 'nombre': r[1]} for r in filas]

    def get_nombre_medico(self, id_medico):
        r = self._consultar("SELECT nombre || ' ' || apellido FROM medico WHERE id_medico = %s", (id_medico,))
        return r[0][0] if r else None

    def get_empresa(self):
        r = self._consultar("SELECT razon_social, ruc, direccion, telefono FROM empresa LIMIT 1")
        return {'razon_social': r[0][0], 'ruc': r[0][1], 'direccion': r[0][2], 'telefono': r[0][3]} if r else None

    # ---------------------------------------------------------------------------------------------------------------
    # Resumen
    # ---------------------------------------------------------------------------------------------------------------
    def resumen(self, f):
        """Total facturado (facturas - notas de crédito + notas de débito, solo EMITIDAS), saldo por cobrar de las cuentas PENDIENTES emitidas
        en el período, citas, tasa de asistencia (atendidas / (atendidas + ausentes)), consultas e ingresos (cobros EMITIDOS) por día.
        El filtro de médico alcanza a citas y consultas; la facturación no depende del médico."""
        d, h = f['desde'], f['hasta']
        total = self._consultar("SELECT COALESCE(SUM(total), 0) FROM v_inf_comprobantes WHERE estado = 'EMITIDA' AND fecha BETWEEN %s AND %s", (d, h))[0][0]
        saldo = self._consultar("SELECT COALESCE(SUM(saldo), 0) FROM v_inf_cuentas_cobrar WHERE estado = 'PENDIENTE' AND fecha BETWEEN %s AND %s", (d, h))[0][0]
        mc, pm = self._medico(f)
        c = self._consultar(f"""SELECT COUNT(*), COUNT(*) FILTER (WHERE categoria = 'ATENDIDA'), COUNT(*) FILTER (WHERE categoria = 'AUSENTE')
                                  FROM v_inf_citas WHERE fecha_cita BETWEEN %s AND %s{mc}""", [d, h] + pm)[0]
        consultas = self._consultar(f"SELECT COUNT(*) FROM v_inf_consultas WHERE fecha BETWEEN %s AND %s{mc}", [d, h] + pm)[0][0]
        ing = self._consultar("SELECT fecha, SUM(monto) FROM v_inf_cobros WHERE fecha BETWEEN %s AND %s GROUP BY fecha ORDER BY fecha", (d, h))
        return {
            'kpis': [_kpi('total_facturado', 'Total facturado (neto)', total, 'gs'), _kpi('saldo_por_cobrar', 'Saldo por cobrar', saldo, 'gs'),
                     _kpi('citas', 'Citas agendadas', c[0]), _kpi('tasa_asistencia', 'Tasa de asistencia', _pct(c[1], c[1] + c[2]), 'pct'),
                     _kpi('consultas', 'Consultas', consultas)],
            'graficos': [{'id': 'ingresos_dia', 'titulo': 'Ingresos por día (cobros emitidos)', 'tipo': 'bar',
                          'categorias': [_dia(r[0]) for r in ing], 'series': [{'nombre': 'Ingresos', 'datos': [_num(r[1]) for r in ing]}]}],
            'tablas': [],
        }

    # ---------------------------------------------------------------------------------------------------------------
    # Agendamiento
    # ---------------------------------------------------------------------------------------------------------------
    def agendamiento(self, f):
        """Categorías de v_inf_citas. AUSENTE = estado 5 "No Asistió" + Confirmado con fecha pasada y sin consulta. Reprogramado solo suma en agendadas.
        Tasas: asistencia = atendidas / (atendidas + ausentes); ausentismo y cancelación sobre las agendadas."""
        d, h = f['desde'], f['hasta']
        mc, pm = self._medico(f)
        base = [d, h] + pm
        k = self._consultar(f"""SELECT COUNT(*), COUNT(*) FILTER (WHERE categoria = 'ATENDIDA'), COUNT(*) FILTER (WHERE categoria = 'CANCELADA'),
                                       COUNT(*) FILTER (WHERE categoria = 'AUSENTE'), COUNT(*) FILTER (WHERE categoria = 'REPROGRAMADA')
                                  FROM v_inf_citas WHERE fecha_cita BETWEEN %s AND %s{mc}""", base)[0]
        ag, at, ca, au, rep = k
        evo = self._consultar(f"""SELECT fecha_cita, COUNT(*), COUNT(*) FILTER (WHERE categoria = 'ATENDIDA'), COUNT(*) FILTER (WHERE categoria = 'CANCELADA'),
                                         COUNT(*) FILTER (WHERE categoria = 'AUSENTE')
                                    FROM v_inf_citas WHERE fecha_cita BETWEEN %s AND %s{mc} GROUP BY fecha_cita ORDER BY fecha_cita""", base)
        med = self._consultar(f"""SELECT medico, COUNT(*), COUNT(*) FILTER (WHERE categoria = 'ATENDIDA'), COUNT(*) FILTER (WHERE categoria = 'CANCELADA'),
                                         COUNT(*) FILTER (WHERE categoria = 'AUSENTE')
                                    FROM v_inf_citas WHERE fecha_cita BETWEEN %s AND %s{mc} GROUP BY id_medico, medico ORDER BY 2 DESC, medico""", base)
        aus = self._consultar(f"""WITH aus AS (SELECT * FROM v_inf_citas WHERE categoria = 'AUSENTE')
                                  SELECT a.fecha_cita, a.hora_cita, a.paciente, a.ci_paciente, a.medico,
                                         (SELECT COUNT(*) FROM aus b WHERE b.id_paciente = a.id_paciente
                                             AND (b.fecha_cita, b.hora_cita) < (a.fecha_cita, a.hora_cita)) AS previas
                                    FROM aus a WHERE a.fecha_cita BETWEEN %s AND %s{mc.replace('id_medico', 'a.id_medico')}
                                   ORDER BY a.fecha_cita DESC, a.hora_cita DESC LIMIT {TOPE_FILAS}""", base)
        reit = self._consultar(f"""SELECT paciente, ci_paciente, COUNT(*), MAX(fecha_cita)
                                     FROM v_inf_citas WHERE categoria = 'AUSENTE' AND fecha_cita BETWEEN %s AND %s{mc}
                                    GROUP BY id_paciente, paciente, ci_paciente HAVING COUNT(*) >= 2 ORDER BY 3 DESC, paciente""", base)
        can = self._consultar(f"""SELECT fecha_cita, hora_cita, paciente, ci_paciente, medico
                                    FROM v_inf_citas WHERE categoria = 'CANCELADA' AND fecha_cita BETWEEN %s AND %s{mc}
                                   ORDER BY fecha_cita DESC, hora_cita DESC LIMIT {TOPE_FILAS}""", base)
        cols_cita = [_col('fecha', 'Fecha'), _col('hora', 'Hora'), _col('paciente', 'Paciente'), _col('ci', 'CI'), _col('medico', 'Médico')]
        fila_cita = lambda r: {'fecha': _dia(r[0]), 'hora': r[1].strftime('%H:%M') if r[1] else '', 'paciente': r[2], 'ci': r[3], 'medico': r[4]}
        return {
            'kpis': [_kpi('agendadas', 'Agendadas', ag), _kpi('atendidas', 'Atendidas', at), _kpi('canceladas', 'Canceladas', ca), _kpi('ausentes', 'Ausentes', au),
                     _kpi('tasa_asistencia', 'Tasa de asistencia', _pct(at, at + au), 'pct'), _kpi('tasa_ausentismo', 'Tasa de ausentismo', _pct(au, ag), 'pct'),
                     _kpi('tasa_cancelacion', 'Tasa de cancelación', _pct(ca, ag), 'pct'), _kpi('reprogramadas', 'Reprogramadas (solo en agendadas)', rep)],
            'graficos': [{'id': 'evolucion', 'titulo': 'Evolución diaria de citas', 'tipo': 'line', 'categorias': [_dia(r[0]) for r in evo],
                          'series': [{'nombre': 'Agendadas', 'datos': [r[1] for r in evo]}, {'nombre': 'Atendidas', 'datos': [r[2] for r in evo]},
                                     {'nombre': 'Canceladas', 'datos': [r[3] for r in evo]}, {'nombre': 'Ausentes', 'datos': [r[4] for r in evo]}]}],
            'tablas': [
                _tabla('por_medico', 'Citas por médico', [_col('medico', 'Médico'), _col('agendadas', 'Agendadas', 'num'), _col('atendidas', 'Atendidas', 'num'),
                                                          _col('canceladas', 'Canceladas', 'num'), _col('ausentes', 'Ausentes', 'num'), _col('tasa', 'Asistencia', 'pct')],
                       [{'medico': r[0], 'agendadas': r[1], 'atendidas': r[2], 'canceladas': r[3], 'ausentes': r[4], 'tasa': _pct(r[2], r[2] + r[4])} for r in med]),
                _tabla('ausentes', 'Pacientes ausentes', cols_cita + [_col('previas', 'Ausencias previas', 'num')],
                       [dict(fila_cita(r), previas=r[5]) for r in aus]),
                _tabla('reiteradas', 'Ausencias reiteradas (2 o más)', [_col('paciente', 'Paciente'), _col('ci', 'CI'), _col('ausencias', 'Ausencias', 'num'), _col('ultima', 'Última ausencia')],
                       [{'paciente': r[0], 'ci': r[1], 'ausencias': r[2], 'ultima': _dia(r[3])} for r in reit]),
                _tabla('canceladas', 'Citas canceladas', cols_cita, [fila_cita(r) for r in can]),
            ],
        }

    # ---------------------------------------------------------------------------------------------------------------
    # Consultorio (sin pacientes por nombre ni datos clínicos)
    # ---------------------------------------------------------------------------------------------------------------
    def consultorio(self, f):
        """Pacientes nuevos = pacientes cuya primera consulta cae en el período. Promedio diario = consultas / días del período."""
        d, h = f['desde'], f['hasta']
        mc, pm = self._medico(f)
        base = [d, h] + pm
        k = self._consultar(f"""SELECT COUNT(*), COUNT(DISTINCT id_paciente), COUNT(DISTINCT id_paciente) FILTER (WHERE primera_consulta BETWEEN %s AND %s)
                                  FROM v_inf_consultas WHERE fecha BETWEEN %s AND %s{mc}""", [d, h] + base)[0]
        consultas, pacientes, nuevos = k

        def top(vista, campo, medida='COUNT(*)', limite=50):
            return self._consultar(f"SELECT {campo}, {medida} AS n FROM {vista} WHERE fecha BETWEEN %s AND %s{mc} GROUP BY {campo} ORDER BY n DESC, {campo} LIMIT {limite}", base)

        diag = top('v_inf_diagnosticos', 'tipo')
        trat = top('v_inf_tratamientos', 'estado')
        proc = top('v_inf_procedimientos', 'descripcion')
        ins = top('v_inf_insumos', 'descripcion', 'SUM(cantidad)')
        med = self._consultar(f"SELECT medico, COUNT(*) FROM v_inf_consultas WHERE fecha BETWEEN %s AND %s{mc} GROUP BY id_medico, medico ORDER BY 2 DESC, medico", base)
        tabla = lambda id_, titulo, nombre, filas: _tabla(id_, titulo, [_col('nombre', nombre), _col('cantidad', 'Cantidad', 'num')],
                                                          [{'nombre': r[0], 'cantidad': _num(r[1])} for r in filas])
        return {
            'kpis': [_kpi('consultas', 'Consultas', consultas), _kpi('pacientes', 'Pacientes distintos', pacientes), _kpi('nuevos', 'Pacientes nuevos', nuevos),
                     _kpi('promedio', 'Promedio diario de consultas', round(consultas / self._dias(f), 2))],
            'graficos': [{'id': 'diagnosticos', 'titulo': 'Diagnósticos más frecuentes', 'tipo': 'bar', 'categorias': [r[0] for r in diag[:10]],
                          'series': [{'nombre': 'Diagnósticos', 'datos': [r[1] for r in diag[:10]]}]},
                         {'id': 'tratamientos', 'titulo': 'Tratamientos por estado', 'tipo': 'donut', 'categorias': [r[0] for r in trat],
                          'series': [{'nombre': 'Tratamientos', 'datos': [r[1] for r in trat]}]}],
            'tablas': [tabla('diagnosticos', 'Diagnósticos más frecuentes', 'Tipo de diagnóstico', diag),
                       tabla('tratamientos', 'Tratamientos por estado', 'Estado', trat),
                       tabla('procedimientos', 'Procedimientos más usados', 'Procedimiento', proc),
                       tabla('insumos', 'Insumos más usados (unidades)', 'Insumo', ins),
                       tabla('por_medico', 'Consultas por médico', 'Médico', med)],
        }

    # ---------------------------------------------------------------------------------------------------------------
    # Facturación
    # ---------------------------------------------------------------------------------------------------------------
    def facturacion(self, f):
        """Comprobantes EMITIDOS: las facturas suman, las notas de crédito restan y las de débito suman (la vista ya trae los importes con signo).
        Las cuentas a cobrar son las PENDIENTES con saldo, emitidas en el período (el saldo ya incluye las notas)."""
        d, h = f['desde'], f['hasta']
        cc, pc = self._condicion(f)
        base = [d, h] + pc
        k = self._consultar(f"""SELECT COALESCE(SUM(gravada_10), 0), COALESCE(SUM(gravada_5), 0), COALESCE(SUM(iva_5 + iva_10), 0), COALESCE(SUM(exenta), 0), COALESCE(SUM(total), 0)
                                  FROM v_inf_comprobantes WHERE estado = 'EMITIDA' AND fecha BETWEEN %s AND %s{cc}""", base)[0]
        cond = self._consultar(f"""SELECT condicion, COUNT(*), COALESCE(SUM(total), 0) FROM v_inf_comprobantes
                                    WHERE estado = 'EMITIDA' AND fecha BETWEEN %s AND %s{cc} GROUP BY condicion ORDER BY condicion""", base)
        dia = self._consultar(f"""SELECT fecha, SUM(total) FROM v_inf_comprobantes WHERE estado = 'EMITIDA' AND fecha BETWEEN %s AND %s{cc}
                                   GROUP BY fecha ORDER BY fecha""", base)
        cob = self._consultar(f"""SELECT forma_cobro, COUNT(*), SUM(monto) FROM v_inf_cobros WHERE fecha BETWEEN %s AND %s{cc}
                                   GROUP BY forma_cobro ORDER BY 3 DESC, forma_cobro""", base)
        cta = self._consultar(f"""SELECT fecha, numero_factura, cliente, ci_ruc, condicion, monto_total, saldo, fecha_vencimiento, dias_vencida
                                    FROM v_inf_cuentas_cobrar WHERE estado = 'PENDIENTE' AND saldo > 0 AND fecha BETWEEN %s AND %s{cc}
                                   ORDER BY fecha_vencimiento, numero_factura LIMIT {TOPE_FILAS}""", base)
        det = self._consultar(f"""SELECT fecha, tipo, numero, cliente, ci_ruc, condicion, gravada_10, gravada_5, exenta, iva_5 + iva_10, total
                                    FROM v_inf_comprobantes WHERE estado = 'EMITIDA' AND fecha BETWEEN %s AND %s{cc}
                                   ORDER BY fecha DESC, numero DESC LIMIT {TOPE_FILAS}""", base)
        return {
            'kpis': [_kpi('gravado_10', 'Gravado 10%', k[0], 'gs'), _kpi('gravado_5', 'Gravado 5%', k[1], 'gs'), _kpi('iva', 'IVA', k[2], 'gs'),
                     _kpi('exentas', 'Exentas', k[3], 'gs'), _kpi('total', 'Total (neto)', k[4], 'gs')],
            'graficos': [{'id': 'ventas_dia', 'titulo': 'Ventas por día (neto)', 'tipo': 'bar', 'categorias': [_dia(r[0]) for r in dia],
                          'series': [{'nombre': 'Ventas', 'datos': [_num(r[1]) for r in dia]}]},
                         {'id': 'condicion', 'titulo': 'Contado vs. crédito', 'tipo': 'donut', 'categorias': [r[0].capitalize() for r in cond],
                          'series': [{'nombre': 'Total', 'datos': [_num(r[2]) for r in cond]}]}],
            'tablas': [
                _tabla('condicion', 'Contado vs. crédito', [_col('condicion', 'Condición'), _col('comprobantes', 'Comprobantes', 'num'), _col('total', 'Total', 'gs')],
                       [{'condicion': r[0].capitalize(), 'comprobantes': r[1], 'total': _num(r[2])} for r in cond]),
                _tabla('cobros', 'Cobros por forma de cobro', [_col('forma', 'Forma de cobro'), _col('cobros', 'Cobros', 'num'), _col('monto', 'Monto', 'gs')],
                       [{'forma': r[0], 'cobros': r[1], 'monto': _num(r[2])} for r in cob]),
                _tabla('cuentas', 'Cuentas a cobrar con saldo',
                       [_col('fecha', 'Fecha'), _col('factura', 'Factura'), _col('cliente', 'Cliente'), _col('ci_ruc', 'CI/RUC'), _col('condicion', 'Condición'),
                        _col('monto', 'Monto', 'gs'), _col('saldo', 'Saldo', 'gs'), _col('vence', 'Vencimiento'), _col('dias', 'Días vencida', 'num')],
                       [{'fecha': _dia(r[0]), 'factura': r[1], 'cliente': r[2], 'ci_ruc': r[3], 'condicion': r[4].capitalize(), 'monto': _num(r[5]), 'saldo': _num(r[6]),
                         'vence': _dia(r[7]), 'dias': r[8]} for r in cta]),
                _tabla('detalle', 'Detalle de comprobantes (notas de crédito en negativo)',
                       [_col('fecha', 'Fecha'), _col('tipo', 'Tipo'), _col('numero', 'Número'), _col('cliente', 'Cliente'), _col('ci_ruc', 'CI/RUC'), _col('condicion', 'Condición'),
                        _col('gravado_10', 'Gravado 10%', 'gs'), _col('gravado_5', 'Gravado 5%', 'gs'), _col('exenta', 'Exenta', 'gs'), _col('iva', 'IVA', 'gs'), _col('total', 'Total', 'gs')],
                       [{'fecha': _dia(r[0]), 'tipo': r[1].title(), 'numero': r[2], 'cliente': r[3], 'ci_ruc': r[4], 'condicion': r[5].capitalize(), 'gravado_10': _num(r[6]),
                         'gravado_5': _num(r[7]), 'exenta': _num(r[8]), 'iva': _num(r[9]), 'total': _num(r[10])} for r in det]),
            ],
        }

    # ---------------------------------------------------------------------------------------------------------------
    # Auditoría de accesos
    # ---------------------------------------------------------------------------------------------------------------
    def auditoria(self, f):
        """Accesos exitosos (LOGIN EXITOSO), fallidos (LOGIN / 2FA con resultado distinto de EXITOSO) y bloqueos (acción BLOQUEO), de auditoria_acceso."""
        d, h = f['desde'], f['hasta']
        base = [d, h]
        k = self._consultar("""SELECT COUNT(*) FILTER (WHERE resultado_informe = 'EXITOSO'), COUNT(*) FILTER (WHERE resultado_informe = 'FALLIDO'),
                                      COUNT(*) FILTER (WHERE accion = 'BLOQUEO')
                                 FROM v_inf_accesos WHERE fecha BETWEEN %s AND %s""", base)[0]
        dia = self._consultar("""SELECT fecha, COUNT(*) FILTER (WHERE resultado_informe = 'EXITOSO'), COUNT(*) FILTER (WHERE resultado_informe = 'FALLIDO')
                                   FROM v_inf_accesos WHERE fecha BETWEEN %s AND %s GROUP BY fecha ORDER BY fecha""", base)
        ips = self._consultar("""SELECT COALESCE(ip, '(sin IP)'), COUNT(*) FILTER (WHERE accion = 'BLOQUEO'), COUNT(*) FILTER (WHERE resultado_informe = 'FALLIDO')
                                   FROM v_inf_accesos WHERE fecha BETWEEN %s AND %s GROUP BY ip
                                 HAVING COUNT(*) FILTER (WHERE accion = 'BLOQUEO') > 0 OR COUNT(*) FILTER (WHERE resultado_informe = 'FALLIDO') > 0
                                  ORDER BY 2 DESC, 3 DESC, 1 LIMIT 50""", base)
        usr = self._consultar("""SELECT COALESCE(NULLIF(a.ci_ruc_ingresado, ''), '(sin dato)'),
                                        MAX(COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido)), COUNT(*), MAX(a.fecha_hora)
                                   FROM v_inf_accesos a
                                   LEFT JOIN usuarios u ON u.id_usuario = a.id_usuario
                                   LEFT JOIN funcionario f ON f.id_funcionario = u.id_funcionario
                                   LEFT JOIN medico m ON m.id_medico = u.id_medico
                                  WHERE a.fecha BETWEEN %s AND %s AND a.resultado_informe = 'FALLIDO'
                                  GROUP BY 1 ORDER BY 3 DESC, 1 LIMIT 50""", base)
        return {
            'kpis': [_kpi('exitosos', 'Accesos exitosos', k[0]), _kpi('fallidos', 'Accesos fallidos', k[1]), _kpi('bloqueos', 'Bloqueos de cuenta', k[2])],
            'graficos': [{'id': 'accesos_dia', 'titulo': 'Accesos por día', 'tipo': 'bar', 'categorias': [_dia(r[0]) for r in dia],
                          'series': [{'nombre': 'Exitosos', 'datos': [r[1] for r in dia]}, {'nombre': 'Fallidos', 'datos': [r[2] for r in dia]}]}],
            'tablas': [
                _tabla('ips', 'Bloqueos e intentos fallidos por IP', [_col('ip', 'IP'), _col('bloqueos', 'Bloqueos', 'num'), _col('fallidos', 'Intentos fallidos', 'num')],
                       [{'ip': r[0], 'bloqueos': r[1], 'fallidos': r[2]} for r in ips]),
                _tabla('usuarios', 'Usuarios con más intentos fallidos',
                       [_col('ci_ruc', 'CI/RUC ingresado'), _col('usuario', 'Usuario'), _col('fallidos', 'Intentos fallidos', 'num'), _col('ultimo', 'Último intento')],
                       [{'ci_ruc': r[0], 'usuario': r[1] or '(no registrado)', 'fallidos': r[2], 'ultimo': r[3].strftime('%d/%m/%Y %H:%M') if r[3] else ''} for r in usr]),
            ],
        }
