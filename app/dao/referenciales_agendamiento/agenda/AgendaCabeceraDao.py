import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

# Códigos de resultado (además de un ID o True)
DUPLICADO = "DUPLICADO"
NO_EXISTE = "NO_EXISTE"
YA_ACTIVO = "YA_ACTIVO"
INVALIDO = "INVALIDO"   # ("INVALIDO", campo, mensaje): un médico, especialidad, consultorio o funcionario no existe o está anulado
EN_USO = "EN_USO"       # ("EN_USO", motivo)

_SELECT = """
SELECT ac.id_agenda_cabecera, ac.id_medico, (m.nombre || ' ' || m.apellido) AS medico_nombre,
       ac.id_especialidad, e.nombre_especialidad, ac.id_consultorio, co.nombre_consultorio,
       ac.fecha_agenda, ac.estado, ac.id_funcionario, (f.nombre || ' ' || f.apellido) AS funcionario_nombre,
       ac.fecha_registro, ac.observaciones,
       (SELECT COUNT(*) FROM agenda_detalle d WHERE d.id_agenda_cabecera = ac.id_agenda_cabecera AND d.estado_detalle <> 'Cancelado') AS horarios
FROM agenda_cabecera ac
JOIN medico m ON ac.id_medico = m.id_medico
JOIN especialidades e ON ac.id_especialidad = e.id_especialidad
JOIN consultorio co ON ac.id_consultorio = co.codigo
JOIN funcionario f ON ac.id_funcionario = f.id_funcionario
"""


def _fila(r):
    return {
        'id_agenda_cabecera': r[0], 'id_medico': r[1], 'medico_nombre': r[2], 'id_especialidad': r[3], 'especialidad': r[4],
        'id_consultorio': r[5], 'nombre_consultorio': r[6], 'fecha_agenda': str(r[7]), 'estado': r[8], 'activo': r[8] != 'Inactivo',
        'id_funcionario': r[9], 'funcionario_nombre': r[10], 'fecha_registro': str(r[11]) if r[11] else None,
        'observaciones': r[12], 'horarios': r[13],
    }


class AgendaCabeceraDao:
    """
    Cabecera de la Agenda (movimiento con baja lógica por `estado` Activo / Inactivo). Al guardar toma FOR SHARE sobre el médico, la
    especialidad, el consultorio y el funcionario (siempre en ese orden) y los rechaza si están anulados. Anular y reactivar van en una
    transacción con la fila bloqueada; anular se bloquea si algún horario ya tiene citas (que ocupan cupo).
    """

    # ---- lectura ----
    def getCabeceras(self, incluir_inactivos=False, id_medico=None, desde=None, hasta=None):
        sql = _SELECT + " WHERE TRUE"
        params = []
        if not incluir_inactivos:
            sql += " AND ac.estado <> 'Inactivo'"
        if id_medico:
            sql += " AND ac.id_medico = %s"; params.append(id_medico)
        if desde:
            sql += " AND ac.fecha_agenda >= %s"; params.append(desde)
        if hasta:
            sql += " AND ac.fecha_agenda <= %s"; params.append(hasta)
        sql += " ORDER BY ac.fecha_agenda DESC, ac.id_agenda_cabecera DESC"
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, params)
            return [_fila(r) for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener cabeceras: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getCabeceraById(self, id_agenda_cabecera, incluir_inactivos=False):
        sql = _SELECT + " WHERE ac.id_agenda_cabecera = %s" + ("" if incluir_inactivos else " AND ac.estado <> 'Inactivo'")
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_agenda_cabecera,))
            r = cur.fetchone()
            return _fila(r) if r else None
        except Exception as e:
            app.logger.error(f"Error al obtener cabecera: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    # ---- escritura ----
    def _bloquear_padres(self, cur, v, id_funcionario):
        """FOR SHARE sobre médico, especialidad, consultorio y funcionario. Devuelve ("INVALIDO", campo, mensaje) o None."""
        for tabla, pk, valor, campo, msg in (
                ('medico', 'id_medico', v['id_medico'], 'id_medico', 'El médico seleccionado no existe o está anulado.'),
                ('especialidades', 'id_especialidad', v['id_especialidad'], 'id_especialidad', 'La especialidad seleccionada no existe o está anulada.'),
                ('consultorio', 'codigo', v['id_consultorio'], 'id_consultorio', 'El consultorio seleccionado no existe o está anulado.'),
                ('funcionario', 'id_funcionario', id_funcionario, 'id_funcionario', 'Su usuario no está vinculado a un funcionario activo.')):
            cur.execute(f"SELECT activo FROM {tabla} WHERE {pk} = %s FOR SHARE", (valor,))
            f = cur.fetchone()
            if f is None or not f[0]:
                return (INVALIDO, campo, msg)
        return None

    def guardarCabecera(self, v, id_funcionario):
        """
        v = {id_medico, id_especialidad, id_consultorio, fecha_agenda, observaciones}. La agenda nace Activa.
        Returns: ID nuevo; ("INVALIDO", campo, mensaje); ("DUPLICADO", campo, mensaje) si el médico ya tiene una agenda vigente ese día; False.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            invalido = self._bloquear_padres(cur, v, id_funcionario)
            if invalido:
                con.rollback()
                return invalido
            cur.execute("""INSERT INTO agenda_cabecera(id_medico, id_especialidad, id_consultorio, fecha_agenda, estado, id_funcionario, observaciones)
                           VALUES (%s, %s, %s, %s, 'Activo', %s, %s) RETURNING id_agenda_cabecera""",
                        (v['id_medico'], v['id_especialidad'], v['id_consultorio'], v['fecha_agenda'], id_funcionario, v.get('observaciones')))
            nuevo = cur.fetchone()[0]
            con.commit()
            return nuevo
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return (DUPLICADO, 'fecha_agenda', 'El médico ya tiene una agenda vigente para esa fecha.')
        except Exception as e:
            app.logger.error(f"Error al insertar cabecera: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateCabecera(self, id_agenda_cabecera, v):
        """
        Returns: True; False si no existe o está anulada; ("EN_USO", motivo) si cambia el médico o la fecha y ya tiene horarios publicados;
        ("INVALIDO", campo, mensaje); ("DUPLICADO", campo, mensaje).
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_medico, fecha_agenda, id_funcionario FROM agenda_cabecera WHERE id_agenda_cabecera = %s AND estado <> 'Inactivo' FOR UPDATE",
                        (id_agenda_cabecera,))
            f = cur.fetchone()
            if f is None:
                con.rollback()
                return False
            cur.execute("SELECT COUNT(*) FROM agenda_detalle WHERE id_agenda_cabecera = %s AND estado_detalle <> 'Cancelado'", (id_agenda_cabecera,))
            if cur.fetchone()[0] and (f[0] != v['id_medico'] or f[1] != v['fecha_agenda']):
                con.rollback()
                return (EN_USO, 'No se puede cambiar el médico ni la fecha: la agenda ya tiene horarios publicados.')
            invalido = self._bloquear_padres(cur, v, f[2])
            if invalido:
                con.rollback()
                return invalido
            cur.execute("""UPDATE agenda_cabecera SET id_medico=%s, id_especialidad=%s, id_consultorio=%s, fecha_agenda=%s, observaciones=%s
                           WHERE id_agenda_cabecera=%s""",
                        (v['id_medico'], v['id_especialidad'], v['id_consultorio'], v['fecha_agenda'], v.get('observaciones'), id_agenda_cabecera))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return (DUPLICADO, 'fecha_agenda', 'El médico ya tiene otra agenda vigente para esa fecha.')
        except Exception as e:
            app.logger.error(f"Error al actualizar cabecera: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def deleteCabecera(self, id_agenda_cabecera):
        """
        Anula la agenda y cancela sus horarios en la MISMA transacción. Se bloquea si algún horario tiene citas que ocupan cupo.
        Returns: True; False (no existía o ya estaba anulada / falló); ("EN_USO", motivo).
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT 1 FROM agenda_cabecera WHERE id_agenda_cabecera = %s AND estado <> 'Inactivo' FOR UPDATE", (id_agenda_cabecera,))
            if cur.fetchone() is None:
                con.rollback()
                return False
            cur.execute("""SELECT COUNT(*) FROM cita_detalle cd JOIN estado_cita ec ON ec.id_estado_cita = cd.id_estado_cita
                           JOIN agenda_detalle ad ON ad.id_agenda_detalle = cd.id_agenda_detalle
                           WHERE ad.id_agenda_cabecera = %s AND ec.ocupa_cupo = TRUE""", (id_agenda_cabecera,))
            n = cur.fetchone()[0]
            if n:
                con.rollback()
                return (EN_USO, f'No se puede anular la agenda: tiene {n} cita(s) en sus horarios. Cancele primero las citas.')
            cur.execute("UPDATE agenda_detalle SET estado_detalle = 'Cancelado' WHERE id_agenda_cabecera = %s AND estado_detalle <> 'Cancelado'", (id_agenda_cabecera,))
            cur.execute("UPDATE agenda_cabecera SET estado = 'Inactivo' WHERE id_agenda_cabecera = %s", (id_agenda_cabecera,))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al anular cabecera: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def reactivarCabecera(self, id_agenda_cabecera):
        """
        Reactiva una agenda anulada (sus horarios siguen cancelados: se vuelven a publicar). Exige que el médico, la especialidad y el
        consultorio sigan activos y que el médico no tenga otra agenda vigente ese día.
        Returns: True; NO_EXISTE; YA_ACTIVO; ("INVALIDO", campo, mensaje); ("DUPLICADO", campo, mensaje); False.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT estado, id_medico, id_especialidad, id_consultorio, id_funcionario FROM agenda_cabecera WHERE id_agenda_cabecera = %s FOR UPDATE",
                        (id_agenda_cabecera,))
            f = cur.fetchone()
            if f is None:
                con.rollback()
                return NO_EXISTE
            if f[0] != 'Inactivo':
                con.rollback()
                return YA_ACTIVO
            invalido = self._bloquear_padres(cur, {'id_medico': f[1], 'id_especialidad': f[2], 'id_consultorio': f[3]}, f[4])
            if invalido and invalido[1] != 'id_funcionario':   # el funcionario que la cargó puede estar anulado: no impide reactivarla
                con.rollback()
                return invalido
            cur.execute("UPDATE agenda_cabecera SET estado = 'Activo' WHERE id_agenda_cabecera = %s", (id_agenda_cabecera,))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return (DUPLICADO, 'fecha_agenda', 'No se puede reactivar: el médico ya tiene otra agenda vigente para esa fecha.')
        except Exception as e:
            app.logger.error(f"Error al reactivar cabecera: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
