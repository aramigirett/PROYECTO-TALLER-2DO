# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

# Códigos de resultado (además de un ID o True)
DUPLICADO = "DUPLICADO"
NO_EXISTE = "NO_EXISTE"
YA_ACTIVO = "YA_ACTIVO"

MSG_BAJA_EN_USO = "No se puede dar de baja, el tipo está asignado a uno o más ítems."
MSG_STOCK_EN_USO = ("No se puede cambiar \"Controla stock\": el tipo está asignado a uno o más ítems. "
                    "Anule o reasigne esos ítems primero.")

_COLUMNAS = "id_tipo_item, descripcion, controla_stock, activo"


def _a_dict(f):
    return {'id_tipo_item': f[0], 'descripcion': f[1], 'controla_stock': f[2], 'activo': f[3]}


class TipoItemDao:

    def getTiposItem(self, incluir_inactivos=False):
        sql = f"SELECT {_COLUMNAS} FROM tipo_items" + ("" if incluir_inactivos else " WHERE activo = true") + " ORDER BY activo DESC, descripcion"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            return [_a_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener tipos de ítem: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getTipoItemById(self, id_tipo_item, incluir_inactivos=False):
        sql = f"SELECT {_COLUMNAS} FROM tipo_items WHERE id_tipo_item = %s" + ("" if incluir_inactivos else " AND activo = true")
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_tipo_item,))
            f = cur.fetchone()
            return _a_dict(f) if f else None
        except Exception as e:
            app.logger.error(f"Error al obtener tipo de ítem: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, descripcion, excluir_id=None):
        """Indica si ya hay un tipo de ítem ACTIVO con esa descripción (sin distinguir mayúsculas)."""
        sql = "SELECT 1 FROM tipo_items WHERE activo = true AND UPPER(descripcion) = UPPER(%s)"
        params = [descripcion]
        if excluir_id:
            sql += " AND id_tipo_item != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de tipo de ítem: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarTipoItem(self, descripcion, controla_stock):
        """
        Returns:
            int | str | bool: ID nuevo, "DUPLICADO" si el índice único lo rechaza, False ante otro error.
        """
        sql = """
        INSERT INTO tipo_items(descripcion, controla_stock)
        VALUES(%s, %s) RETURNING id_tipo_item
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion.upper(), controla_stock))
            nuevo_id = cur.fetchone()[0]
            con.commit()
            return nuevo_id
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return "DUPLICADO"
        except Exception as e:
            app.logger.error(f"Error al insertar tipo de ítem: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateTipoItem(self, id_tipo_item, descripcion, controla_stock):
        """
        Cambiar "controla_stock" se bloquea si el tipo tiene ítems activos (quedarían ítems con stock
        bajo un tipo que no lo controla). La verificación y el UPDATE van en la misma transacción,
        con la fila del tipo bloqueada.

        Returns:
            bool | str | tuple: True si se actualizó, False si no existe o falló, "DUPLICADO",
            ("EN_USO", motivo) si se intentó cambiar controla_stock con ítems activos.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT controla_stock FROM tipo_items WHERE id_tipo_item = %s AND activo = true FOR UPDATE",
                        (id_tipo_item,))
            actual = cur.fetchone()
            if actual is None:
                con.rollback()
                return False

            if actual[0] != controla_stock and self._tiene_items_activos(cur, id_tipo_item):
                con.rollback()
                return ("EN_USO", MSG_STOCK_EN_USO)

            cur.execute("UPDATE tipo_items SET descripcion = %s, controla_stock = %s WHERE id_tipo_item = %s",
                        (descripcion.upper(), controla_stock, id_tipo_item))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return "DUPLICADO"
        except Exception as e:
            app.logger.error(f"Error al actualizar tipo de ítem: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def _tiene_items_activos(self, cur, id_tipo_item):
        cur.execute("SELECT EXISTS(SELECT 1 FROM items WHERE id_tipo_item = %s AND activo = true)", (id_tipo_item,))
        return cur.fetchone()[0]

    def _motivo_en_uso(self, cur, id_tipo_item):
        """Devuelve el motivo (texto para el usuario) si el tipo está en uso, o False."""
        if self._tiene_items_activos(cur, id_tipo_item):
            return MSG_BAJA_EN_USO
        return False

    def esta_en_uso(self, id_tipo_item):
        """False si se puede anular; si no, el texto con el motivo (truthy)."""
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            return self._motivo_en_uso(cur, id_tipo_item)
        except Exception as e:
            app.logger.error(f"Error al verificar uso de tipo de ítem: {str(e)}")
            return "No se pudo verificar si el tipo está en uso."  # ante la duda, bloquear
        finally:
            cur.close()
            con.close()

    def deleteTipoItem(self, id_tipo_item):
        """
        Anula (baja lógica) un tipo de ítem. Verificación de uso y UPDATE en la misma transacción,
        con la fila bloqueada, para que no se cuele un ítem nuevo entre ambos pasos.

        Returns:
            bool | tuple: True si se anuló, False si no existía o falló, ("EN_USO", motivo) si está en uso.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT 1 FROM tipo_items WHERE id_tipo_item = %s AND activo = true FOR UPDATE",
                        (id_tipo_item,))
            if cur.fetchone() is None:
                con.rollback()
                return False

            motivo = self._motivo_en_uso(cur, id_tipo_item)
            if motivo:
                con.rollback()
                app.logger.warning(f"No se puede anular tipo de ítem {id_tipo_item}: está en uso")
                return ("EN_USO", motivo)

            cur.execute("UPDATE tipo_items SET activo = false WHERE id_tipo_item = %s", (id_tipo_item,))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al anular tipo de ítem: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def reactivarTipoItem(self, id_tipo_item):
        """
        Reactiva el tipo de ítem anulado. En una sola transacción: bloquea el registro y valida que no haya otro
        ACTIVO con la misma descripción.

        Returns:
            bool | str: True si se reactivó; NO_EXISTE, YA_ACTIVO o DUPLICADO; False ante otro error.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT descripcion, activo FROM tipo_items WHERE id_tipo_item = %s FOR UPDATE", (id_tipo_item,))
            fila = cur.fetchone()
            if fila is None:
                con.rollback()
                return NO_EXISTE
            descripcion, activo = fila
            if activo:
                con.rollback()
                return YA_ACTIVO

            cur.execute("""
                SELECT 1 FROM tipo_items
                WHERE activo = true AND UPPER(descripcion) = UPPER(%s) AND id_tipo_item != %s
            """, (descripcion, id_tipo_item))
            if cur.fetchone() is not None:
                con.rollback()
                return DUPLICADO

            cur.execute("UPDATE tipo_items SET activo = true WHERE id_tipo_item = %s", (id_tipo_item,))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al reactivar el tipo de ítem: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
