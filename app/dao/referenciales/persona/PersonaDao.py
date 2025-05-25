from flask import current_app as app
from app.conexion.Conexion import Conexion

class PersonaDao:

    def getPersonas(self):
        personaSQL = """
        SELECT
            pe.id_persona,
            p.nombre,
            p.apellido,
            p.cedula,
            p.telefono,
            pe.fecha_nacimiento
        FROM 
            personas pe
            INNER JOIN pacientes p ON pe.id_paciente = p.id_paciente
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(personaSQL)
            personas = cur.fetchall()
            return [
                {
                    'id_persona': persona[0],
                    'nombre': persona[1],
                    'apellido': persona[2],
                    'cedula': persona[3],
                    'telefono': persona[4],
                    'fecha_nacimiento': persona[5].strftime('%d/%m/%Y') if persona[5] else None
                }
                for persona in personas
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener todos los pacientes: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getPersonaById(self, id_persona):
        personaSQL = """
        SELECT 
            pe.id_persona,
            p.nombre,
            p.apellido,
            p.cedula,
            p.telefono,
            pe.fecha_nacimiento,
            p.id_paciente
        FROM 
            personas pe
            INNER JOIN pacientes p ON pe.id_paciente = p.id_paciente
        WHERE 
            pe.id_persona = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(personaSQL, (id_persona,))
            persona = cur.fetchone()
            if persona:
                return {
                    "id_persona": persona[0],
                    "nombre": persona[1],
                    "apellido": persona[2],
                    "cedula": persona[3],
                    "telefono": persona[4],
                    "fecha_nacimiento": persona[5],
                    "id_paciente": persona[6]
                }
            else:
                return None
        except Exception as e:
            app.logger.error(f"Error al obtener paciente por ID: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def guardarPersona(self, id_paciente, fecha_nacimiento):
        insertPersonaSQL = """
        INSERT INTO personas (id_paciente, fecha_nacimiento)
        VALUES (%s, %s)
        RETURNING id_persona
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(insertPersonaSQL, (id_paciente, fecha_nacimiento))
            id_persona = cur.fetchone()[0]
            con.commit()
            return id_persona
        except Exception as e:
            app.logger.error(f"Error al insertar paciente: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updatePersona(self, id_persona, id_paciente, fecha_nacimiento):
        updatePersonaSQL = """
        UPDATE personas
        SET id_paciente = %s,
            fecha_nacimiento = %s
        WHERE id_persona = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(updatePersonaSQL, (id_paciente, fecha_nacimiento, id_persona))
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

    def deletePersona(self, id_persona):
        deletePersonaSQL = """
        DELETE FROM personas
        WHERE id_persona = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(deletePersonaSQL, (id_persona,))
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
