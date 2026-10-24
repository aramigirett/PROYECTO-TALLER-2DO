# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

# Códigos de resultado (además de un ID o True)
DUPLICADO = "DUPLICADO"
NO_EXISTE = "NO_EXISTE"
YA_ACTIVO = "YA_ACTIVO"

MSG_BAJA_CON_ITEMS = "No se puede dar de baja, el depósito tiene ítems asignados."

_COLUMNAS = "id_deposito, descripcion, ubicacion, activo"


def _a_dict(f):
    return {'id_deposito': f[0], 'descripcion': f[1], 'ubicacion': f[2], 'activo': f[3]}


class DepositoDao:

    def getDepositos(self, incluir_inactivos=False):
        sql = f"SELECT {_COLUMNAS} FROM deposito" + ("" if incluir_inactivos else " WHERE activo = true") + \
              " ORDER BY activo DESC, descripcion"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            return [_a_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener depósitos: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getDepositoById(self, id_deposito, incluir_inactivos=False):
        sql = f"SELECT {_COLUMNAS} FROM deposito WHERE id_deposito = %s" + \
              ("" if incluir_inactivos else " AND activo = true")
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_deposito,))
            f = cur.fetchone()
            return _a_dict(f) if f else None
        except Exception as e:
            app.logger.error(f"Error al obtener depósito: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, descripcion, excluir_id=None):
        """Indica si ya hay un depósito ACTIVO con esa descripción (sin distinguir mayúsculas)."""
        sql = "SELECT 1 FROM deposito WHERE activo = true AND UPPER(descripcion) = UPPER(%s)"
        params = [descripcion]
        if excluir_id:
            sql += " AND id_deposito != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de depósito: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarDeposito(self, descripcion, ubicacion):
        """
        Returns:
            int | str | bool: ID nuevo, "DUPLICADO" si el índice único lo rechaza, False ante otro error.
        """
        sql = """
        INSERT INTO deposito(descripcion, ubicacion)
        VALUES(%s, %s) RETURNING id_deposito
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion.upper(), ubicacion.upper()))
            nuevo_id = cur.fetchone()[0]
            con.commit()
            return nuevo_id
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al insertar depósito: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateDeposito(self, id_deposito, descripcion, ubicacion):
        """
        Returns:
            bool | str: True si se actualizó, False si no existe o falló, "DUPLICADO" si el índice lo rechaza.
        """
        sql = """
        UPDATE deposito SET descripcion = %s, ubicacion = %s
        WHERE id_deposito = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion.upper(), ubicacion.upper(), id_deposito))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al actualizar depósito: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def _motivo_en_uso(self, cur, id_deposito):
        """Devuelve el motivo (texto para el usuario) si el depósito está en uso, o False."""
        cur.execute("SELECT EXISTS(SELECT 1 FROM items WHERE id_deposito = %s AND activo = true)", (id_deposito,))
        if cur.fetchone()[0]:
            return MSG_BAJA_CON_ITEMS
        # TODO: debe consultar nota_remision (WHERE id_deposito = %s) cuando exista esa tabla.
        return False

    def esta_en_uso(self, id_deposito):
        """False si se puede anular; si no, el texto con el motivo (truthy)."""
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            return self._motivo_en_uso(cur, id_deposito)
        except Exception as e:
            app.logger.error(f"Error al verificar uso de depósito: {str(e)}")
            return "No se pudo verificar si el depósito está en uso."  # ante la duda, bloquear
        finally:
            cur.close()
            con.close()

    def deleteDeposito(self, id_deposito):
        """
        Anula (baja lógica) un depósito. Verificación de uso y UPDATE en la misma transacción, con la
        fila bloqueada (FOR UPDATE): el alta/edición de un ítem toma FOR SHARE sobre el depósito, así que
        no se puede colar un ítem nuevo entre ambos pasos.

        Returns:
            bool | tuple: True si se anuló, False si no existía o falló, ("EN_USO", motivo) si está en uso.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT 1 FROM deposito WHERE id_deposito = %s AND activo = true FOR UPDATE", (id_deposito,))
            if cur.fetchone() is None:
                con.rollback()
                return False

            motivo = self._motivo_en_uso(cur, id_deposito)
            if motivo:
                con.rollback()
                app.logger.warning(f"No se puede anular depósito {id_deposito}: está en uso")
                return ("EN_USO", motivo)

            cur.execute("UPDATE deposito SET activo = false WHERE id_deposito = %s", (id_deposito,))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al anular depósito: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def reactivarDeposito(self, id_deposito):
        """
        Reactiva un depósito anulado, validando en la misma transacción que no haya otro depósito
        ACTIVO con la misma descripción.

        Returns:
            bool | str: True si se reactivó; NO_EXISTE, YA_ACTIVO o DUPLICADO; False ante otro error.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT descripcion, activo FROM deposito WHERE id_deposito = %s FOR UPDATE", (id_deposito,))
            fila = cur.fetchone()
            if fila is None:
                con.rollback()
                return NO_EXISTE
            descripcion, activo = fila
            if activo:
                con.rollback()
                return YA_ACTIVO

            cur.execute("""
                SELECT 1 FROM deposito
                WHERE activo = true AND UPPER(descripcion) = UPPER(%s) AND id_deposito != %s
            """, (descripcion, id_deposito))
            if cur.fetchone() is not None:
                con.rollback()
                return DUPLICADO

            cur.execute("UPDATE deposito SET activo = true WHERE id_deposito = %s", (id_deposito,))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al reactivar depósito: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
