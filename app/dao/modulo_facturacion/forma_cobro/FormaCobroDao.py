# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

# Códigos de resultado (además de un ID o True)
DUPLICADO = "DUPLICADO"
NO_EXISTE = "NO_EXISTE"
YA_ACTIVO = "YA_ACTIVO"

MSG_BAJA_EN_COBRANZA = "No se puede dar de baja, la forma de cobro está usada en una cobranza."


class FormaCobroDao:

    def getFormasCobro(self, incluir_inactivos=False):
        sql = """
        SELECT id_forma_cobro, descripcion, activo
        FROM forma_cobro
        """ + ("" if incluir_inactivos else " WHERE activo = true") + " ORDER BY activo DESC, descripcion"
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

    def getFormaCobroById(self, id_forma_cobro, incluir_inactivos=False):
        sql = """
        SELECT id_forma_cobro, descripcion, activo
        FROM forma_cobro
        WHERE id_forma_cobro = %s
        """ + ("" if incluir_inactivos else " AND activo = true")
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

    def _motivo_en_uso(self, cur, id_forma_cobro):
        """Devuelve el motivo (texto para el usuario) si la forma de cobro está en uso, o False."""
        # TODO: debe consultar cobro_cabecera (WHERE id_forma_cobro = %s) cuando exista la tabla de
        # cobros y devolver MSG_BAJA_EN_COBRANZA. Mientras tanto no hay nada que pueda referenciarla.
        return False

    def esta_en_uso(self, id_forma_cobro):
        """False si se puede anular; si no, el texto con el motivo (truthy)."""
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            return self._motivo_en_uso(cur, id_forma_cobro)
        except Exception as e:
            app.logger.error(f"Error al verificar uso de forma de cobro: {str(e)}")
            return "No se pudo verificar si la forma de cobro está en uso."  # ante la duda, bloquear
        finally:
            cur.close()
            con.close()

    def deleteFormaCobro(self, id_forma_cobro):
        """
        Anula (baja lógica) una forma de cobro. Verificación de uso y UPDATE en la misma transacción,
        con la fila bloqueada (FOR UPDATE).

        Returns:
            bool | tuple: True si se anuló, False si no existía o falló, ("EN_USO", motivo) si está en uso.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT 1 FROM forma_cobro WHERE id_forma_cobro = %s AND activo = true FOR UPDATE",
                        (id_forma_cobro,))
            if cur.fetchone() is None:
                con.rollback()
                return False

            motivo = self._motivo_en_uso(cur, id_forma_cobro)
            if motivo:
                con.rollback()
                app.logger.warning(f"No se puede anular forma de cobro {id_forma_cobro}: está en uso")
                return ("EN_USO", motivo)

            cur.execute("UPDATE forma_cobro SET activo = false WHERE id_forma_cobro = %s", (id_forma_cobro,))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al anular forma de cobro: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def reactivarFormaCobro(self, id_forma_cobro):
        """
        Reactiva la forma de cobro anulada. En una sola transacción: bloquea el registro y valida que no haya otro
        ACTIVO con la misma descripción.

        Returns:
            bool | str: True si se reactivó; NO_EXISTE, YA_ACTIVO o DUPLICADO; False ante otro error.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT descripcion, activo FROM forma_cobro WHERE id_forma_cobro = %s FOR UPDATE", (id_forma_cobro,))
            fila = cur.fetchone()
            if fila is None:
                con.rollback()
                return NO_EXISTE
            descripcion, activo = fila
            if activo:
                con.rollback()
                return YA_ACTIVO

            cur.execute("""
                SELECT 1 FROM forma_cobro
                WHERE activo = true AND UPPER(descripcion) = UPPER(%s) AND id_forma_cobro != %s
            """, (descripcion, id_forma_cobro))
            if cur.fetchone() is not None:
                con.rollback()
                return DUPLICADO

            cur.execute("UPDATE forma_cobro SET activo = true WHERE id_forma_cobro = %s", (id_forma_cobro,))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al reactivar la forma de cobro: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
