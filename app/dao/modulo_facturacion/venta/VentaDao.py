# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion
from app.dao.modulo_facturacion.pedido_cliente.PedidoClienteDao import calcular_totales

EMITIDA = 'EMITIDA'
ANULADA = 'ANULADA'
CONTADO = 'CONTADO'
CREDITO = 'CREDITO'

# Códigos de resultado (además de un ID, un dict o True)
NO_EXISTE = "NO_EXISTE"
SIN_CAJA = "SIN_CAJA"                      # el cajero no tiene una apertura ABIERTA
PEDIDO_NO_EXISTE = "PEDIDO_NO_EXISTE"
PEDIDO_NO_PENDIENTE = "PEDIDO_NO_PENDIENTE"  # se devuelve como (PEDIDO_NO_PENDIENTE, estado_actual)
ERROR_TIMBRADO = "ERROR_TIMBRADO"          # se devuelve como (ERROR_TIMBRADO, mensaje del procedimiento almacenado)
YA_ANULADA = "YA_ANULADA"
CAJA_CERRADA = "CAJA_CERRADA"              # la apertura de la venta ya no está ABIERTA

MSG_ANULAR_CON_COBROS = "No es posible anular, existen cobros registrados. Utilice una Nota de Crédito."

_SELECT = """
SELECT v.id_venta, v.numero_factura, v.fecha, v.id_cliente, c.nombre || COALESCE(' ' || c.apellido, ''), c.ci_ruc,
       v.id_usuario, COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido),
       v.tipo_venta, v.condicion, v.id_pedido,
       v.total_exenta, v.total_gravada_5, v.total_gravada_10, v.iva_5, v.iva_10, v.total, v.estado,
       v.id_apertura, a.estado, cj.descripcion,
       cc.estado, cc.saldo, cc.fecha_vencimiento
FROM venta_cab v
JOIN cliente c ON c.id_cliente = v.id_cliente
JOIN usuarios u ON u.id_usuario = v.id_usuario
LEFT JOIN funcionario f ON f.id_funcionario = u.id_funcionario
LEFT JOIN medico m ON m.id_medico = u.id_medico
JOIN apertura_cierre_caja a ON a.id_apertura = v.id_apertura
JOIN caja cj ON cj.id_caja = a.id_caja
LEFT JOIN cuenta_cobrar cc ON cc.id_venta = v.id_venta
"""


def _fecha(valor):
    return valor.strftime('%Y-%m-%d %H:%M:%S') if valor else None


def _a_dict(f):
    return {
        'id_venta': f[0], 'numero_factura': f[1], 'fecha': _fecha(f[2]),
        'id_cliente': f[3], 'cliente': f[4], 'ci_ruc': f[5],
        'id_usuario': f[6], 'cajero': f[7],
        'tipo_venta': f[8], 'condicion': f[9], 'id_pedido': f[10],
        'total_exenta': int(f[11]), 'total_gravada_5': int(f[12]), 'total_gravada_10': int(f[13]),
        'iva_5': int(f[14]), 'iva_10': int(f[15]), 'total': int(f[16]), 'estado': f[17],
        'id_apertura': f[18], 'estado_apertura': f[19], 'caja': f[20],
        'estado_cuenta': f[21], 'saldo': int(f[22]) if f[22] is not None else None,
        'fecha_vencimiento': f[23].strftime('%Y-%m-%d') if f[23] else None,
    }


def _escapar_like(texto):
    return texto.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


class VentaDao:

    # ------------------------------------------------------------------ consultas
    def getVentas(self, estado=None, cliente=None, desde=None, hasta=None, tipo=None, limite=500):
        """Ventas, de la más reciente a la más antigua. `desde`/`hasta` son date, ambos inclusive."""
        filtros, params = [], []
        if estado:
            filtros.append("v.estado = %s"); params.append(estado)
        if tipo:
            filtros.append("v.tipo_venta = %s"); params.append(tipo)
        if cliente:
            filtros.append("((c.nombre || COALESCE(' ' || c.apellido, '')) ILIKE %s OR c.ci_ruc ILIKE %s OR v.numero_factura ILIKE %s)")
            patron = '%' + _escapar_like(cliente.strip()) + '%'
            params += [patron, patron, patron]
        if desde:
            filtros.append("v.fecha >= %s"); params.append(desde)
        if hasta:
            filtros.append("v.fecha < %s::date + 1"); params.append(hasta)
        where = (" WHERE " + " AND ".join(filtros)) if filtros else ""
        sql = _SELECT + where + " ORDER BY v.fecha DESC, v.id_venta DESC LIMIT %s"
        params.append(limite)

        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return [_a_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener ventas: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getVentaById(self, id_venta):
        """Venta con su detalle, totales, datos de la empresa y del timbrado (para el comprobante), o None."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(_SELECT + " WHERE v.id_venta = %s", (id_venta,))
            f = cur.fetchone()
            if f is None:
                return None
            venta = _a_dict(f)
            cur.execute("""
                SELECT id_venta_det, id_item, id_tratamiento, descripcion, cantidad, precio_unitario, iva, subtotal
                FROM venta_det WHERE id_venta = %s ORDER BY id_venta_det
            """, (id_venta,))
            venta['detalle'] = [{
                'id_venta_det': r[0], 'id_item': r[1], 'id_tratamiento': r[2], 'descripcion': r[3],
                'cantidad': r[4], 'precio_unitario': int(r[5]), 'iva': r[6], 'subtotal': int(r[7])
            } for r in cur.fetchall()]
            venta['totales'] = calcular_totales(venta['detalle'])
            cur.execute("""
                SELECT t.numero_timbrado, t.fecha_inicio, t.fecha_fin, t.establecimiento, t.punto_expedicion
                FROM timbrado t JOIN venta_cab v ON v.id_timbrado = t.id_timbrado WHERE v.id_venta = %s
            """, (id_venta,))
            t = cur.fetchone()
            venta['timbrado'] = {'numero': t[0], 'vigencia_desde': t[1].strftime('%Y-%m-%d'),
                                 'vigencia_hasta': t[2].strftime('%Y-%m-%d'), 'establecimiento': t[3],
                                 'punto_expedicion': t[4]}
            cur.execute("SELECT razon_social, ruc, direccion, telefono, actividad_economica FROM empresa LIMIT 1")
            e = cur.fetchone()
            venta['empresa'] = ({'razon_social': e[0], 'ruc': e[1], 'direccion': e[2], 'telefono': e[3],
                                 'actividad_economica': e[4]} if e else None)
            return venta
        except Exception as e:
            app.logger.error(f"Error al obtener venta: {str(e)}")
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

    def buscarPedidosPendientes(self, q, limite=20):
        """Pedidos PENDIENTES por N.º de pedido, nombre o CI/RUC del cliente."""
        q = (q or '').strip()
        patron = '%' + _escapar_like(q) + '%'
        sql = """
        SELECT p.id_pedido, c.nombre || COALESCE(' ' || c.apellido, ''), c.ci_ruc, p.fecha_pedido, p.total
        FROM pedido_venta_cab p JOIN cliente c ON c.id_cliente = p.id_cliente
        WHERE p.estado = 'PENDIENTE'
          AND (%s = '' OR p.id_pedido::text = %s OR (c.nombre || COALESCE(' ' || c.apellido, '')) ILIKE %s OR c.ci_ruc ILIKE %s)
        ORDER BY (p.id_pedido::text = %s) DESC, p.fecha_pedido DESC, p.id_pedido DESC
        LIMIT %s
        """
        # Un número puede ser el N.º del pedido o parte de una CI/RUC: el pedido con ese N.º exacto va primero.
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (q, q.lstrip('#'), patron, patron, q.lstrip('#'), limite))
            return [{'id_pedido': f[0], 'cliente': f[1], 'ci_ruc': f[2], 'fecha_pedido': _fecha(f[3]), 'total': int(f[4])}
                    for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al buscar pedidos pendientes: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ alta
    def guardarVentaItems(self, id_usuario, id_pedido, condicion):
        """
        Factura un pedido PENDIENTE en una sola transacción:
          1. la apertura ABIERTA del cajero (FOR SHARE: un cierre/anulación de la apertura concurrente espera);
          2. el pedido (FOR UPDATE: mismo bloqueo que anular el pedido), que debe estar PENDIENTE;
          3. número de factura con sp_siguiente_numero_factura (si algo falla después, el número se deshace);
          4. cabecera + detalle copiados del pedido (precio e IVA del pedido), totales calculados acá;
          5. el pedido pasa a FACTURADO. El trigger trg_generar_cuenta_cobrar crea la cuenta a cobrar.

        Returns:
            int | str | tuple | bool: ID de la venta; SIN_CAJA, PEDIDO_NO_EXISTE, (PEDIDO_NO_PENDIENTE, estado) o
            (ERROR_TIMBRADO, mensaje); False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_apertura FROM apertura_cierre_caja WHERE id_usuario = %s AND estado = 'ABIERTA' FOR SHARE",
                        (id_usuario,))
            apertura = cur.fetchone()
            if apertura is None:
                con.rollback()
                return SIN_CAJA

            cur.execute("SELECT id_cliente, estado FROM pedido_venta_cab WHERE id_pedido = %s FOR UPDATE", (id_pedido,))
            pedido = cur.fetchone()
            if pedido is None:
                con.rollback()
                return PEDIDO_NO_EXISTE
            if pedido[1] != 'PENDIENTE':
                con.rollback()
                return (PEDIDO_NO_PENDIENTE, pedido[1])

            cur.execute("""
                SELECT d.id_item, i.descripcion, d.cantidad, d.precio_unitario, d.iva, d.subtotal
                FROM pedido_venta_det d JOIN items i ON i.id_item = d.id_item
                WHERE d.id_pedido = %s ORDER BY d.id_pedido_det
            """, (id_pedido,))
            renglones = cur.fetchall()
            totales = calcular_totales([{'iva': r[4], 'subtotal': r[5]} for r in renglones])

            try:
                cur.execute("CALL sp_siguiente_numero_factura(NULL, NULL)")
                id_timbrado, numero = cur.fetchone()
            except psycopg2.errors.RaiseException as e:
                con.rollback()
                return (ERROR_TIMBRADO, getattr(getattr(e, 'diag', None), 'message_primary', None) or str(e).splitlines()[0])

            cur.execute("""
                INSERT INTO venta_cab(id_apertura, id_cliente, id_usuario, id_timbrado, numero_factura, tipo_venta,
                                      id_pedido, condicion, total_exenta, total_gravada_5, total_gravada_10,
                                      iva_5, iva_10, total)
                VALUES (%s, %s, %s, %s, %s, 'ITEMS', %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_venta
            """, (apertura[0], pedido[0], id_usuario, id_timbrado, numero, id_pedido, condicion,
                  totales['exentas'], totales['gravadas_5'], totales['gravadas_10'],
                  totales['iva_5'], totales['iva_10'], totales['total']))
            id_venta = cur.fetchone()[0]
            for id_item, descripcion, cantidad, precio, iva, subtotal in renglones:
                cur.execute("""
                    INSERT INTO venta_det(id_venta, id_item, descripcion, cantidad, precio_unitario, iva, subtotal)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (id_venta, id_item, descripcion, cantidad, precio, iva, subtotal))
            cur.execute("UPDATE pedido_venta_cab SET estado = 'FACTURADO' WHERE id_pedido = %s", (id_pedido,))
            con.commit()
            return id_venta
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return (PEDIDO_NO_PENDIENTE, 'FACTURADO')   # ux_venta_pedido_emitida: otro cajero lo facturó antes
        except Exception as e:
            app.logger.error(f"Error al guardar venta de ítems: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ anulación
    def _motivo_con_cobros(self, cur, id_venta):
        """Devuelve el motivo (texto) si la cuenta de la venta tiene cobros, o False."""
        # TODO: debe consultar los cobros de la cuenta a cobrar (cobro_cabecera / cobro_detalle) cuando existan esas
        # tablas y devolver MSG_ANULAR_CON_COBROS. Mientras tanto no hay cobros posibles.
        return False

    def anularVenta(self, id_venta):
        """
        Anula una venta EMITIDA. Solo si la apertura de caja de la venta sigue ABIERTA (FOR SHARE: un cierre
        concurrente espera) y sin cobros. La venta pasa a ANULADA (el número NO se reutiliza), el trigger
        trg_anular_cuenta_cobrar anula la cuenta y el pedido vuelve a PENDIENTE (se puede volver a facturar).

        Returns:
            dict | str | tuple | bool: {'id_pedido', 'numero_factura'}; NO_EXISTE, YA_ANULADA, CAJA_CERRADA o
            ("EN_USO", motivo); False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT estado, id_apertura, id_pedido, numero_factura FROM venta_cab WHERE id_venta = %s FOR UPDATE",
                        (id_venta,))
            venta = cur.fetchone()
            if venta is None:
                con.rollback()
                return NO_EXISTE
            if venta[0] == ANULADA:
                con.rollback()
                return YA_ANULADA

            cur.execute("SELECT estado FROM apertura_cierre_caja WHERE id_apertura = %s FOR SHARE", (venta[1],))
            if cur.fetchone()[0] != 'ABIERTA':
                con.rollback()
                return CAJA_CERRADA

            motivo = self._motivo_con_cobros(cur, id_venta)
            if motivo:
                con.rollback()
                return ("EN_USO", motivo)

            cur.execute("UPDATE venta_cab SET estado = 'ANULADA' WHERE id_venta = %s", (id_venta,))
            if venta[2] is not None:
                cur.execute("UPDATE pedido_venta_cab SET estado = 'PENDIENTE' WHERE id_pedido = %s AND estado = 'FACTURADO'",
                            (venta[2],))
            con.commit()
            return {'id_pedido': venta[2], 'numero_factura': venta[3]}
        except Exception as e:
            app.logger.error(f"Error al anular venta: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
