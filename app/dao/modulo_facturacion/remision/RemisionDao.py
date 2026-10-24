# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

EMITIDA = 'EMITIDA'
ANULADA = 'ANULADA'
MOTIVO_TRASLADO = 'VENTA'   # fijo: el movimiento nace de una venta

# Códigos de resultado (además de un ID o un dict)
NO_EXISTE = "NO_EXISTE"
VENTA_NO_EXISTE = "VENTA_NO_EXISTE"
VENTA_NO_EMITIDA = "VENTA_NO_EMITIDA"       # la venta está anulada
VENTA_NO_ITEMS = "VENTA_NO_ITEMS"           # solo se remiten ventas de ítems
DEPOSITO_INVALIDO = "DEPOSITO_INVALIDO"     # no existe o está inactivo
ITEM_INVALIDO = "ITEM_INVALIDO"             # se devuelve como (ITEM_INVALIDO, id_item)
ERROR_BD = "ERROR_BD"                       # se devuelve como (ERROR_BD, mensaje del trigger de la base)
YA_ANULADA = "YA_ANULADA"

_SELECT = """
SELECT r.id_remision, r.numero_remision, r.fecha_emision, r.fecha_traslado, r.motivo_traslado, r.direccion_llegada,
       r.responsable_traslado, r.observacion, r.estado,
       v.id_venta, v.numero_factura, v.estado, cl.id_cliente, cl.nombre || COALESCE(' ' || cl.apellido, ''), cl.ci_ruc,
       r.id_deposito, dp.descripcion, dp.ubicacion,
       r.id_usuario, COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido),
       (SELECT COALESCE(SUM(d.cantidad), 0) FROM nota_remision_det d WHERE d.id_remision = r.id_remision),
       (SELECT COUNT(*) FROM nota_remision_det d WHERE d.id_remision = r.id_remision)
FROM nota_remision_cab r
JOIN venta_cab v ON v.id_venta = r.id_venta
JOIN cliente cl ON cl.id_cliente = v.id_cliente
JOIN deposito dp ON dp.id_deposito = r.id_deposito
JOIN usuarios u ON u.id_usuario = r.id_usuario
LEFT JOIN funcionario f ON f.id_funcionario = u.id_funcionario
LEFT JOIN medico m ON m.id_medico = u.id_medico
"""


def _fecha(valor, con_hora=True):
    if not valor:
        return None
    return valor.strftime('%Y-%m-%d %H:%M:%S' if con_hora else '%Y-%m-%d')


def _a_dict(f):
    return {
        'id_remision': f[0], 'numero_remision': f[1], 'fecha_emision': _fecha(f[2]), 'fecha_traslado': _fecha(f[3], False),
        'motivo_traslado': f[4], 'direccion_llegada': f[5], 'responsable_traslado': f[6], 'observacion': f[7], 'estado': f[8],
        'id_venta': f[9], 'numero_factura': f[10], 'estado_venta': f[11], 'id_cliente': f[12], 'cliente': f[13], 'ci_ruc': f[14],
        'id_deposito': f[15], 'deposito': f[16], 'ubicacion_deposito': f[17], 'id_usuario': f[18], 'usuario': f[19],
        'total_unidades': int(f[20]), 'cantidad_items': int(f[21]),
    }


def _escapar_like(texto):
    return texto.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


class RemisionDao:

    # ------------------------------------------------------------------ consultas
    def getRemisiones(self, estado=None, cliente=None, desde=None, hasta=None, limite=500):
        """Remisiones, de la más reciente a la más antigua. `cliente` busca por nombre, CI/RUC, N.º de factura o de remisión."""
        filtros, params = [], []
        if estado:
            filtros.append("r.estado = %s"); params.append(estado)
        if cliente:
            filtros.append("((cl.nombre || COALESCE(' ' || cl.apellido, '')) ILIKE %s OR cl.ci_ruc ILIKE %s "
                           "OR v.numero_factura ILIKE %s OR r.numero_remision ILIKE %s)")
            patron = '%' + _escapar_like(cliente.strip()) + '%'
            params += [patron, patron, patron, patron]
        if desde:
            filtros.append("r.fecha_emision >= %s"); params.append(desde)
        if hasta:
            filtros.append("r.fecha_emision < %s::date + 1"); params.append(hasta)
        where = (" WHERE " + " AND ".join(filtros)) if filtros else ""
        sql = _SELECT + where + " ORDER BY r.fecha_emision DESC, r.id_remision DESC LIMIT %s"
        params.append(limite)
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return [_a_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener remisiones: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getRemisionById(self, id_remision):
        """Remisión con su detalle (ítems y cantidades) y los datos de la empresa para el PDF, o None."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(_SELECT + " WHERE r.id_remision = %s", (id_remision,))
            f = cur.fetchone()
            if f is None:
                return None
            remision = _a_dict(f)
            cur.execute("""
                SELECT d.id_remision_det, d.id_item, i.descripcion, d.cantidad
                FROM nota_remision_det d JOIN items i ON i.id_item = d.id_item
                WHERE d.id_remision = %s ORDER BY d.id_remision_det
            """, (id_remision,))
            remision['detalle'] = [{'id_remision_det': r[0], 'id_item': r[1], 'item': r[2], 'cantidad': int(r[3])} for r in cur.fetchall()]
            cur.execute("SELECT razon_social, ruc, direccion, telefono, actividad_economica FROM empresa LIMIT 1")
            e = cur.fetchone()
            remision['empresa'] = ({'razon_social': e[0], 'ruc': e[1], 'direccion': e[2], 'telefono': e[3],
                                    'actividad_economica': e[4]} if e else None)
            return remision
        except Exception as e:
            app.logger.error(f"Error al obtener remisión: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def buscarVentas(self, q, limite=30):
        """Ventas de ítems EMITIDAS con algo pendiente de entrega, por cliente (nombre o CI/RUC) o N.º de factura."""
        patron = '%' + _escapar_like((q or '').strip()) + '%'
        sql = """
            SELECT p.id_venta, p.numero_factura, v.fecha, p.id_cliente, p.cliente, p.ci_ruc, v.total,
                   SUM(p.cantidad_pendiente)::INTEGER, array_agg(DISTINCT p.deposito ORDER BY p.deposito)
            FROM v_pendientes_entrega p JOIN venta_cab v ON v.id_venta = p.id_venta
            WHERE p.estado_venta = 'EMITIDA' AND p.cantidad_pendiente > 0
              AND (p.cliente ILIKE %s OR p.ci_ruc ILIKE %s OR p.numero_factura ILIKE %s)
            GROUP BY p.id_venta, p.numero_factura, v.fecha, p.id_cliente, p.cliente, p.ci_ruc, v.total
            ORDER BY v.fecha DESC, p.id_venta DESC LIMIT %s"""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (patron, patron, patron, limite))
            return [{'id_venta': f[0], 'numero_factura': f[1], 'fecha': _fecha(f[2]), 'id_cliente': f[3], 'cliente': f[4],
                     'ci_ruc': f[5], 'total': int(f[6]), 'unidades_pendientes': f[7], 'depositos': f[8]} for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al buscar ventas para remitir: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getPendientesVenta(self, id_venta):
        """Cabecera de la venta y sus ítems con facturado / remitido / pendiente (v_pendientes_entrega), o None si no existe."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""SELECT v.id_venta, v.numero_factura, v.fecha, v.estado, v.tipo_venta, cl.nombre || COALESCE(' ' || cl.apellido, ''),
                                  cl.ci_ruc, v.total
                           FROM venta_cab v JOIN cliente cl ON cl.id_cliente = v.id_cliente WHERE v.id_venta = %s""", (id_venta,))
            v = cur.fetchone()
            if v is None:
                return None
            cur.execute("""SELECT id_item, item, id_deposito, deposito, cantidad_facturada, cantidad_remitida, cantidad_pendiente
                           FROM v_pendientes_entrega WHERE id_venta = %s ORDER BY deposito, item, id_item""", (id_venta,))
            return {'id_venta': v[0], 'numero_factura': v[1], 'fecha': _fecha(v[2]), 'estado': v[3], 'tipo_venta': v[4],
                    'cliente': v[5], 'ci_ruc': v[6], 'total': int(v[7]),
                    'items': [{'id_item': r[0], 'item': r[1], 'id_deposito': r[2], 'deposito': r[3], 'facturado': r[4],
                               'remitido': r[5], 'pendiente': r[6]} for r in cur.fetchall()]}
        except Exception as e:
            app.logger.error(f"Error al obtener pendientes de entrega: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def getDepositos(self):
        """Depósitos ACTIVOS (para elegir de dónde sale la mercadería)."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_deposito, descripcion, ubicacion FROM deposito WHERE activo = true ORDER BY descripcion")
            return [{'id_deposito': f[0], 'descripcion': f[1], 'ubicacion': f[2]} for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener depósitos: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ alta
    def guardarRemision(self, id_usuario, id_venta, id_deposito, fecha_traslado, direccion_llegada, responsable_traslado,
                        observacion, items):
        """
        Emite una remisión en UNA transacción. `items` = lista de {'id_item', 'cantidad'} ya validada por la API.
          1. la venta (FOR UPDATE: el mismo bloqueo que anular la venta y que otra remisión de la misma venta): EMITIDA y de ítems;
          2. el depósito (FOR SHARE): activo; los ítems (FOR SHARE, en orden de id);
          3. número (fn_siguiente_numero_remision), cabecera y detalle. Los triggers de la base validan que cada ítem esté en la
             venta, controle stock, esté en el depósito elegido y que la cantidad no supere lo pendiente de entrega.
        El motivo de traslado es siempre VENTA y el usuario sale de la sesión.

        Returns:
            int | str | tuple | bool: ID de la remisión; VENTA_NO_EXISTE, VENTA_NO_EMITIDA, VENTA_NO_ITEMS, DEPOSITO_INVALIDO,
            (ITEM_INVALIDO, id_item) o (ERROR_BD, mensaje del trigger); False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT estado, tipo_venta FROM venta_cab WHERE id_venta = %s FOR UPDATE", (id_venta,))
            venta = cur.fetchone()
            if venta is None:
                con.rollback()
                return VENTA_NO_EXISTE
            if venta[0] != 'EMITIDA':
                con.rollback()
                return VENTA_NO_EMITIDA
            if venta[1] != 'ITEMS':
                con.rollback()
                return VENTA_NO_ITEMS

            cur.execute("SELECT activo FROM deposito WHERE id_deposito = %s FOR SHARE", (id_deposito,))
            dep = cur.fetchone()
            if dep is None or not dep[0]:
                con.rollback()
                return DEPOSITO_INVALIDO

            ordenados = sorted(items, key=lambda x: x['id_item'])
            ids = [x['id_item'] for x in ordenados]
            cur.execute("SELECT id_item FROM items WHERE id_item = ANY(%s) ORDER BY id_item FOR SHARE", (ids,))
            existentes = {r[0] for r in cur.fetchall()}
            for i in ids:
                if i not in existentes:
                    con.rollback()
                    return (ITEM_INVALIDO, i)

            cur.execute("SELECT fn_siguiente_numero_remision()")
            numero = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO nota_remision_cab(id_venta, id_deposito, id_usuario, numero_remision, fecha_traslado, motivo_traslado,
                                              direccion_llegada, responsable_traslado, observacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_remision
            """, (id_venta, id_deposito, id_usuario, numero, fecha_traslado, MOTIVO_TRASLADO, direccion_llegada,
                  responsable_traslado, observacion))
            id_remision = cur.fetchone()[0]
            for x in ordenados:
                cur.execute("INSERT INTO nota_remision_det(id_remision, id_item, cantidad) VALUES (%s, %s, %s)",
                            (id_remision, x['id_item'], x['cantidad']))
            con.commit()
            return id_remision
        except psycopg2.errors.RaiseException as e:
            con.rollback()
            return (ERROR_BD, getattr(getattr(e, 'diag', None), 'message_primary', None) or str(e).splitlines()[0])
        except Exception as e:
            app.logger.error(f"Error al guardar remisión: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ anulación
    def anularRemision(self, id_remision):
        """
        Anula una remisión EMITIDA (fila bloqueada FOR UPDATE). Las cantidades quedan libres de inmediato: lo pendiente de
        entrega solo cuenta remisiones EMITIDAS. No toca el stock (la remisión nunca lo movió).

        Returns:
            dict | str | bool: {'numero_remision'}; NO_EXISTE o YA_ANULADA; (ERROR_BD, mensaje) si un trigger lo rechaza;
            False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT estado, numero_remision FROM nota_remision_cab WHERE id_remision = %s FOR UPDATE", (id_remision,))
            r = cur.fetchone()
            if r is None:
                con.rollback()
                return NO_EXISTE
            if r[0] == ANULADA:
                con.rollback()
                return YA_ANULADA
            cur.execute("UPDATE nota_remision_cab SET estado = 'ANULADA' WHERE id_remision = %s", (id_remision,))
            con.commit()
            return {'numero_remision': r[1]}
        except psycopg2.errors.RaiseException as e:
            con.rollback()
            return (ERROR_BD, getattr(getattr(e, 'diag', None), 'message_primary', None) or str(e).splitlines()[0])
        except Exception as e:
            app.logger.error(f"Error al anular remisión: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
