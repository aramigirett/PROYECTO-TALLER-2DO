from flask import current_app as app
from app.conexion.Conexion import Conexion

class MedicoDao:

    def getMedicos(self):
        sql = """
            SELECT m.id_medico, m.nombre, m.apellido, 
                   m.id_especialidad, e.nombre_especialidad AS especialidades, 
                   m.num_registro, m.cedula, m.fecha_nacimiento, m.fecha_registro, 
                   m.telefono, m.direccion, m.correo, 
                   m.id_ciudad, c.descripcion AS ciudades
            FROM medico m
            LEFT JOIN especialidades e ON m.id_especialidad = e.id_especialidad
            LEFT JOIN ciudades c ON m.id_ciudad = c.id_ciudad
            ORDER BY m.id_medico
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            medicos = cur.fetchall()
            return [
                {
                    "id_medico": m[0],
                    "nombre": m[1],
                    "apellido": m[2],
                    "id_especialidad": m[3],  # ID correcto
                    "especialidades": m[4],     # descripción
                    "num_registro": m[5],
                    "cedula": m[6],
                    "fecha_nacimiento": str(m[7]) if m[7] else None,
                    "fecha_registro": str(m[8]) if m[8] else None,
                    "telefono": m[9],
                    "direccion": m[10],
                    "correo": m[11],
                    "id_ciudad": m[12],       # ID correcto
                    "ciudades": m[13]            # descripción
                }
                for m in medicos
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener todos los médicos: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getMedicoById(self, medico_id):
        sql = """
            SELECT m.id_medico, m.nombre, m.apellido, 
                   m.id_especialidad, e.nombre_especialidad AS especialidades, 
                   m.num_registro, m.cedula, m.fecha_nacimiento, m.fecha_registro, 
                   m.telefono, m.direccion, m.correo, 
                   m.id_ciudad, c.descripcion AS ciudades
            FROM medico m
            LEFT JOIN especialidades e ON m.id_especialidad = e.id_especialidad
            LEFT JOIN ciudades c ON m.id_ciudad = c.id_ciudad
            WHERE m.id_medico = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (medico_id,))
            medico = cur.fetchone()
            if medico:
                return {
                    "id_medico": medico[0],
                    "nombre": medico[1],
                    "apellido": medico[2],
                    "id_especialidad": medico[3],
                    "especialidades": medico[4],
                    "num_registro": medico[5],
                    "cedula": medico[6],
                    "fecha_nacimiento": str(medico[7]) if medico[7] else None,
                    "fecha_registro": str(medico[8]) if medico[8] else None,
                    "telefono": medico[9],
                    "direccion": medico[10],
                    "correo": medico[11],
                    "id_ciudad": medico[12],
                    "ciudades": medico[13]
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener médico por ID: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def guardarMedico(self, nombre, apellido, id_especialidad, num_registro,
                      cedula, fecha_nacimiento, fecha_registro,
                      telefono, direccion, correo, id_ciudad):
        sql = """
            INSERT INTO medico (nombre, apellido, id_especialidad, num_registro,
                                cedula, fecha_nacimiento, fecha_registro,
                                telefono, direccion, correo, id_ciudad)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id_medico
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nombre, apellido, id_especialidad, num_registro,
                              cedula, fecha_nacimiento, fecha_registro,
                              telefono, direccion, correo, id_ciudad))
            medico_id = cur.fetchone()[0]
            con.commit()
            return medico_id
        except Exception as e:
            app.logger.error(f"Error al insertar médico: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
    
    def updateMedico(self, medico_id, nombre, apellido, id_especialidad, num_registro,
                     cedula, fecha_nacimiento, fecha_registro,
                     telefono, direccion, correo, id_ciudad):
        sql = """
            UPDATE medico
            SET nombre=%s, apellido=%s, id_especialidad=%s, num_registro=%s,
                cedula=%s, fecha_nacimiento=%s, fecha_registro=%s,
                telefono=%s, direccion=%s, correo=%s, id_ciudad=%s
            WHERE id_medico=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nombre, apellido, id_especialidad, num_registro,
                              cedula, fecha_nacimiento, fecha_registro,
                              telefono, direccion, correo, id_ciudad, medico_id))
            actualizado = cur.rowcount > 0
            con.commit()
            return actualizado
        except Exception as e:
            app.logger.error(f"Error al actualizar médico: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def deleteMedico(self, medico_id):
        sql = "DELETE FROM medico WHERE id_medico=%s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (medico_id,))
            eliminado = cur.rowcount > 0
            con.commit()
            return eliminado
        except Exception as e:
            app.logger.error(f"Error al eliminar médico: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, cedula, num_registro):
        """Verifica si ya existe un médico con la misma cédula o número de registro"""
        sql = "SELECT COUNT(*) FROM medico WHERE cedula = %s OR num_registro = %s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (cedula, num_registro))
            result = cur.fetchone()[0]
            return result > 0
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()