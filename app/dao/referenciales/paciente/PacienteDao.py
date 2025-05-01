from flask import current_app as app
from app.conexion.Conexion import Conexion

class PacienteDao:
    def getPacientes(self):
        pacienteSQL = """
        SELECT 
          id_paciente, nombre, apellido, fechanacimiento, cedula, sexo, telefono, direccion, correo
        FROM pacientes
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(pacienteSQL)
            pacientes = cur.fetchall()

            return [
                {
                    'id': paciente[0],
                    'nombre': paciente[1],
                    'apellido': paciente[2],
                    'fechanacimiento': paciente[3],
                    'cedula': paciente[4],
                    'sexo': paciente[5],
                    'telefono': paciente[6],
                    'direccion': paciente[7],
                    'correo': paciente[8]
                }
                for paciente in pacientes
            ]

        except Exception as e:
            app.logger.error(f"Error al obtener todas las pacientes: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getPacienteById(self, id_paciente):
        pacienteSQL = """
        SELECT 
          id_paciente, nombre, apellido, fechanacimiento, cedula, sexo, telefono, direccion, correo
        FROM pacientes
        WHERE id_paciente = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(pacienteSQL, (id_paciente,))
            paciente = cur.fetchone()
            if paciente:
                return {
                    'id': paciente[0],
                    'nombre': paciente[1],
                    'apellido': paciente[2],
                    'fechanacimiento': paciente[3],
                    'cedula': paciente[4],
                    'sexo': paciente[5],
                    'telefono': paciente[6],
                    'direccion': paciente[7],
                    'correo': paciente[8]
                }
            else:
                return None

        except Exception as e:
            app.logger.error(f"Error al obtener paciente: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarPaciente(self, nombre, apellido, fechanacimiento, cedula, sexo, telefono, direccion, correo):
        insertPacienteSQL = """
        INSERT INTO pacientes(nombre, apellido, fechanacimiento, cedula, sexo, telefono, direccion, correo) 
        VALUES(%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_paciente
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(insertPacienteSQL, (nombre, apellido, fechanacimiento, cedula, sexo, telefono, direccion, correo))
            paciente_id = cur.fetchone()[0]
            con.commit()
            return paciente_id

        except Exception as e:
            app.logger.error(f"Error al insertar paciente: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def updatePaciente(self, id_paciente, nombre, apellido, fechanacimiento, cedula, sexo, telefono, direccion, correo):
        updatePacienteSQL = """
        UPDATE pacientes
        SET nombre=%s, apellido=%s, fechanacimiento=%s, cedula=%s, sexo=%s, telefono=%s, direccion=%s, correo=%s
        WHERE id_paciente=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(updatePacienteSQL, (nombre, apellido, fechanacimiento, cedula, sexo, telefono, direccion, correo, id_paciente))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0

        except Exception as e:
            app.logger.error(f"Error al actualizar paciente: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deletePaciente(self, id_paciente):
        deletePacienteSQL = """
        DELETE FROM pacientes
        WHERE id_paciente=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(deletePacienteSQL, (id_paciente,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0

        except Exception as e:
            app.logger.error(f"Error al eliminar paciente: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()
