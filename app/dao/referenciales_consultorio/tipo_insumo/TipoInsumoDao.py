# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class TipoInsumoDao:
    """
    DAO para la referencial 'Tipo Insumo Utilizado'.
    Usa la tabla `insumos` (descripcion, presentacion).

    `estaEnUso()` valida contra `sesion_insumos` (Gestionar Procedimientos
    e Insumos Utilizados).
    """

    def getTiposInsumo(self):
        sql = """
        SELECT id_insumo, descripcion, presentacion, fecha_registro
        FROM insumos
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
                    'id_insumo': t[0],
                    'descripcion': t[1],
                    'presentacion': t[2],
                    'fecha_registro': str(t[3]) if t[3] else None
                }
                for t in tipos
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener tipos de insumo: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getTipoInsumoById(self, id_insumo):
        sql = """
        SELECT id_insumo, descripcion, presentacion, fecha_registro
        FROM insumos
        WHERE id_insumo = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_insumo,))
            t = cur.fetchone()
            if t:
                return {
                    'id_insumo': t[0],
                    'descripcion': t[1],
                    'presentacion': t[2],
                    'fecha_registro': str(t[3]) if t[3] else None
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener tipo de insumo: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, descripcion, excluir_id=None):
        """
        Verifica si ya existe (entre los activos) un tipo de insumo con la
        misma descripción (ignorando mayúsculas/minúsculas).
        """
        sql = "SELECT 1 FROM insumos WHERE activo = true AND UPPER(descripcion) = UPPER(%s)"
        params = [descripcion]

        if excluir_id:
            sql += " AND id_insumo != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de tipo de insumo: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarTipoInsumo(self, descripcion, presentacion=None):
        sql = """
        INSERT INTO insumos(descripcion, presentacion)
        VALUES(%s, %s) RETURNING id_insumo
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion, presentacion))
            nuevo_id = cur.fetchone()[0]
            con.commit()
            return nuevo_id
        except Exception as e:
            app.logger.error(f"Error al insertar tipo de insumo: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateTipoInsumo(self, id_insumo, descripcion, presentacion=None):
        sql = """
        UPDATE insumos
        SET descripcion = %s, presentacion = %s
        WHERE id_insumo = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion, presentacion, id_insumo))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar tipo de insumo: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def estaEnUso(self, id_insumo):
        """
        Indica si el insumo está utilizado en alguna sesión de tratamiento
        activa (`sesion_insumos`).
        """
        sql = "SELECT EXISTS(SELECT 1 FROM sesion_insumos WHERE id_insumo = %s AND activo = true)"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_insumo,))
            return bool(cur.fetchone()[0])
        except Exception as e:
            app.logger.error(f"Error al verificar uso de insumo: {str(e)}")
            return True  # Ante la duda, bloquear el borrado
        finally:
            cur.close()
            con.close()

    def deleteTipoInsumo(self, id_insumo):
        """
        Anula (baja lógica) un tipo de insumo, validando antes que no esté
        en uso en ninguna sesión de tratamiento activa.

        Returns:
            bool | str: True si se anuló, False si no existía, "EN_USO" si
            está en uso.
        """
        if self.estaEnUso(id_insumo):
            app.logger.warning(f"No se puede eliminar insumo {id_insumo}: está en uso")
            return "EN_USO"

        sql = """
        UPDATE insumos
        SET activo = false
        WHERE id_insumo = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_insumo,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al eliminar tipo de insumo: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
