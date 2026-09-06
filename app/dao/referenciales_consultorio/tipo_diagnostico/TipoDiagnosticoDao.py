# Data access object - DAO para tipo_diagnostico
from flask import current_app as app
from app.conexion.Conexion import Conexion

class TipoDiagnosticoDao:

    def getTiposDiagnostico(self):
        sql = """
        SELECT id_tipo_diagnostico, descripcion_diagnostico, tipo_diagnostico
        FROM tipo_diagnostico
        ORDER BY descripcion_diagnostico ASC
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            diagnosticos = cur.fetchall()
            return [
                {
                    'id_tipo_diagnostico': diag[0],
                    'descripcion_diagnostico': diag[1],
                    'tipo_diagnostico': diag[2]
                }
                for diag in diagnosticos
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener todos los diagnósticos: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getTipoDiagnosticoById(self, id_tipo_diagnostico):
        sql = """
        SELECT id_tipo_diagnostico, descripcion_diagnostico, tipo_diagnostico
        FROM tipo_diagnostico
        WHERE id_tipo_diagnostico = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_tipo_diagnostico,))
            diagnostico = cur.fetchone()
            if diagnostico:
                return {
                    "id_tipo_diagnostico": diagnostico[0],
                    "descripcion_diagnostico": diagnostico[1],
                    "tipo_diagnostico": diagnostico[2]
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener diagnóstico: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def diagnosticoExiste(self, descripcion_diagnostico):
        sql = """
        SELECT 1 FROM tipo_diagnostico
        WHERE UPPER(descripcion_diagnostico) = UPPER(%s)
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion_diagnostico,))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar existencia de diagnóstico: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarTipoDiagnostico(self, descripcion_diagnostico, tipo_diagnostico):
        sql = """
        INSERT INTO tipo_diagnostico(descripcion_diagnostico, tipo_diagnostico)
        VALUES (%s, %s)
        RETURNING id_tipo_diagnostico
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            if not descripcion_diagnostico or not descripcion_diagnostico.strip():
                app.logger.error("Descripción vacía o nula al intentar guardar diagnóstico")
                return False

            if self.diagnosticoExiste(descripcion_diagnostico):
                app.logger.error(f"Ya existe un diagnóstico con la descripción: {descripcion_diagnostico}")
                return False

            cur.execute(sql, (descripcion_diagnostico, tipo_diagnostico))
            id_diagnostico = cur.fetchone()[0]
            con.commit()
            return id_diagnostico
        except Exception as e:
            app.logger.error(f"Error al insertar diagnóstico: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateTipoDiagnostico(self, id_tipo_diagnostico, descripcion_diagnostico, tipo_diagnostico):
        sql = """
        UPDATE tipo_diagnostico
        SET descripcion_diagnostico = %s,
            tipo_diagnostico = %s
        WHERE id_tipo_diagnostico = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion_diagnostico, tipo_diagnostico, id_tipo_diagnostico))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar diagnóstico: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def estaEnUso(self, id_tipo_diagnostico):
        """Indica si el tipo de diagnóstico está referenciado en consultas, diagnósticos o tratamientos."""
        sql = """
        SELECT
            EXISTS(SELECT 1 FROM consultas_detalle WHERE id_tipo_diagnostico = %s) AS en_consultas,
            EXISTS(SELECT 1 FROM diagnosticos WHERE id_tipo_diagnostico = %s) AS en_diagnosticos,
            EXISTS(SELECT 1 FROM tratamientos WHERE id_tipo_diagnostico = %s) AS en_tratamientos
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_tipo_diagnostico, id_tipo_diagnostico, id_tipo_diagnostico))
            en_consultas, en_diagnosticos, en_tratamientos = cur.fetchone()
            return bool(en_consultas or en_diagnosticos or en_tratamientos)
        except Exception as e:
            app.logger.error(f"Error al verificar uso del tipo de diagnóstico: {str(e)}")
            return True  # Ante la duda, bloquear el borrado
        finally:
            cur.close()
            con.close()

    def deleteTipoDiagnostico(self, id_diagnostico):
        """
        Elimina un tipo de diagnóstico por su ID, validando antes que no esté en uso.

        Returns:
            bool | str: True si se eliminó, False si no existía, "EN_USO" si está
            en uso en consultas, diagnósticos o tratamientos.
        """
        if self.estaEnUso(id_diagnostico):
            app.logger.warning(f"No se puede eliminar tipo de diagnóstico {id_diagnostico}: está en uso")
            return "EN_USO"

        sql = """
        DELETE FROM tipo_diagnostico
        WHERE id_tipo_diagnostico = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_diagnostico,))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except Exception as e:
            app.logger.error(f"Error al eliminar diagnóstico: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()