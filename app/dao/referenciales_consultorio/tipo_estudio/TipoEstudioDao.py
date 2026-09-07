# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class TipoEstudioDao:
    """
    DAO para la referencial 'Tipo Estudio' (tabla `tipo_estudio`).

    NOTA: `estaEnUso()` todavía no valida nada real: depende de
    `orden_estudios` (tabla de "Generar Orden de Estudios"), que no existe
    en la base todavía. Cuando se programe ese movimiento, agregar acá el
    chequeo contra esa tabla, igual que se documentó en
    TipoInsumoDao/TipoProcedimientoMedicoDao.
    """

    def getTiposEstudio(self):
        sql = """
        SELECT id_tipo_estudio, codigo, descripcion, fecha_registro
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
                    'codigo': t[1],
                    'descripcion': t[2],
                    'fecha_registro': str(t[3]) if t[3] else None
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
        SELECT id_tipo_estudio, codigo, descripcion, fecha_registro
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
                    'codigo': t[1],
                    'descripcion': t[2],
                    'fecha_registro': str(t[3]) if t[3] else None
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener tipo de estudio: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, descripcion, codigo, excluir_id=None):
        """
        Verifica si ya existe (entre los activos) un tipo de estudio con el
        mismo código o la misma descripción (ignorando mayúsculas/minúsculas).
        """
        sql = """
        SELECT 1 FROM tipo_estudio
        WHERE activo = true
          AND (UPPER(descripcion) = UPPER(%s) OR UPPER(codigo) = UPPER(%s))
        """
        params = [descripcion, codigo]

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

    def guardarTipoEstudio(self, codigo, descripcion):
        sql = """
        INSERT INTO tipo_estudio(codigo, descripcion)
        VALUES(%s, %s) RETURNING id_tipo_estudio
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (codigo, descripcion))
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

    def updateTipoEstudio(self, id_tipo_estudio, codigo, descripcion):
        sql = """
        UPDATE tipo_estudio
        SET codigo = %s, descripcion = %s
        WHERE id_tipo_estudio = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (codigo, descripcion, id_tipo_estudio))
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
        Pendiente: todavía no hay tabla `orden_estudios` para chequear.
        Cuando se programe "Generar Orden de Estudios", reemplazar este
        método por un chequeo real contra esa tabla.
        """
        return False

    def deleteTipoEstudio(self, id_tipo_estudio):
        """
        Anula (baja lógica) un tipo de estudio, validando antes que no esté
        en uso (ver nota de `estaEnUso()`: hoy esa validación no chequea
        nada real todavía).

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
