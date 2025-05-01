from flask import current_app as app
from app.conexion.Conexion import Conexion

class AgendaDao:

    def getAgendas(self):
        agendaSQL = """
        SELECT 
            am.id_agenda_medica, 
            am.fecha_agenda, 
            am.hora_inicio, 
            am.hora_final, 
            am.duracion, 
            m.nombre, 
            m.apellido, 
            m.especialidad
        FROM agenda am
        JOIN medicos m ON am.id_medico = m.id_medico
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(agendaSQL)
            agendas = cur.fetchall()
            
            return [ 
                    {
                        'id_agenda_medica': agenda[0],
                        'nombre': agenda[1],
                        'apellido': agenda[2],
                        'especialidad': agenda[3],
                        'fecha_agenda': agenda[4],
                        'hora_inicio': agenda[5],
                        'hora_final': agenda[6],
                        'duracion': agenda[7]
                    } 
                    for agenda in agendas 
                ]

        except Exception as e:
            app.logger.error(f"Error al obtener las agendas médicas: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getAgendaById(self, id_agenda_medica):
        agendaSQL = """
        SELECT 
            am.id_agenda_medica, 
            am.fecha_agenda, 
            am.hora_inicio, 
            am.hora_final, 
            am.duracion, 
            m.nombre, 
            m.apellido, 
            m.especialidad
        FROM agenda am
        JOIN medicos m ON am.id_medico = m.id_medico
        WHERE am.id_agenda_medica = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(agendaSQL, (id_agenda_medica,))
            agenda = cur.fetchone()
            if agenda:
                return {
                    'id_agenda_medica': agenda[0],
                    'fecha_agenda': agenda[1],
                    'hora_inicio': agenda[2],
                    'hora_final': agenda[3],
                    'duracion': agenda[4],
                    'medico_nombre': agenda[5],
                    'medico_apellido': agenda[6],
                    'medico_especialidad': agenda[7]
                }
            else:
                return None

        except Exception as e:
            app.logger.error(f"Error al obtener la agenda médica por ID: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarAgenda(self, id_medico, fecha_agenda, hora_inicio, hora_final, duracion):
        insertAgendaSQL = """
        INSERT INTO agenda(fecha_agenda, hora_inicio, hora_final, duracion, id_medico) 
        VALUES (%s, %s, %s, %s, %s) RETURNING id_agenda_medica
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(insertAgendaSQL, (fecha_agenda, hora_inicio, hora_final, duracion, id_medico))
            id_agenda_medica = cur.fetchone()[0]
            con.commit()
            return id_agenda_medica

        except Exception as e:
            app.logger.error(f"Error al insertar la agenda médica: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def updateAgenda(self, id_agenda_medica, id_medico, fecha_agenda, hora_inicio, hora_final, duracion):
        updateAgendaSQL = """
        UPDATE agenda
        SET id_medico=%s, fecha_agenda=%s, hora_inicio=%s, hora_final=%s, duracion=%s
        WHERE id_agenda_medica=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateAgendaSQL, (id_medico, fecha_agenda, hora_inicio, hora_final, duracion, id_agenda_medica))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0

        except Exception as e:
            app.logger.error(f"Error al actualizar la agenda médica: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deleteAgenda(self, id_agenda_medica):
        deleteAgendaSQL = """
        DELETE FROM agenda
        WHERE id_agenda=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(deleteAgendaSQL, (id_agenda_medica,))
            rows_affected = cur.rowcount
            con.commit()
            return rows_affected > 0

        except Exception as e:
            app.logger.error(f"Error al eliminar la agenda médica: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()