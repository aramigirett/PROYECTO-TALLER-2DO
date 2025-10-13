from flask import current_app as app
from app.conexion.Conexion import Conexion

class PacienteDao:

    # ==============================
    #   Obtener todos los pacientes
    # ==============================
    def getPacientes(self):
        sql = """
            SELECT p.id_paciente, p.nombre, p.apellido,
                   p.cedula_entidad, p.fecha_nacimiento, p.fecha_registro,
                   p.telefono, p.direccion, p.correo,
                   p.id_ciudad, c.descripcion AS ciudades
            FROM paciente p
            LEFT JOIN ciudades c ON p.id_ciudad = c.id_ciudad
            ORDER BY p.id_paciente
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            pacientes = cur.fetchall()
            return [
                {
                    "id_paciente": p[0],
                    "nombre": p[1],
                    "apellido": p[2],
                    "cedula_entidad": p[3],
                    "fecha_nacimiento": str(p[4]) if p[4] else None,
                    "fecha_registro": str(p[5]) if p[5] else None,
                    "telefono": p[6],
                    "direccion": p[7],
                    "correo": p[8],
                    "id_ciudad": p[9],
                    "ciudades": p[10]
                }
                for p in pacientes
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener pacientes: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    # ==============================
    #   Obtener paciente por ID
    # ==============================
    def getPacienteById(self, paciente_id):
        sql = """
            SELECT p.id_paciente, p.nombre, p.apellido,
                   p.cedula_entidad, p.fecha_nacimiento, p.fecha_registro,
                   p.telefono, p.direccion, p.correo,
                   p.id_ciudad, c.descripcion AS ciudades
            FROM paciente p
            LEFT JOIN ciudades c ON p.id_ciudad = c.id_ciudad
            WHERE p.id_paciente = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (paciente_id,))
            p = cur.fetchone()
            if p:
                return {
                    "id_paciente": p[0],
                    "nombre": p[1],
                    "apellido": p[2],
                    "cedula_entidad": p[3],
                    "fecha_nacimiento": str(p[4]) if p[4] else None,
                    "fecha_registro": str(p[5]) if p[5] else None,
                    "telefono": p[6],
                    "direccion": p[7],
                    "correo": p[8],
                    "id_ciudad": p[9],
                    "ciudades": p[10]
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener paciente por ID: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    # ==============================
    #   Insertar nuevo paciente
    # ==============================
    def guardarPaciente(self, nombre, apellido, cedula_entidad, fecha_nacimiento,
                         telefono, direccion, correo, id_ciudad, fecha_registro=None):
        sql = """
            INSERT INTO paciente (nombre, apellido, cedula_entidad, fecha_nacimiento,
                                  telefono, direccion, correo, id_ciudad, fecha_registro)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id_paciente
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nombre, apellido, cedula_entidad, fecha_nacimiento,
                              telefono, direccion, correo, id_ciudad, fecha_registro))
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

    # ==============================
    #   Actualizar paciente
    # ==============================
    def updatePaciente(self, paciente_id, nombre, apellido, cedula_entidad, fecha_nacimiento,
                       telefono, direccion, correo, id_ciudad, fecha_registro=None):
        sql = """
            UPDATE paciente
            SET nombre=%s, apellido=%s, cedula_entidad=%s, fecha_nacimiento=%s,
                telefono=%s, direccion=%s, correo=%s, id_ciudad=%s, fecha_registro=%s
            WHERE id_paciente=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nombre, apellido, cedula_entidad, fecha_nacimiento,
                              telefono, direccion, correo, id_ciudad, fecha_registro, paciente_id))
            actualizado = cur.rowcount > 0
            con.commit()
            return actualizado
        except Exception as e:
            app.logger.error(f"Error al actualizar paciente: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ==============================
    #   Eliminar paciente
    # ==============================
    def deletePaciente(self, paciente_id):
        sql = "DELETE FROM paciente WHERE id_paciente=%s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (paciente_id,))
            eliminado = cur.rowcount > 0
            con.commit()
            return eliminado
        except Exception as e:
            app.logger.error(f"Error al eliminar paciente: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ==============================
    #   Verificar duplicado
    # ==============================
    def existeDuplicado(self, cedula_entidad, correo):
        """Verifica si ya existe un paciente con la misma cédula o correo"""
        sql = "SELECT COUNT(*) FROM paciente WHERE cedula_entidad = %s OR correo = %s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (cedula_entidad, correo))
            result = cur.fetchone()[0]
            return result > 0
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()
