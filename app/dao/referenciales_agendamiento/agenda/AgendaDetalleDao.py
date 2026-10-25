import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

EN_USO = "EN_USO"        # ("EN_USO", motivo)

_SELECT = """
SELECT d.id_agenda_detalle, d.id_agenda_cabecera, d.id_disponibilidad_horaria, d.id_dia, dia.descripcion, d.id_turno, t.descripcion,
       d.hora_inicio, d.hora_fin, d.cupos_disponibles, d.cupos_maximos, d.estado_detalle
FROM agenda_detalle d
JOIN dias dia ON dia.id_dia = d.id_dia
JOIN turnos t ON t.id_turno = d.id_turno
"""


def _fila(r):
    return {'id_agenda_detalle': r[0], 'id_agenda_cabecera': r[1], 'id_disponibilidad_horaria': r[2], 'id_dia': r[3], 'dia': r[4],
            'id_turno': r[5], 'turno': r[6], 'hora_inicio': str(r[7])[:5], 'hora_fin': str(r[8])[:5], 'cupos_disponibles': r[9],
            'cupos_maximos': r[10], 'estado_detalle': r[11]}


class AgendaDetalleDao:
    """
    Horarios (detalles) de una agenda: se publican copiando una disponibilidad horaria del mismo médico y fecha. Estado derivado de los cupos
    (Disponible / Agotado); Cancelado = anulado. No se anula un horario con citas que ocupan cupo.
    """

    def getDetallesPorCabecera(self, id_agenda_cabecera, incluir_cancelados=False):
        sql = _SELECT + " WHERE d.id_agenda_cabecera = %s" + ("" if incluir_cancelados else " AND d.estado_detalle <> 'Cancelado'") + " ORDER BY d.hora_inicio, d.id_agenda_detalle"
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_agenda_cabecera,))
            return [_fila(r) for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener detalles: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getDetalleById(self, id_agenda_detalle):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(_SELECT + " WHERE d.id_agenda_detalle = %s", (id_agenda_detalle,))
            r = cur.fetchone()
            return _fila(r) if r else None
        except Exception as e:
            app.logger.error(f"Error al obtener detalle: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def publicarDisponibilidades(self, id_agenda_cabecera, ids_disponibilidad):
        """
        Publica disponibilidades como horarios de la agenda, en una transacción con la agenda bloqueada (FOR SHARE) y cada disponibilidad
        bloqueada (FOR SHARE, en orden de id). Cada una tiene que estar activa y ser del mismo médico y de la misma fecha de la agenda.
        Returns: (ids_creados, errores[str]); ("INVALIDO", mensaje) si la agenda no existe o está anulada.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        creados, errores = [], []
        try:
            cur.execute("SELECT id_medico, fecha_agenda, estado FROM agenda_cabecera WHERE id_agenda_cabecera = %s FOR SHARE", (id_agenda_cabecera,))
            cab = cur.fetchone()
            if cab is None or cab[2] == 'Inactivo':
                con.rollback()
                return ("INVALIDO", 'La agenda no existe o está anulada.')
            for id_disp in sorted(set(ids_disponibilidad)):
                cur.execute("""SELECT id_medico, dispo_fecha, id_dia, id_turno, dispo_hora_inicio, dispo_hora_fin, dispo_cupos, activo
                               FROM disponibilidad_horaria WHERE id_disponibilidad = %s FOR SHARE""", (id_disp,))
                d = cur.fetchone()
                if d is None or not d[7]:
                    errores.append(f'La disponibilidad {id_disp} no existe o está anulada.')
                    continue
                if d[0] != cab[0] or d[1] != cab[1]:
                    errores.append(f'La disponibilidad de {str(d[4])[:5]} a {str(d[5])[:5]} no es de este médico y esta fecha.')
                    continue
                cur.execute("SAVEPOINT p")
                try:
                    cur.execute("""INSERT INTO agenda_detalle(id_agenda_cabecera, id_disponibilidad_horaria, id_dia, id_turno, hora_inicio, hora_fin,
                                                              cupos_disponibles, cupos_maximos, estado_detalle)
                                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'Disponible') RETURNING id_agenda_detalle""",
                                (id_agenda_cabecera, id_disp, d[2], d[3], d[4], d[5], d[6], d[6]))
                    creados.append(cur.fetchone()[0])
                    cur.execute("RELEASE SAVEPOINT p")
                except psycopg2.errors.UniqueViolation:
                    cur.execute("ROLLBACK TO SAVEPOINT p")
                    errores.append(f'El horario de {str(d[4])[:5]} a {str(d[5])[:5]} ya está publicado en esta agenda.')
            con.commit()
            return creados, errores
        except Exception as e:
            app.logger.error(f"Error al publicar disponibilidades: {str(e)}")
            con.rollback()
            return [], ['Ocurrió un error interno al publicar los horarios.']
        finally:
            cur.close()
            con.close()

    def deleteDetalle(self, id_agenda_detalle):
        """Cancela un horario. Returns: True; False (no existía o ya estaba cancelado); ("EN_USO", motivo) si tiene citas que ocupan cupo."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT 1 FROM agenda_detalle WHERE id_agenda_detalle = %s AND estado_detalle <> 'Cancelado' FOR UPDATE", (id_agenda_detalle,))
            if cur.fetchone() is None:
                con.rollback()
                return False
            cur.execute("""SELECT COUNT(*) FROM cita_detalle cd JOIN estado_cita ec ON ec.id_estado_cita = cd.id_estado_cita
                           WHERE cd.id_agenda_detalle = %s AND ec.ocupa_cupo = TRUE""", (id_agenda_detalle,))
            n = cur.fetchone()[0]
            if n:
                con.rollback()
                return (EN_USO, f'No se puede anular el horario: tiene {n} cita(s). Cancele primero las citas.')
            cur.execute("UPDATE agenda_detalle SET estado_detalle = 'Cancelado' WHERE id_agenda_detalle = %s", (id_agenda_detalle,))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al anular detalle: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def actualizarCuposDisponibles(self, id_agenda_detalle, nuevos_cupos):
        """
        Fija los cupos disponibles de un horario (solo Administrador: permiso 'editar'). Entre 0 y los máximos, y no menos que... (las citas
        que ocupan cupo ya descontaron los suyos). Returns: True; False (no existe / cancelado); ("EN_USO", mensaje) si excede el máximo.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT cupos_maximos FROM agenda_detalle WHERE id_agenda_detalle = %s AND estado_detalle <> 'Cancelado' FOR UPDATE", (id_agenda_detalle,))
            f = cur.fetchone()
            if f is None:
                con.rollback()
                return False
            if nuevos_cupos > f[0]:
                con.rollback()
                return (EN_USO, f'Los cupos disponibles no pueden superar los cupos máximos ({f[0]}).')
            cur.execute("""UPDATE agenda_detalle SET cupos_disponibles = %s, estado_detalle = CASE WHEN %s = 0 THEN 'Agotado' ELSE 'Disponible' END
                           WHERE id_agenda_detalle = %s""", (nuevos_cupos, nuevos_cupos, id_agenda_detalle))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al actualizar cupos: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
