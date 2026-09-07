# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class TipoAnalisisDao:
    """
    DAO para la referencial 'Tipo Análisis' (tabla `tipo_analisis`).

    NOTA: `estaEnUso()` todavía no valida nada real: depende de
    `orden_analisis` (tabla de "Generar Orden de Análisis"), que no existe
    en la base todavía. Cuando se programe ese movimiento, agregar acá el
    chequeo contra esa tabla, igual que se documentó en
    TipoInsumoDao/TipoProcedimientoMedicoDao/TipoEstudioDao.
    """

    def getTiposAnalisis(self):
        sql = """
        SELECT id_tipo_analisis, descripcion, fecha_registro
        FROM tipo_analisis
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
                    'id_tipo_analisis': t[0],
                    'descripcion': t[1],
                    'fecha_registro': str(t[2]) if t[2] else None
                }
                for t in tipos
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener tipos de análisis: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getTipoAnalisisById(self, id_tipo_analisis):
        sql = """
        SELECT id_tipo_analisis, descripcion, fecha_registro
        FROM tipo_analisis
        WHERE id_tipo_analisis = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_tipo_analisis,))
            t = cur.fetchone()
            if t:
                return {
                    'id_tipo_analisis': t[0],
                    'descripcion': t[1],
                    'fecha_registro': str(t[2]) if t[2] else None
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener tipo de análisis: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, descripcion, excluir_id=None):
        """
        Verifica si ya existe (entre los activos) un tipo de análisis con la
        misma descripción (ignorando mayúsculas/minúsculas).
        """
        sql = "SELECT 1 FROM tipo_analisis WHERE activo = true AND UPPER(descripcion) = UPPER(%s)"
        params = [descripcion]

        if excluir_id:
            sql += " AND id_tipo_analisis != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de tipo de análisis: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarTipoAnalisis(self, descripcion):
        sql = """
        INSERT INTO tipo_analisis(descripcion)
        VALUES(%s) RETURNING id_tipo_analisis
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
            app.logger.error(f"Error al insertar tipo de análisis: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateTipoAnalisis(self, id_tipo_analisis, descripcion):
        sql = """
        UPDATE tipo_analisis
        SET descripcion = %s
        WHERE id_tipo_analisis = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion, id_tipo_analisis))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar tipo de análisis: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def estaEnUso(self, id_tipo_analisis):
        """
        Pendiente: todavía no hay tabla `orden_analisis` para chequear.
        Cuando se programe "Generar Orden de Análisis", reemplazar este
        método por un chequeo real contra esa tabla.
        """
        return False

    def deleteTipoAnalisis(self, id_tipo_analisis):
        """
        Anula (baja lógica) un tipo de análisis, validando antes que no esté
        en uso (ver nota de `estaEnUso()`: hoy esa validación no chequea
        nada real todavía).

        Returns:
            bool | str: True si se anuló, False si no existía, "EN_USO" si
            está en uso.
        """
        if self.estaEnUso(id_tipo_analisis):
            app.logger.warning(f"No se puede eliminar tipo de análisis {id_tipo_analisis}: está en uso")
            return "EN_USO"

        sql = """
        UPDATE tipo_analisis
        SET activo = false
        WHERE id_tipo_analisis = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_tipo_analisis,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al eliminar tipo de análisis: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
