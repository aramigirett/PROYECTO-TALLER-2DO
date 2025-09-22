from flask import current_app as app
from app.conexion.Conexion import Conexion
from datetime import date, datetime

class Agenda_medicaDao:
    def getAgenda_medicas(self):
        agenda_medicaSQL = """
        SELECT 
            a.id_agenda_medica,  
            p.nombre,
            p.apellido,
            e.nombre_especialidad, 
            a.fecha, 
            t.descripcion,
            d.descripcion, 
            a.hora_inicio, 
            a.hora_final,
            a.estado
        FROM agenda_medicas a, pacientes p, especialidades e, dias d, turnos t, medicos m
        WHERE a.id_medico = m.id_medico AND m.id_paciente = p.id_paciente 
            AND a.id_especialidad = e.id_especialidad 
            AND a.id_dia = d.id_dia 
            AND a.id_turno = t.id_turno
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(agenda_medicaSQL)
            agenda_medicas = cur.fetchall()
            return [
                {
                    'id_agenda_medica': ag[0],
                    'nombre': ag[1],
                    'apellido': ag[2],
                    'especialidad': ag[3],
                    'fecha': ag[4].strftime('%Y-%m-%d') if isinstance(ag[4], (date, datetime)) else str(ag[4]),
                    'turno': ag[5],
                    'dia': ag[6],
                    'hora_inicio': str(ag[7]),
                    'hora_final': str(ag[8]),
                    'estado': 'activo' if ag[9] in (True, 'activo', 1) else 'inactivo'
                }
                for ag in agenda_medicas
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener todas las agendas médicas: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getAgenda_medicaById(self, id_agenda_medica):
        agenda_medicaSQL = """
        SELECT 
            a.id_agenda_medica,  
            p.nombre,
            p.apellido,
            e.nombre_especialidad, 
            a.fecha, 
            t.descripcion,
            d.descripcion, 
            a.hora_inicio, 
            a.hora_final,
            a.estado,
            a.id_medico,
            a.id_especialidad,
            a.id_dia,
            a.id_turno
        FROM agenda_medicas a, pacientes p, especialidades e, dias d, turnos t, medicos m
        WHERE a.id_medico = m.id_medico AND m.id_paciente = p.id_paciente 
            AND a.id_especialidad = e.id_especialidad 
            AND a.id_dia = d.id_dia 
            AND a.id_turno = t.id_turno
            AND a.id_agenda_medica = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(agenda_medicaSQL, (id_agenda_medica,))
            row = cur.fetchone()
            if row:
                return {
                    'id_agenda_medica': row[0],
                    'nombre': row[1],
                    'apellido': row[2],
                    'nombre_especialidad': row[3],
                    'fecha': row[4].strftime('%Y-%m-%d') if isinstance(row[4], (date, datetime)) else str(row[4]),
                    'turno': row[5],
                    'dia': row[6],
                    'hora_inicio': str(row[7]),
                    'hora_final': str(row[8]),
                    'estado': 'activo' if row[9] in (True, 'activo', 1) else 'inactivo',
                    'id_medico': row[10],
                    'id_especialidad': row[11],
                    'id_dia': row[12],
                    'id_turno': row[13]
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener agenda médica: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def guardarAgenda_medica(self, id_medico, id_especialidad, fecha, id_dia, id_turno, hora_inicio, hora_final, estado):
        insertSQL = """
        INSERT INTO agenda_medicas 
        (id_medico, id_especialidad, fecha, id_dia, id_turno, hora_inicio, hora_final, estado)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_agenda_medica
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(insertSQL, (id_medico, id_especialidad, fecha, id_dia, id_turno, hora_inicio, hora_final, estado))
            agenda_id = cur.fetchone()[0]
            con.commit()
            return agenda_id
        except Exception as e:
            app.logger.error(f"Error al insertar agenda médica: {str(e)}")
            con.rollback()
            return None
        finally:
            cur.close()
            con.close()

    def updateAgenda_medica(self, id_agenda_medica, id_medico, id_especialidad, fecha, id_dia, id_turno, hora_inicio, hora_final, estado):
        updateSQL = """
        UPDATE agenda_medicas
        SET id_medico = %s, id_especialidad = %s, fecha = %s, id_dia = %s, id_turno = %s,
            hora_inicio = %s, hora_final = %s, estado = %s
        WHERE id_agenda_medica = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(updateSQL, (id_medico, id_especialidad, fecha, id_dia, id_turno, hora_inicio, hora_final, estado, id_agenda_medica))
            con.commit()
            return cur.rowcount > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar agenda médica: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def deleteAgenda_medica(self, id_agenda_medica):
        deleteSQL = """
        DELETE FROM agenda_medicas WHERE id_agenda_medica = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(deleteSQL, (id_agenda_medica,))
            con.commit()
            return cur.rowcount > 0
        except Exception as e:
            app.logger.error(f"Error al eliminar agenda médica: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def getAgendasByFechaAndMedico(self, fecha, id_medico):
        query = """
        SELECT hora_inicio, hora_final
        FROM agenda_medicas
        WHERE fecha = %s AND id_medico = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(query, (fecha, id_medico))
            agendas = cur.fetchall()
            return [
                {'hora_inicio': str(agenda[0]), 'hora_final': str(agenda[1])}
                for agenda in agendas
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener horarios de la agenda médica: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()
            
    def getAgendasByFecha(self, fecha):
        query = """
        SELECT id_medico, hora_inicio, hora_final
        FROM agenda_medicas
        WHERE fecha = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(query, (fecha,))
            agendas = cur.fetchall()
            return [
                {
                    'id_medico': agenda[0],
                    'hora_inicio': str(agenda[1]),
                    'hora_final': str(agenda[2])
                }
                for agenda in agendas
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener agendas por fecha: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()
