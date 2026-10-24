# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

# CI/RUC del consumidor final (cliente "SIN NOMBRE"): no se modifica ni se da de baja.
CONSUMIDOR_FINAL_RUC = '44444401-7'

# Códigos de resultado (además de un ID o True)
DUPLICADO_CI_RUC = "DUPLICADO_CI_RUC"
DUPLICADO_PACIENTE = "DUPLICADO_PACIENTE"
PACIENTE_INVALIDO = "PACIENTE_INVALIDO"
NO_EXISTE = "NO_EXISTE"
YA_ACTIVO = "YA_ACTIVO"

MSG_BAJA_CONSUMIDOR_FINAL = "El consumidor final no se puede dar de baja."
MSG_MOD_CONSUMIDOR_FINAL = "El consumidor final no se puede modificar."
MSG_BAJA_CON_PEDIDOS = "No se puede dar de baja, el cliente tiene pedidos registrados."
MSG_BAJA_CON_VENTAS ="No se puede dar de baja, el cliente tiene ventas registradas."

_COLUMNAS = "id_cliente, id_paciente, nombre, apellido, ci_ruc, telefono, correo, activo"

# Nombres de los índices únicos parciales -> código de error
_INDICES = {
    'ux_cliente_ci_ruc_activo': DUPLICADO_CI_RUC,
    'ux_cliente_paciente_activo': DUPLICADO_PACIENTE,
}


def _a_dict(f):
    return {
        'id_cliente': f[0], 'id_paciente': f[1], 'nombre': f[2], 'apellido': f[3],
        'ci_ruc': f[4], 'telefono': f[5], 'correo': f[6], 'activo': f[7],
        'es_paciente': f[1] is not None,
        'es_consumidor_final': f[4] == CONSUMIDOR_FINAL_RUC,
    }


def _codigo_unique(e):
    """Qué índice único violó el error (por su nombre); por omisión, el de CI/RUC."""
    nombre = getattr(getattr(e, 'diag', None), 'constraint_name', None)
    return _INDICES.get(nombre, DUPLICADO_CI_RUC)


def _escapar_like(texto):
    return texto.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


class ClienteDao:

    def getClientes(self, incluir_inactivos=False):
        sql = f"SELECT {_COLUMNAS} FROM cliente" + ("" if incluir_inactivos else " WHERE activo = true") + \
              " ORDER BY activo DESC, nombre, apellido NULLS FIRST, id_cliente"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            return [_a_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener clientes: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getClienteById(self, id_cliente, incluir_inactivos=False):
        sql = f"SELECT {_COLUMNAS} FROM cliente WHERE id_cliente = %s" + \
              ("" if incluir_inactivos else " AND activo = true")
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_cliente,))
            f = cur.fetchone()
            return _a_dict(f) if f else None
        except Exception as e:
            app.logger.error(f"Error al obtener cliente: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeCiRuc(self, ci_ruc, excluir_id=None):
        """Indica si ya hay un cliente ACTIVO con esa CI/RUC."""
        sql = "SELECT 1 FROM cliente WHERE activo = true AND ci_ruc = %s"
        params = [ci_ruc]
        if excluir_id:
            sql += " AND id_cliente != %s"
            params.append(excluir_id)
        return self._existe(sql, params, "CI/RUC")

    def existePaciente(self, id_paciente, excluir_id=None):
        """Indica si ese paciente ya está registrado como cliente ACTIVO."""
        sql = "SELECT 1 FROM cliente WHERE activo = true AND id_paciente = %s"
        params = [id_paciente]
        if excluir_id:
            sql += " AND id_cliente != %s"
            params.append(excluir_id)
        return self._existe(sql, params, "paciente")

    def _existe(self, sql, params, que):
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de cliente ({que}): {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def buscarPacientes(self, q, limite=20):
        """
        Busca pacientes por cédula (prefijo) o por nombre y apellido (contiene), sin distinguir mayúsculas.
        Cada resultado indica si ya es cliente ACTIVO. El paciente no tiene baja lógica: "activo" = "existe".
        """
        q = _escapar_like(q.strip())
        sql = """
        SELECT p.id_paciente, p.nombre, p.apellido, p.cedula_entidad, p.telefono, p.correo,
               EXISTS(SELECT 1 FROM cliente c WHERE c.id_paciente = p.id_paciente AND c.activo = true)
        FROM paciente p
        WHERE p.cedula_entidad ILIKE %s OR (p.nombre || ' ' || p.apellido) ILIKE %s
        ORDER BY p.apellido, p.nombre, p.id_paciente
        LIMIT %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (q + '%', '%' + q + '%', limite))
            return [{
                'id_paciente': f[0], 'nombre': f[1], 'apellido': f[2], 'cedula': f[3],
                'telefono': f[4], 'correo': f[5], 'ya_es_cliente': f[6]
            } for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al buscar pacientes: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def guardarCliente(self, id_paciente, nombre, apellido, ci_ruc, telefono, correo):
        """
        Bloquea (FOR SHARE) la fila del paciente, si hay, y verifica que exista: así no se puede borrar
        el paciente entre la verificación y el alta.

        Returns:
            int | str | bool: ID nuevo; DUPLICADO_CI_RUC / DUPLICADO_PACIENTE / PACIENTE_INVALIDO;
            False ante otro error.
        """
        sql = """
        INSERT INTO cliente(id_paciente, nombre, apellido, ci_ruc, telefono, correo)
        VALUES(%s, %s, %s, %s, %s, %s) RETURNING id_cliente
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            if id_paciente is not None:
                cur.execute("SELECT 1 FROM paciente WHERE id_paciente = %s FOR SHARE", (id_paciente,))
                if cur.fetchone() is None:
                    con.rollback()
                    return PACIENTE_INVALIDO
            cur.execute(sql, (id_paciente, nombre, apellido, ci_ruc, telefono, correo))
            nuevo_id = cur.fetchone()[0]
            con.commit()
            return nuevo_id
        except psycopg2.errors.UniqueViolation as e:
            con.rollback()
            return _codigo_unique(e)
        except Exception as e:
            app.logger.error(f"Error al insertar cliente: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateCliente(self, id_cliente, nombre, apellido, ci_ruc, telefono, correo):
        """
        id_paciente NO se modifica (queda fijo desde el alta). El consumidor final no se puede modificar.

        Returns:
            bool | str | tuple: True si se actualizó, False si no existe o falló; DUPLICADO_CI_RUC;
            ("EN_USO", motivo) si es el consumidor final.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT ci_ruc FROM cliente WHERE id_cliente = %s AND activo = true FOR UPDATE", (id_cliente,))
            fila = cur.fetchone()
            if fila is None:
                con.rollback()
                return False
            if fila[0] == CONSUMIDOR_FINAL_RUC:
                con.rollback()
                return ("EN_USO", MSG_MOD_CONSUMIDOR_FINAL)

            cur.execute("""
                UPDATE cliente SET nombre = %s, apellido = %s, ci_ruc = %s, telefono = %s, correo = %s
                WHERE id_cliente = %s
            """, (nombre, apellido, ci_ruc, telefono, correo, id_cliente))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation as e:
            con.rollback()
            return _codigo_unique(e)
        except Exception as e:
            app.logger.error(f"Error al actualizar cliente: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def esta_en_uso(self, id_cliente):
        """False si se puede anular; si no, el texto con el motivo (truthy)."""
        # Pedidos PENDIENTES o FACTURADOS y ventas EMITIDAS (los anulados no cuentan). deleteCliente lo llama con la
        # fila del cliente bloqueada (FOR UPDATE) y un pedido nuevo toma FOR SHARE sobre el cliente, así que no puede
        # colarse; la venta sale de un pedido del cliente, que ya lo bloquea.
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT 1 FROM venta_cab WHERE id_cliente = %s AND estado <> 'ANULADA' LIMIT 1", (id_cliente,))
            if cur.fetchone():
                return MSG_BAJA_CON_VENTAS
            cur.execute("SELECT 1 FROM pedido_venta_cab WHERE id_cliente = %s AND estado <> 'ANULADO' LIMIT 1",
                        (id_cliente,))
            return MSG_BAJA_CON_PEDIDOS if cur.fetchone() else False
        finally:
            cur.close()
            con.close()

    def deleteCliente(self, id_cliente):
        """
        Anula (baja lógica) un cliente. El consumidor final (SIN NOMBRE) nunca se da de baja.

        Returns:
            bool | tuple: True si se anuló, False si no existía o falló, ("EN_USO", motivo) si no se puede.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT ci_ruc FROM cliente WHERE id_cliente = %s AND activo = true FOR UPDATE", (id_cliente,))
            fila = cur.fetchone()
            if fila is None:
                con.rollback()
                return False
            if fila[0] == CONSUMIDOR_FINAL_RUC:
                con.rollback()
                return ("EN_USO", MSG_BAJA_CONSUMIDOR_FINAL)

            motivo = self.esta_en_uso(id_cliente)
            if motivo:
                con.rollback()
                app.logger.warning(f"No se puede anular cliente {id_cliente}: está en uso")
                return ("EN_USO", motivo if isinstance(motivo, str) else MSG_BAJA_CON_VENTAS)

            cur.execute("UPDATE cliente SET activo = false WHERE id_cliente = %s", (id_cliente,))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al anular cliente: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def reactivarCliente(self, id_cliente):
        """
        Reactiva un cliente anulado. En una sola transacción: bloquea el cliente, verifica que el paciente
        (si lo tiene) exista y que no haya otro cliente ACTIVO con la misma CI/RUC ni con el mismo paciente.

        Returns:
            bool | str: True si se reactivó; NO_EXISTE, YA_ACTIVO, PACIENTE_INVALIDO, DUPLICADO_CI_RUC o
            DUPLICADO_PACIENTE; False ante otro error.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_paciente, ci_ruc, activo FROM cliente WHERE id_cliente = %s FOR UPDATE", (id_cliente,))
            fila = cur.fetchone()
            if fila is None:
                con.rollback()
                return NO_EXISTE
            id_paciente, ci_ruc, activo = fila
            if activo:
                con.rollback()
                return YA_ACTIVO

            if id_paciente is not None:
                cur.execute("SELECT 1 FROM paciente WHERE id_paciente = %s FOR SHARE", (id_paciente,))
                if cur.fetchone() is None:
                    con.rollback()
                    return PACIENTE_INVALIDO

            cur.execute("SELECT 1 FROM cliente WHERE activo = true AND ci_ruc = %s AND id_cliente != %s",
                        (ci_ruc, id_cliente))
            if cur.fetchone() is not None:
                con.rollback()
                return DUPLICADO_CI_RUC
            if id_paciente is not None:
                cur.execute("SELECT 1 FROM cliente WHERE activo = true AND id_paciente = %s AND id_cliente != %s",
                            (id_paciente, id_cliente))
                if cur.fetchone() is not None:
                    con.rollback()
                    return DUPLICADO_PACIENTE

            cur.execute("UPDATE cliente SET activo = true WHERE id_cliente = %s", (id_cliente,))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation as e:
            con.rollback()
            return _codigo_unique(e)
        except Exception as e:
            app.logger.error(f"Error al reactivar cliente: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
