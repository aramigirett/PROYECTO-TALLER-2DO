# Data access object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class TurnoDao:

    def getTurnos(self):

        turnoSQL = """
        SELECT id, descripcion
        FROM turnos
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(turnoSQL)
            turnos = cur.fetchall() # trae datos de la bd

            # Transformar los datos en una lista de diccionarios
            return [{'id': turno[0], 'descripcion': turno[1]} for turno in turnos]

        except Exception as e:
            app.logger.error(f"Error al obtener todos los turnos: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getTurnoById(self, id):

        turnoSQL = """
        SELECT id, descripcion
        FROM turnos WHERE id=%s
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(turnoSQL, (id,))
            turnoEncontrado = cur.fetchone() # Obtener una sola fila
            if turnoEncontrado:
                return {
                        "id": turnoEncontrado[0],
                        "descripcion": turnoEncontrado[1]
                    }  # Retornar los datos de la turno
            else:
                return None # Retornar None si no se encuentra la turno
        except Exception as e:
            app.logger.error(f"Error al obtener turno: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarTurno(self, descripcion):

        insertTurnoSQL = """
        INSERT INTO turnos(descripcion) VALUES(%s) RETURNING id
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        # Ejecucion exitosa
        try:
            cur.execute(insertTurnoSQL, (descripcion,))
            turno_id = cur.fetchone()[0]
            con.commit() # se confirma la insercion
            return turno_id

        # Si algo fallo entra aqui
        except Exception as e:
            app.logger.error(f"Error al insertar turno: {str(e)}")
            con.rollback() # retroceder si hubo error
            return False

        # Siempre se va ejecutar
        finally:
            cur.close()
            con.close()

    def updateTurno(self, id, descripcion):

        updateTurnoSQL = """
        UPDATE turnos
        SET descripcion=%s
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateTurnoSQL, (descripcion, id,))
            filas_afectadas = cur.rowcount # Obtener el número de filas afectadas
            con.commit()

            return filas_afectadas > 0 # Retornar True si se actualizó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al actualizar turno: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deleteTurno(self, id):

        updateTurnoSQL = """
        DELETE FROM turnos
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateTurnoSQL, (id,))
            rows_affected = cur.rowcount
            con.commit()

            return rows_affected > 0  # Retornar True si se eliminó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al eliminar turno: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

            