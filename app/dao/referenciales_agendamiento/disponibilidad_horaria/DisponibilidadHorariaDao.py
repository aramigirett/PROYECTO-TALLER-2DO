from flask import current_app as app
from app.conexion.Conexion import Conexion

class DisponibilidadDao:

    def getDisponibilidades(self):
        sql = """
        SELECT d.id_disponibilidad, d.id_medico, d.id_dia, d.id_turno,
           d.dispo_hora_inicio, d.dispo_hora_fin, d.dispo_fecha, d.dispo_cupos,
           (m.nombre || ' ' || m.apellido) AS medico_nombre,
           dia.descripcion AS des_dia,
           t.descripcion   AS des_turno
        FROM disponibilidad_horaria d
        JOIN medico  m ON d.id_medico = m.id_medico
        JOIN dias    dia ON d.id_dia = dia.id_dia
        JOIN turnos  t   ON d.id_turno = t.id_turno
        ORDER BY d.dispo_fecha, d.dispo_hora_inicio
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            return [
                {
                    'id_disponibilidad': r[0],
                    'id_medico': r[1],
                    'id_dia': r[2],
                    'id_turno': r[3],
                    'dispo_hora_inicio': str(r[4]),
                    'dispo_hora_fin': str(r[5]),
                    'dispo_fecha': str(r[6]),
                    'dispo_cupos': r[7],
                    'medico_nombre': r[8],
                    'des_dia': r[9],
                    'des_turno': r[10]
                } for r in rows
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener disponibilidades: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getDisponibilidadById(self, id_disponibilidad):
        sql = """
        SELECT d.id_disponibilidad, d.id_medico, d.id_dia, d.id_turno,
           d.dispo_hora_inicio, d.dispo_hora_fin, d.dispo_fecha, d.dispo_cupos,
           (m.nombre || ' ' || m.apellido) AS medico_nombre,
           dia.descripcion AS des_dia,
           t.descripcion   AS des_turno
        FROM disponibilidad_horaria d
        JOIN medico  m ON d.id_medico = m.id_medico
        JOIN dias    dia ON d.id_dia = dia.id_dia
        JOIN turnos  t   ON d.id_turno = t.id_turno
        WHERE d.id_disponibilidad = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_disponibilidad,))
            r = cur.fetchone()
            if r:
                return {
                    'id_disponibilidad': r[0],
                    'id_medico': r[1],
                    'id_dia': r[2],
                    'id_turno': r[3],
                    'dispo_hora_inicio': str(r[4]),
                    'dispo_hora_fin': str(r[5]),
                    'dispo_fecha': str(r[6]),
                    'dispo_cupos': r[7],
                    'medico_nombre': r[8],
                    'des_dia': r[9],
                    'des_turno': r[10]
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener disponibilidad: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDisponibilidad(self, id_medico, dispo_fecha, dispo_hora_inicio, dispo_hora_fin, excluir_id=None):
        sql = """
        SELECT id_disponibilidad
        FROM disponibilidad_horaria
        WHERE id_medico = %s
          AND dispo_fecha = %s
          AND NOT (dispo_hora_fin <= %s OR dispo_hora_inicio >= %s)
        """
        params = [id_medico, dispo_fecha, dispo_hora_inicio, dispo_hora_fin]
        if excluir_id:
            sql += " AND id_disponibilidad != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error en existeDisponibilidad: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarDisponibilidad(self, id_medico, id_dia, id_turno, dispo_hora_inicio, dispo_hora_fin, dispo_fecha, dispo_cupos):
        if self.existeDisponibilidad(id_medico, dispo_fecha, dispo_hora_inicio, dispo_hora_fin):
            app.logger.warning("Disponibilidad duplicada detectada")
            return False

        sql = """
        INSERT INTO disponibilidad_horaria(
            id_medico, id_dia, id_turno, dispo_hora_inicio, dispo_hora_fin, dispo_fecha, dispo_cupos
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id_disponibilidad
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_medico, id_dia, id_turno, dispo_hora_inicio, dispo_hora_fin, dispo_fecha, dispo_cupos))
            new_id = cur.fetchone()[0]
            con.commit()
            return new_id
        except Exception as e:
            app.logger.error(f"Error al insertar disponibilidad: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateDisponibilidad(self, id_disponibilidad, id_medico, id_dia, id_turno, dispo_hora_inicio, dispo_hora_fin, dispo_fecha, dispo_cupos):
        if self.existeDisponibilidad(id_medico, dispo_fecha, dispo_hora_inicio, dispo_hora_fin, excluir_id=id_disponibilidad):
            app.logger.warning("Disponibilidad duplicada detectada en update")
            return False

        sql = """
        UPDATE disponibilidad_horaria
        SET id_medico=%s, id_dia=%s, id_turno=%s,
            dispo_hora_inicio=%s, dispo_hora_fin=%s, dispo_fecha=%s, dispo_cupos=%s
        WHERE id_disponibilidad=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_medico, id_dia, id_turno, dispo_hora_inicio, dispo_hora_fin, dispo_fecha, dispo_cupos, id_disponibilidad))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar disponibilidad: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def deleteDisponibilidad(self, id_disponibilidad):
        sql = "DELETE FROM disponibilidad_horaria WHERE id_disponibilidad=%s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_disponibilidad,))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except Exception as e:
            app.logger.error(f"Error al eliminar disponibilidad: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ✅ AQUÍ VA EL NUEVO MÉTODO - Después de deleteDisponibilidad
    def getDisponibilidadesPorMedicoFecha(self, id_medico, fecha):
        """
        Obtiene todas las disponibilidades de un médico para una fecha específica.
        Este método se usa al agregar detalles a la agenda.
        """
        sql = """
        SELECT d.id_disponibilidad, d.id_medico, d.id_dia, d.id_turno,
               d.dispo_hora_inicio, d.dispo_hora_fin, d.dispo_fecha, d.dispo_cupos,
               (m.nombre || ' ' || m.apellido) AS medico_nombre,
               dia.descripcion AS des_dia,
               t.descripcion   AS des_turno
        FROM disponibilidad_horaria d
        JOIN medico  m ON d.id_medico = m.id_medico
        JOIN dias    dia ON d.id_dia = dia.id_dia
        JOIN turnos  t   ON d.id_turno = t.id_turno
        WHERE d.id_medico = %s AND d.dispo_fecha = %s
        ORDER BY d.dispo_hora_inicio
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_medico, fecha))
            rows = cur.fetchall()
            return [
                {
                    'id_disponibilidad': r[0],
                    'id_medico': r[1],
                    'id_dia': r[2],
                    'id_turno': r[3],
                    'dispo_hora_inicio': str(r[4]),
                    'dispo_hora_fin': str(r[5]),
                    'dispo_fecha': str(r[6]),
                    'dispo_cupos': r[7],
                    'medico_nombre': r[8],
                    'des_dia': r[9],
                    'des_turno': r[10]
                } for r in rows
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener disponibilidades por médico y fecha: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()