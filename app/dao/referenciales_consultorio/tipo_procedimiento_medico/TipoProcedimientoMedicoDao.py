# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class TipoProcedimientoMedicoDao:
    """
    DAO para la referencial 'Tipo Procedimiento Médico' (tabla
    `tipo_procedimiento_medico`).

    NOTA: `estaEnUso()` hoy solo valida contra `consultas_detalle`. Todavía
    falta sumar la validación contra `sesion_insumos`/`sesiones_tratamiento`
    (tablas de "Gestionar Procedimientos e Insumos Utilizados"), que no
    existen en la base todavía. Cuando se programe ese movimiento, agregar
    acá esa validación, igual que se documentó en TipoInsumoDao.
    """

    def getTiposProcedimientoMedico(self):
        sql = """
        SELECT id_tipo_procedimiento, codigo, descripcion, fecha_registro
        FROM tipo_procedimiento_medico
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
                    'id_tipo_procedimiento': t[0],
                    'codigo': t[1],
                    'descripcion': t[2],
                    'fecha_registro': str(t[3]) if t[3] else None
                }
                for t in tipos
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener tipos de procedimiento médico: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getTipoProcedimientoMedicoById(self, id_tipo_procedimiento):
        sql = """
        SELECT id_tipo_procedimiento, codigo, descripcion, fecha_registro
        FROM tipo_procedimiento_medico
        WHERE id_tipo_procedimiento = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_tipo_procedimiento,))
            t = cur.fetchone()
            if t:
                return {
                    'id_tipo_procedimiento': t[0],
                    'codigo': t[1],
                    'descripcion': t[2],
                    'fecha_registro': str(t[3]) if t[3] else None
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener tipo de procedimiento médico: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, descripcion, codigo, excluir_id=None):
        """
        Verifica si ya existe (entre los activos) un tipo de procedimiento
        médico con el mismo código o la misma descripción (ignorando
        mayúsculas/minúsculas).
        """
        sql = """
        SELECT 1 FROM tipo_procedimiento_medico
        WHERE activo = true
          AND (UPPER(descripcion) = UPPER(%s) OR UPPER(codigo) = UPPER(%s))
        """
        params = [descripcion, codigo]

        if excluir_id:
            sql += " AND id_tipo_procedimiento != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de tipo de procedimiento médico: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarTipoProcedimientoMedico(self, codigo, descripcion):
        sql = """
        INSERT INTO tipo_procedimiento_medico(codigo, descripcion)
        VALUES(%s, %s) RETURNING id_tipo_procedimiento
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
            app.logger.error(f"Error al insertar tipo de procedimiento médico: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateTipoProcedimientoMedico(self, id_tipo_procedimiento, codigo, descripcion):
        sql = """
        UPDATE tipo_procedimiento_medico
        SET codigo = %s, descripcion = %s
        WHERE id_tipo_procedimiento = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (codigo, descripcion, id_tipo_procedimiento))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar tipo de procedimiento médico: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def estaEnUso(self, id_tipo_procedimiento):
        """
        Indica si el tipo de procedimiento médico está referenciado en algún
        detalle de consulta.

        Pendiente: sumar acá el chequeo contra `sesion_insumos`/
        `sesiones_tratamiento` cuando esas tablas existan (ver docstring de
        la clase).
        """
        sql = "SELECT EXISTS(SELECT 1 FROM consultas_detalle WHERE id_tipo_procedimiento = %s)"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_tipo_procedimiento,))
            return bool(cur.fetchone()[0])
        except Exception as e:
            app.logger.error(f"Error al verificar uso de tipo de procedimiento médico: {str(e)}")
            return True  # Ante la duda, bloquear el borrado
        finally:
            cur.close()
            con.close()

    def deleteTipoProcedimientoMedico(self, id_tipo_procedimiento):
        """
        Anula (baja lógica) un tipo de procedimiento médico, validando antes
        que no esté en uso.

        Returns:
            bool | str: True si se anuló, False si no existía, "EN_USO" si
            está en uso en algún detalle de consulta.
        """
        if self.estaEnUso(id_tipo_procedimiento):
            app.logger.warning(f"No se puede eliminar tipo de procedimiento médico {id_tipo_procedimiento}: está en uso")
            return "EN_USO"

        sql = """
        UPDATE tipo_procedimiento_medico
        SET activo = false
        WHERE id_tipo_procedimiento = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_tipo_procedimiento,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al eliminar tipo de procedimiento médico: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
