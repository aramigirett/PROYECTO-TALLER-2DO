# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

ANULADO = 'ANULADO'
EMITIDO = 'EMITIDO'

# Códigos de resultado (además de un ID, un dict o True)
NO_EXISTE = "NO_EXISTE"
SIN_CAJA = "SIN_CAJA"
CUENTA_NO_EXISTE = "CUENTA_NO_EXISTE"
CUENTA_NO_PENDIENTE = "CUENTA_NO_PENDIENTE"   # se devuelve como (CUENTA_NO_PENDIENTE, estado_actual)
SALDO_EXCEDIDO = "SALDO_EXCEDIDO"             # se devuelve como (SALDO_EXCEDIDO, saldo)
FORMA_INVALIDA = "FORMA_INVALIDA"             # se devuelve como (FORMA_INVALIDA, fila): no existe o está inactiva
FORMA_SIN_TIPO = "FORMA_SIN_TIPO"             # se devuelve como (FORMA_SIN_TIPO, descripción)
FORMA_CAMBIO = "FORMA_CAMBIO"                 # el tipo de la forma cambió mientras se cobraba
ADHERIDA_INVALIDA = "ADHERIDA_INVALIDA"       # se devuelve como (ADHERIDA_INVALIDA, fila, motivo)
EMISORA_INVALIDA = "EMISORA_INVALIDA"         # se devuelve como (EMISORA_INVALIDA, fila)
ERROR_BD = "ERROR_BD"                         # se devuelve como (ERROR_BD, mensaje del trigger de la base)
YA_ANULADO = "YA_ANULADO"
CAJA_CERRADA = "CAJA_CERRADA"                 # la apertura del cobro ya no está ABIERTA

_SELECT = """
SELECT c.id_cobro, c.numero_recibo, c.fecha, c.total, c.estado, c.observacion,
       c.id_cuenta, v.id_venta, v.numero_factura, cl.id_cliente, cl.nombre || COALESCE(' ' || cl.apellido, ''), cl.ci_ruc,
       c.id_usuario, COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido),
       c.id_apertura, a.estado, cj.descripcion,
       cc.monto_total, cc.saldo, cc.estado,
       (SELECT string_agg(DISTINCT fc.descripcion, ', ') FROM cobro_det d
          JOIN forma_cobro fc ON fc.id_forma_cobro = d.id_forma_cobro WHERE d.id_cobro = c.id_cobro)
FROM cobro_cab c
JOIN cuenta_cobrar cc ON cc.id_cuenta = c.id_cuenta
JOIN venta_cab v ON v.id_venta = cc.id_venta
JOIN cliente cl ON cl.id_cliente = cc.id_cliente
JOIN usuarios u ON u.id_usuario = c.id_usuario
LEFT JOIN funcionario f ON f.id_funcionario = u.id_funcionario
LEFT JOIN medico m ON m.id_medico = u.id_medico
JOIN apertura_cierre_caja a ON a.id_apertura = c.id_apertura
JOIN caja cj ON cj.id_caja = a.id_caja
"""


def _fecha(valor):
    return valor.strftime('%Y-%m-%d %H:%M:%S') if valor else None


def _a_dict(f):
    return {
        'id_cobro': f[0], 'numero_recibo': f[1], 'fecha': _fecha(f[2]), 'total': int(f[3]), 'estado': f[4],
        'observacion': f[5], 'id_cuenta': f[6], 'id_venta': f[7], 'numero_factura': f[8],
        'id_cliente': f[9], 'cliente': f[10], 'ci_ruc': f[11], 'id_usuario': f[12], 'cajero': f[13],
        'id_apertura': f[14], 'estado_apertura': f[15], 'caja': f[16],
        'monto_cuenta': int(f[17]), 'saldo_cuenta': int(f[18]), 'estado_cuenta': f[19], 'formas': f[20],
    }


def _escapar_like(texto):
    return texto.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


class CobroDao:

    # ------------------------------------------------------------------ consultas
    def getCobros(self, estado=None, cliente=None, desde=None, hasta=None, limite=500):
        """Cobros, del más reciente al más antiguo. `cliente` busca por nombre, CI/RUC, N.º de factura o N.º de recibo."""
        filtros, params = [], []
        if estado:
            filtros.append("c.estado = %s"); params.append(estado)
        if cliente:
            filtros.append("((cl.nombre || COALESCE(' ' || cl.apellido, '')) ILIKE %s OR cl.ci_ruc ILIKE %s "
                           "OR v.numero_factura ILIKE %s OR c.numero_recibo ILIKE %s)")
            patron = '%' + _escapar_like(cliente.strip()) + '%'
            params += [patron, patron, patron, patron]
        if desde:
            filtros.append("c.fecha >= %s"); params.append(desde)
        if hasta:
            filtros.append("c.fecha < %s::date + 1"); params.append(hasta)
        where = (" WHERE " + " AND ".join(filtros)) if filtros else ""
        sql = _SELECT + where + " ORDER BY c.fecha DESC, c.id_cobro DESC LIMIT %s"
        params.append(limite)
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return [_a_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener cobros: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getCobroById(self, id_cobro):
        """Cobro con el detalle por forma de cobro (y sus datos de tarjeta o cheque), o None."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(_SELECT + " WHERE c.id_cobro = %s", (id_cobro,))
            f = cur.fetchone()
            if f is None:
                return None
            cobro = _a_dict(f)
            cur.execute("""
                SELECT d.id_cobro_det, d.id_forma_cobro, fc.descripcion, fc.tipo, d.monto, d.numero_referencia,
                       t.tipo_tarjeta, t.ultimos_digitos, t.numero_autorizacion, ea.descripcion, mt.descripcion, em.descripcion,
                       ch.numero_cheque, ch.titular, ch.fecha_emision, ch.fecha_cobro, emc.descripcion
                FROM cobro_det d
                JOIN forma_cobro fc ON fc.id_forma_cobro = d.id_forma_cobro
                LEFT JOIN cobro_tarjeta t ON t.id_cobro_det = d.id_cobro_det
                LEFT JOIN entidad_adherida ea ON ea.id_entidad_adherida = t.id_entidad_adherida
                LEFT JOIN marca_tarjeta mt ON mt.id_marca_tarjeta = ea.id_marca_tarjeta
                LEFT JOIN entidad_emisora em ON em.id_entidad_emisora = ea.id_entidad_emisora
                LEFT JOIN cobro_cheque ch ON ch.id_cobro_det = d.id_cobro_det
                LEFT JOIN entidad_emisora emc ON emc.id_entidad_emisora = ch.id_entidad_emisora
                WHERE d.id_cobro = %s ORDER BY d.id_cobro_det
            """, (id_cobro,))
            cobro['detalle'] = []
            for r in cur.fetchall():
                d = {'id_cobro_det': r[0], 'id_forma_cobro': r[1], 'forma_cobro': r[2], 'tipo': r[3], 'monto': int(r[4]),
                     'numero_referencia': r[5], 'tarjeta': None, 'cheque': None}
                if r[6] is not None:
                    d['tarjeta'] = {'tipo_tarjeta': r[6], 'ultimos_digitos': r[7], 'numero_autorizacion': r[8],
                                    'entidad_adherida': r[9], 'marca': r[10], 'emisora': r[11]}
                if r[12] is not None:
                    d['cheque'] = {'numero_cheque': r[12], 'titular': r[13], 'fecha_emision': r[14].strftime('%Y-%m-%d'),
                                   'fecha_cobro': r[15].strftime('%Y-%m-%d'), 'emisora': r[16]}
                cobro['detalle'].append(d)
            # saldo de la factura DESPUÉS de este cobro (cobros EMITIDOS de la cuenta hasta este inclusive), para el recibo
            cur.execute("SELECT COALESCE(SUM(total), 0) FROM cobro_cab WHERE id_cuenta = %s AND estado = 'EMITIDO' AND id_cobro <= %s",
                        (cobro['id_cuenta'], id_cobro))
            cobro['saldo_despues'] = cobro['monto_cuenta'] - int(cur.fetchone()[0])
            cur.execute("SELECT razon_social, ruc, direccion, telefono, actividad_economica FROM empresa LIMIT 1")
            e = cur.fetchone()
            cobro['empresa'] = ({'razon_social': e[0], 'ruc': e[1], 'direccion': e[2], 'telefono': e[3],
                                 'actividad_economica': e[4]} if e else None)
            return cobro
        except Exception as e:
            app.logger.error(f"Error al obtener cobro: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def getAperturaActual(self, id_usuario):
        """La apertura ABIERTA del cajero (con su caja), o None."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""
                SELECT a.id_apertura, cj.descripcion, a.fecha_apertura
                FROM apertura_cierre_caja a JOIN caja cj ON cj.id_caja = a.id_caja
                WHERE a.id_usuario = %s AND a.estado = 'ABIERTA'
            """, (id_usuario,))
            f = cur.fetchone()
            return {'id_apertura': f[0], 'caja': f[1], 'fecha_apertura': _fecha(f[2])} if f else None
        except Exception as e:
            app.logger.error(f"Error al obtener la apertura actual: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    _SELECT_CUENTA = """
        SELECT cc.id_cuenta, v.id_venta, v.numero_factura, v.fecha, v.condicion, cl.id_cliente,
               cl.nombre || COALESCE(' ' || cl.apellido, ''), cl.ci_ruc, cc.monto_total, cc.saldo, cc.fecha_vencimiento,
               cc.estado, v.estado
        FROM cuenta_cobrar cc
        JOIN venta_cab v ON v.id_venta = cc.id_venta
        JOIN cliente cl ON cl.id_cliente = cc.id_cliente
    """

    @staticmethod
    def _cuenta_dict(f):
        return {'id_cuenta': f[0], 'id_venta': f[1], 'numero_factura': f[2], 'fecha_venta': _fecha(f[3]), 'condicion': f[4],
                'id_cliente': f[5], 'cliente': f[6], 'ci_ruc': f[7], 'monto_total': int(f[8]), 'saldo': int(f[9]),
                'fecha_vencimiento': f[10].strftime('%Y-%m-%d'), 'estado': f[11], 'estado_venta': f[12]}

    def buscarCuentas(self, q, limite=30):
        """Cuentas a cobrar PENDIENTES con saldo, por cliente (nombre o CI/RUC) o N.º de factura; las más vencidas primero."""
        patron = '%' + _escapar_like((q or '').strip()) + '%'
        sql = self._SELECT_CUENTA + """
            WHERE cc.estado = 'PENDIENTE' AND cc.saldo > 0 AND v.estado = 'EMITIDA'
              AND ((cl.nombre || COALESCE(' ' || cl.apellido, '')) ILIKE %s OR cl.ci_ruc ILIKE %s OR v.numero_factura ILIKE %s)
            ORDER BY cc.fecha_vencimiento, cc.id_cuenta LIMIT %s"""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (patron, patron, patron, limite))
            return [self._cuenta_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al buscar cuentas a cobrar: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getCuentaById(self, id_cuenta):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(self._SELECT_CUENTA + " WHERE cc.id_cuenta = %s", (id_cuenta,))
            f = cur.fetchone()
            return self._cuenta_dict(f) if f else None
        except Exception as e:
            app.logger.error(f"Error al obtener la cuenta a cobrar: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def getFormasCobro(self):
        """Formas de cobro ACTIVAS con tipo asignado (las demás no se pueden usar)."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_forma_cobro, descripcion, tipo FROM forma_cobro WHERE activo = true AND tipo IS NOT NULL ORDER BY descripcion")
            return [{'id_forma_cobro': f[0], 'descripcion': f[1], 'tipo': f[2]} for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener formas de cobro: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getFormasPorIds(self, ids):
        """{id: {'descripcion', 'tipo', 'activo'}} para validar el cuerpo del pedido (lectura, sin bloqueo)."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_forma_cobro, descripcion, tipo, activo FROM forma_cobro WHERE id_forma_cobro = ANY(%s)", (list(ids),))
            return {f[0]: {'descripcion': f[1], 'tipo': f[2], 'activo': f[3]} for f in cur.fetchall()}
        except Exception as e:
            app.logger.error(f"Error al leer formas de cobro: {str(e)}")
            return {}
        finally:
            cur.close()
            con.close()

    def getAdheridas(self):
        """Entidades adheridas ACTIVAS cuya marca y emisora también están activas, con sus nombres."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""
                SELECT ea.id_entidad_adherida, ea.descripcion, mt.descripcion, em.descripcion
                FROM entidad_adherida ea
                JOIN marca_tarjeta mt ON mt.id_marca_tarjeta = ea.id_marca_tarjeta AND mt.activo = true
                JOIN entidad_emisora em ON em.id_entidad_emisora = ea.id_entidad_emisora AND em.activo = true
                WHERE ea.activo = true ORDER BY ea.descripcion, mt.descripcion, em.descripcion""")
            return [{'id_entidad_adherida': f[0], 'descripcion': f[1], 'marca': f[2], 'emisora': f[3]} for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener entidades adheridas: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getEmisoras(self):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_entidad_emisora, descripcion FROM entidad_emisora WHERE activo = true ORDER BY descripcion")
            return [{'id_entidad_emisora': f[0], 'descripcion': f[1]} for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener entidades emisoras: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ alta
    def guardarCobro(self, id_usuario, id_cuenta, observacion, formas):
        """
        Registra un cobro en UNA transacción. `formas` = lista de dicts ya validados por la API:
        {'id_forma_cobro', 'tipo', 'monto', 'numero_referencia', 'tarjeta': {...}|None, 'cheque': {...}|None}.
          1. apertura ABIERTA del cajero (FOR SHARE: un cierre concurrente espera);
          2. cuenta a cobrar (FOR UPDATE): debe estar PENDIENTE y el total no puede superar el saldo;
          3. formas de cobro (FOR SHARE, en orden de id): activas y con el mismo tipo que la API validó; tarjeta: adherida,
             marca y emisora activas; cheque: emisora activa;
          4. número de recibo (fn_siguiente_numero_recibo), cabecera (el trigger trg_aplicar_cobro descuenta el saldo),
             detalle y datos de tarjeta/cheque. Al confirmar, trg_validar_cobro verifica suma = total y datos completos.

        Returns:
            int | str | tuple | bool: ID del cobro; SIN_CAJA, CUENTA_NO_EXISTE, FORMA_CAMBIO, (CUENTA_NO_PENDIENTE, estado),
            (SALDO_EXCEDIDO, saldo), (FORMA_INVALIDA, fila), (FORMA_SIN_TIPO, descripción), (ADHERIDA_INVALIDA, fila, motivo),
            (EMISORA_INVALIDA, fila) o (ERROR_BD, mensaje); False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_apertura FROM apertura_cierre_caja WHERE id_usuario = %s AND estado = 'ABIERTA' FOR SHARE", (id_usuario,))
            apertura = cur.fetchone()
            if apertura is None:
                con.rollback()
                return SIN_CAJA

            cur.execute("SELECT estado, saldo FROM cuenta_cobrar WHERE id_cuenta = %s FOR UPDATE", (id_cuenta,))
            cuenta = cur.fetchone()
            if cuenta is None:
                con.rollback()
                return CUENTA_NO_EXISTE
            if cuenta[0] != 'PENDIENTE':
                con.rollback()
                return (CUENTA_NO_PENDIENTE, cuenta[0])
            total = sum(f['monto'] for f in formas)
            if total > int(cuenta[1]):
                con.rollback()
                return (SALDO_EXCEDIDO, int(cuenta[1]))

            # formas de cobro: bloqueo compartido en orden de id (una baja o cambio de tipo concurrente espera)
            ids_forma = sorted({f['id_forma_cobro'] for f in formas})
            cur.execute("SELECT id_forma_cobro, activo, tipo, descripcion FROM forma_cobro WHERE id_forma_cobro = ANY(%s) "
                        "ORDER BY id_forma_cobro FOR SHARE", (ids_forma,))
            vigentes = {r[0]: r for r in cur.fetchall()}
            for n, f in enumerate(formas, start=1):
                v = vigentes.get(f['id_forma_cobro'])
                if v is None or not v[1]:
                    con.rollback()
                    return (FORMA_INVALIDA, n)
                if v[2] is None:
                    con.rollback()
                    return (FORMA_SIN_TIPO, v[3])
                if v[2] != f['tipo']:
                    con.rollback()
                    return FORMA_CAMBIO

            for n, f in enumerate(formas, start=1):
                if f['tarjeta']:
                    cur.execute("""
                        SELECT ea.activo, mt.activo, em.activo
                        FROM entidad_adherida ea
                        JOIN marca_tarjeta mt ON mt.id_marca_tarjeta = ea.id_marca_tarjeta
                        JOIN entidad_emisora em ON em.id_entidad_emisora = ea.id_entidad_emisora
                        WHERE ea.id_entidad_adherida = %s FOR SHARE OF ea, mt, em""", (f['tarjeta']['id_entidad_adherida'],))
                    r = cur.fetchone()
                    if r is None:
                        con.rollback()
                        return (ADHERIDA_INVALIDA, n, 'adherida')
                    if not r[0]:
                        con.rollback()
                        return (ADHERIDA_INVALIDA, n, 'adherida')
                    if not r[1]:
                        con.rollback()
                        return (ADHERIDA_INVALIDA, n, 'marca')
                    if not r[2]:
                        con.rollback()
                        return (ADHERIDA_INVALIDA, n, 'emisora')
                if f['cheque']:
                    cur.execute("SELECT activo FROM entidad_emisora WHERE id_entidad_emisora = %s FOR SHARE",
                                (f['cheque']['id_entidad_emisora'],))
                    r = cur.fetchone()
                    if r is None or not r[0]:
                        con.rollback()
                        return (EMISORA_INVALIDA, n)

            cur.execute("SELECT fn_siguiente_numero_recibo()")
            numero = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO cobro_cab(id_cuenta, id_apertura, id_usuario, numero_recibo, total, observacion)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id_cobro
            """, (id_cuenta, apertura[0], id_usuario, numero, total, observacion))
            id_cobro = cur.fetchone()[0]
            for f in formas:
                cur.execute("""INSERT INTO cobro_det(id_cobro, id_forma_cobro, monto, numero_referencia)
                               VALUES (%s, %s, %s, %s) RETURNING id_cobro_det""",
                            (id_cobro, f['id_forma_cobro'], f['monto'], f['numero_referencia']))
                id_det = cur.fetchone()[0]
                if f['tarjeta']:
                    t = f['tarjeta']
                    cur.execute("""INSERT INTO cobro_tarjeta(id_cobro_det, id_entidad_adherida, tipo_tarjeta, ultimos_digitos, numero_autorizacion)
                                   VALUES (%s, %s, %s, %s, %s)""",
                                (id_det, t['id_entidad_adherida'], t['tipo_tarjeta'], t['ultimos_digitos'], t['numero_autorizacion']))
                if f['cheque']:
                    c = f['cheque']
                    cur.execute("""INSERT INTO cobro_cheque(id_cobro_det, id_entidad_emisora, numero_cheque, titular, fecha_emision, fecha_cobro)
                                   VALUES (%s, %s, %s, %s, %s, %s)""",
                                (id_det, c['id_entidad_emisora'], c['numero_cheque'], c['titular'], c['fecha_emision'], c['fecha_cobro']))
            con.commit()   # acá corre el trigger diferido trg_validar_cobro
            return id_cobro
        except psycopg2.errors.RaiseException as e:
            con.rollback()
            return (ERROR_BD, getattr(getattr(e, 'diag', None), 'message_primary', None) or str(e).splitlines()[0])
        except Exception as e:
            app.logger.error(f"Error al guardar cobro: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ anulación
    def anularCobro(self, id_cobro):
        """
        Anula un cobro EMITIDO. Solo si su apertura de caja sigue ABIERTA (FOR SHARE: un cierre concurrente espera). El
        trigger trg_aplicar_cobro repone el saldo y la cuenta vuelve a PENDIENTE. Orden de bloqueos: cobro, apertura, cuenta.

        Returns:
            dict | str | bool: {'numero_recibo', 'total'}; NO_EXISTE, YA_ANULADO o CAJA_CERRADA; (ERROR_BD, mensaje) si el
            trigger lo rechaza; False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT estado, id_apertura, numero_recibo, total, id_cuenta FROM cobro_cab WHERE id_cobro = %s FOR UPDATE", (id_cobro,))
            cobro = cur.fetchone()
            if cobro is None:
                con.rollback()
                return NO_EXISTE
            if cobro[0] == ANULADO:
                con.rollback()
                return YA_ANULADO
            cur.execute("SELECT estado FROM apertura_cierre_caja WHERE id_apertura = %s FOR SHARE", (cobro[1],))
            if cur.fetchone()[0] != 'ABIERTA':
                con.rollback()
                return CAJA_CERRADA
            cur.execute("UPDATE cobro_cab SET estado = 'ANULADO' WHERE id_cobro = %s", (id_cobro,))
            con.commit()
            return {'numero_recibo': cobro[2], 'total': int(cobro[3])}
        except psycopg2.errors.RaiseException as e:
            con.rollback()
            return (ERROR_BD, getattr(getattr(e, 'diag', None), 'message_primary', None) or str(e).splitlines()[0])
        except Exception as e:
            app.logger.error(f"Error al anular cobro: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
