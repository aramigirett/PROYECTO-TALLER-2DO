# Data access object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class InstrumentoDao:

    def getInstrumentos(self):
        instrumentoSQL = """
        SELECT id_instrumento, descripcion
        FROM instrumentos
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(instrumentoSQL)
            instrumentos = cur.fetchall()  # trae datos de la bd

            # Transformar los datos en una lista de diccionarios
            return [{'id_instrumento': instrumento[0], 'descripcion': instrumento[1]} for instrumento in instrumentos]

        except Exception as e:
            app.logger.error(f"Error al obtener todos los instrumentos: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getInstrumentoById(self, id):
        instrumentoSQL = """
        SELECT id_instrumento, descripcion
        FROM instrumentos WHERE id_instrumento=%s
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(instrumentoSQL, (id,))
            instrumentoEncontrado = cur.fetchone()  # Obtener una sola fila
            if instrumentoEncontrado:
                return {
                    "id_instrumento": instrumentoEncontrado[0],
                    "descripcion": instrumentoEncontrado[1]
                }  # Retornar los datos del instrumento
            else:
                return None  # Retornar None si no se encuentra el instrumento
        except Exception as e:
            app.logger.error(f"Error al obtener instrumento: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarInstrumento(self, descripcion):
        insertInstrumentoSQL = """
        INSERT INTO instrumentos(descripcion) VALUES(%s) RETURNING id_instrumento
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        # Ejecucion exitosa
        try:
            cur.execute(insertInstrumentoSQL, (descripcion,))
            instrumento_id = cur.fetchone()[0]
            con.commit()  # se confirma la insercion
            return instrumento_id

        # Si algo fallo entra aqui
        except Exception as e:
            app.logger.error(f"Error al insertar instrumento: {str(e)}")
            con.rollback()  # retroceder si hubo error
            return False

        # Siempre se va ejecutar
        finally:
            cur.close()
            con.close()

    def updateInstrumento(self, id, descripcion):
        updateInstrumentoSQL = """
        UPDATE instrumentos
        SET descripcion=%s
        WHERE id_instrumento=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateInstrumentoSQL, (descripcion, id,))
            filas_afectadas = cur.rowcount  # Obtener el número de filas afectadas
            con.commit()

            return filas_afectadas > 0  # Retornar True si se actualizó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al actualizar instrumento: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deleteInstrumento(self, id):
        deleteInstrumentoSQL = """
        DELETE FROM instrumentos
        WHERE id_instrumento=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(deleteInstrumentoSQL, (id,))
            rows_affected = cur.rowcount
            con.commit()

            return rows_affected > 0  # Retornar True si se eliminó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al eliminar instrumento: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()
