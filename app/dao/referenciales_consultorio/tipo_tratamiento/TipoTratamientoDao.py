# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class TipoTratamientoDao:

    def getTiposTratamiento(self):
        sql = """
        SELECT id_tipo_tratamiento, descripcion, fecha_registro
        FROM tipos_tratamiento
        WHERE activo = true
        ORDER BY descripcion
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            tipos = cur.fetchall()
            return [
                {
                    'id_tipo_tratamiento': t[0],
                    'descripcion': t[1],
                    'fecha_registro': str(t[2]) if t[2] else None
                }
                for t in tipos
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener tipos de tratamiento: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getTipoTratamientoById(self, id_tipo_tratamiento):
        sql = """
        SELECT id_tipo_tratamiento, descripcion, fecha_registro
        FROM tipos_tratamiento
        WHERE id_tipo_tratamiento = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_tipo_tratamiento,))
            t = cur.fetchone()
            if t:
                return {
                    'id_tipo_tratamiento': t[0],
                    'descripcion': t[1],
                    'fecha_registro': str(t[2]) if t[2] else None
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener tipo de tratamiento: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, descripcion, excluir_id=None):
        """
        Verifica si ya existe (entre los activos) un tipo de tratamiento con
        la misma descripción (ignorando mayúsculas/minúsculas).
        """
        sql = "SELECT 1 FROM tipos_tratamiento WHERE activo = true AND UPPER(descripcion) = UPPER(%s)"
        params = [descripcion]

        if excluir_id:
            sql += " AND id_tipo_tratamiento != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de tipo de tratamiento: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarTipoTratamiento(self, descripcion):
        sql = """
        INSERT INTO tipos_tratamiento(descripcion)
        VALUES(%s) RETURNING id_tipo_tratamiento
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion,))
            nuevo_id = cur.fetchone()[0]
            con.commit()
            return nuevo_id
        except Exception as e:
            app.logger.error(f"Error al insertar tipo de tratamiento: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateTipoTratamiento(self, id_tipo_tratamiento, descripcion):
        sql = """
        UPDATE tipos_tratamiento
        SET descripcion = %s
        WHERE id_tipo_tratamiento = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion, id_tipo_tratamiento))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar tipo de tratamiento: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def estaEnUso(self, id_tipo_tratamiento):
        """Indica si el tipo de tratamiento está asignado a algún tratamiento registrado."""
        sql = "SELECT EXISTS(SELECT 1 FROM tratamientos WHERE id_tipo_tratamiento = %s)"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_tipo_tratamiento,))
            return bool(cur.fetchone()[0])
        except Exception as e:
            app.logger.error(f"Error al verificar uso de tipo de tratamiento: {str(e)}")
            return True  # Ante la duda, bloquear el borrado
        finally:
            cur.close()
            con.close()

    def deleteTipoTratamiento(self, id_tipo_tratamiento):
        """
        Anula (baja lógica) un tipo de tratamiento, validando antes que no
        esté en uso.

        Returns:
            bool | str: True si se anuló, False si no existía, "EN_USO" si
            está en uso en algún tratamiento registrado.
        """
        if self.estaEnUso(id_tipo_tratamiento):
            app.logger.warning(f"No se puede eliminar tipo de tratamiento {id_tipo_tratamiento}: está en uso")
            return "EN_USO"

        sql = """
        UPDATE tipos_tratamiento
        SET activo = false
        WHERE id_tipo_tratamiento = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_tipo_tratamiento,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al eliminar tipo de tratamiento: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
