# Data access object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class SexoDao:

    def getSexos(self):

        sexoSQL = """
        SELECT id, descripcion
        FROM sexos
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sexoSQL)
            sexos = cur.fetchall() # trae datos de la bd

            # Transformar los datos en una lista de diccionarios
            return [{'id': sexo[0], 'descripcion': sexo[1]} for sexo in sexos]

        except Exception as e:
            app.logger.error(f"Error al obtener todos los sexos: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getSexoById(self, id):

        sexoSQL = """
        SELECT id, descripcion
        FROM sexos WHERE id=%s
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sexoSQL, (id,))
            sexoEncontrada = cur.fetchone() # Obtener una sola fila
            if sexoEncontrada:
                return {
                        "id": sexoEncontrada[0],
                        "descripcion": sexoEncontrada[1]
                    }  # Retornar los datos de la tabla sexo
            else:
                return None # Retornar None si no se encuentra la tabla sexo
        except Exception as e:
            app.logger.error(f"Error al obtener el sexo: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarSexo(self, descripcion):

        insertSexoSQL = """
        INSERT INTO sexos(descripcion) VALUES(%s) RETURNING id
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        # Ejecucion exitosa
        try:
            cur.execute(insertSexoSQL, (descripcion,))
            sexo_id = cur.fetchone()[0]
            con.commit() # se confirma la insercion
            return sexo_id

        # Si algo fallo entra aqui
        except Exception as e:
            app.logger.error(f"Error al insertar el sexo: {str(e)}")
            con.rollback() # retroceder si hubo error
            return False

        # Siempre se va ejecutar
        finally:
            cur.close()
            con.close()

    def updateSexo(self, id, descripcion):

        updateSexoSQL = """
        UPDATE sexos
        SET descripcion=%s
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateSexoSQL, (descripcion, id,))
            filas_afectadas = cur.rowcount # Obtener el número de filas afectadas
            con.commit()

            return filas_afectadas > 0 # Retornar True si se actualizó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al actualizar el sexo: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deleteSexo(self, id):

        updateSexoSQL = """
        DELETE FROM sexos
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateSexoSQL, (id,))
            rows_affected = cur.rowcount
            con.commit()

            return rows_affected > 0  # Retornar True si se eliminó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al eliminar el sexo: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()