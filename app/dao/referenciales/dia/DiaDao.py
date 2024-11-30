# Data access object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class DiaDao:

    def getDias(self):

        diaSQL = """
        SELECT id, descripcion
        FROM dias
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(diaSQL)
            dias = cur.fetchall() # trae datos de la bd

            # Transformar los datos en una lista de diccionarios
            return [{'id': dia[0], 'descripcion': dia[1]} for dia in dias]

        except Exception as e:
            app.logger.error(f"Error al obtener todos los dias: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getDiaById(self, id):

        diaSQL = """
        SELECT id, descripcion
        FROM dias WHERE id=%s
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(diaSQL, (id,))
            diaEncontrada = cur.fetchone() # Obtener una sola fila
            if diaEncontrada:
                return {
                        "id": diaEncontrada[0],
                        "descripcion": diaEncontrada[1]
                    }  # Retornar los datos de los dias
            else:
                return None # Retornar None si no se encuentra el dia
        except Exception as e:
            app.logger.error(f"Error al obtener dia: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarDia(self, descripcion):

        insertDiaSQL = """
        INSERT INTO dias(descripcion) VALUES(%s) RETURNING id
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        # Ejecucion exitosa
        try:
            cur.execute(insertDiaSQL, (descripcion,))
            dia_id = cur.fetchone()[0]
            con.commit() # se confirma la insercion
            return dia_id

        # Si algo fallo entra aqui
        except Exception as e:
            app.logger.error(f"Error al insertar dia: {str(e)}")
            con.rollback() # retroceder si hubo error
            return False

        # Siempre se va ejecutar
        finally:
            cur.close()
            con.close()

    def updateDia(self, id, descripcion):

        updateDiaSQL = """
        UPDATE dias
        SET descripcion=%s
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateDiaSQL, (descripcion, id,))
            filas_afectadas = cur.rowcount # Obtener el número de filas afectadas
            con.commit()

            return filas_afectadas > 0 # Retornar True si se actualizó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al actualizar dia: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deleteDia(self, id):

        updateDiaSQL = """
        DELETE FROM dias
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateDiaSQL, (id,))
            rows_affected = cur.rowcount
            con.commit()

            return rows_affected > 0  # Retornar True si se eliminó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al eliminar dia: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()