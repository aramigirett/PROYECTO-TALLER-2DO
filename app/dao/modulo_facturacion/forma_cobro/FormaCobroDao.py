# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion


class FormaCobroDao:

    def getFormasCobro(self):
        sql = """
        SELECT id_forma_cobro, descripcion, activo
        FROM forma_cobro
        WHERE activo = true
        ORDER BY descripcion
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            return [
                {'id_forma_cobro': f[0], 'descripcion': f[1], 'activo': f[2]}
                for f in cur.fetchall()
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener formas de cobro: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getFormaCobroById(self, id_forma_cobro):
        sql = """
        SELECT id_forma_cobro, descripcion, activo
        FROM forma_cobro
        WHERE id_forma_cobro = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_forma_cobro,))
            f = cur.fetchone()
            if f:
                return {'id_forma_cobro': f[0], 'descripcion': f[1], 'activo': f[2]}
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener forma de cobro: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, descripcion, excluir_id=None):
        """Indica si ya hay una forma de cobro ACTIVA con esa descripción (sin distinguir mayúsculas)."""
        sql = "SELECT 1 FROM forma_cobro WHERE activo = true AND UPPER(descripcion) = UPPER(%s)"
        params = [descripcion]
        if excluir_id:
            sql += " AND id_forma_cobro != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de forma de cobro: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarFormaCobro(self, descripcion):
        """
        Returns:
            int | str | bool: ID nuevo, "DUPLICADO" si el índice único lo rechaza
            (carrera entre dos altas simultáneas), False ante otro error.
        """
        sql = """
        INSERT INTO forma_cobro(descripcion)
        VALUES(%s) RETURNING id_forma_cobro
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
            app.logger.error(f"Error al insertar forma de cobro: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateFormaCobro(self, id_forma_cobro, descripcion):
        """
        Returns:
            bool | str: True si se actualizó, False si no existe o falló,
            "DUPLICADO" si el índice único lo rechaza.
        """
        sql = """
        UPDATE forma_cobro
        SET descripcion = %s
        WHERE id_forma_cobro = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion.upper(), id_forma_cobro))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return "DUPLICADO"
        except Exception as e:
            app.logger.error(f"Error al actualizar forma de cobro: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def esta_en_uso(self, id_forma_cobro):
        """Indica si la forma de cobro está usada en alguna cobranza."""
        # TODO: debe consultar cobro_cabecera (WHERE id_forma_cobro = %s) cuando exista
        # la tabla de cobros. Mientras tanto no hay nada que pueda referenciarla.
        return False

    def deleteFormaCobro(self, id_forma_cobro):
        """
        Anula (baja lógica) una forma de cobro, validando antes que no esté en uso.

        Returns:
            bool | str: True si se anuló, False si no existía o falló,
            "EN_USO" si está usada en una cobranza.
        """
        if self.esta_en_uso(id_forma_cobro):
            app.logger.warning(f"No se puede anular forma de cobro {id_forma_cobro}: está en uso")
            return "EN_USO"

        sql = """
        UPDATE forma_cobro
        SET activo = false
        WHERE id_forma_cobro = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_forma_cobro,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al anular forma de cobro: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
