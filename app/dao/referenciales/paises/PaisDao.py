# Data access object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class PaisDao:

    def getPaises(self):

        paisSQL = """
        SELECT id, descripcion
        FROM paises
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(paisSQL)
            paises = cur.fetchall() # trae datos de la bd

            # Transformar los datos en una lista de diccionarios
            return [{'id': pais[0], 'descripcion': pais[1]} for pais in paises]

        except Exception as e:
            app.logger.error(f"Error al obtener todas las paises: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getPaisById(self, id):

        paisSQL = """
        SELECT id, descripcion
        FROM paises WHERE id=%s
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(paisSQL, (id,))
            paisEncontrada = cur.fetchone() # Obtener una sola fila
            if paisEncontrada:
                return {
                        "id": paisEncontrada[0],
                        "descripcion": paisEncontrada[1]
                    }  # Retornar los datos de pais
            else:
                return None # Retornar None si no se encuentra el pais
        except Exception as e:
            app.logger.error(f"Error al obtener pais: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarPais(self, descripcion):

        insertPaisSQL = """
        INSERT INTO paises(descripcion) VALUES(%s) RETURNING id
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        # Ejecucion exitosa
        try:
            cur.execute(insertPaisSQL, (descripcion,))
            pais_id = cur.fetchone()[0]
            con.commit() # se confirma la insercion
            return pais_id

        # Si algo fallo entra aqui
        except Exception as e:
            app.logger.error(f"Error al insertar pais: {str(e)}")
            con.rollback() # retroceder si hubo error
            return False

        # Siempre se va ejecutar
        finally:
            cur.close()
            con.close()

    def updatePais(self, id, descripcion):

        updatePaisSQL = """
        UPDATE paises
        SET descripcion=%s
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updatePaisSQL, (descripcion, id,))
            filas_afectadas = cur.rowcount # Obtener el número de filas afectadas
            con.commit()

            return filas_afectadas > 0 # Retornar True si se actualizó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al actualizar pais: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deletePais(self, id):

        updatePaisSQL = """
        DELETE FROM paises
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updatePaisSQL, (id,))
            rows_affected = cur.rowcount
            con.commit()

            return rows_affected > 0  # Retornar True si se eliminó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al eliminar pais: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()