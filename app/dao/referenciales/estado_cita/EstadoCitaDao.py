# Data access object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class EstadoCitaDao:

    def getEstadosCitas(self):

        estadocitaSQL = """
        SELECT id, descripcion
        FROM estado_cita
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(estadocitaSQL)
            estadoscitas = cur.fetchall() # trae datos de la bd

            # Transformar los datos en una lista de diccionarios
            return [{'id': estadocita[0], 'descripcion': estadocita[1]} for estadocita in estadoscitas]

        except Exception as e:
            app.logger.error(f"Error al obtener todos los Estados de Cita: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getEstadoCitaById(self, id):

        estadocitaSQL = """
        SELECT id, descripcion
        FROM estado_cita WHERE id=%s
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(estadocitaSQL, (id,))
            estadocitaEncontrada = cur.fetchone() # Obtener una sola fila
            if estadocitaEncontrada:
                return {
                        "id": estadocitaEncontrada[0],
                        "descripcion": estadocitaEncontrada[1]
                    }  # Retornar los datos de los estados de cita
            else:
                return None # Retornar None si no se encuentra los estados de citas
        except Exception as e:
            app.logger.error(f"Error al obtener el estado de cita: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarEstadoCita(self, descripcion):

        insertEstadoCitaSQL = """
        INSERT INTO estado_cita(descripcion) VALUES(%s) RETURNING id
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        # Ejecucion exitosa
        try:
            cur.execute(insertEstadoCitaSQL, (descripcion,))
            estadocita_id = cur.fetchone()[0]
            con.commit() # se confirma la insercion
            return estadocita_id

        # Si algo fallo entra aqui
        except Exception as e:
            app.logger.error(f"Error al insertar estado de cita: {str(e)}")
            con.rollback() # retroceder si hubo error
            return False

        # Siempre se va ejecutar
        finally:
            cur.close()
            con.close()

    def updateEstadoCita(self, id, descripcion):

        updateEstadoCitaSQL = """
        UPDATE estado_cita
        SET descripcion=%s
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateEstadoCitaSQL, (descripcion, id,))
            filas_afectadas = cur.rowcount # Obtener el número de filas afectadas
            con.commit()

            return filas_afectadas > 0 # Retornar True si se actualizó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al actualizar Estado de Cita: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deleteEstadoCita(self, id):

        updateEstadoCitaSQL = """
        DELETE FROM estado_cita
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateEstadoCitaSQL, (id,))
            rows_affected = cur.rowcount
            con.commit()

            return rows_affected > 0  # Retornar True si se eliminó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al eliminar Estado de Cita: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()