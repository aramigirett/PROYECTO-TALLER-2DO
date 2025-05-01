from flask import current_app as app
from app.conexion.Conexion import Conexion

class DisponibilidadDao:

    def getDisponibilidad(self):
        disponibilidadSQL = """
        SELECT 
            md.id_medico_disponibilidad,
            m.nombre, 
            m.apellido, 
            m.especialidad, 
            d.descripcion AS dia, 
            h.hora_inicio, 
            h.hora_fin
        FROM 
            medicos_disponibilidad md
        JOIN 
            medicos m ON md.id_medico = m.id_medico
        JOIN 
            dias d ON md.id_dia = d.id_dia
        JOIN 
            horarios h ON md.id_horario = h.id_horario
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(disponibilidadSQL)
            disponibilidades = cur.fetchall()

            # Transformar los datos en una lista de diccionarios
            return [{
                'id_medico_disponibilidad': disponibilidad[0],
                'nombre': disponibilidad[1],
                'apellido': disponibilidad[2],
                'especialidad': disponibilidad[3],
                'dia': disponibilidad[4],
                'hora_inicio': disponibilidad[5],
                'hora_fin': disponibilidad[6]
            } for disponibilidad in disponibilidades]

        except Exception as e:
            app.logger.error(f"Error al obtener la disponibilidad de médicos: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getDisponibilidadById(self, id_medico):
        disponibilidadSQL = """
        SELECT 
            md.id_medico_disponibilidad,
            m.nombre, 
            m.apellido, 
            m.especialidad, 
            d.descripcion AS dia, 
            h.hora_inicio, 
            h.hora_fin
        FROM 
            medicos_disponibilidad md
        JOIN 
            medicos m ON md.id_medico = m.id_medico
        JOIN 
            dias d ON md.id_dia = d.id_dia
        JOIN 
            horarios h ON md.id_horario = h.id_horario
        WHERE 
            md.id_medico = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(disponibilidadSQL, (id_medico,))
            disponibilidadEncontrada = cur.fetchall()
            if disponibilidadEncontrada:
                return [{
                    'id_medico_disponibilidad': disponibilidad[0],
                    'nombre': disponibilidad[1],
                    'apellido': disponibilidad[2],
                    'especialidad': disponibilidad[3],
                    'dia': disponibilidad[4],
                    'hora_inicio': disponibilidad[5],
                    'hora_fin': disponibilidad[6]
                } for disponibilidad in disponibilidadEncontrada]
            else:
                return None
        except Exception as e:
            app.logger.error(f"Error al obtener la disponibilidad del médico por ID: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarDisponibilidad(self, id_medico, id_dia, id_horario):
        insertDisponibilidadSQL = """
        INSERT INTO medicos_disponibilidad(id_medico, id_dia, id_horario) 
        VALUES(%s, %s, %s) RETURNING id_medico_disponibilidad
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(insertDisponibilidadSQL, (id_medico, id_dia, id_horario))
            disponibilidad_id = cur.fetchone()[0]
            con.commit()
            return disponibilidad_id

        except Exception as e:
            app.logger.error(f"Error al insertar la disponibilidad del médico: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def updateDisponibilidad(self, id_medico_disponibilidad, id_medico, id_dia, id_horario):
        updateDisponibilidadSQL = """
        UPDATE medicos_disponibilidad
        SET id_medico=%s, id_dia=%s, id_horario=%s
        WHERE id_medico_disponibilidad=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateDisponibilidadSQL, (id_medico, id_dia, id_horario, id_medico_disponibilidad))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0

        except Exception as e:
            app.logger.error(f"Error al actualizar la disponibilidad del médico: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deleteDisponibilidad(self, id_medico_disponibilidad):
        deleteDisponibilidadSQL = """
        DELETE FROM medicos_disponibilidad
        WHERE id_medico_disponibilidad=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(deleteDisponibilidadSQL, (id_medico_disponibilidad,))
            rows_affected = cur.rowcount
            con.commit()

            return rows_affected > 0

        except Exception as e:
            app.logger.error(f"Error al eliminar la disponibilidad del médico: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()