# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class TipoInsumoDao:
    """
    DAO para la referencial 'Tipo Insumo Utilizado'.
    Usa la tabla `insumos` (codigo, descripcion, presentacion), ya existente
    en la base pero sin código de aplicación hasta ahora.

    NOTA: a diferencia de TipoTratamientoDao, esta referencial todavía NO
    valida "en uso" antes de anular. La validación real depende de
    `sesion_insumos` (tabla de "Gestionar Procedimientos e Insumos
    Utilizados"), que no existe en la base todavía. Cuando se programe ese
    movimiento, agregar acá un estaEnUso() que chequee
    `sesion_insumos.id_insumo` antes de permitir la baja, igual que se hizo
    con TipoTratamientoDao contra `tratamientos`.
    """

    def getTiposInsumo(self):
        sql = """
        SELECT id_insumo, codigo, descripcion, presentacion, fecha_registro
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
                    'codigo': t[1],
                    'descripcion': t[2],
                    'presentacion': t[3],
                    'fecha_registro': str(t[4]) if t[4] else None
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
        SELECT id_insumo, codigo, descripcion, presentacion, fecha_registro
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
                    'codigo': t[1],
                    'descripcion': t[2],
                    'presentacion': t[3],
                    'fecha_registro': str(t[4]) if t[4] else None
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener tipo de insumo: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, descripcion, codigo, excluir_id=None):
        """
        Verifica si ya existe (entre los activos) un tipo de insumo con el
        mismo código o la misma descripción (ignorando mayúsculas/minúsculas).
        """
        sql = """
        SELECT 1 FROM insumos
        WHERE activo = true
          AND (UPPER(descripcion) = UPPER(%s) OR UPPER(codigo) = UPPER(%s))
        """
        params = [descripcion, codigo]

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

    def guardarTipoInsumo(self, codigo, descripcion, presentacion=None):
        sql = """
        INSERT INTO insumos(codigo, descripcion, presentacion)
        VALUES(%s, %s, %s) RETURNING id_insumo
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (codigo, descripcion, presentacion))
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

    def updateTipoInsumo(self, id_insumo, codigo, descripcion, presentacion=None):
        sql = """
        UPDATE insumos
        SET codigo = %s, descripcion = %s, presentacion = %s
        WHERE id_insumo = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (codigo, descripcion, presentacion, id_insumo))
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

    def deleteTipoInsumo(self, id_insumo):
        """
        Anula (baja lógica) un tipo de insumo.

        NOTA: no valida "en uso" (ver docstring de la clase) porque
        `sesion_insumos` todavía no existe.

        Returns:
            bool: True si se anuló, False si no existía.
        """
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
