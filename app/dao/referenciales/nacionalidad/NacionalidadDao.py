# Data access object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class NacionalidadDao:

    def getNacionalidades(self):

        nacionalidadSQL = """
        SELECT id, descripcion
        FROM nacionalidades
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(nacionalidadSQL)
            nacionalidades = cur.fetchall() # trae datos de la bd

            # Transformar los datos en una lista de diccionarios
            return [{'id': nacionalidad[0], 'descripcion': nacionalidad[1]} for nacionalidad in nacionalidades]

        except Exception as e:
            app.logger.error(f"Error al obtener todas las nacionalidades: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getNacionalidadById(self, id):

        nacionalidadSQL = """
        SELECT id, descripcion
        FROM nacionalidades WHERE id=%s
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(nacionalidadSQL, (id,))
            nacionalidadEncontrada = cur.fetchone() # Obtener una sola fila
            if nacionalidadEncontrada:
                return {
                        "id": nacionalidadEncontrada[0],
                        "descripcion": nacionalidadEncontrada[1]
                    }  # Retornar los datos de nacionalidad
            else:
                return None # Retornar None si no se encuentra la nacionalidad
        except Exception as e:
            app.logger.error(f"Error al obtener nacionalidad: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarNacionalidad(self, descripcion):

        insertNacionalidadSQL = """
        INSERT INTO nacionalidades(descripcion) VALUES(%s) RETURNING id
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        # Ejecucion exitosa
        try:
            cur.execute(insertNacionalidadSQL, (descripcion,))
            nacionalidad_id = cur.fetchone()[0]
            con.commit() # se confirma la insercion
            return nacionalidad_id

        # Si algo fallo entra aqui
        except Exception as e:
            app.logger.error(f"Error al insertar nacionalidad: {str(e)}")
            con.rollback() # retroceder si hubo error
            return False

        # Siempre se va ejecutar
        finally:
            cur.close()
            con.close()

    def updateNacionalidad(self, id, descripcion):

        updateNacionalidadSQL = """
        UPDATE nacionalidades
        SET descripcion=%s
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateNacionalidadSQL, (descripcion, id,))
            filas_afectadas = cur.rowcount # Obtener el número de filas afectadas
            con.commit()

            return filas_afectadas > 0 # Retornar True si se actualizó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al actualizar nacionalidad: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deleteNacionalidad(self, id):

        updateNacionalidadSQL = """
        DELETE FROM nacionalidades
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateNacionalidadSQL, (id,))
            rows_affected = cur.rowcount
            con.commit()

            return rows_affected > 0  # Retornar True si se eliminó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al eliminar nacionalidad: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()
            