# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class TipoEstudioDao:
    """
    DAO para la referencial 'Tipo Estudio' (tabla `tipo_estudio`).

    `estaEnUso()` valida contra `orden_estudios` (Generar Orden de
    Estudios) — una orden cancelada no cuenta como "en uso".
    """

    def getTiposEstudio(self):
        sql = """
        SELECT id_tipo_estudio, descripcion, fecha_registro
        FROM tipo_estudio
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
                    'id_tipo_estudio': t[0],
                    'descripcion': t[1],
                    'fecha_registro': str(t[2]) if t[2] else None
                }
                for t in tipos
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener tipos de estudio: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getTipoEstudioById(self, id_tipo_estudio):
        sql = """
        SELECT id_tipo_estudio, descripcion, fecha_registro
        FROM tipo_estudio
        WHERE id_tipo_estudio = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_tipo_estudio,))
            t = cur.fetchone()
            if t:
                return {
                    'id_tipo_estudio': t[0],
                    'descripcion': t[1],
                    'fecha_registro': str(t[2]) if t[2] else None
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener tipo de estudio: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, descripcion, excluir_id=None):
        """
        Verifica si ya existe (entre los activos) un tipo de estudio con la
        misma descripción (ignorando mayúsculas/minúsculas).
        """
        sql = "SELECT 1 FROM tipo_estudio WHERE activo = true AND UPPER(descripcion) = UPPER(%s)"
        params = [descripcion]

        if excluir_id:
            sql += " AND id_tipo_estudio != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de tipo de estudio: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarTipoEstudio(self, descripcion):
        sql = """
        INSERT INTO tipo_estudio(descripcion)
        VALUES(%s) RETURNING id_tipo_estudio
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
            app.logger.error(f"Error al insertar tipo de estudio: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateTipoEstudio(self, id_tipo_estudio, descripcion):
        sql = """
        UPDATE tipo_estudio
        SET descripcion = %s
        WHERE id_tipo_estudio = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion, id_tipo_estudio))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar tipo de estudio: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def estaEnUso(self, id_tipo_estudio):
        """
        Indica si el tipo de estudio está utilizado en alguna orden de
        estudio no cancelada.
        """
        sql = "SELECT EXISTS(SELECT 1 FROM orden_estudios WHERE id_tipo_estudio = %s AND estado <> 'cancelado')"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_tipo_estudio,))
            return bool(cur.fetchone()[0])
        except Exception as e:
            app.logger.error(f"Error al verificar uso de tipo de estudio: {str(e)}")
            return True  # Ante la duda, bloquear el borrado
        finally:
            cur.close()
            con.close()

    def deleteTipoEstudio(self, id_tipo_estudio):
        """
        Anula (baja lógica) un tipo de estudio, validando antes que no esté
        en uso en ninguna orden de estudio activa.

        Returns:
            bool | str: True si se anuló, False si no existía, "EN_USO" si
            está en uso.
        """
        if self.estaEnUso(id_tipo_estudio):
            app.logger.warning(f"No se puede eliminar tipo de estudio {id_tipo_estudio}: está en uso")
            return "EN_USO"

        sql = """
        UPDATE tipo_estudio
        SET activo = false
        WHERE id_tipo_estudio = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_tipo_estudio,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al eliminar tipo de estudio: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
