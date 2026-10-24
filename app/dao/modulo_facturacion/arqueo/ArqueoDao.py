# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

REGISTRADO = 'REGISTRADO'
ANULADO = 'ANULADO'
PENDIENTE = 'PENDIENTE'
DEPOSITADA = 'DEPOSITADA'
ANULADA = 'ANULADA'

# Códigos de resultado (además de un ID o un dict)
NO_EXISTE = "NO_EXISTE"
YA_ANULADO = "YA_ANULADO"
RECAUDACION_DEPOSITADA = "RECAUDACION_DEPOSITADA"   # no se anula un arqueo cuya recaudación ya se depositó
NO_PENDIENTE = "NO_PENDIENTE"                       # se devuelve como (NO_PENDIENTE, estado_actual)
CUENTA_INVALIDA = "CUENTA_INVALIDA"                 # la cuenta bancaria no existe o está anulada
FECHA_ANTERIOR = "FECHA_ANTERIOR"                   # el depósito no puede ser anterior al arqueo
ERROR_BD = "ERROR_BD"                               # se devuelve como (ERROR_BD, mensaje de la base)

_SELECT = """
SELECT v.id_arqueo, v.id_apertura, v.caja, v.id_cajero, v.cajero, v.fecha_apertura, v.fecha_cierre, v.fecha_arqueo,
       v.id_arqueador, v.arqueador, v.total_sistema, v.total_contado, v.diferencia, v.resultado, v.estado, v.observacion,
       a.monto_apertura, a.monto_cierre,
       r.id_recaudacion, r.estado, r.total
FROM v_arqueos_diferencias v
JOIN apertura_cierre_caja a ON a.id_apertura = v.id_apertura
LEFT JOIN recaudacion_depositar r ON r.id_arqueo = v.id_arqueo AND r.estado <> 'ANULADA'
"""

_SELECT_RECAUDACION = """
SELECT r.id_recaudacion, r.id_arqueo, r.fecha_generacion, r.monto_efectivo, r.monto_cheque, r.total, r.estado, r.fecha_deposito, r.numero_boleta,
       r.id_cuenta_bancaria, c.tipo_cuenta, c.numero_cuenta, e.descripcion,
       q.id_apertura, cj.descripcion, q.fecha
FROM recaudacion_depositar r
JOIN arqueo_caja q ON q.id_arqueo = r.id_arqueo
JOIN apertura_cierre_caja a ON a.id_apertura = q.id_apertura
JOIN caja cj ON cj.id_caja = a.id_caja
LEFT JOIN cuenta_bancaria c ON c.id_cuenta_bancaria = r.id_cuenta_bancaria
LEFT JOIN entidad_emisora e ON e.id_entidad_emisora = c.id_entidad_emisora
"""


def _fecha(valor, con_hora=True):
    return valor.strftime('%Y-%m-%d %H:%M:%S' if con_hora else '%Y-%m-%d') if valor else None


def _a_dict(f):
    return {
        'id_arqueo': f[0], 'id_apertura': f[1], 'caja': f[2], 'id_cajero': f[3], 'cajero': f[4],
        'fecha_apertura': _fecha(f[5]), 'fecha_cierre': _fecha(f[6]), 'fecha_arqueo': _fecha(f[7]),
        'id_arqueador': f[8], 'arqueador': f[9], 'total_sistema': int(f[10]), 'total_contado': int(f[11]), 'diferencia': int(f[12]),
        'resultado': f[13], 'estado': f[14], 'observacion': f[15], 'monto_apertura': int(f[16]), 'monto_cierre': int(f[17]) if f[17] is not None else None,
        'id_recaudacion': f[18], 'estado_recaudacion': f[19], 'total_recaudacion': int(f[20]) if f[20] is not None else None,
    }


def _recaudacion_dict(f):
    return {
        'id_recaudacion': f[0], 'id_arqueo': f[1], 'fecha_generacion': _fecha(f[2]), 'monto_efectivo': int(f[3]), 'monto_cheque': int(f[4]),
        'total': int(f[5]), 'estado': f[6], 'fecha_deposito': _fecha(f[7], False), 'numero_boleta': f[8],
        'id_cuenta_bancaria': f[9], 'cuenta': (f'{f[10]} {f[12]} {f[11]}' if f[9] else None),
        'id_apertura': f[13], 'caja': f[14], 'fecha_arqueo': _fecha(f[15]),
    }


def _escapar_like(texto):
    return texto.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


class ArqueoDao:

    # ------------------------------------------------------------------ consultas
    def getArqueos(self, estado=None, resultado=None, texto=None, desde=None, hasta=None, limite=500):
        """Arqueos, del más reciente al más antiguo. `texto` busca por caja, cajero o arqueador; `desde`/`hasta` son la fecha del arqueo."""
        filtros, params = [], []
        if estado:
            filtros.append("v.estado = %s"); params.append(estado)
        if resultado:
            filtros.append("v.resultado = %s"); params.append(resultado)
        if texto:
            filtros.append("(v.caja ILIKE %s OR v.cajero ILIKE %s OR v.arqueador ILIKE %s)")
            patron = '%' + _escapar_like(texto.strip()) + '%'
            params += [patron, patron, patron]
        if desde:
            filtros.append("v.fecha_arqueo >= %s"); params.append(desde)
        if hasta:
            filtros.append("v.fecha_arqueo < %s::date + 1"); params.append(hasta)
        where = (" WHERE " + " AND ".join(filtros)) if filtros else ""
        sql = _SELECT + where + " ORDER BY v.fecha_arqueo DESC, v.id_arqueo DESC LIMIT %s"
        params.append(limite)
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return [_a_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener arqueos: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getArqueoById(self, id_arqueo):
        """Arqueo con su detalle por forma de cobro, su recaudación y los datos de la empresa (para el PDF), o None."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(_SELECT + " WHERE v.id_arqueo = %s", (id_arqueo,))
            f = cur.fetchone()
            if f is None:
                return None
            arqueo = _a_dict(f)
            cur.execute("""SELECT d.id_forma_cobro, fc.descripcion, fc.tipo, d.monto_sistema, d.monto_contado, d.diferencia
                           FROM arqueo_caja_det d JOIN forma_cobro fc ON fc.id_forma_cobro = d.id_forma_cobro
                           WHERE d.id_arqueo = %s ORDER BY (fc.tipo <> 'EFECTIVO'), fc.descripcion""", (id_arqueo,))
            arqueo['detalle'] = [{'id_forma_cobro': r[0], 'forma_cobro': r[1], 'tipo': r[2], 'monto_sistema': int(r[3]),
                                  'monto_contado': int(r[4]), 'diferencia': int(r[5])} for r in cur.fetchall()]
            cur.execute(_SELECT_RECAUDACION + " WHERE r.id_arqueo = %s ORDER BY r.id_recaudacion DESC LIMIT 1", (id_arqueo,))
            r = cur.fetchone()
            arqueo['recaudacion'] = _recaudacion_dict(r) if r else None
            cur.execute("SELECT razon_social, ruc, direccion, telefono, actividad_economica FROM empresa LIMIT 1")
            e = cur.fetchone()
            arqueo['empresa'] = ({'razon_social': e[0], 'ruc': e[1], 'direccion': e[2], 'telefono': e[3], 'actividad_economica': e[4]} if e else None)
            return arqueo
        except Exception as e:
            app.logger.error(f"Error al obtener arqueo: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def getAperturasSinArqueo(self, excluir_usuario=None):
        """Aperturas CERRADAS sin arqueo REGISTRADO, de la más reciente a la más antigua. `excluir_usuario`: no se listan sus propias
        cajas (nadie arquea su propia caja)."""
        sql = """
            SELECT a.id_apertura, cj.descripcion, a.id_usuario, COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido),
                   a.fecha_apertura, a.fecha_cierre, a.monto_apertura, a.total_recaudado, a.monto_cierre
            FROM apertura_cierre_caja a
            JOIN caja cj ON cj.id_caja = a.id_caja
            JOIN usuarios u ON u.id_usuario = a.id_usuario
            LEFT JOIN funcionario f ON f.id_funcionario = u.id_funcionario
            LEFT JOIN medico m ON m.id_medico = u.id_medico
            WHERE a.estado = 'CERRADA' AND NOT EXISTS (SELECT 1 FROM arqueo_caja q WHERE q.id_apertura = a.id_apertura AND q.estado = 'REGISTRADO')
        """
        params = []
        if excluir_usuario is not None:
            sql += " AND a.id_usuario <> %s"; params.append(excluir_usuario)
        sql += " ORDER BY a.fecha_cierre DESC, a.id_apertura DESC LIMIT 200"
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return [{'id_apertura': r[0], 'caja': r[1], 'id_cajero': r[2], 'cajero': r[3], 'fecha_apertura': _fecha(r[4]), 'fecha_cierre': _fecha(r[5]),
                     'monto_apertura': int(r[6]), 'total_recaudado': int(r[7]) if r[7] is not None else 0,
                     'monto_cierre': int(r[8]) if r[8] is not None else None} for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener aperturas sin arqueo: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getFormasArqueo(self, id_apertura):
        """La apertura y las formas de cobro a contar con el monto del SISTEMA (fn_formas_arqueo), o None si la apertura no existe."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""
                SELECT a.id_apertura, a.estado, a.id_usuario, cj.descripcion, COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido),
                       a.fecha_apertura, a.fecha_cierre, a.monto_apertura, fn_total_reintegros(a.id_apertura),
                       EXISTS (SELECT 1 FROM arqueo_caja q WHERE q.id_apertura = a.id_apertura AND q.estado = 'REGISTRADO')
                FROM apertura_cierre_caja a JOIN caja cj ON cj.id_caja = a.id_caja
                JOIN usuarios u ON u.id_usuario = a.id_usuario
                LEFT JOIN funcionario f ON f.id_funcionario = u.id_funcionario LEFT JOIN medico m ON m.id_medico = u.id_medico
                WHERE a.id_apertura = %s""", (id_apertura,))
            a = cur.fetchone()
            if a is None:
                return None
            cur.execute("SELECT id_forma_cobro, forma_cobro, tipo, cobrado, monto_sistema FROM fn_formas_arqueo(%s)", (id_apertura,))
            return {'id_apertura': a[0], 'estado': a[1], 'id_cajero': a[2], 'caja': a[3], 'cajero': a[4], 'fecha_apertura': _fecha(a[5]),
                    'fecha_cierre': _fecha(a[6]), 'monto_apertura': int(a[7]), 'reintegros': int(a[8]), 'tiene_arqueo': bool(a[9]),
                    'formas': [{'id_forma_cobro': r[0], 'forma_cobro': r[1], 'tipo': r[2], 'cobrado': int(r[3]), 'monto_sistema': int(r[4])}
                               for r in cur.fetchall()]}
        except Exception as e:
            app.logger.error(f"Error al obtener las formas del arqueo: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def getRecaudaciones(self, estado=None, desde=None, hasta=None, limite=500):
        """Recaudaciones a depositar, de la más reciente a la más antigua (las anuladas solo si se pide ese estado)."""
        filtros, params = [], []
        if estado:
            filtros.append("r.estado = %s"); params.append(estado)
        else:
            filtros.append("r.estado <> 'ANULADA'")
        if desde:
            filtros.append("r.fecha_generacion >= %s"); params.append(desde)
        if hasta:
            filtros.append("r.fecha_generacion < %s::date + 1"); params.append(hasta)
        sql = _SELECT_RECAUDACION + " WHERE " + " AND ".join(filtros) + " ORDER BY r.fecha_generacion DESC, r.id_recaudacion DESC LIMIT %s"
        params.append(limite)
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return [_recaudacion_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener recaudaciones: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getRecaudacionById(self, id_recaudacion):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(_SELECT_RECAUDACION + " WHERE r.id_recaudacion = %s", (id_recaudacion,))
            f = cur.fetchone()
            return _recaudacion_dict(f) if f else None
        except Exception as e:
            app.logger.error(f"Error al obtener recaudación: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ alta
    def registrarArqueo(self, id_apertura, id_usuario, formas, contados, observacion):
        """
        Registra el arqueo llamando al procedimiento sp_registrar_arqueo (una transacción: arqueo, detalle y recaudación). El monto del
        sistema lo calcula la base; este método solo manda lo contado.

        Returns:
            tuple | bool: (id_arqueo, id_recaudacion o None); (ERROR_BD, mensaje) si el procedimiento rechaza el arqueo; False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("CALL sp_registrar_arqueo(%s, %s, %s::int[], %s::numeric[], %s, NULL, NULL)",
                        (id_apertura, id_usuario, list(formas), list(contados), observacion))
            r = cur.fetchone()
            con.commit()
            return (r[0], r[1])
        except psycopg2.errors.RaiseException as e:
            con.rollback()
            return (ERROR_BD, getattr(getattr(e, 'diag', None), 'message_primary', None) or str(e).splitlines()[0])
        except Exception as e:
            app.logger.error(f"Error al registrar arqueo: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ anulación
    def anularArqueo(self, id_arqueo):
        """
        Anula un arqueo REGISTRADO y, en la misma transacción, su recaudación PENDIENTE. Si la recaudación ya fue DEPOSITADA no se anula.
        Orden de bloqueos: arqueo, recaudación (el mismo que "Marcar depositada").

        Returns:
            dict | str | bool: {'id_apertura', 'recaudacion_anulada'}; NO_EXISTE, YA_ANULADO o RECAUDACION_DEPOSITADA;
            (ERROR_BD, mensaje) si un trigger lo rechaza; False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT estado, id_apertura FROM arqueo_caja WHERE id_arqueo = %s FOR UPDATE", (id_arqueo,))
            q = cur.fetchone()
            if q is None:
                con.rollback()
                return NO_EXISTE
            if q[0] == ANULADO:
                con.rollback()
                return YA_ANULADO
            cur.execute("SELECT id_recaudacion, estado FROM recaudacion_depositar WHERE id_arqueo = %s AND estado <> 'ANULADA' FOR UPDATE", (id_arqueo,))
            r = cur.fetchone()
            if r is not None and r[1] != PENDIENTE:
                con.rollback()
                return RECAUDACION_DEPOSITADA
            if r is not None:
                cur.execute("UPDATE recaudacion_depositar SET estado = 'ANULADA' WHERE id_recaudacion = %s", (r[0],))
            cur.execute("UPDATE arqueo_caja SET estado = 'ANULADO' WHERE id_arqueo = %s", (id_arqueo,))
            con.commit()
            return {'id_apertura': q[1], 'recaudacion_anulada': r is not None}
        except psycopg2.errors.RaiseException as e:
            con.rollback()
            return (ERROR_BD, getattr(getattr(e, 'diag', None), 'message_primary', None) or str(e).splitlines()[0])
        except Exception as e:
            app.logger.error(f"Error al anular arqueo: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ marcar depositada
    def marcarDepositada(self, id_recaudacion, id_cuenta_bancaria, numero_boleta, fecha_deposito):
        """
        Marca la recaudación como DEPOSITADA: cuenta bancaria ACTIVA (FOR SHARE: una baja concurrente de la cuenta espera), número de
        boleta y fecha (no anterior a la del arqueo). Solo desde PENDIENTE y con el arqueo REGISTRADO (bloqueado FOR SHARE).

        Returns:
            bool | str | tuple: True; NO_EXISTE, CUENTA_INVALIDA, FECHA_ANTERIOR, (NO_PENDIENTE, estado) o (ERROR_BD, mensaje); False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT r.estado, q.fecha::date FROM recaudacion_depositar r JOIN arqueo_caja q ON q.id_arqueo = r.id_arqueo "
                        "WHERE r.id_recaudacion = %s FOR UPDATE OF r", (id_recaudacion,))
            r = cur.fetchone()
            if r is None:
                con.rollback()
                return NO_EXISTE
            if r[0] != PENDIENTE:
                con.rollback()
                return (NO_PENDIENTE, r[0])
            if fecha_deposito < r[1]:
                con.rollback()
                return FECHA_ANTERIOR
            cur.execute("SELECT 1 FROM cuenta_bancaria WHERE id_cuenta_bancaria = %s AND activo = true FOR SHARE", (id_cuenta_bancaria,))
            if cur.fetchone() is None:
                con.rollback()
                return CUENTA_INVALIDA
            cur.execute("""UPDATE recaudacion_depositar SET estado = 'DEPOSITADA', id_cuenta_bancaria = %s, numero_boleta = %s, fecha_deposito = %s
                           WHERE id_recaudacion = %s""", (id_cuenta_bancaria, numero_boleta, fecha_deposito, id_recaudacion))
            con.commit()
            return True
        except psycopg2.errors.RaiseException as e:
            con.rollback()
            return (ERROR_BD, getattr(getattr(e, 'diag', None), 'message_primary', None) or str(e).splitlines()[0])
        except Exception as e:
            app.logger.error(f"Error al marcar la recaudación como depositada: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
