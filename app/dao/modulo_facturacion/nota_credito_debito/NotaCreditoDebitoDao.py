# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion
from app.dao.modulo_facturacion.pedido_cliente.PedidoClienteDao import calcular_totales

EMITIDA = 'EMITIDA'
ANULADA = 'ANULADA'
CREDITO = 'CREDITO'
DEBITO = 'DEBITO'

# Códigos de resultado (además de un ID o un dict)
NO_EXISTE = "NO_EXISTE"
SIN_CAJA = "SIN_CAJA"
CUENTA_NO_EXISTE = "CUENTA_NO_EXISTE"
VENTA_NO_EMITIDA = "VENTA_NO_EMITIDA"       # la venta está anulada
VENTA_NO_ITEMS = "VENTA_NO_ITEMS"           # la devolución de mercadería solo aplica a ventas de ítems
ITEM_INVALIDO = "ITEM_INVALIDO"             # se devuelve como (ITEM_INVALIDO, id_item): no está en la factura
ERROR_BD = "ERROR_BD"                       # se devuelve como (ERROR_BD, mensaje del trigger de la base)
YA_ANULADA = "YA_ANULADA"
CAJA_CERRADA = "CAJA_CERRADA"               # la apertura de la nota ya no está ABIERTA
STOCK_INSUFICIENTE = "STOCK_INSUFICIENTE"   # se devuelve como (STOCK_INSUFICIENTE, ítem, disponible, a deshacer)

_SELECT = """
SELECT n.id_nota, n.numero_nota, n.tipo_nota, n.fecha, n.motivo, n.total_exenta, n.total_gravada_5, n.total_gravada_10,
       n.iva_5, n.iva_10, n.total, n.estado, n.monto_reintegro,
       n.id_cuenta, v.id_venta, v.numero_factura, v.fecha, v.tipo_venta, v.total,
       cl.id_cliente, cl.nombre || COALESCE(' ' || cl.apellido, ''), cl.ci_ruc,
       n.id_usuario, COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido),
       n.id_apertura, a.estado, cj.descripcion, n.id_timbrado,
       EXISTS (SELECT 1 FROM nota_credito_debito_det d WHERE d.id_nota = n.id_nota AND d.id_item IS NOT NULL)
FROM nota_credito_debito_cab n
JOIN cuenta_cobrar cc ON cc.id_cuenta = n.id_cuenta
JOIN venta_cab v ON v.id_venta = cc.id_venta
JOIN cliente cl ON cl.id_cliente = cc.id_cliente
JOIN usuarios u ON u.id_usuario = n.id_usuario
LEFT JOIN funcionario f ON f.id_funcionario = u.id_funcionario
LEFT JOIN medico m ON m.id_medico = u.id_medico
JOIN apertura_cierre_caja a ON a.id_apertura = n.id_apertura
JOIN caja cj ON cj.id_caja = a.id_caja
"""


def _fecha(valor, con_hora=True):
    return valor.strftime('%Y-%m-%d %H:%M:%S' if con_hora else '%Y-%m-%d') if valor else None


def _a_dict(f):
    return {
        'id_nota': f[0], 'numero_nota': f[1], 'tipo_nota': f[2], 'fecha': _fecha(f[3]), 'motivo': f[4],
        'total_exenta': int(f[5]), 'total_gravada_5': int(f[6]), 'total_gravada_10': int(f[7]),
        'iva_5': int(f[8]), 'iva_10': int(f[9]), 'total': int(f[10]), 'estado': f[11], 'monto_reintegro': int(f[12]),
        'id_cuenta': f[13], 'id_venta': f[14], 'numero_factura': f[15], 'fecha_factura': _fecha(f[16]), 'tipo_venta': f[17],
        'total_factura': int(f[18]), 'id_cliente': f[19], 'cliente': f[20], 'ci_ruc': f[21],
        'id_usuario': f[22], 'cajero': f[23], 'id_apertura': f[24], 'estado_apertura': f[25], 'caja': f[26],
        'id_timbrado': f[27], 'es_devolucion': bool(f[28]),
    }


def _escapar_like(texto):
    return texto.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


class NotaCreditoDebitoDao:

    # ------------------------------------------------------------------ consultas
    def getNotas(self, estado=None, tipo=None, cliente=None, desde=None, hasta=None, limite=500):
        """Notas, de la más reciente a la más antigua. `cliente` busca por nombre, CI/RUC, N.º de factura o N.º de nota."""
        filtros, params = [], []
        if estado:
            filtros.append("n.estado = %s"); params.append(estado)
        if tipo:
            filtros.append("n.tipo_nota = %s"); params.append(tipo)
        if cliente:
            filtros.append("((cl.nombre || COALESCE(' ' || cl.apellido, '')) ILIKE %s OR cl.ci_ruc ILIKE %s "
                           "OR v.numero_factura ILIKE %s OR n.numero_nota ILIKE %s)")
            patron = '%' + _escapar_like(cliente.strip()) + '%'
            params += [patron, patron, patron, patron]
        if desde:
            filtros.append("n.fecha >= %s"); params.append(desde)
        if hasta:
            filtros.append("n.fecha < %s::date + 1"); params.append(hasta)
        where = (" WHERE " + " AND ".join(filtros)) if filtros else ""
        sql = _SELECT + where + " ORDER BY n.fecha DESC, n.id_nota DESC LIMIT %s"
        params.append(limite)
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return [_a_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener notas: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getNotaById(self, id_nota):
        """Nota con su detalle, empresa y timbrado (para el comprobante), o None."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(_SELECT + " WHERE n.id_nota = %s", (id_nota,))
            f = cur.fetchone()
            if f is None:
                return None
            nota = _a_dict(f)
            cur.execute("""SELECT id_nota_det, id_item, descripcion, cantidad, precio_unitario, iva, subtotal
                           FROM nota_credito_debito_det WHERE id_nota = %s ORDER BY id_nota_det""", (id_nota,))
            nota['detalle'] = [{'id_nota_det': r[0], 'id_item': r[1], 'descripcion': r[2], 'cantidad': r[3],
                                'precio_unitario': int(r[4]), 'iva': r[5], 'subtotal': int(r[6])} for r in cur.fetchall()]
            nota['totales'] = calcular_totales(nota['detalle'])
            cur.execute("SELECT numero_timbrado, fecha_inicio, fecha_fin FROM timbrado WHERE id_timbrado = %s", (nota['id_timbrado'],))
            t = cur.fetchone()
            nota['timbrado'] = {'numero': t[0], 'vigencia_desde': t[1].strftime('%Y-%m-%d'), 'vigencia_hasta': t[2].strftime('%Y-%m-%d')}
            cur.execute("SELECT razon_social, ruc, direccion, telefono, actividad_economica FROM empresa LIMIT 1")
            e = cur.fetchone()
            nota['empresa'] = ({'razon_social': e[0], 'ruc': e[1], 'direccion': e[2], 'telefono': e[3],
                                'actividad_economica': e[4]} if e else None)
            return nota
        except Exception as e:
            app.logger.error(f"Error al obtener nota: {str(e)}")
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
                SELECT a.id_apertura, cj.descripcion, a.fecha_apertura,
                       a.monto_apertura + fn_total_efectivo_apertura(a.id_apertura)
                FROM apertura_cierre_caja a JOIN caja cj ON cj.id_caja = a.id_caja
                WHERE a.id_usuario = %s AND a.estado = 'ABIERTA'
            """, (id_usuario,))
            f = cur.fetchone()
            return ({'id_apertura': f[0], 'caja': f[1], 'fecha_apertura': _fecha(f[2]), 'efectivo_disponible': int(f[3])} if f else None)
        except Exception as e:
            app.logger.error(f"Error al obtener la apertura actual: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    _SELECT_FACTURA = """
        SELECT cc.id_cuenta, v.id_venta, v.numero_factura, v.fecha, v.tipo_venta, v.condicion, cl.id_cliente,
               cl.nombre || COALESCE(' ' || cl.apellido, ''), cl.ci_ruc, v.total, cc.saldo, cc.estado,
               COALESCE((SELECT SUM(total) FROM nota_credito_debito_cab n WHERE n.id_cuenta = cc.id_cuenta AND n.tipo_nota = 'CREDITO' AND n.estado = 'EMITIDA'), 0),
               COALESCE((SELECT SUM(total) FROM nota_credito_debito_cab n WHERE n.id_cuenta = cc.id_cuenta AND n.tipo_nota = 'DEBITO' AND n.estado = 'EMITIDA'), 0),
               (SELECT count(*) FROM nota_credito_debito_cab n WHERE n.id_cuenta = cc.id_cuenta AND n.estado = 'EMITIDA')
        FROM cuenta_cobrar cc
        JOIN venta_cab v ON v.id_venta = cc.id_venta
        JOIN cliente cl ON cl.id_cliente = cc.id_cliente
        WHERE v.estado = 'EMITIDA' AND cc.estado <> 'ANULADA'
    """

    @staticmethod
    def _factura_dict(f):
        return {'id_cuenta': f[0], 'id_venta': f[1], 'numero_factura': f[2], 'fecha': _fecha(f[3]), 'tipo_venta': f[4],
                'condicion': f[5], 'id_cliente': f[6], 'cliente': f[7], 'ci_ruc': f[8], 'total': int(f[9]), 'saldo': int(f[10]),
                'estado_cuenta': f[11], 'creditos_previos': int(f[12]), 'debitos_previos': int(f[13]), 'cantidad_notas': f[14],
                'max_credito': int(f[9]) - int(f[12])}

    def buscarFacturas(self, q, limite=30):
        """Facturas EMITIDAS (con cuenta no anulada) por cliente (nombre o CI/RUC) o N.º de factura, con lo necesario para la nota."""
        patron = '%' + _escapar_like((q or '').strip()) + '%'
        sql = self._SELECT_FACTURA + """
            AND ((cl.nombre || COALESCE(' ' || cl.apellido, '')) ILIKE %s OR cl.ci_ruc ILIKE %s OR v.numero_factura ILIKE %s)
            ORDER BY v.fecha DESC, v.id_venta DESC LIMIT %s"""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (patron, patron, patron, limite))
            return [self._factura_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al buscar facturas para notas: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getFacturaParaNota(self, id_cuenta):
        """Una factura con lo necesario para la nota y, si es de ítems, la mercadería que se puede devolver
        (ítems que controlan stock: facturado, ya devuelto y pendiente de devolución). None si no existe o está anulada."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(self._SELECT_FACTURA + " AND cc.id_cuenta = %s", (id_cuenta,))
            f = cur.fetchone()
            if f is None:
                return None
            factura = self._factura_dict(f)
            factura['items'] = []
            if factura['tipo_venta'] == 'ITEMS':
                cur.execute("""
                    SELECT i.id_item, i.descripcion, SUM(d.cantidad)::INTEGER, MAX(d.precio_unitario), MAX(d.iva),
                           COALESCE((SELECT SUM(nd.cantidad) FROM nota_credito_debito_det nd JOIN nota_credito_debito_cab nc ON nc.id_nota = nd.id_nota
                                      WHERE nc.id_cuenta = %s AND nc.tipo_nota = 'CREDITO' AND nc.estado = 'EMITIDA' AND nd.id_item = i.id_item), 0)::INTEGER
                    FROM venta_det d JOIN items i ON i.id_item = d.id_item JOIN tipo_items ti ON ti.id_tipo_item = i.id_tipo_item AND ti.controla_stock = true
                    WHERE d.id_venta = %s GROUP BY i.id_item, i.descripcion ORDER BY i.descripcion, i.id_item
                """, (id_cuenta, factura['id_venta']))
                factura['items'] = [{'id_item': r[0], 'item': r[1], 'facturado': r[2], 'precio_unitario': int(r[3]), 'iva': r[4],
                                     'devuelto': r[5], 'pendiente': r[2] - r[5]} for r in cur.fetchall()]
            return factura
        except Exception as e:
            app.logger.error(f"Error al obtener la factura para la nota: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ alta
    def guardarNota(self, id_usuario, tipo, id_cuenta, motivo, renglones, devolucion):
        """
        Emite una nota en UNA transacción.
          * `renglones` (nota libre): [{'descripcion', 'monto', 'iva'}] ya validados por la API (cantidad 1, precio = monto).
          * `devolucion` True (solo CRÉDITO sobre una venta de ítems): `renglones` = [{'id_item', 'cantidad'}]; la descripción,
            el precio y el IVA salen de la FACTURA (nunca del navegador) y el stock de esos ítems se repone en la misma transacción.
          Orden de bloqueos: venta (FOR UPDATE: el mismo que anular la venta), apertura del cajero (FOR UPDATE: serializa los
          reintegros), ítems devueltos (FOR UPDATE, en orden de id) y, en los triggers, la cuenta a cobrar.
          Los triggers de la base validan caja abierta, venta EMITIDA, máximo del crédito, efectivo suficiente para el
          reintegro, cantidades devueltas y totales; aplican la nota al saldo de la cuenta.

        Returns:
            int | str | tuple | bool: ID de la nota; SIN_CAJA, CUENTA_NO_EXISTE, VENTA_NO_EMITIDA, VENTA_NO_ITEMS, (ITEM_INVALIDO, id_item)
            o (ERROR_BD, mensaje del trigger); False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_apertura FROM apertura_cierre_caja WHERE id_usuario = %s AND estado = 'ABIERTA'", (id_usuario,))
            ap = cur.fetchone()
            if ap is None:
                con.rollback()
                return SIN_CAJA
            cur.execute("SELECT id_venta FROM cuenta_cobrar WHERE id_cuenta = %s", (id_cuenta,))
            cuenta = cur.fetchone()
            if cuenta is None:
                con.rollback()
                return CUENTA_NO_EXISTE
            cur.execute("SELECT estado, tipo_venta FROM venta_cab WHERE id_venta = %s FOR UPDATE", (cuenta[0],))
            venta = cur.fetchone()
            if venta[0] != 'EMITIDA':
                con.rollback()
                return VENTA_NO_EMITIDA
            cur.execute("SELECT estado FROM apertura_cierre_caja WHERE id_apertura = %s FOR UPDATE", (ap[0],))
            if cur.fetchone()[0] != 'ABIERTA':
                con.rollback()
                return SIN_CAJA

            lineas = []   # (id_item, descripcion, cantidad, precio_unitario, iva, subtotal)
            if devolucion:
                if venta[1] != 'ITEMS':
                    con.rollback()
                    return VENTA_NO_ITEMS
                pedidos = sorted(renglones, key=lambda x: x['id_item'])
                cur.execute("SELECT id_item FROM items WHERE id_item = ANY(%s) ORDER BY id_item FOR UPDATE", ([x['id_item'] for x in pedidos],))
                cur.fetchall()
                for x in pedidos:
                    cur.execute("""SELECT d.descripcion, d.precio_unitario, d.iva FROM venta_det d
                                   WHERE d.id_venta = %s AND d.id_item = %s ORDER BY d.id_venta_det LIMIT 1""", (cuenta[0], x['id_item']))
                    d = cur.fetchone()
                    if d is None:
                        con.rollback()
                        return (ITEM_INVALIDO, x['id_item'])
                    lineas.append((x['id_item'], d[0], x['cantidad'], int(d[1]), d[2], int(d[1]) * x['cantidad']))
            else:
                for x in renglones:
                    lineas.append((None, x['descripcion'], 1, x['monto'], x['iva'], x['monto']))

            totales = calcular_totales([{'iva': l[4], 'subtotal': l[5]} for l in lineas])
            cur.execute("SELECT p_id_timbrado, p_numero_nota FROM fn_siguiente_numero_nota(%s)", (tipo,))
            id_timbrado, numero = cur.fetchone()
            cur.execute("""
                INSERT INTO nota_credito_debito_cab(id_cuenta, id_timbrado, id_usuario, id_apertura, tipo_nota, numero_nota, motivo,
                    total_exenta, total_gravada_5, total_gravada_10, iva_5, iva_10, total)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_nota
            """, (id_cuenta, id_timbrado, id_usuario, ap[0], tipo, numero, motivo, totales['exentas'], totales['gravadas_5'],
                  totales['gravadas_10'], totales['iva_5'], totales['iva_10'], totales['total']))
            id_nota = cur.fetchone()[0]
            for l in lineas:
                cur.execute("""INSERT INTO nota_credito_debito_det(id_nota, id_item, descripcion, cantidad, precio_unitario, iva, subtotal)
                               VALUES (%s, %s, %s, %s, %s, %s, %s)""", (id_nota,) + l)
                if devolucion:
                    cur.execute("UPDATE items SET cantidad_disponible = cantidad_disponible + %s WHERE id_item = %s", (l[2], l[0]))
            con.commit()   # acá corre el trigger diferido trg_validar_nota
            return id_nota
        except psycopg2.errors.RaiseException as e:
            con.rollback()
            return (ERROR_BD, getattr(getattr(e, 'diag', None), 'message_primary', None) or str(e).splitlines()[0])
        except Exception as e:
            app.logger.error(f"Error al guardar nota: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ anulación
    def anularNota(self, id_nota):
        """
        Anula una nota EMITIDA. Solo si su apertura de caja sigue ABIERTA. El trigger trg_aplicar_nota revierte el efecto en el saldo
        (el reintegro vuelve a la caja solo: las funciones de caja cuentan únicamente notas EMITIDAS) y, si fue una devolución,
        acá se descuenta del stock lo que había repuesto (si ya no alcanza, no se anula).
        Orden de bloqueos: nota, venta (FOR UPDATE), apertura (FOR SHARE), ítems y, en el trigger, la cuenta.

        Returns:
            dict | str | tuple | bool: {'numero_nota', 'tipo_nota', 'total'}; NO_EXISTE, YA_ANULADA o CAJA_CERRADA;
            (STOCK_INSUFICIENTE, ítem, disponible, a_deshacer); (ERROR_BD, mensaje) si un trigger lo rechaza; False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT estado, id_apertura, numero_nota, tipo_nota, total, id_cuenta FROM nota_credito_debito_cab WHERE id_nota = %s FOR UPDATE", (id_nota,))
            n = cur.fetchone()
            if n is None:
                con.rollback()
                return NO_EXISTE
            if n[0] == ANULADA:
                con.rollback()
                return YA_ANULADA
            cur.execute("SELECT id_venta FROM cuenta_cobrar WHERE id_cuenta = %s", (n[5],))
            cur.execute("SELECT id_venta FROM venta_cab WHERE id_venta = %s FOR UPDATE", (cur.fetchone()[0],))
            cur.execute("SELECT estado FROM apertura_cierre_caja WHERE id_apertura = %s FOR SHARE", (n[1],))
            if cur.fetchone()[0] != 'ABIERTA':
                con.rollback()
                return CAJA_CERRADA
            cur.execute("SELECT id_item, cantidad FROM nota_credito_debito_det WHERE id_nota = %s AND id_item IS NOT NULL ORDER BY id_item", (id_nota,))
            devueltos = cur.fetchall()
            if devueltos:
                cur.execute("SELECT id_item, descripcion, cantidad_disponible FROM items WHERE id_item = ANY(%s) ORDER BY id_item FOR UPDATE",
                            ([r[0] for r in devueltos],))
                stock = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
                for id_item, cantidad in devueltos:
                    desc, disponible = stock[id_item]
                    if disponible < cantidad:
                        con.rollback()
                        return (STOCK_INSUFICIENTE, desc, disponible, cantidad)
                for id_item, cantidad in devueltos:
                    cur.execute("UPDATE items SET cantidad_disponible = cantidad_disponible - %s WHERE id_item = %s", (cantidad, id_item))
            cur.execute("UPDATE nota_credito_debito_cab SET estado = 'ANULADA' WHERE id_nota = %s", (id_nota,))
            con.commit()
            return {'numero_nota': n[2], 'tipo_nota': n[3], 'total': int(n[4])}
        except psycopg2.errors.RaiseException as e:
            con.rollback()
            return (ERROR_BD, getattr(getattr(e, 'diag', None), 'message_primary', None) or str(e).splitlines()[0])
        except Exception as e:
            app.logger.error(f"Error al anular nota: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
