# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion


class MarcaTarjetaDao:

    def getMarcasTarjeta(self):
        sql = """
        SELECT id_marca_tarjeta, descripcion, activo
        FROM marca_tarjeta
        WHERE activo = true
        ORDER BY descripcion
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            return [
                {'id_marca_tarjeta': f[0], 'descripcion': f[1], 'activo': f[2]}
                for f in cur.fetchall()
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener marcas de tarjeta: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getMarcaTarjetaById(self, id_marca_tarjeta):
        sql = """
        SELECT id_marca_tarjeta, descripcion, activo
        FROM marca_tarjeta
        WHERE id_marca_tarjeta = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_marca_tarjeta,))
            f = cur.fetchone()
            if f:
                return {'id_marca_tarjeta': f[0], 'descripcion': f[1], 'activo': f[2]}
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener marca de tarjeta: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, descripcion, excluir_id=None):
        """Indica si ya hay una marca de tarjeta ACTIVA con esa descripción (sin distinguir mayúsculas)."""
        sql = "SELECT 1 FROM marca_tarjeta WHERE activo = true AND UPPER(descripcion) = UPPER(%s)"
        params = [descripcion]
        if excluir_id:
            sql += " AND id_marca_tarjeta != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de marca de tarjeta: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarMarcaTarjeta(self, descripcion):
        """
        Returns:
            int | str | bool: ID nuevo, "DUPLICADO" si el índice único lo rechaza
            (carrera entre dos altas simultáneas), False ante otro error.
        """
        sql = """
        INSERT INTO marca_tarjeta(descripcion)
        VALUES(%s) RETURNING id_marca_tarjeta
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion.upper(),))
            nuevo_id = cur.fetchone()[0]
            con.commit()
            return nuevo_id
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return "DUPLICADO"
        except Exception as e:
            app.logger.error(f"Error al insertar marca de tarjeta: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateMarcaTarjeta(self, id_marca_tarjeta, descripcion):
        """
        Returns:
            bool | str: True si se actualizó, False si no existe o falló,
            "DUPLICADO" si el índice único lo rechaza.
        """
        sql = """
        UPDATE marca_tarjeta
        SET descripcion = %s
        WHERE id_marca_tarjeta = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion.upper(), id_marca_tarjeta))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return "DUPLICADO"
        except Exception as e:
            app.logger.error(f"Error al actualizar marca de tarjeta: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def esta_en_uso(self, id_marca_tarjeta):
        """Indica si la marca de tarjeta está usada en algún cobro con tarjeta."""
        # TODO: debe consultar cobro_tarjeta (WHERE id_marca_tarjeta = %s) cuando exista
        # la tabla. Mientras tanto no hay nada que pueda referenciarla.
        return False

    def deleteMarcaTarjeta(self, id_marca_tarjeta):
        """
        Anula (baja lógica) una marca de tarjeta, validando antes que no esté en uso.

        Returns:
            bool | str: True si se anuló, False si no existía o falló,
            "EN_USO" si está usada en un cobro con tarjeta.
        """
        if self.esta_en_uso(id_marca_tarjeta):
            app.logger.warning(f"No se puede anular marca de tarjeta {id_marca_tarjeta}: está en uso")
            return "EN_USO"

        sql = """
        UPDATE marca_tarjeta
        SET activo = false
        WHERE id_marca_tarjeta = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_marca_tarjeta,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al anular marca de tarjeta: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
