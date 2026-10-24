# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

ABIERTA = 'ABIERTA'
CERRADA = 'CERRADA'
ANULADA = 'ANULADA'

# Códigos de resultado (además de un ID, un dict o True)
NO_EXISTE = "NO_EXISTE"
SIN_PERMISO_PROPIO = "SIN_PERMISO_PROPIO"   # no es el cajero de la apertura ni Administrador
NO_ABIERTA = "NO_ABIERTA"                    # se devuelve como (NO_ABIERTA, estado_actual)
CAJA_INVALIDA = "CAJA_INVALIDA"
USUARIO_YA_ABIERTO = "USUARIO_YA_ABIERTO"
CAJA_ABIERTA = "CAJA_ABIERTA"

MSG_ANULAR_CON_MOVIMIENTOS = "La apertura tiene movimientos registrados; debe cerrarse en lugar de anularse."

# Nombre del índice único parcial -> código de error (red de seguridad ante dos aperturas simultáneas)
_INDICES = {
    'ux_apertura_usuario_abierta': USUARIO_YA_ABIERTO,
    'ux_apertura_caja_abierta': CAJA_ABIERTA,
}

_SELECT = """
SELECT a.id_apertura, a.id_caja, c.descripcion, k.codigo, k.nombre_consultorio,
       a.id_usuario, COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido),
       a.fecha_apertura, a.monto_apertura, a.fecha_cierre, a.total_recaudado, a.monto_cierre, a.estado
FROM apertura_cierre_caja a
JOIN caja c ON c.id_caja = a.id_caja
JOIN consultorio k ON k.codigo = c.id_consultorio
JOIN usuarios u ON u.id_usuario = a.id_usuario
LEFT JOIN funcionario f ON f.id_funcionario = u.id_funcionario
LEFT JOIN medico m ON m.id_medico = u.id_medico
"""


def _fecha(valor):
    return valor.strftime('%Y-%m-%d %H:%M:%S') if valor else None


def _entero(valor):
    return int(valor) if valor is not None else None


def _a_dict(f):
    return {
        'id_apertura': f[0],
        'id_caja': f[1], 'caja': f[2],
        'id_consultorio': f[3], 'consultorio': f[4],
        'id_usuario': f[5], 'cajero': f[6],
        'fecha_apertura': _fecha(f[7]), 'monto_apertura': _entero(f[8]),
        'fecha_cierre': _fecha(f[9]), 'total_recaudado': _entero(f[10]), 'monto_cierre': _entero(f[11]),
        'estado': f[12],
    }


class AperturaCajaDao:

    # ------------------------------------------------------------------ consultas
    def getAperturas(self, id_usuario=None, estado=None, desde=None, hasta=None, limite=500):
        """
        Aperturas, de la más reciente a la más antigua. `id_usuario` limita a las de ese cajero (quien no es
        Administrador ve solo las propias). `desde`/`hasta` son date, ambos inclusive, sobre la fecha de apertura.
        """
        filtros, params = [], []
        if id_usuario is not None:
            filtros.append("a.id_usuario = %s"); params.append(id_usuario)
        if estado:
            filtros.append("a.estado = %s"); params.append(estado)
        if desde:
            filtros.append("a.fecha_apertura >= %s"); params.append(desde)
        if hasta:
            filtros.append("a.fecha_apertura < %s::date + 1"); params.append(hasta)
        where = (" WHERE " + " AND ".join(filtros)) if filtros else ""
        sql = _SELECT + where + " ORDER BY a.fecha_apertura DESC, a.id_apertura DESC LIMIT %s"
        params.append(limite)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return [_a_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener aperturas de caja: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getAperturaById(self, id_apertura):
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(_SELECT + " WHERE a.id_apertura = %s", (id_apertura,))
            f = cur.fetchone()
            return _a_dict(f) if f else None
        except Exception as e:
            app.logger.error(f"Error al obtener apertura de caja: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def getActualDeUsuario(self, id_usuario):
        """La apertura ABIERTA del cajero, o None."""
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(_SELECT + " WHERE a.id_usuario = %s AND a.estado = 'ABIERTA'", (id_usuario,))
            f = cur.fetchone()
            return _a_dict(f) if f else None
        except Exception as e:
            app.logger.error(f"Error al obtener la apertura actual del cajero: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def getCajasDisponibles(self):
        """Cajas ACTIVAS que no están abiertas, con su consultorio."""
        sql = """
        SELECT c.id_caja, c.descripcion, k.codigo, k.nombre_consultorio
        FROM caja c
        JOIN consultorio k ON k.codigo = c.id_consultorio
        WHERE c.activo = true
          AND NOT EXISTS (SELECT 1 FROM apertura_cierre_caja a WHERE a.id_caja = c.id_caja AND a.estado = 'ABIERTA')
        ORDER BY k.nombre_consultorio, c.descripcion
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            return [{'id_caja': f[0], 'descripcion': f[1], 'id_consultorio': f[2], 'consultorio': f[3]}
                    for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener cajas disponibles: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ apertura
    def abrirCaja(self, id_usuario, id_caja, monto_apertura):
        """
        Abre una caja para el cajero. En una transacción: bloquea la caja (FOR SHARE: una baja concurrente de la
        caja, que toma FOR UPDATE, espera), verifica que esté activa, que el cajero no tenga ya una apertura
        ABIERTA y que la caja no esté abierta. Los índices únicos parciales son la red de seguridad.

        Returns:
            int | str | bool: ID de la apertura; CAJA_INVALIDA, USUARIO_YA_ABIERTO o CAJA_ABIERTA; False ante otro error.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT 1 FROM caja WHERE id_caja = %s AND activo = true FOR SHARE", (id_caja,))
            if cur.fetchone() is None:
                con.rollback()
                return CAJA_INVALIDA

            cur.execute("SELECT 1 FROM apertura_cierre_caja WHERE id_usuario = %s AND estado = 'ABIERTA'", (id_usuario,))
            if cur.fetchone() is not None:
                con.rollback()
                return USUARIO_YA_ABIERTO
            cur.execute("SELECT 1 FROM apertura_cierre_caja WHERE id_caja = %s AND estado = 'ABIERTA'", (id_caja,))
            if cur.fetchone() is not None:
                con.rollback()
                return CAJA_ABIERTA

            cur.execute("""
                INSERT INTO apertura_cierre_caja(id_caja, id_usuario, monto_apertura)
                VALUES (%s, %s, %s) RETURNING id_apertura
            """, (id_caja, id_usuario, monto_apertura))
            nuevo_id = cur.fetchone()[0]
            con.commit()
            return nuevo_id
        except psycopg2.errors.UniqueViolation as e:
            con.rollback()
            nombre = getattr(getattr(e, 'diag', None), 'constraint_name', None)
            return _INDICES.get(nombre, USUARIO_YA_ABIERTO)
        except Exception as e:
            app.logger.error(f"Error al abrir caja: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ helpers de anulación / cierre
    def _bloquear_y_validar(self, cur, id_apertura, id_usuario, es_admin, bloquear=True):
        """
        Lee la apertura (con FOR UPDATE si `bloquear`) y valida: existe, es del cajero o el usuario es
        Administrador, y sigue ABIERTA. Devuelve (error, fila): error es None, NO_EXISTE, SIN_PERMISO_PROPIO o
        (NO_ABIERTA, estado). La propiedad se valida antes que el estado para no revelar el de aperturas ajenas.
        """
        cur.execute("SELECT id_usuario, estado, monto_apertura FROM apertura_cierre_caja WHERE id_apertura = %s" +
                    (" FOR UPDATE" if bloquear else ""), (id_apertura,))
        fila = cur.fetchone()
        if fila is None:
            return NO_EXISTE, None
        if fila[0] != id_usuario and not es_admin:
            return SIN_PERMISO_PROPIO, None
        if fila[1] != ABIERTA:
            return (NO_ABIERTA, fila[1]), None
        return None, fila

    def _motivo_con_movimientos(self, cur, id_apertura):
        """Devuelve el motivo (texto) si la apertura ya tiene movimientos del turno, o False."""
        # Ventas EMITIDAS de esta apertura. anularApertura la llama con la apertura bloqueada (FOR UPDATE) y una
        # venta nueva toma FOR SHARE sobre ella, así que no puede colarse entre la verificación y el UPDATE.
        # Un cobro nuevo toma FOR SHARE sobre la apertura, igual que la venta, así que tampoco puede colarse.
        cur.execute("SELECT 1 FROM venta_cab WHERE id_apertura = %s AND estado = 'EMITIDA' LIMIT 1", (id_apertura,))
        if cur.fetchone():
            return MSG_ANULAR_CON_MOVIMIENTOS
        cur.execute("SELECT 1 FROM cobro_cab WHERE id_apertura = %s AND estado = 'EMITIDO' LIMIT 1", (id_apertura,))
        return MSG_ANULAR_CON_MOVIMIENTOS if cur.fetchone() else False

    def _total_recaudado(self, cur, id_apertura):
        """TODO lo cobrado en el turno (todas las formas de cobro), en guaraníes: fn_total_recaudado (cobros EMITIDOS)."""
        cur.execute("SELECT fn_total_recaudado(%s)", (id_apertura,))
        return int(cur.fetchone()[0])

    def _total_efectivo(self, cur, id_apertura):
        """Solo lo cobrado en EFECTIVO en el turno, en guaraníes: fn_total_efectivo_apertura (cobros EMITIDOS)."""
        cur.execute("SELECT fn_total_efectivo_apertura(%s)", (id_apertura,))
        return int(cur.fetchone()[0])

    def _resumen_por_forma(self, cur, id_apertura):
        """Desglose de lo cobrado por forma de cobro (vista v_resumen_caja), para el detalle del Cierre."""
        cur.execute("""SELECT id_forma_cobro, forma_cobro, tipo_forma, cantidad_pagos, total_cobrado
                       FROM v_resumen_caja WHERE id_apertura = %s ORDER BY total_cobrado DESC, forma_cobro""", (id_apertura,))
        return [{'id_forma_cobro': r[0], 'forma_cobro': r[1], 'tipo': r[2], 'cantidad_pagos': r[3], 'total_cobrado': int(r[4])}
                for r in cur.fetchall()]

    def _totales_cierre(self, cur, id_apertura, monto_apertura):
        """
        Importes del cierre, calculados por el servidor: total_recaudado = todo lo cobrado (todas las formas);
        monto_cierre = monto_apertura + solo lo cobrado en EFECTIVO (tarjetas, cheques y transferencias no son plata
        en el cajón; su desglose va en `resumen`).
        """
        total = self._total_recaudado(cur, id_apertura)
        efectivo = self._total_efectivo(cur, id_apertura)
        return {'monto_apertura': monto_apertura, 'total_recaudado': total, 'efectivo': efectivo,
                'monto_cierre': monto_apertura + efectivo, 'resumen': self._resumen_por_forma(cur, id_apertura)}
    # ------------------------------------------------------------------ anulación
    def anularApertura(self, id_apertura, id_usuario, es_admin):
        """
        Pasa una apertura ABIERTA a ANULADA. Solo la del propio cajero (o cualquiera si es Administrador).
        Bloqueada si el turno ya tiene movimientos.

        Returns:
            bool | str | tuple: True si se anuló; NO_EXISTE, SIN_PERMISO_PROPIO, (NO_ABIERTA, estado) o
            ("EN_USO", motivo); False ante otro error.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            error, _ = self._bloquear_y_validar(cur, id_apertura, id_usuario, es_admin)
            if error:
                con.rollback()
                return error
            motivo = self._motivo_con_movimientos(cur, id_apertura)
            if motivo:
                con.rollback()
                return ("EN_USO", motivo)
            cur.execute("UPDATE apertura_cierre_caja SET estado = 'ANULADA' WHERE id_apertura = %s", (id_apertura,))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al anular apertura de caja: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ cierre
    def previewCierre(self, id_apertura, id_usuario, es_admin):
        """
        Detalle que se muestra antes de confirmar el cierre: monto de apertura + total recaudado = monto de cierre.
        Lo calcula el servidor; no cambia nada.

        Returns:
            dict | str | tuple: {'monto_apertura', 'total_recaudado', 'efectivo', 'monto_cierre', 'resumen'}; NO_EXISTE,
            SIN_PERMISO_PROPIO o (NO_ABIERTA, estado); False ante otro error.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            error, fila = self._bloquear_y_validar(cur, id_apertura, id_usuario, es_admin, bloquear=False)
            if error:
                return error
            return self._totales_cierre(cur, id_apertura, int(fila[2]))
        except Exception as e:
            app.logger.error(f"Error al calcular el cierre de caja: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def cerrarApertura(self, id_apertura, id_usuario, es_admin):
        """
        Cierra una apertura ABIERTA: fecha_cierre = now(), total_recaudado = TODO lo cobrado, monto_cierre = apertura + solo EFECTIVO,
        estado CERRADA. Los importes los calcula el servidor en la misma transacción (el cliente no los manda).

        Returns:
            dict | str | tuple: {'monto_apertura', 'total_recaudado', 'efectivo', 'monto_cierre', 'resumen'}; NO_EXISTE,
            SIN_PERMISO_PROPIO o (NO_ABIERTA, estado); False ante otro error.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            error, fila = self._bloquear_y_validar(cur, id_apertura, id_usuario, es_admin)
            if error:
                con.rollback()
                return error
            totales = self._totales_cierre(cur, id_apertura, int(fila[2]))
            cur.execute("""
                UPDATE apertura_cierre_caja
                SET fecha_cierre = now(), total_recaudado = %s, monto_cierre = %s, estado = 'CERRADA'
                WHERE id_apertura = %s
            """, (totales['total_recaudado'], totales['monto_cierre'], id_apertura))
            con.commit()
            return totales
        except Exception as e:
            app.logger.error(f"Error al cerrar la caja: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
