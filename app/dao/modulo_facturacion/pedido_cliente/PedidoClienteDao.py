# Data Access Object - DAO
from decimal import Decimal, ROUND_HALF_UP
from flask import current_app as app
from app.conexion.Conexion import Conexion

PENDIENTE = 'PENDIENTE'
FACTURADO = 'FACTURADO'
ANULADO = 'ANULADO'

MAX_TOTAL = 999_999_999_999   # NUMERIC(12,0)

# Códigos de resultado (además de un ID, un dict o True)
NO_EXISTE = "NO_EXISTE"
CLIENTE_INVALIDO = "CLIENTE_INVALIDO"
ITEM_INVALIDO = "ITEM_INVALIDO"
TOTAL_EXCEDIDO = "TOTAL_EXCEDIDO"
YA_FACTURADO = "YA_FACTURADO"
YA_ANULADO = "YA_ANULADO"
STOCK_INSUFICIENTE = "STOCK_INSUFICIENTE"   # se devuelve como (STOCK_INSUFICIENTE, item, disponible, solicitado)

_SELECT = """
SELECT p.id_pedido, p.id_cliente,
       c.nombre || COALESCE(' ' || c.apellido, ''), c.ci_ruc,
       p.id_usuario, COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido),
       p.fecha_pedido, p.observacion, p.total, p.estado
FROM pedido_venta_cab p
JOIN cliente c ON c.id_cliente = p.id_cliente
JOIN usuarios u ON u.id_usuario = p.id_usuario
LEFT JOIN funcionario f ON f.id_funcionario = u.id_funcionario
LEFT JOIN medico m ON m.id_medico = u.id_medico
"""


def _redondear(valor):
    return int(Decimal(valor).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def calcular_totales(lineas):
    """
    Totales de un pedido a partir de sus renglones [{'iva', 'subtotal'}]. El precio incluye el IVA: las bases por tasa
    son la suma de los subtotales de cada una y el IVA liquidado es gravada10 / 11 y gravada5 / 21 (redondeado).
    """
    exentas = sum(int(l['subtotal']) for l in lineas if l['iva'] == 0)
    grav5 = sum(int(l['subtotal']) for l in lineas if l['iva'] == 5)
    grav10 = sum(int(l['subtotal']) for l in lineas if l['iva'] == 10)
    iva5 = _redondear(Decimal(grav5) / 21)
    iva10 = _redondear(Decimal(grav10) / 11)
    return {'exentas': exentas, 'gravadas_5': grav5, 'gravadas_10': grav10,
            'iva_5': iva5, 'iva_10': iva10, 'total_iva': iva5 + iva10, 'total': exentas + grav5 + grav10}


def _fecha(valor):
    return valor.strftime('%Y-%m-%d %H:%M:%S') if valor else None


def _a_dict(f):
    return {
        'id_pedido': f[0], 'id_cliente': f[1], 'cliente': f[2], 'ci_ruc': f[3],
        'id_usuario': f[4], 'cajero': f[5],
        'fecha_pedido': _fecha(f[6]), 'observacion': f[7], 'total': int(f[8]), 'estado': f[9],
    }


def _escapar_like(texto):
    return texto.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


class PedidoClienteDao:

    # ------------------------------------------------------------------ consultas
    def getPedidos(self, estado=None, cliente=None, desde=None, hasta=None, limite=500):
        """
        Pedidos, del más reciente al más antiguo. `cliente` es un texto que se busca en el nombre o en la CI/RUC.
        `desde`/`hasta` son date, ambos inclusive, sobre la fecha del pedido.
        """
        filtros, params = [], []
        if estado:
            filtros.append("p.estado = %s"); params.append(estado)
        if cliente:
            filtros.append("((c.nombre || COALESCE(' ' || c.apellido, '')) ILIKE %s OR c.ci_ruc ILIKE %s)")
            patron = '%' + _escapar_like(cliente.strip()) + '%'
            params += [patron, patron]
        if desde:
            filtros.append("p.fecha_pedido >= %s"); params.append(desde)
        if hasta:
            filtros.append("p.fecha_pedido < %s::date + 1"); params.append(hasta)
        where = (" WHERE " + " AND ".join(filtros)) if filtros else ""
        sql = _SELECT + where + " ORDER BY p.fecha_pedido DESC, p.id_pedido DESC LIMIT %s"
        params.append(limite)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return [_a_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener pedidos de cliente: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getPedidoById(self, id_pedido):
        """Pedido con su detalle y totales (exentas, gravadas, IVA liquidado), o None."""
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(_SELECT + " WHERE p.id_pedido = %s", (id_pedido,))
            f = cur.fetchone()
            if f is None:
                return None
            pedido = _a_dict(f)
            cur.execute("""
                SELECT d.id_pedido_det, d.id_item, i.descripcion, d.cantidad, d.precio_unitario, d.iva, d.subtotal
                FROM pedido_venta_det d
                JOIN items i ON i.id_item = d.id_item
                WHERE d.id_pedido = %s
                ORDER BY d.id_pedido_det
            """, (id_pedido,))
            pedido['detalle'] = [{
                'id_pedido_det': r[0], 'id_item': r[1], 'item': r[2], 'cantidad': r[3],
                'precio_unitario': int(r[4]), 'iva': r[5], 'subtotal': int(r[6])
            } for r in cur.fetchall()]
            pedido['totales'] = calcular_totales(pedido['detalle'])
            return pedido
        except Exception as e:
            app.logger.error(f"Error al obtener pedido de cliente: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def buscarClientes(self, q, limite=20):
        """Clientes ACTIVOS por nombre o CI/RUC (contiene); el consumidor final (SIN NOMBRE) va primero."""
        patron = '%' + _escapar_like((q or '').strip()) + '%'
        sql = """
        SELECT id_cliente, nombre || COALESCE(' ' || apellido, ''), ci_ruc
        FROM cliente
        WHERE activo = true AND ((nombre || COALESCE(' ' || apellido, '')) ILIKE %s OR ci_ruc ILIKE %s)
        ORDER BY (ci_ruc = '44444401-7') DESC, nombre, apellido NULLS FIRST, id_cliente
        LIMIT %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (patron, patron, limite))
            return [{'id_cliente': f[0], 'nombre': f[1], 'ci_ruc': f[2]} for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al buscar clientes para pedido: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def buscarItems(self, q, limite=30):
        """Ítems ACTIVOS (con tipo y depósito activos) por descripción, con precio, IVA y stock."""
        patron = '%' + _escapar_like((q or '').strip()) + '%'
        sql = """
        SELECT i.id_item, i.descripcion, t.descripcion, t.controla_stock, i.precio_unitario, i.iva, i.cantidad_disponible
        FROM items i
        JOIN tipo_items t ON t.id_tipo_item = i.id_tipo_item
        WHERE i.activo = true AND t.activo = true AND i.descripcion ILIKE %s
        ORDER BY i.descripcion
        LIMIT %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (patron, limite))
            return [{'id_item': f[0], 'descripcion': f[1], 'tipo_item': f[2], 'controla_stock': f[3],
                     'precio_unitario': int(f[4]), 'iva': f[5], 'cantidad_disponible': f[6]}
                    for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al buscar ítems para pedido: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ alta
    def guardarPedido(self, id_usuario, id_cliente, observacion, lineas):
        """
        Crea un pedido PENDIENTE y descuenta el stock, todo en una transacción. `lineas` = [(id_item, cantidad)] ya
        validadas y sin repetir. Precio, IVA, subtotal y total salen de `items` (nunca del cliente).

        Bloqueos: el cliente con FOR SHARE (una baja concurrente espera) y los ítems con FOR UPDATE en orden de
        id_item (evita deadlocks entre pedidos que comparten ítems), más el tipo de cada ítem con FOR SHARE.

        Returns:
            int | str | tuple | bool: ID del pedido; CLIENTE_INVALIDO, ITEM_INVALIDO, TOTAL_EXCEDIDO o
            (STOCK_INSUFICIENTE, descripcion, disponible, solicitado); False ante otro error.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT 1 FROM cliente WHERE id_cliente = %s AND activo = true FOR SHARE", (id_cliente,))
            if cur.fetchone() is None:
                con.rollback()
                return CLIENTE_INVALIDO

            ids = sorted(i for i, _ in lineas)
            cur.execute("""
                SELECT i.id_item, i.descripcion, i.precio_unitario, i.iva, i.cantidad_disponible,
                       t.controla_stock, i.activo, t.activo
                FROM items i
                JOIN tipo_items t ON t.id_tipo_item = i.id_tipo_item
                WHERE i.id_item = ANY(%s)
                ORDER BY i.id_item
                FOR UPDATE OF i FOR SHARE OF t
            """, (ids,))
            items = {f[0]: f for f in cur.fetchall()}
            if len(items) != len(ids) or any(not (f[6] and f[7]) for f in items.values()):
                con.rollback()
                return ITEM_INVALIDO

            renglones, total = [], 0
            for id_item, cantidad in lineas:
                _, descripcion, precio, iva, disponible, controla, _, _ = items[id_item]
                if controla and disponible < cantidad:
                    con.rollback()
                    return (STOCK_INSUFICIENTE, descripcion, disponible, cantidad)
                subtotal = int(precio) * cantidad
                total += subtotal
                renglones.append((id_item, cantidad, int(precio), iva, subtotal, controla))
            if total > MAX_TOTAL or any(r[4] > MAX_TOTAL for r in renglones):
                con.rollback()
                return TOTAL_EXCEDIDO

            cur.execute("""
                INSERT INTO pedido_venta_cab(id_cliente, id_usuario, observacion, total)
                VALUES (%s, %s, %s, %s) RETURNING id_pedido
            """, (id_cliente, id_usuario, observacion, total))
            id_pedido = cur.fetchone()[0]
            for id_item, cantidad, precio, iva, subtotal, controla in sorted(renglones):
                cur.execute("""
                    INSERT INTO pedido_venta_det(id_pedido, id_item, cantidad, precio_unitario, iva, subtotal)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (id_pedido, id_item, cantidad, precio, iva, subtotal))
                if controla:
                    cur.execute("UPDATE items SET cantidad_disponible = cantidad_disponible - %s WHERE id_item = %s",
                                (cantidad, id_item))
            con.commit()
            return id_pedido
        except Exception as e:
            app.logger.error(f"Error al guardar pedido de cliente: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ anulación
    def anular_y_reponer_en_cursor(self, cur, id_pedido):
        """
        Pasa el pedido a ANULADO y repone el stock de sus ítems DENTRO de la transacción del que llama (que ya tiene la
        fila del pedido bloqueada con FOR UPDATE y no hace commit acá). Comparte la lógica entre anular un pedido y
        anular una venta con la casilla "anular también el pedido". Los ítems se bloquean en orden de id_item. Si el tipo
        del ítem dejó de controlar stock desde el pedido, no se repone (ese ítem ya no maneja stock).

        Returns:
            dict: {'repuestos': [(item, cantidad)], 'sin_reposicion': [item]}
        """
        cur.execute("""
            SELECT d.id_item, d.cantidad, i.descripcion, t.controla_stock
            FROM pedido_venta_det d
            JOIN items i ON i.id_item = d.id_item
            JOIN tipo_items t ON t.id_tipo_item = i.id_tipo_item
            WHERE d.id_pedido = %s
            ORDER BY d.id_item
            FOR UPDATE OF i FOR SHARE OF t
        """, (id_pedido,))
        repuestos, sin_reposicion = [], []
        for id_item, cantidad, descripcion, controla in cur.fetchall():
            if controla:
                cur.execute("UPDATE items SET cantidad_disponible = cantidad_disponible + %s WHERE id_item = %s",
                            (cantidad, id_item))
                repuestos.append((descripcion, cantidad))
            else:
                sin_reposicion.append(descripcion)
        cur.execute("UPDATE pedido_venta_cab SET estado = 'ANULADO' WHERE id_pedido = %s", (id_pedido,))
        return {'repuestos': repuestos, 'sin_reposicion': sin_reposicion}

    def anularPedido(self, id_pedido):
        """
        Anula un pedido PENDIENTE y repone el stock de los ítems que controlan stock, en la misma transacción.
        Si el tipo del ítem dejó de controlar stock desde el pedido, no se repone (ese ítem ya no maneja stock).

        Returns:
            dict | str | bool: {'repuestos': [(item, cantidad)], 'sin_reposicion': [item]}; NO_EXISTE, YA_FACTURADO
            o YA_ANULADO; False ante otro error.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT estado FROM pedido_venta_cab WHERE id_pedido = %s FOR UPDATE", (id_pedido,))
            fila = cur.fetchone()
            if fila is None:
                con.rollback()
                return NO_EXISTE
            if fila[0] == FACTURADO:
                con.rollback()
                return YA_FACTURADO
            if fila[0] == ANULADO:
                con.rollback()
                return YA_ANULADO

            resultado = self.anular_y_reponer_en_cursor(cur, id_pedido)
            con.commit()
            return resultado
        except Exception as e:
            app.logger.error(f"Error al anular pedido de cliente: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
