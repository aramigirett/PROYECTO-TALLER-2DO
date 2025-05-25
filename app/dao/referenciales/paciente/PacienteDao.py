from flask import current_app as app
from app.conexion.Conexion import Conexion

class PacienteDao:
    def getPacientes(self):
        pacienteSQL = """
        SELECT 
          p.id_paciente, p.nombre, p.apellido, p.fecha_nacimiento, p.cedula, p.genero, 
          p.telefono, p.direccion, p.correo, p.id_ciudad, c.descripcion AS ciudad
        FROM pacientes p
        LEFT JOIN ciudades c ON p.id_ciudad = c.id_ciudad
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(pacienteSQL)
            pacientes = cur.fetchall()

            return [
                {
                    'id': p[0],
                    'nombre': p[1],
                    'apellido': p[2],
                    'fecha_nacimiento': p[3],
                    'cedula': p[4],
                    'genero': p[5],
                    'telefono': p[6],
                    'direccion': p[7],
                    'correo': p[8],
                    'id_ciudad': p[9],
                    'ciudad': p[10]
                }
                for p in pacientes
            ]

        except Exception as e:
            app.logger.error(f"Error al obtener todos los pacientes: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getPacienteById(self, id_paciente):
        pacienteSQL = """
        SELECT 
          p.id_paciente, p.nombre, p.apellido, p.fecha_nacimiento, p.cedula, p.genero, 
          p.telefono, p.direccion, p.correo, p.id_ciudad, c.descripcion AS ciudad
        FROM pacientes p
        LEFT JOIN ciudades c ON p.id_ciudad = c.id_ciudad
        WHERE p.id_paciente = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(pacienteSQL, (id_paciente,))
            p = cur.fetchone()
            if p:
                return {
                    'id': p[0],
                    'nombre': p[1],
                    'apellido': p[2],
                    'fecha_nacimiento': p[3],
                    'cedula': p[4],
                    'genero': p[5],
                    'telefono': p[6],
                    'direccion': p[7],
                    'correo': p[8],
                    'id_ciudad': p[9],
                    'ciudad': p[10]
                }
            else:
                return None

        except Exception as e:
            app.logger.error(f"Error al obtener paciente por ID: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarPaciente(self, nombre, apellido, fecha_nacimiento, cedula, genero, telefono, direccion, correo, id_ciudad):
        insertPacienteSQL = """
        INSERT INTO pacientes(nombre, apellido, fecha_nacimiento, cedula, genero, telefono, direccion, correo, id_ciudad) 
        VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_paciente
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(insertPacienteSQL, (nombre, apellido, fecha_nacimiento, cedula, genero, telefono, direccion, correo, id_ciudad))
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

    def updatePaciente(self, id_paciente, nombre, apellido, fecha_nacimiento, cedula, genero, telefono, direccion, correo, id_ciudad):
        updatePacienteSQL = """
        UPDATE pacientes
        SET nombre=%s, apellido=%s, fecha_nacimiento=%s, cedula=%s, genero=%s, 
            telefono=%s, direccion=%s, correo=%s, id_ciudad=%s
        WHERE id_paciente=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(updatePacienteSQL, (nombre, apellido, fecha_nacimiento, cedula, genero, telefono, direccion, correo, id_ciudad, id_paciente))
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
