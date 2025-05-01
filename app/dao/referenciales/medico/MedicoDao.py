from flask import current_app as app
from app.conexion.Conexion import Conexion

class MedicoDao:
    def getMedicos(self):
        medicosSQL = """
        SELECT 
          id_medico, nombre, apellido, telefono, correo, especialidad, genero
        FROM medicos
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(medicosSQL)
            medicos = cur.fetchall()

            return [
                {
                    'id': medico[0],
                    'nombre': medico[1],
                    'apellido': medico[2],
                    'telefono': medico[3],
                    'correo': medico[4],
                    'especialidad': medico[5],
                    'genero': medico[6]
                }
                for medico in medicos
            ]

        except Exception as e:
            app.logger.error(f"Error al obtener todos los medicos: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getMedicoById(self, id_medico):
        medicoSQL = """
        SELECT 
          id_medico, nombre, apellido, telefono, correo, especialidad, genero
        FROM medicos
        WHERE id_medico = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(medicoSQL, (id_medico,))
            medico = cur.fetchone()
            if medico:
                return {
                    'id': medico[0],
                    'nombre': medico[1],
                    'apellido': medico[2],
                    'telefono': medico[3],
                    'correo': medico[4],
                    'especialidad': medico[5],
                    'genero': medico[6]
                }
            else:
                return None

        except Exception as e:
            app.logger.error(f"Error al obtener medico: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarMedico(self, nombre, apellido, telefono, correo, especialidad, genero):
        insertMedicoSQL = """
        INSERT INTO medicos(nombre, apellido, telefono, correo, especialidad, genero) 
        VALUES(%s, %s, %s, %s, %s, %s) RETURNING id_medico
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(insertMedicoSQL, (nombre, apellido, telefono, correo, especialidad, genero))
            medico_id = cur.fetchone()[0]  # Obtener el ID del médico recién insertado
            con.commit()
            return medico_id

        except Exception as e:
            app.logger.error(f"Error al insertar medico: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def updateMedico(self, id_medico, nombre, apellido, telefono, correo, especialidad, genero):
        updateMedicoSQL = """
        UPDATE medicos
        SET nombre=%s, apellido=%s, telefono=%s, correo=%s, especialidad=%s, genero=%s
        WHERE id_medico=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(updateMedicoSQL, (nombre, apellido, telefono, correo, especialidad, genero, id_medico))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0

        except Exception as e:
            app.logger.error(f"Error al actualizar medico: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deleteMedico(self, id_medico):
        deleteMedicoSQL = """
        DELETE FROM medicos
        WHERE id_medico=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(deleteMedicoSQL, (id_medico,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0

        except Exception as e:
            app.logger.error(f"Error al eliminar medico: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()
