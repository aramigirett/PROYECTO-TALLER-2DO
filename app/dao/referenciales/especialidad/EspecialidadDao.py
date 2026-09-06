# Data access object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class EspecialidadDao:

    def getEspecialidades(self):
        especialidadSQL = """
        SELECT id_especialidad, nombre_especialidad
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
            return [{'id_especialidad': especialidad[0], 'nombre_especialidad': especialidad[1]} for especialidad in especialidades]

        except Exception as e:
            app.logger.error(f"Error al obtener todas las especialidades: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getEspecialidadById(self, id_especialidad):
        especialidadSQL = """
        SELECT id_especialidad, nombre_especialidad
        FROM especialidades WHERE id_especialidad=%s
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(especialidadSQL, (id_especialidad,))
            especialidadEncontrada = cur.fetchone() # Obtener una sola fila
            if especialidadEncontrada:
                return {
                        "id_especialidad": especialidadEncontrada[0],
                        "nombre_especialidad": especialidadEncontrada[1]
                    }  # Retornar los datos de la ciudad
            else:
                return None # Retornar None si no se encuentra la especialidad
        except Exception as e:
            app.logger.error(f"Error al obtener especialidad: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarEspecialidad(self, nombre_especialidad):
        insertEspecialidadSQL = """
        INSERT INTO especialidades(nombre_especialidad) VALUES(%s) RETURNING id_especialidad
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        # Ejecucion exitosa
        try:
            cur.execute(insertEspecialidadSQL, (nombre_especialidad,))
            especialidad_id = cur.fetchone()[0]
            con.commit() # se confirma la insercion
            return especialidad_id

        # Si algo fallo entra aqui
        except Exception as e:
            app.logger.error(f"Error al insertar especialidad: {str(e)}")
            con.rollback() # retroceder si hubo error
            return False

        # Siempre se va ejecutar
        finally:
            cur.close()
            con.close()

    def updateEspecialidad(self, id_especialidad, nombre_especialidad):
        updateEspecialidadSQL = """
        UPDATE especialidades
        SET nombre_especialidad=%s
        WHERE id_especialidad=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateEspecialidadSQL, (nombre_especialidad, id_especialidad,))
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

    def estaEnUso(self, id_especialidad):
        """Indica si la especialidad está asignada a algún médico o agenda."""
        sql = """
        SELECT
            EXISTS(SELECT 1 FROM medico WHERE id_especialidad = %s) AS en_medico,
            EXISTS(SELECT 1 FROM agenda_cabecera WHERE id_especialidad = %s) AS en_agenda
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_especialidad, id_especialidad))
            en_medico, en_agenda = cur.fetchone()
            return bool(en_medico or en_agenda)
        except Exception as e:
            app.logger.error(f"Error al verificar uso de especialidad: {str(e)}")
            return True  # Ante la duda, bloquear el borrado
        finally:
            cur.close()
            con.close()

    def deleteEspecialidad(self, id_especialidad):
        if self.estaEnUso(id_especialidad):
            app.logger.warning(f"No se puede eliminar especialidad {id_especialidad}: está en uso")
            return "EN_USO"

        deleteEspecialidadSQL = """
        DELETE FROM especialidades
        WHERE id_especialidad=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(deleteEspecialidadSQL, (id_especialidad,))
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