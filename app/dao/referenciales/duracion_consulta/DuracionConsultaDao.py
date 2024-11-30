# Data access object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class DuracionConsultaDao:

    def getDuracionConsultas(self):

        duracionconsultaSQL = """
        SELECT id, descripcion
        FROM duracion_consulta
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(duracionconsultaSQL)
            duracionconsultas = cur.fetchall() # trae datos de la bd

            # Transformar los datos en una lista de diccionarios
            return [{'id': duracionconsulta[0], 'descripcion': duracionconsulta[1]} for duracionconsulta in duracionconsultas]

        except Exception as e:
            app.logger.error(f"Error al obtener todos las Duraciones de Consultas: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getDuracionConsultaById(self, id):

        duracionconsultaSQL = """
        SELECT id, descripcion
        FROM duracion_consulta WHERE id=%s
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(duracionconsultaSQL, (id,))
            duracionconsultaEncontrada = cur.fetchone() # Obtener una sola fila
            if duracionconsultaEncontrada:
                return {
                        "id": duracionconsultaEncontrada[0],
                        "descripcion": duracionconsultaEncontrada[1]
                    }  # Retornar los datos de las duraciones de consultas
            else:
                return None # Retornar None si no se encuentra las duraciones de conultas
        except Exception as e:
            app.logger.error(f"Error al obtener la duración de consulta: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarDuracionConsulta(self, descripcion):

        insertDuracionConsultaSQL = """
        INSERT INTO duracion_consulta(descripcion) VALUES(%s) RETURNING id
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        # Ejecucion exitosa
        try:
            cur.execute(insertDuracionConsultaSQL, (descripcion,))
            duracionconsulta_id = cur.fetchone()[0]
            con.commit() # se confirma la insercion
            return duracionconsulta_id

        # Si algo fallo entra aqui
        except Exception as e:
            app.logger.error(f"Error al insertar duración de la consulta: {str(e)}")
            con.rollback() # retroceder si hubo error
            return False

        # Siempre se va ejecutar
        finally:
            cur.close()
            con.close()

    def updateDuracionConsulta(self, id, descripcion):

        updateDuracionConsultaSQL = """
        UPDATE duracion_consulta
        SET descripcion=%s
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateDuracionConsultaSQL, (descripcion, id,))
            filas_afectadas = cur.rowcount # Obtener el número de filas afectadas
            con.commit()

            return filas_afectadas > 0 # Retornar True si se actualizó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al actualizar Duración de la Consulta: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deleteDuracionConsulta(self, id):

        updateDuracionConsultaSQL = """
        DELETE FROM duracion_consulta
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateDuracionConsultaSQL, (id,))
            rows_affected = cur.rowcount
            con.commit()

            return rows_affected > 0  # Retornar True si se eliminó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al eliminar Duración de la Consulta: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()