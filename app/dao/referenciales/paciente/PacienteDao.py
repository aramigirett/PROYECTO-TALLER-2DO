from flask import current_app as app
from app.conexion.Conexion import Conexion

class PacienteDao:

    # Obtener todos los pacientes
    def getPacientes(self):
        pacienteSQL = """
        SELECT 
            pa.id_paciente,
            p.nombre,
            p.apellido,
            p.sexo,
            p.cedula,
            p.telefono,
            p.fechanacimiento,
            pa.direccion,
            pa.correo,
            f.nro_ficha
        FROM pacientes pa
        JOIN persona p ON pa.id_persona = p.id_persona
        JOIN fichas f ON pa.id_ficha = f.id_ficha
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(pacienteSQL)
            pacientes = cur.fetchall()  # trae datos de la bd

            # Transformar los datos en una lista de diccionarios
            return [
                {
                    'id_paciente': paciente[0],
                    'nombre': paciente[1],
                    'apellido': paciente[2],
                    'sexo': paciente[3],
                    'cedula': paciente[4],
                    'telefono': paciente[5],
                    'fechanacimiento': paciente[6],
                    'direccion': paciente[7],
                    'correo': paciente[8],
                    'nro_ficha': paciente[9]
                }
                for paciente in pacientes
            ]

        except Exception as e:
            app.logger.error(f"Error al obtener todos los pacientes: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    # Obtener un paciente por ID
    def getPacienteById(self, id_paciente):
        pacienteSQL = """
        SELECT 
            pa.id_paciente,
            p.nombre,
            p.apellido,
            p.sexo,
            p.cedula,
            p.telefono,
            p.fechanacimiento,
            pa.direccion,
            pa.correo,
            f.nro_ficha
        FROM pacientes pa
        JOIN persona p ON pa.id_persona = p.id_persona
        JOIN fichas f ON pa.id_ficha = f.id_ficha
        WHERE pa.id_paciente = %s
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(pacienteSQL, (id_paciente,))
            paciente = cur.fetchone()  # Obtener una sola fila
            if paciente:
                return {
                    'id_paciente': paciente[0],
                    'nombre': paciente[1],
                    'apellido': paciente[2],
                    'sexo': paciente[3],
                    'cedula': paciente[4],
                    'telefono': paciente[5],
                    'fechanacimiento': paciente[6],
                    'direccion': paciente[7],
                    'correo': paciente[8],
                    'nro_ficha': paciente[9]
                }
            else:
                return None

        except Exception as e:
            app.logger.error(f"Error al obtener paciente: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    # Guardar un nuevo paciente
    def guardarPaciente(self, id_persona, id_ficha, direccion, correo):
        insertPacienteSQL = """
        INSERT INTO pacientes(id_persona, id_ficha, direccion, correo) 
        VALUES(%s, %s, %s, %s) RETURNING id_paciente
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(insertPacienteSQL, (id_persona, id_ficha, direccion, correo))
            paciente_id = cur.fetchone()[0]
            con.commit()  # se confirma la inserción
            return paciente_id

        except Exception as e:
            app.logger.error(f"Error al insertar paciente: {str(e)}")
            con.rollback()  # retroceder si hubo error
            return False

        finally:
            cur.close()
            con.close()

    # Actualizar un paciente
    def updatePaciente(self, id_paciente, id_persona, id_ficha, direccion, correo):
        updatePacienteSQL = """
        UPDATE pacientes
        SET id_persona=%s, id_ficha=%s, direccion=%s, correo=%s
        WHERE id_paciente=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updatePacienteSQL, (id_persona, id_ficha, direccion, correo, id_paciente))
            filas_afectadas = cur.rowcount  # Obtener el número de filas afectadas
            con.commit()

            return filas_afectadas > 0  # Retornar True si se actualizó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al actualizar paciente: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    # Eliminar un paciente
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
            rows_affected = cur.rowcount
            con.commit()

            return rows_affected > 0  # Retornar True si se eliminó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al eliminar paciente: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()