import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

# Códigos de resultado (además de un ID o True)
DUPLICADO = "DUPLICADO"
NO_EXISTE = "NO_EXISTE"
YA_ACTIVO = "YA_ACTIVO"

_SELECT = """
SELECT d.id_disponibilidad, d.id_medico, d.id_dia, d.id_turno,
       d.dispo_hora_inicio, d.dispo_hora_fin, d.dispo_fecha, d.dispo_cupos,
       (m.nombre || ' ' || m.apellido) AS medico_nombre,
       dia.descripcion AS des_dia,
       t.descripcion   AS des_turno,
       d.activo
FROM disponibilidad_horaria d
JOIN medico  m   ON d.id_medico = m.id_medico
JOIN dias    dia ON d.id_dia = dia.id_dia
JOIN turnos  t   ON d.id_turno = t.id_turno
"""


def _fila(r):
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
        'des_turno': r[10],
        'activo': r[11],
    }


class DisponibilidadDao:
    """
    Disponibilidad Horaria (Estándar de referenciales: borrado lógico, único parcial por médico + fecha + horario, Estado /
    Reactivar). Es operativa: la usa la Agenda al armar sus horarios. La baja y la modificación se bloquean si un horario de una
    agenda vigente ya la publicó. Al guardar toma FOR SHARE sobre el médico, el día y el turno (y exige que estén activos) y un bloqueo
    asesor por médico para que dos altas simultáneas no se superpongan.
    """

    # ---- lectura ----
    def getDisponibilidades(self, incluir_inactivos=False):
        sql = _SELECT + ("" if incluir_inactivos else " WHERE d.activo = true") + " ORDER BY d.activo DESC, d.dispo_fecha, d.dispo_hora_inicio"
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            return [_fila(r) for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener disponibilidades: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getDisponibilidadById(self, id_disponibilidad, incluir_inactivos=False):
        sql = _SELECT + " WHERE d.id_disponibilidad = %s" + ("" if incluir_inactivos else " AND d.activo = true")
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_disponibilidad,))
            r = cur.fetchone()
            return _fila(r) if r else None
        except Exception as e:
            app.logger.error(f"Error al obtener disponibilidad: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def getDisponibilidadesPorMedicoFecha(self, id_medico, fecha):
        """Disponibilidades ACTIVAS de un médico para una fecha (se usa al agregar horarios a la agenda)."""
        sql = _SELECT + " WHERE d.id_medico = %s AND d.dispo_fecha = %s AND d.activo = true ORDER BY d.dispo_hora_inicio"
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_medico, fecha))
            return [_fila(r) for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener disponibilidades por médico y fecha: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def _superpuesta(self, cur, id_medico, fecha, inicio, fin, excluir_id=None):
        sql = """SELECT 1 FROM disponibilidad_horaria
                 WHERE activo = true AND id_medico = %s AND dispo_fecha = %s AND NOT (dispo_hora_fin <= %s OR dispo_hora_inicio >= %s)"""
        params = [id_medico, fecha, inicio, fin]
        if excluir_id:
            sql += " AND id_disponibilidad != %s"
            params.append(excluir_id)
        cur.execute(sql, params)
        return cur.fetchone() is not None

    def existeDisponibilidad(self, id_medico, dispo_fecha, dispo_hora_inicio, dispo_hora_fin, excluir_id=None):
        """Indica si el médico ya tiene una disponibilidad ACTIVA que se superpone en esa fecha."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            return self._superpuesta(cur, id_medico, dispo_fecha, dispo_hora_inicio, dispo_hora_fin, excluir_id)
        except Exception as e:
            app.logger.error(f"Error en existeDisponibilidad: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    # ---- escritura ----
    def _bloquear_padres(self, cur, id_medico, id_dia, id_turno):
        """FOR SHARE sobre médico, día y turno (siempre en este orden). Devuelve un mensaje si alguno no existe o está anulado."""
        cur.execute("SELECT nombre || ' ' || apellido, activo FROM medico WHERE id_medico = %s FOR SHARE", (id_medico,))
        f = cur.fetchone()
        if f is None or not f[1]:
            return "El médico seleccionado no existe o está anulado."
        cur.execute("SELECT descripcion, activo FROM dias WHERE id_dia = %s FOR SHARE", (id_dia,))
        f = cur.fetchone()
        if f is None or not f[1]:
            return "El día seleccionado no existe o está anulado."
        cur.execute("SELECT descripcion, activo FROM turnos WHERE id_turno = %s FOR SHARE", (id_turno,))
        f = cur.fetchone()
        if f is None or not f[1]:
            return "El turno seleccionado no existe o está anulado."
        return None

    def guardarDisponibilidad(self, id_medico, id_dia, id_turno, dispo_hora_inicio, dispo_hora_fin, dispo_fecha, dispo_cupos):
        """
        Returns:
            int | str | tuple | bool: ID nuevo; "DUPLICADO" (superposición); ("INVALIDO", mensaje) si el médico, el día o el turno no
            están disponibles; False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            motivo = self._bloquear_padres(cur, id_medico, id_dia, id_turno)
            if motivo:
                con.rollback()
                return ("INVALIDO", motivo)
            cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (7001, id_medico))
            if self._superpuesta(cur, id_medico, dispo_fecha, dispo_hora_inicio, dispo_hora_fin):
                con.rollback()
                return DUPLICADO
            cur.execute("""INSERT INTO disponibilidad_horaria(id_medico, id_dia, id_turno, dispo_hora_inicio, dispo_hora_fin, dispo_fecha, dispo_cupos)
                           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id_disponibilidad""",
                        (id_medico, id_dia, id_turno, dispo_hora_inicio, dispo_hora_fin, dispo_fecha, dispo_cupos))
            nuevo = cur.fetchone()[0]
            con.commit()
            return nuevo
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al insertar disponibilidad: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateDisponibilidad(self, id_disponibilidad, id_medico, id_dia, id_turno, dispo_hora_inicio, dispo_hora_fin, dispo_fecha, dispo_cupos):
        """
        Returns:
            bool | str | tuple: True si se actualizó, False si no existe (o está anulada) o falló; "DUPLICADO";
            ("INVALIDO", mensaje); ("EN_USO", motivo) si ya está publicada en una agenda vigente.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT 1 FROM disponibilidad_horaria WHERE id_disponibilidad = %s AND activo = true FOR UPDATE", (id_disponibilidad,))
            if cur.fetchone() is None:
                con.rollback()
                return False
            motivo = self._motivo_en_uso(cur, id_disponibilidad, accion='modificar')
            if motivo:
                con.rollback()
                return ("EN_USO", motivo)
            motivo = self._bloquear_padres(cur, id_medico, id_dia, id_turno)
            if motivo:
                con.rollback()
                return ("INVALIDO", motivo)
            cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (7001, id_medico))
            if self._superpuesta(cur, id_medico, dispo_fecha, dispo_hora_inicio, dispo_hora_fin, excluir_id=id_disponibilidad):
                con.rollback()
                return DUPLICADO
            cur.execute("""UPDATE disponibilidad_horaria
                           SET id_medico=%s, id_dia=%s, id_turno=%s, dispo_hora_inicio=%s, dispo_hora_fin=%s, dispo_fecha=%s, dispo_cupos=%s
                           WHERE id_disponibilidad=%s AND activo = true""",
                        (id_medico, id_dia, id_turno, dispo_hora_inicio, dispo_hora_fin, dispo_fecha, dispo_cupos, id_disponibilidad))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al actualizar disponibilidad: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ---- baja / reactivación ----
    def _motivo_en_uso(self, cur, id_disponibilidad, accion='anular'):
        cur.execute("""SELECT COUNT(*) FROM agenda_detalle d JOIN agenda_cabecera c ON c.id_agenda_cabecera = d.id_agenda_cabecera
                       WHERE d.id_disponibilidad_horaria = %s AND d.estado_detalle <> 'Cancelado' AND c.estado <> 'Inactivo'""",
                    (id_disponibilidad,))
        n = cur.fetchone()[0]
        if n:
            return f"No se puede {accion}, la disponibilidad ya fue publicada en {n} agenda(s) vigente(s)."
        return False

    def esta_en_uso(self, id_disponibilidad):
        """False si se puede anular; si no, el texto con el motivo (truthy)."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            return self._motivo_en_uso(cur, id_disponibilidad)
        except Exception as e:
            app.logger.error(f"Error al verificar uso de disponibilidad: {str(e)}")
            return "No se pudo verificar si la disponibilidad está en uso."  # ante la duda, bloquear
        finally:
            cur.close()
            con.close()

    def deleteDisponibilidad(self, id_disponibilidad):
        """Baja lógica. Returns: True, False (no existía o ya estaba anulada / falló) o ("EN_USO", motivo)."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT 1 FROM disponibilidad_horaria WHERE id_disponibilidad = %s AND activo = true FOR UPDATE", (id_disponibilidad,))
            if cur.fetchone() is None:
                con.rollback()
                return False
            motivo = self._motivo_en_uso(cur, id_disponibilidad)
            if motivo:
                con.rollback()
                app.logger.warning(f"No se puede anular disponibilidad {id_disponibilidad}: está en uso")
                return ("EN_USO", motivo)
            cur.execute("UPDATE disponibilidad_horaria SET activo = false WHERE id_disponibilidad = %s", (id_disponibilidad,))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al anular disponibilidad: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def reactivarDisponibilidad(self, id_disponibilidad):
        """
        Reactiva una disponibilidad anulada en una sola transacción: la bloquea, exige que el médico, el día y el turno sigan activos y
        que no se superponga con otra activa. Returns: True; NO_EXISTE, YA_ACTIVO, DUPLICADO, ("INVALIDO", mensaje); False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""SELECT id_medico, id_dia, id_turno, dispo_fecha, dispo_hora_inicio, dispo_hora_fin, activo
                           FROM disponibilidad_horaria WHERE id_disponibilidad = %s FOR UPDATE""", (id_disponibilidad,))
            f = cur.fetchone()
            if f is None:
                con.rollback()
                return NO_EXISTE
            id_medico, id_dia, id_turno, fecha, inicio, fin, activo = f
            if activo:
                con.rollback()
                return YA_ACTIVO
            motivo = self._bloquear_padres(cur, id_medico, id_dia, id_turno)
            if motivo:
                con.rollback()
                return ("INVALIDO", motivo)
            cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (7001, id_medico))
            if self._superpuesta(cur, id_medico, fecha, inicio, fin, excluir_id=id_disponibilidad):
                con.rollback()
                return DUPLICADO
            cur.execute("UPDATE disponibilidad_horaria SET activo = true WHERE id_disponibilidad = %s", (id_disponibilidad,))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al reactivar disponibilidad: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
