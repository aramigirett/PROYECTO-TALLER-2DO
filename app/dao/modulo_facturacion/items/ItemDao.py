# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

# Códigos de resultado de guardar/update (además de un ID o True)
DUPLICADO = "DUPLICADO"
TIPO_INVALIDO = "TIPO_INVALIDO"
DEPOSITO_INVALIDO = "DEPOSITO_INVALIDO"
NO_EXISTE = "NO_EXISTE"
YA_ACTIVO = "YA_ACTIVO"
TIPO_INACTIVO = "TIPO_INACTIVO"
DEPOSITO_INACTIVO = "DEPOSITO_INACTIVO"
# reactivarItem devuelve (STOCK_REINICIADO, stock_anterior) si tuvo que poner el stock en 0
STOCK_REINICIADO = "STOCK_REINICIADO"

_SELECT = """
SELECT i.id_item, i.id_tipo_item, t.descripcion, t.controla_stock,
       i.descripcion, i.precio_unitario, i.iva, i.cantidad_disponible, i.activo,
       i.id_deposito, dep.descripcion
FROM items i
JOIN tipo_items t ON t.id_tipo_item = i.id_tipo_item
JOIN deposito dep ON dep.id_deposito = i.id_deposito
"""


def _a_dict(f):
    return {
        'id_item': f[0],
        'id_tipo_item': f[1], 'tipo_item': f[2], 'controla_stock': f[3],
        'descripcion': f[4], 'precio_unitario': int(f[5]), 'iva': f[6],
        'cantidad_disponible': f[7], 'activo': f[8],
        'id_deposito': f[9], 'deposito': f[10]
    }


class ItemDao:

    def getItems(self, incluir_inactivos=False):
        sql = _SELECT + ("" if incluir_inactivos else " WHERE i.activo = true") + " ORDER BY i.activo DESC, i.descripcion"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            return [_a_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener ítems: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getItemById(self, id_item, incluir_inactivos=False):
        sql = _SELECT + " WHERE i.id_item = %s" + ("" if incluir_inactivos else " AND i.activo = true")
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_item,))
            f = cur.fetchone()
            return _a_dict(f) if f else None
        except Exception as e:
            app.logger.error(f"Error al obtener ítem: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, descripcion, excluir_id=None):
        """Indica si ya hay un ítem ACTIVO con esa descripción (sin distinguir mayúsculas)."""
        sql = "SELECT 1 FROM items WHERE activo = true AND UPPER(descripcion) = UPPER(%s)"
        params = [descripcion]
        if excluir_id:
            sql += " AND id_item != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de ítem: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def _cantidad_efectiva(self, cur, id_tipo_item, cantidad):
        """
        Bloquea (FOR SHARE) el tipo y verifica que exista y esté activo: una baja o un cambio de
        "controla_stock" concurrente espera a que esta transacción termine. Si el tipo no controla
        stock, la cantidad es 0 sin importar lo que se haya enviado.
        Devuelve la cantidad a guardar, o None si el tipo no existe o está anulado.
        """
        cur.execute("SELECT controla_stock FROM tipo_items WHERE id_tipo_item = %s AND activo = true FOR SHARE",
                    (id_tipo_item,))
        fila = cur.fetchone()
        if fila is None:
            return None
        return cantidad if fila[0] else 0

    def _deposito_activo(self, cur, id_deposito):
        """Bloquea (FOR SHARE) el depósito y verifica que exista y esté activo: una baja concurrente del
        depósito (FOR UPDATE) espera a que esta transacción termine. Siempre se toma después del tipo."""
        cur.execute("SELECT 1 FROM deposito WHERE id_deposito = %s AND activo = true FOR SHARE", (id_deposito,))
        return cur.fetchone() is not None

    def guardarItem(self, id_tipo_item, descripcion, precio_unitario, iva, cantidad_disponible, id_deposito):
        """
        Returns:
            int | str | bool: ID nuevo; DUPLICADO / TIPO_INVALIDO / DEPOSITO_INVALIDO; False ante otro error.
        """
        sql = """
        INSERT INTO items(id_tipo_item, descripcion, precio_unitario, iva, cantidad_disponible, id_deposito)
        VALUES(%s, %s, %s, %s, %s, %s) RETURNING id_item
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cantidad = self._cantidad_efectiva(cur, id_tipo_item, cantidad_disponible)
            if cantidad is None:
                con.rollback()
                return TIPO_INVALIDO
            if not self._deposito_activo(cur, id_deposito):
                con.rollback()
                return DEPOSITO_INVALIDO
            cur.execute(sql, (id_tipo_item, descripcion.upper(), precio_unitario, iva, cantidad, id_deposito))
            nuevo_id = cur.fetchone()[0]
            con.commit()
            return nuevo_id
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al insertar ítem: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateItem(self, id_item, id_tipo_item, descripcion, precio_unitario, iva, cantidad_disponible, id_deposito):
        """
        Returns:
            bool | str: True si se actualizó, False si no existe o falló;
            DUPLICADO / TIPO_INVALIDO / DEPOSITO_INVALIDO.
        """
        sql = """
        UPDATE items
        SET id_tipo_item = %s, descripcion = %s, precio_unitario = %s, iva = %s, cantidad_disponible = %s,
            id_deposito = %s
        WHERE id_item = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cantidad = self._cantidad_efectiva(cur, id_tipo_item, cantidad_disponible)
            if cantidad is None:
                con.rollback()
                return TIPO_INVALIDO
            if not self._deposito_activo(cur, id_deposito):
                con.rollback()
                return DEPOSITO_INVALIDO
            cur.execute(sql, (id_tipo_item, descripcion.upper(), precio_unitario, iva, cantidad, id_deposito, id_item))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al actualizar ítem: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def esta_en_uso(self, id_item):
        """False si se puede anular; si no, el texto con el motivo (truthy)."""
        # TODO: debe consultar pedido_venta_det y venta_det (WHERE id_item = %s) cuando existan
        # esas tablas. Mientras tanto no hay nada que pueda referenciarlo.
        return False

    def deleteItem(self, id_item):
        """
        Anula (baja lógica) un ítem, validando antes que no esté en uso.

        Returns:
            bool | tuple: True si se anuló, False si no existía o falló, ("EN_USO", motivo) si está en uso.
        """
        motivo = self.esta_en_uso(id_item)
        if motivo:
            app.logger.warning(f"No se puede anular ítem {id_item}: está en uso")
            return ("EN_USO", motivo if isinstance(motivo, str) else
                    "No se puede dar de baja, el ítem está usado en pedidos o ventas.")

        sql = "UPDATE items SET activo = false WHERE id_item = %s AND activo = true"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_item,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al anular ítem: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def reactivarItem(self, id_item):
        """
        Reactiva un ítem anulado. En una sola transacción: bloquea el ítem, bloquea (FOR SHARE) su tipo y su
        depósito y exige que estén ACTIVOS, y que no haya otro ítem ACTIVO con la misma descripción.
        Si el tipo ya no controla stock y el ítem conservaba cantidad, el stock se pone en 0 (regla de Ítems).

        Returns:
            bool | str | tuple: True si se reactivó; (STOCK_REINICIADO, stock_anterior) si se reactivó con el
            stock puesto en 0; NO_EXISTE, YA_ACTIVO, TIPO_INACTIVO, DEPOSITO_INACTIVO o DUPLICADO;
            False ante otro error.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("""
                SELECT id_tipo_item, id_deposito, descripcion, cantidad_disponible, activo
                FROM items WHERE id_item = %s FOR UPDATE
            """, (id_item,))
            fila = cur.fetchone()
            if fila is None:
                con.rollback()
                return NO_EXISTE
            id_tipo, id_deposito, descripcion, cantidad, activo = fila
            if activo:
                con.rollback()
                return YA_ACTIVO

            # mismo orden de bloqueo que guardarItem/updateItem: tipo y después depósito
            cur.execute("SELECT activo, controla_stock FROM tipo_items WHERE id_tipo_item = %s FOR SHARE", (id_tipo,))
            tipo_activo, controla_stock = cur.fetchone()
            if not tipo_activo:
                con.rollback()
                return TIPO_INACTIVO
            cur.execute("SELECT activo FROM deposito WHERE id_deposito = %s FOR SHARE", (id_deposito,))
            if not cur.fetchone()[0]:
                con.rollback()
                return DEPOSITO_INACTIVO

            cur.execute("SELECT 1 FROM items WHERE activo = true AND UPPER(descripcion) = UPPER(%s) AND id_item != %s",
                        (descripcion, id_item))
            if cur.fetchone() is not None:
                con.rollback()
                return DUPLICADO

            reiniciar = (not controla_stock) and cantidad > 0
            cur.execute("UPDATE items SET activo = true, cantidad_disponible = %s WHERE id_item = %s",
                        (0 if reiniciar else cantidad, id_item))
            con.commit()
            return (STOCK_REINICIADO, cantidad) if reiniciar else True
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al reactivar ítem: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
