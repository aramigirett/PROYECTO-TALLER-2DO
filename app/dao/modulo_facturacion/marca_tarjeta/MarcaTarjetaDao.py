# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

# Códigos de resultado (además de un ID o True)
DUPLICADO = "DUPLICADO"
NO_EXISTE = "NO_EXISTE"
YA_ACTIVO = "YA_ACTIVO"


class MarcaTarjetaDao:

    def getMarcasTarjeta(self, incluir_inactivos=False):
        sql = """
        SELECT id_marca_tarjeta, descripcion, activo
        FROM marca_tarjeta
        """ + ("" if incluir_inactivos else " WHERE activo = true") + " ORDER BY activo DESC, descripcion"
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

    def getMarcaTarjetaById(self, id_marca_tarjeta, incluir_inactivos=False):
        sql = """
        SELECT id_marca_tarjeta, descripcion, activo
        FROM marca_tarjeta
        WHERE id_marca_tarjeta = %s
        """ + ("" if incluir_inactivos else " AND activo = true")
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

    def _motivo_en_uso(self, cur, id_marca_tarjeta):
        """Devuelve el motivo (texto para el usuario) si la marca está en uso, o False."""
        cur.execute(
            "SELECT EXISTS(SELECT 1 FROM entidad_adherida WHERE id_marca_tarjeta = %s AND activo = true)",
            (id_marca_tarjeta,))
        if cur.fetchone()[0]:
            return "No se puede dar de baja, la marca está asociada a una entidad adherida."
        # Cobranzas EMITIDAS con tarjeta de esta marca (la marca sale de la entidad adherida del cobro).
        cur.execute("""SELECT 1 FROM cobro_tarjeta t
                       JOIN entidad_adherida ea ON ea.id_entidad_adherida = t.id_entidad_adherida
                       JOIN cobro_det d ON d.id_cobro_det = t.id_cobro_det
                       JOIN cobro_cab c ON c.id_cobro = d.id_cobro
                       WHERE ea.id_marca_tarjeta = %s AND c.estado = 'EMITIDO' LIMIT 1""", (id_marca_tarjeta,))
        if cur.fetchone():
            return "No se puede dar de baja, la marca está usada en una cobranza con tarjeta."
        return False

    def esta_en_uso(self, id_marca_tarjeta):
        """False si se puede anular; si no, el texto con el motivo (truthy)."""
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            return self._motivo_en_uso(cur, id_marca_tarjeta)
        except Exception as e:
            app.logger.error(f"Error al verificar uso de marca de tarjeta: {str(e)}")
            return "No se pudo verificar si la marca está en uso."  # ante la duda, bloquear
        finally:
            cur.close()
            con.close()

    def deleteMarcaTarjeta(self, id_marca_tarjeta):
        """
        Anula (baja lógica) una marca de tarjeta. La verificación de uso y el UPDATE van en
        la misma transacción, con la fila bloqueada, para que no se cuele una entidad
        adherida nueva entre ambos pasos.

        Returns:
            bool | tuple: True si se anuló, False si no existía o falló,
            ("EN_USO", motivo) si está en uso.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(
                "SELECT 1 FROM marca_tarjeta WHERE id_marca_tarjeta = %s AND activo = true FOR UPDATE",
                (id_marca_tarjeta,))
            if cur.fetchone() is None:
                con.rollback()
                return False

            motivo = self._motivo_en_uso(cur, id_marca_tarjeta)
            if motivo:
                con.rollback()
                app.logger.warning(f"No se puede anular marca de tarjeta {id_marca_tarjeta}: está en uso")
                return ("EN_USO", motivo)

            cur.execute("UPDATE marca_tarjeta SET activo = false WHERE id_marca_tarjeta = %s",
                        (id_marca_tarjeta,))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al anular marca de tarjeta: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def reactivarMarcaTarjeta(self, id_marca_tarjeta):
        """
        Reactiva la marca de tarjeta anulada. En una sola transacción: bloquea el registro y valida que no haya otro
        ACTIVO con la misma descripción.

        Returns:
            bool | str: True si se reactivó; NO_EXISTE, YA_ACTIVO o DUPLICADO; False ante otro error.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT descripcion, activo FROM marca_tarjeta WHERE id_marca_tarjeta = %s FOR UPDATE", (id_marca_tarjeta,))
            fila = cur.fetchone()
            if fila is None:
                con.rollback()
                return NO_EXISTE
            descripcion, activo = fila
            if activo:
                con.rollback()
                return YA_ACTIVO

            cur.execute("""
                SELECT 1 FROM marca_tarjeta
                WHERE activo = true AND UPPER(descripcion) = UPPER(%s) AND id_marca_tarjeta != %s
            """, (descripcion, id_marca_tarjeta))
            if cur.fetchone() is not None:
                con.rollback()
                return DUPLICADO

            cur.execute("UPDATE marca_tarjeta SET activo = true WHERE id_marca_tarjeta = %s", (id_marca_tarjeta,))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al reactivar la marca de tarjeta: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
