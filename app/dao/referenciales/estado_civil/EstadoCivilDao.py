# Data access object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class EstadoCivilDao:

    def getEstadosCiviles(self):

        estadocivilSQL = """
        SELECT id, descripcion
        FROM estado_civil
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(estadocivilSQL)
            estadosciviles = cur.fetchall() # trae datos de la bd

            # Transformar los datos en una lista de diccionarios
            return [{'id': estadocivil[0], 'descripcion': estadocivil[1]} for estadocivil in estadosciviles]

        except Exception as e:
            app.logger.error(f"Error al obtener todos los Estados Civiles: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getEstadoCivilById(self, id):

        estadocivilSQL = """
        SELECT id, descripcion
        FROM estado_civil WHERE id=%s
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(estadocivilSQL, (id,))
            estadocivilEncontrada = cur.fetchone() # Obtener una sola fila
            if estadocivilEncontrada:
                return {
                        "id": estadocivilEncontrada[0],
                        "descripcion": estadocivilEncontrada[1]
                    }  # Retornar los datos de los estados civiles
            else:
                return None # Retornar None si no se encuentra los estados civiles
        except Exception as e:
            app.logger.error(f"Error al obtener el estado civil: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarEstadoCivil(self, descripcion):

        insertEstadoCivilSQL = """
        INSERT INTO estado_civil(descripcion) VALUES(%s) RETURNING id
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        # Ejecucion exitosa
        try:
            cur.execute(insertEstadoCivilSQL, (descripcion,))
            estadocivil_id = cur.fetchone()[0]
            con.commit() # se confirma la insercion
            return estadocivil_id

        # Si algo fallo entra aqui
        except Exception as e:
            app.logger.error(f"Error al insertar estado civil: {str(e)}")
            con.rollback() # retroceder si hubo error
            return False

        # Siempre se va ejecutar
        finally:
            cur.close()
            con.close()

    def updateEstadoCivil(self, id, descripcion):

        updateEstadoCivilSQL = """
        UPDATE estado_civil
        SET descripcion=%s
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateEstadoCivilSQL, (descripcion, id,))
            filas_afectadas = cur.rowcount # Obtener el número de filas afectadas
            con.commit()

            return filas_afectadas > 0 # Retornar True si se actualizó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al actualizar Estado Civil: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deleteEstadoCivil(self, id):

        updateEstadoCivilSQL = """
        DELETE FROM estado_civil
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateEstadoCivilSQL, (id,))
            rows_affected = cur.rowcount
            con.commit()

            return rows_affected > 0  # Retornar True si se eliminó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al eliminar Estado Civil: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()