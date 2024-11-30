# Data access object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class EspecialidadDao:

    def getEspecialidades(self):

        especialidadSQL = """
        SELECT id, descripcion
        FROM especialidades
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(especialidadSQL)
            especialidades = cur.fetchall() # trae datos de la bd

            # Transformar los datos en una lista de diccionarios
            return [{'id': especialidad[0], 'descripcion': especialidad[1]} for especialidad in especialidades]

        except Exception as e:
            app.logger.error(f"Error al obtener todas las especialidades: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getEspecialidadById(self, id):

        especialidadSQL = """
        SELECT id, descripcion
        FROM especialidades WHERE id=%s
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(especialidadSQL, (id,))
            especialidadEncontrada = cur.fetchone() # Obtener una sola fila
            if especialidadEncontrada:
                return {
                        "id": especialidadEncontrada[0],
                        "descripcion": especialidadEncontrada[1]
                    }  # Retornar los datos de la ciudad
            else:
                return None # Retornar None si no se encuentra la especialidad
        except Exception as e:
            app.logger.error(f"Error al obtener especialidad: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarEspecialidad(self, descripcion):

        insertEspecialidadSQL = """
        INSERT INTO especialidades(descripcion) VALUES(%s) RETURNING id
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        # Ejecucion exitosa
        try:
            cur.execute(insertEspecialidadSQL, (descripcion,))
            ciudad_id = cur.fetchone()[0]
            con.commit() # se confirma la insercion
            return ciudad_id

        # Si algo fallo entra aqui
        except Exception as e:
            app.logger.error(f"Error al insertar especialidad: {str(e)}")
            con.rollback() # retroceder si hubo error
            return False

        # Siempre se va ejecutar
        finally:
            cur.close()
            con.close()

    def updateEspecialidad(self, id, descripcion):

        updateEspecialidadSQL = """
        UPDATE especialidades
        SET descripcion=%s
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateEspecialidadSQL, (descripcion, id,))
            filas_afectadas = cur.rowcount # Obtener el número de filas afectadas
            con.commit()

            return filas_afectadas > 0 # Retornar True si se actualizó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al actualizar especialidad: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deleteEspecialidad(self, id):

        updateEspecialidadSQL = """
        DELETE FROM especialidades
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateEspecialidadSQL, (id,))
            rows_affected = cur.rowcount
            con.commit()

            return rows_affected > 0  # Retornar True si se eliminó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al eliminar especialidad: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()