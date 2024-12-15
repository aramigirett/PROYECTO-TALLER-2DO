# Data access object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion  
class PersonaDao:

    def getPersonas(self):
        personaSQL = """
        SELECT 
         p.id_persona, p.nombre, p.apellido, p.fechanacimiento, p.cedula, p.sexo, p.telefono, c.descripcion AS ciudad, paises.descripcion AS pais, n.descripcion AS nacionalidad
        FROM personas p
        JOIN ciudades c ON p.id_ciudad = c.id_ciudad
        JOIN paises ON p.id_pais = paises.id_pais
        JOIN nacionalidades n ON p.id_nacionalidad = n.id_nacionalidad
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(personaSQL)
            personas = cur.fetchall()  # trae datos de la bd

            # Transformar los datos en una lista de diccionarios
            return [
                {
                    'id': persona[0],
                    'nombre': persona[1],
                    'apellido': persona[2],
                    'fechanacimiento': persona[3],
                    'cedula': persona[4],
                    'sexo': persona[5],
                    'telefono': persona[6],
                    'ciudad': persona[7],
                    'pais': persona[8],
                    'nacionalidad': persona[9]
                }
                for persona in personas
            ]

        except Exception as e:
            app.logger.error(f"Error al obtener todas las personas: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getPersonasById(self, id_persona):
        personaSQL = """
        SELECT 
            p.id_persona, p.nombre, p.apellido, p.fechanacimiento, p.cedula, p.sexo, p.telefono, c.descripcion AS ciudad, paises.descripcion AS pais, n.descripcion AS nacionalidad
        FROM personas p
        JOIN ciudades c ON p.id_ciudad = c.id_ciudad
        JOIN paises ON p.id_pais = paises.id_pais
        JOIN nacionalidades n ON p.id_nacionalidad = n.id_nacionalidad
        WHERE p.id_persona = %s
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(personaSQL, (id_persona,))
            personaEncontrada = cur.fetchone()  # Obtener una sola fila
            if personaEncontrada:
                return {
                    "id": personaEncontrada[0],
                    "nombre": personaEncontrada[1],
                    "apellido": personaEncontrada[2],
                    "fechanacimiento": personaEncontrada[3],
                    "cedula": personaEncontrada[4],
                    "sexo": personaEncontrada[5],
                    "telefono": personaEncontrada[6],
                    "ciudad": personaEncontrada[7],
                    "pais": personaEncontrada[8],
                    "nacionalidad": personaEncontrada[9]
                }  # Retornar los datos de persona
            else:
                return None  # Retornar None si no se encuentra la persona
        except Exception as e:
            app.logger.error(f"Error al obtener persona: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarPersona(self, nombre, apellido, fechanacimiento, cedula, sexo, telefono, id_ciudad, id_pais, id_nacionalidad):
        insertPersonaSQL = """
        INSERT INTO personas(nombre, apellido, fechanacimiento, cedula, sexo, telefono, id_ciudad, id_pais, id_nacionalidad) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_persona
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        # Ejecucion exitosa
        try:
            cur.execute(insertPersonaSQL, (nombre, apellido, fechanacimiento, cedula, sexo, telefono, id_ciudad, id_pais, id_nacionalidad))
            persona_id = cur.fetchone()[0]
            con.commit()  # se confirma la insercion
            return persona_id

        # Si algo fallo entra aqui
        except Exception as e:
            app.logger.error(f"Error al insertar persona: {str(e)}")
            con.rollback()  # retroceder si hubo error
            return False

        # Siempre se va ejecutar
        finally:
            cur.close()
            con.close()

    def updatePersona(self, id_persona, nombre, apellido, fechanacimiento, cedula, sexo, telefono, id_ciudad, id_pais, id_nacionalidad):
        updatePersonaSQL = """
        UPDATE personas
        SET nombre=%s, apellido=%s, fechanacimiento=%s, cedula=%s, sexo=%s, telefono=%s, id_ciudad=%s, id_pais=%s, id_nacionalidad=%s
        WHERE id_persona=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updatePersonaSQL, (nombre, apellido, fechanacimiento, cedula, sexo, telefono, id_ciudad, id_pais, id_nacionalidad, id_persona))
            filas_afectadas = cur.rowcount  # Obtener el número de filas afectadas
            con.commit()

            return filas_afectadas > 0  # Retornar True si se actualizó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al actualizar persona: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deletePersona(self, id_persona):
        deletePersonaSQL = """
        DELETE FROM personas
        WHERE id_persona=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(deletePersonaSQL, (id_persona,))
            rows_affected = cur.rowcount
            con.commit()

            return rows_affected > 0  # Retornar True si se eliminó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al eliminar persona: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()
