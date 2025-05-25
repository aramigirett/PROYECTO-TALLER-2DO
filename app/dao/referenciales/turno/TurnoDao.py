# Data access object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class TurnoDao:

    def getTurnos(self):

        turnoSQL = """
        SELECT id_turno, descripcion
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
            return [{'id_turno': turno[0], 'descripcion': turno[1]} for turno in turnos]

        except Exception as e:
            app.logger.error(f"Error al obtener todos los turnos: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getTurnoById(self, id_turno):

        turnoSQL = """
        SELECT id_turno, descripcion
        FROM turnos WHERE id_turno=%s
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(turnoSQL, (id_turno,))
            turnoEncontrado = cur.fetchone() # Obtener una sola fila
            if turnoEncontrado:
                return {
                        "id_turno": turnoEncontrado[0],
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
        INSERT INTO turnos(descripcion) VALUES(%s) RETURNING id_turno
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

    def updateTurno(self, id_turno, descripcion):

        updateTurnoSQL = """
        UPDATE turnos
        SET descripcion=%s
        WHERE id_turno=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateTurnoSQL, (descripcion, id_turno,))
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

    def deleteTurno(self, id_turno):

        updateTurnoSQL = """
        DELETE FROM turnos
        WHERE id_turno=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateTurnoSQL, (id_turno,))
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

            