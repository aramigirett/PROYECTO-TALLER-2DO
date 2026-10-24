# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion
from app.dao.modulo_facturacion.pedido_cliente.PedidoClienteDao import PedidoClienteDao, calcular_totales

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
CLIENTE_INVALIDO = "CLIENTE_INVALIDO"
PACIENTE_INVALIDO = "PACIENTE_INVALIDO"
TRATAMIENTO_INVALIDO = "TRATAMIENTO_INVALIDO"            # alguno no existe
TRATAMIENTO_OTRO_PACIENTE = "TRATAMIENTO_OTRO_PACIENTE"  # se devuelve como (código, descripción)
TRATAMIENTO_CANCELADO = "TRATAMIENTO_CANCELADO"          # se devuelve como (código, descripción)
TRATAMIENTO_FACTURADO = "TRATAMIENTO_FACTURADO"          # se devuelve como (código, descripción, número de factura)

MSG_ANULAR_CON_COBROS = "No es posible anular, existen cobros registrados. Utilice una Nota de Crédito."
MSG_ANULAR_CON_REMISIONES = "No es posible anular, existen remisiones emitidas. Anule primero las remisiones."
MSG_ANULAR_CON_NOTAS = "No es posible anular, existen notas de crédito o débito emitidas. Anúlelas primero."

_SELECT = """
SELECT v.id_venta, v.numero_factura, v.fecha, v.id_cliente, c.nombre || COALESCE(' ' || c.apellido, ''), c.ci_ruc,
       v.id_usuario, COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido),
       v.tipo_venta, v.condicion, v.id_pedido,
       v.total_exenta, v.total_gravada_5, v.total_gravada_10, v.iva_5, v.iva_10, v.total, v.estado,
       v.id_apertura, a.estado, cj.descripcion,
       cc.estado, cc.saldo, cc.fecha_vencimiento, cc.id_cuenta
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
        'id_cuenta': f[24],
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

    # ------------------------------------------------------------------ apoyo de la venta de tratamiento
    def buscarClientes(self, q, limite=20):
        """Clientes ACTIVOS por nombre o CI/RUC; incluye el paciente vinculado (si lo hay). SIN NOMBRE va primero."""
        patron = '%' + _escapar_like((q or '').strip()) + '%'
        sql = """
        SELECT c.id_cliente, c.nombre || COALESCE(' ' || c.apellido, ''), c.ci_ruc, c.id_paciente,
               p.nombre || ' ' || p.apellido
        FROM cliente c LEFT JOIN paciente p ON p.id_paciente = c.id_paciente
        WHERE c.activo = true AND ((c.nombre || COALESCE(' ' || c.apellido, '')) ILIKE %s OR c.ci_ruc ILIKE %s)
        ORDER BY (c.ci_ruc = '44444401-7') DESC, c.nombre, c.apellido NULLS FIRST, c.id_cliente
        LIMIT %s
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (patron, patron, limite))
            return [{'id_cliente': f[0], 'nombre': f[1], 'ci_ruc': f[2], 'id_paciente': f[3], 'paciente': f[4]}
                    for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al buscar clientes para la venta: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def buscarPacientes(self, q, limite=20):
        """Pacientes por cédula (prefijo) o nombre/apellido (contiene). Solo lo necesario para elegir uno."""
        q = _escapar_like((q or '').strip())
        sql = """
        SELECT id_paciente, nombre || ' ' || apellido, cedula_entidad FROM paciente
        WHERE cedula_entidad ILIKE %s OR (nombre || ' ' || apellido) ILIKE %s
        ORDER BY apellido, nombre, id_paciente LIMIT %s
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (q + '%', '%' + q + '%', limite))
            return [{'id_paciente': f[0], 'nombre': f[1], 'cedula': f[2]} for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al buscar pacientes para la venta: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getTratamientosDisponibles(self, id_paciente):
        """Tratamientos del paciente que NO están cancelados y NO tienen una venta EMITIDA, con el precio e IVA vigentes."""
        sql = """
        SELECT t.id_tratamiento, tt.descripcion, tt.precio, tt.iva, t.fecha_tratamiento, t.estado, t.codigo
        FROM tratamientos t JOIN tipos_tratamiento tt ON tt.id_tipo_tratamiento = t.id_tipo_tratamiento
        WHERE t.id_paciente = %s AND t.estado <> 'cancelado'
          AND NOT EXISTS (SELECT 1 FROM venta_det d JOIN venta_cab v ON v.id_venta = d.id_venta
                          WHERE d.id_tratamiento = t.id_tratamiento AND v.estado = 'EMITIDA')
        ORDER BY t.fecha_tratamiento DESC, t.id_tratamiento DESC
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_paciente,))
            return [{'id_tratamiento': f[0], 'descripcion': f[1], 'precio': int(f[2]), 'iva': f[3],
                     'fecha_tratamiento': f[4].strftime('%Y-%m-%d'), 'estado': f[5], 'codigo': f[6]}
                    for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener tratamientos disponibles: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ alta
    def guardarVentaTratamientos(self, id_usuario, id_cliente, id_paciente, ids_tratamiento, condicion):
        """
        Factura tratamientos de un paciente (sin pedido) en una sola transacción:
          1. la apertura ABIERTA del cajero (FOR SHARE) y el cliente activo (FOR SHARE);
          2. los tratamientos con FOR UPDATE en orden de id (el mismo bloqueo que toma TratamientoDao.deleteTratamiento):
             deben existir, ser del paciente, no estar cancelados ni tener ya una venta EMITIDA;
          3. número de factura con sp_siguiente_numero_factura;
          4. cabecera (tipo TRATAMIENTO, sin pedido) y un renglón por tratamiento (cantidad 1, descripción, precio e IVA
             copiados de tipos_tratamiento AHORA), con los totales calculados acá. El trigger crea la cuenta a cobrar.

        Returns:
            int | str | tuple | bool: ID de la venta; SIN_CAJA, CLIENTE_INVALIDO, PACIENTE_INVALIDO, TRATAMIENTO_INVALIDO,
            (TRATAMIENTO_OTRO_PACIENTE | TRATAMIENTO_CANCELADO, descripción), (TRATAMIENTO_FACTURADO, descripción, número)
            o (ERROR_TIMBRADO, mensaje); False ante otro error.
        """
        ids_ordenados = sorted(ids_tratamiento)
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_apertura FROM apertura_cierre_caja WHERE id_usuario = %s AND estado = 'ABIERTA' FOR SHARE",
                        (id_usuario,))
            apertura = cur.fetchone()
            if apertura is None:
                con.rollback()
                return SIN_CAJA
            cur.execute("SELECT 1 FROM cliente WHERE id_cliente = %s AND activo = true FOR SHARE", (id_cliente,))
            if cur.fetchone() is None:
                con.rollback()
                return CLIENTE_INVALIDO
            cur.execute("SELECT 1 FROM paciente WHERE id_paciente = %s", (id_paciente,))
            if cur.fetchone() is None:
                con.rollback()
                return PACIENTE_INVALIDO

            cur.execute("""
                SELECT t.id_tratamiento, t.id_paciente, t.estado, tt.descripcion, tt.precio, tt.iva
                FROM tratamientos t JOIN tipos_tratamiento tt ON tt.id_tipo_tratamiento = t.id_tipo_tratamiento
                WHERE t.id_tratamiento = ANY(%s)
                ORDER BY t.id_tratamiento
                FOR UPDATE OF t
            """, (ids_ordenados,))
            filas = cur.fetchall()
            if len(filas) != len(ids_ordenados):
                con.rollback()
                return TRATAMIENTO_INVALIDO
            for id_trat, pac, estado, descripcion, _, _ in filas:
                if pac != id_paciente:
                    con.rollback()
                    return (TRATAMIENTO_OTRO_PACIENTE, descripcion)
                if estado == 'cancelado':
                    con.rollback()
                    return (TRATAMIENTO_CANCELADO, descripcion)
                cur.execute("""
                    SELECT v.numero_factura FROM venta_det d JOIN venta_cab v ON v.id_venta = d.id_venta
                    WHERE d.id_tratamiento = %s AND v.estado = 'EMITIDA' LIMIT 1
                """, (id_trat,))
                factura = cur.fetchone()
                if factura is not None:
                    con.rollback()
                    return (TRATAMIENTO_FACTURADO, descripcion, factura[0])

            renglones = [(f[0], f[3], int(f[4]), f[5]) for f in filas]   # (id, descripción, precio, iva); cantidad 1
            totales = calcular_totales([{'iva': r[3], 'subtotal': r[2]} for r in renglones])

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
                VALUES (%s, %s, %s, %s, %s, 'TRATAMIENTO', NULL, %s, %s, %s, %s, %s, %s, %s) RETURNING id_venta
            """, (apertura[0], id_cliente, id_usuario, id_timbrado, numero, condicion,
                  totales['exentas'], totales['gravadas_5'], totales['gravadas_10'],
                  totales['iva_5'], totales['iva_10'], totales['total']))
            id_venta = cur.fetchone()[0]
            for id_trat, descripcion, precio, iva in renglones:
                cur.execute("""
                    INSERT INTO venta_det(id_venta, id_tratamiento, descripcion, cantidad, precio_unitario, iva, subtotal)
                    VALUES (%s, %s, %s, 1, %s, %s, %s)
                """, (id_venta, id_trat, descripcion, precio, iva, precio))
            con.commit()
            return id_venta
        except Exception as e:
            app.logger.error(f"Error al guardar venta de tratamientos: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

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
        # Cobros EMITIDOS de la cuenta de esta venta. Se bloquea la cuenta (FOR UPDATE) ANTES de mirar: un cobro nuevo toma
        # el mismo bloqueo, así que no puede colarse entre la verificación y la anulación. (Los anulados no cuentan.)
        cur.execute("SELECT id_cuenta FROM cuenta_cobrar WHERE id_venta = %s FOR UPDATE", (id_venta,))
        cuenta = cur.fetchone()
        if cuenta is None:
            return False
        cur.execute("SELECT 1 FROM cobro_cab WHERE id_cuenta = %s AND estado = 'EMITIDO' LIMIT 1", (cuenta[0],))
        return MSG_ANULAR_CON_COBROS if cur.fetchone() else False

    def _motivo_con_remisiones(self, cur, id_venta):
        """Devuelve el motivo (texto) si la venta tiene remisiones EMITIDAS, o False. La venta ya está bloqueada (FOR UPDATE), el mismo
        bloqueo que toma la emisión de una remisión (trg_validar_remision_cab): no puede colarse una remisión nueva."""
        cur.execute("SELECT 1 FROM nota_remision_cab WHERE id_venta = %s AND estado = 'EMITIDA' LIMIT 1", (id_venta,))
        return MSG_ANULAR_CON_REMISIONES if cur.fetchone() else False

    def _motivo_con_notas(self, cur, id_venta):
        """Devuelve el motivo (texto) si la venta tiene notas de crédito o débito EMITIDAS, o False. La venta ya está bloqueada
        (FOR UPDATE), el mismo bloqueo que toma la emisión de una nota: no puede colarse una nota nueva."""
        cur.execute("""SELECT 1 FROM nota_credito_debito_cab n JOIN cuenta_cobrar cc ON cc.id_cuenta = n.id_cuenta
                       WHERE cc.id_venta = %s AND n.estado = 'EMITIDA' LIMIT 1""", (id_venta,))
        return MSG_ANULAR_CON_NOTAS if cur.fetchone() else False

    def anularVenta(self, id_venta, anular_pedido=False):
        """
        Anula una venta EMITIDA. Solo si la apertura de caja de la venta sigue ABIERTA (FOR SHARE: un cierre
        concurrente espera) y sin cobros. La venta pasa a ANULADA (el número NO se reutiliza) y el trigger
        trg_anular_cuenta_cobrar anula la cuenta.
          * Venta de ítems, `anular_pedido=False`: el pedido vuelve a PENDIENTE (se puede volver a facturar).
          * Venta de ítems, `anular_pedido=True`: en la misma transacción el pedido pasa a ANULADO y se repone el stock
            (la misma lógica de anular un pedido).
          * Venta de tratamiento: no hay pedido; los tratamientos quedan libres solos (la disponibilidad se calcula a
            partir de las ventas EMITIDAS).

        Returns:
            dict | str | tuple | bool: {'id_pedido', 'numero_factura', 'tipo_venta', 'pedido_anulado', 'repuestos',
            'sin_reposicion'}; NO_EXISTE, YA_ANULADA, CAJA_CERRADA o ("EN_USO", motivo); False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""SELECT estado, id_apertura, id_pedido, numero_factura, tipo_venta
                           FROM venta_cab WHERE id_venta = %s FOR UPDATE""", (id_venta,))
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

            motivo = self._motivo_con_cobros(cur, id_venta) or self._motivo_con_remisiones(cur, id_venta) or self._motivo_con_notas(cur, id_venta)
            if motivo:
                con.rollback()
                return ("EN_USO", motivo)

            cur.execute("UPDATE venta_cab SET estado = 'ANULADA' WHERE id_venta = %s", (id_venta,))
            resultado = {'id_pedido': venta[2], 'numero_factura': venta[3], 'tipo_venta': venta[4],
                         'pedido_anulado': False, 'repuestos': [], 'sin_reposicion': []}
            if venta[2] is not None:
                cur.execute("SELECT estado FROM pedido_venta_cab WHERE id_pedido = %s FOR UPDATE", (venta[2],))
                estado_pedido = cur.fetchone()[0]
                if anular_pedido and estado_pedido == 'FACTURADO':
                    reposicion = PedidoClienteDao().anular_y_reponer_en_cursor(cur, venta[2])
                    resultado.update(pedido_anulado=True, **reposicion)
                else:
                    cur.execute("UPDATE pedido_venta_cab SET estado = 'PENDIENTE' WHERE id_pedido = %s AND estado = 'FACTURADO'",
                                (venta[2],))
            con.commit()
            return resultado
        except Exception as e:
            app.logger.error(f"Error al anular venta: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
