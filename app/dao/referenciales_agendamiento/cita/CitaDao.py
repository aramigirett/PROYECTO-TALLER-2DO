from flask import current_app as app
from app.conexion.Conexion import Conexion

# Códigos de resultado (además de un ID o True)
SIN_CUPOS = "SIN_CUPOS"
INVALIDO = "INVALIDO"      # ("INVALIDO", campo, mensaje): un paciente, funcionario, agenda u horario no existe o está anulado
EN_USO = "EN_USO"          # ("EN_USO", motivo): la cita tiene una consulta registrada o el estado no admite el cambio
DUPLICADO = "DUPLICADO"    # ("DUPLICADO", campo, mensaje)

_CABECERA = """
SELECT cc.id_cita_cabecera, cc.id_paciente, (p.nombre || ' ' || p.apellido) AS paciente_nombre, p.cedula_entidad,
       cc.id_agenda_cabecera, ac.fecha_agenda, ac.id_medico, (m.nombre || ' ' || m.apellido) AS medico_nombre,
       e.nombre_especialidad, co.nombre_consultorio, cc.fecha_registro, cc.observaciones, cc.estado, cc.id_funcionario,
       (f.nombre || ' ' || f.apellido) AS funcionario_nombre,
       (SELECT COUNT(*) FROM cita_detalle cd JOIN estado_cita ec ON ec.id_estado_cita = cd.id_estado_cita
         WHERE cd.id_cita_cabecera = cc.id_cita_cabecera AND ec.descripcion <> 'Cancelado') AS horarios,
       (SELECT cd.hora_cita FROM cita_detalle cd JOIN estado_cita ec ON ec.id_estado_cita = cd.id_estado_cita
         WHERE cd.id_cita_cabecera = cc.id_cita_cabecera AND ec.descripcion <> 'Cancelado' ORDER BY cd.hora_cita LIMIT 1) AS hora,
       (SELECT ec.descripcion FROM cita_detalle cd JOIN estado_cita ec ON ec.id_estado_cita = cd.id_estado_cita
         WHERE cd.id_cita_cabecera = cc.id_cita_cabecera ORDER BY (ec.descripcion = 'Cancelado'), cd.hora_cita LIMIT 1) AS estado_cita
FROM cita_cabecera cc
JOIN paciente p ON cc.id_paciente = p.id_paciente
JOIN agenda_cabecera ac ON cc.id_agenda_cabecera = ac.id_agenda_cabecera
JOIN medico m ON ac.id_medico = m.id_medico
JOIN especialidades e ON ac.id_especialidad = e.id_especialidad
JOIN consultorio co ON ac.id_consultorio = co.codigo
JOIN funcionario f ON cc.id_funcionario = f.id_funcionario
"""


def _cabecera(r):
    return {'id_cita_cabecera': r[0], 'id_paciente': r[1], 'paciente_nombre': r[2], 'paciente_cedula': r[3], 'id_agenda_cabecera': r[4],
            'fecha_agenda': str(r[5]) if r[5] else None, 'id_medico': r[6], 'medico_nombre': r[7], 'especialidad': r[8],
            'nombre_consultorio': r[9], 'fecha_registro': str(r[10]) if r[10] else None, 'observaciones': r[11], 'estado': r[12],
            'activo': r[12] != 'Inactivo', 'id_funcionario': r[13], 'funcionario_nombre': r[14], 'horarios': r[15],
            'hora_cita': str(r[16])[:5] if r[16] else None, 'estado_cita': r[17]}


_DETALLE = """
SELECT cd.id_cita_detalle, cd.id_cita_cabecera, cd.id_agenda_detalle, cd.fecha_cita, cd.hora_cita, cd.motivo_consulta, cd.id_estado_cita,
       ec.descripcion, cd.fecha_cambio_estado, ad.hora_inicio, ad.hora_fin, ad.cupos_disponibles, co.nombre_consultorio,
       ac.id_medico, ac.id_consultorio, cc.id_paciente,
       EXISTS(SELECT 1 FROM consultas_cab con WHERE con.id_cita = cd.id_cita_detalle AND con.activo = true) AS con_consulta
FROM cita_detalle cd
JOIN estado_cita ec ON cd.id_estado_cita = ec.id_estado_cita
JOIN agenda_detalle ad ON cd.id_agenda_detalle = ad.id_agenda_detalle
JOIN agenda_cabecera ac ON ad.id_agenda_cabecera = ac.id_agenda_cabecera
JOIN consultorio co ON ac.id_consultorio = co.codigo
JOIN cita_cabecera cc ON cd.id_cita_cabecera = cc.id_cita_cabecera
"""


def _detalle(r):
    return {'id_cita_detalle': r[0], 'id_cita_cabecera': r[1], 'id_agenda_detalle': r[2], 'fecha_cita': str(r[3]), 'hora_cita': str(r[4])[:5],
            'motivo_consulta': r[5], 'id_estado_cita': r[6], 'estado_descripcion': r[7], 'fecha_cambio_estado': str(r[8]) if r[8] else None,
            'hora_inicio': str(r[9])[:5], 'hora_fin': str(r[10])[:5], 'cupos_disponibles': r[11], 'nombre_consultorio': r[12],
            'id_medico': r[13], 'id_consultorio': r[14], 'id_paciente': r[15], 'con_consulta': r[16]}


class CitaDao:
    """
    Cita (cabecera + horarios) con el cupo de la agenda. Cada operación que toca el cupo va en UNA transacción: se bloquea el horario de la agenda
    (FOR UPDATE, siempre por id) y, en ella, el alta / cambio de estado / anulación de la cita y el descuento o la devolución del cupo. Los estados
    que ocupan cupo salen de `estado_cita.ocupa_cupo`. Al guardar se toma FOR SHARE sobre el paciente, el funcionario y la agenda y se rechazan si
    están anulados. Una cita cancelada no se reactiva, y una cita con consulta registrada no cambia de estado desde acá (la maneja Consultorio).
    """

    # ---------------- estados ----------------
    def getEstadosCita(self):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_estado_cita, descripcion, ocupa_cupo FROM estado_cita WHERE activo = true ORDER BY id_estado_cita")
            return [{'id_estado_cita': r[0], 'descripcion': r[1], 'ocupa_cupo': r[2]} for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener estados de cita: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getIdEstadoCancelado(self):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_estado_cita FROM estado_cita WHERE descripcion = 'Cancelado'")
            r = cur.fetchone()
            return r[0] if r else None
        except Exception as e:
            app.logger.error(f"Error al obtener id de estado Cancelado: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def verificarCuposDisponibles(self, id_agenda_detalle):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT cupos_disponibles FROM agenda_detalle WHERE id_agenda_detalle = %s", (id_agenda_detalle,))
            r = cur.fetchone()
            return r[0] if r else 0
        except Exception as e:
            app.logger.error(f"Error al verificar cupos: {str(e)}")
            return 0
        finally:
            cur.close()
            con.close()

    # ---------------- lectura ----------------
    def getCitasCabecera(self, incluir_inactivos=False, id_paciente=None, id_medico=None, desde=None, hasta=None):
        sql = _CABECERA + " WHERE TRUE"
        params = []
        if not incluir_inactivos:
            sql += " AND cc.estado <> 'Inactivo'"
        for cond, valor in ((" AND cc.id_paciente = %s", id_paciente), (" AND ac.id_medico = %s", id_medico),
                            (" AND ac.fecha_agenda >= %s", desde), (" AND ac.fecha_agenda <= %s", hasta)):
            if valor:
                sql += cond; params.append(valor)
        sql += " ORDER BY ac.fecha_agenda DESC, cc.id_cita_cabecera DESC"
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, params)
            return [_cabecera(r) for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener cabeceras de citas: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getCitaCabeceraById(self, id_cita_cabecera, incluir_inactivos=False):
        sql = _CABECERA + " WHERE cc.id_cita_cabecera = %s" + ("" if incluir_inactivos else " AND cc.estado <> 'Inactivo'")
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_cita_cabecera,))
            r = cur.fetchone()
            return _cabecera(r) if r else None
        except Exception as e:
            app.logger.error(f"Error al obtener cabecera: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def getDetallesPorCabecera(self, id_cita_cabecera, incluir_cancelados=True):
        sql = _DETALLE + " WHERE cd.id_cita_cabecera = %s" + ("" if incluir_cancelados else " AND ec.descripcion <> 'Cancelado'") + " ORDER BY cd.fecha_cita, cd.hora_cita"
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_cita_cabecera,))
            return [_detalle(r) for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener detalles: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getDetalleById(self, id_cita_detalle):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(_DETALLE + " WHERE cd.id_cita_detalle = %s", (id_cita_detalle,))
            r = cur.fetchone()
            return _detalle(r) if r else None
        except Exception as e:
            app.logger.error(f"Error al obtener detalle: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    # ---------------- escritura ----------------
    def guardarCitaCabecera(self, id_paciente, id_agenda_cabecera, id_funcionario, observaciones=None):
        """Returns: ID nuevo; ("INVALIDO", campo, mensaje) si el paciente, la agenda o el funcionario no existen o están anulados; False."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            invalido = self._bloquear_padres(cur, id_paciente, id_agenda_cabecera, id_funcionario)
            if invalido:
                con.rollback()
                return invalido
            cur.execute("""INSERT INTO cita_cabecera(id_paciente, id_agenda_cabecera, id_funcionario, observaciones)
                           VALUES (%s, %s, %s, %s) RETURNING id_cita_cabecera""", (id_paciente, id_agenda_cabecera, id_funcionario, observaciones))
            nuevo = cur.fetchone()[0]
            con.commit()
            return nuevo
        except Exception as e:
            app.logger.error(f"Error al guardar cabecera: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def _bloquear_padres(self, cur, id_paciente, id_agenda_cabecera, id_funcionario):
        cur.execute("SELECT activo FROM paciente WHERE id_paciente = %s FOR SHARE", (id_paciente,))
        f = cur.fetchone()
        if f is None or not f[0]:
            return (INVALIDO, 'id_paciente', 'El paciente seleccionado no existe o está anulado.')
        cur.execute("SELECT estado FROM agenda_cabecera WHERE id_agenda_cabecera = %s FOR SHARE", (id_agenda_cabecera,))
        f = cur.fetchone()
        if f is None or f[0] == 'Inactivo':
            return (INVALIDO, 'id_agenda_cabecera', 'La agenda seleccionada no existe o está anulada.')
        cur.execute("SELECT activo FROM funcionario WHERE id_funcionario = %s FOR SHARE", (id_funcionario,))
        f = cur.fetchone()
        if f is None or not f[0]:
            return (INVALIDO, 'id_funcionario', 'Su usuario no está vinculado a un funcionario activo.')
        return None

    def updateCitaCabecera(self, id_cita_cabecera, id_paciente, id_agenda_cabecera, observaciones=None):
        """Returns: True; False si no existe o está anulada; ("EN_USO", motivo) si ya tiene horarios; ("INVALIDO", campo, mensaje)."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_paciente, id_agenda_cabecera, id_funcionario FROM cita_cabecera WHERE id_cita_cabecera = %s AND estado <> 'Inactivo' FOR UPDATE",
                        (id_cita_cabecera,))
            f = cur.fetchone()
            if f is None:
                con.rollback()
                return False
            cur.execute("""SELECT COUNT(*) FROM cita_detalle cd JOIN estado_cita ec ON ec.id_estado_cita = cd.id_estado_cita
                           WHERE cd.id_cita_cabecera = %s AND ec.descripcion <> 'Cancelado'""", (id_cita_cabecera,))
            if cur.fetchone()[0] and (f[0] != id_paciente or f[1] != id_agenda_cabecera):
                con.rollback()
                return (EN_USO, 'No se puede cambiar el paciente ni la agenda: la cita ya tiene horarios. Cancélela y registre una nueva.')
            invalido = self._bloquear_padres(cur, id_paciente, id_agenda_cabecera, f[2])
            if invalido:
                con.rollback()
                return invalido
            cur.execute("UPDATE cita_cabecera SET id_paciente=%s, id_agenda_cabecera=%s, observaciones=%s WHERE id_cita_cabecera=%s",
                        (id_paciente, id_agenda_cabecera, observaciones, id_cita_cabecera))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al actualizar cabecera: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def guardarCitaDetalle(self, id_cita_cabecera, id_agenda_detalle, hora_cita, motivo_consulta, id_estado_cita):
        """
        Agrega un horario a la cita. La fecha sale de la agenda; la hora tiene que estar dentro del horario publicado. Si el estado ocupa cupo, descuenta
        uno en la misma transacción. Returns: ID nuevo; "SIN_CUPOS"; ("INVALIDO", campo, mensaje); ("DUPLICADO", campo, mensaje); False.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            r = self._insertar_detalle(cur, id_cita_cabecera, id_agenda_detalle, hora_cita, motivo_consulta, id_estado_cita)
            if isinstance(r, int):
                con.commit()
            else:
                con.rollback()
            return r
        except Exception as e:
            app.logger.error(f"Error al guardar detalle de cita: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def crearCita(self, id_paciente, id_agenda_detalle, hora_cita, motivo_consulta, id_estado_cita, id_funcionario, observaciones=None):
        """
        Cabecera + primer horario en UNA transacción (si el horario no se puede reservar no queda una cita vacía). Los datos de la agenda salen del
        horario elegido. Returns: (id_cita_cabecera, id_cita_detalle); "SIN_CUPOS"; ("INVALIDO", campo, mensaje); ("DUPLICADO", campo, mensaje); False.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_agenda_cabecera FROM agenda_detalle WHERE id_agenda_detalle = %s", (id_agenda_detalle,))
            f = cur.fetchone()
            if f is None:
                con.rollback()
                return (INVALIDO, 'id_agenda_detalle', 'El horario seleccionado no existe o fue anulado.')
            invalido = self._bloquear_padres(cur, id_paciente, f[0], id_funcionario)
            if invalido:
                con.rollback()
                return invalido
            cur.execute("""INSERT INTO cita_cabecera(id_paciente, id_agenda_cabecera, id_funcionario, observaciones)
                           VALUES (%s, %s, %s, %s) RETURNING id_cita_cabecera""", (id_paciente, f[0], id_funcionario, observaciones))
            id_cab = cur.fetchone()[0]
            r = self._insertar_detalle(cur, id_cab, id_agenda_detalle, hora_cita, motivo_consulta, id_estado_cita)
            if not isinstance(r, int) or isinstance(r, bool):
                con.rollback()
                return r
            con.commit()
            return (id_cab, r)
        except Exception as e:
            app.logger.error(f"Error al crear la cita: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def _insertar_detalle(self, cur, id_cita_cabecera, id_agenda_detalle, hora_cita, motivo_consulta, id_estado_cita):
        """Valida y guarda un horario dentro de la transacción de `cur` (no hace commit). Devuelve el ID o el código / tupla de error."""
        cur.execute("SELECT id_agenda_cabecera, id_paciente, estado FROM cita_cabecera WHERE id_cita_cabecera = %s FOR SHARE", (id_cita_cabecera,))
        cab = cur.fetchone()
        if cab is None or cab[2] == 'Inactivo':
            return (INVALIDO, 'id_cita_cabecera', 'La cita no existe o está anulada.')
        cur.execute("""SELECT ad.id_agenda_cabecera, ad.estado_detalle, ad.hora_inicio, ad.hora_fin, ad.cupos_disponibles, ac.fecha_agenda, ac.estado
                       FROM agenda_detalle ad JOIN agenda_cabecera ac ON ac.id_agenda_cabecera = ad.id_agenda_cabecera
                       WHERE ad.id_agenda_detalle = %s FOR UPDATE OF ad""", (id_agenda_detalle,))
        ad = cur.fetchone()
        if ad is None or ad[1] == 'Cancelado' or ad[6] == 'Inactivo':
            return (INVALIDO, 'id_agenda_detalle', 'El horario seleccionado no existe o fue anulado.')
        if ad[0] != cab[0]:
            return (INVALIDO, 'id_agenda_detalle', 'El horario no pertenece a la agenda de esta cita.')
        if not (ad[2] <= hora_cita < ad[3]):
            return (INVALIDO, 'hora_cita', f'La hora debe estar entre {str(ad[2])[:5]} y {str(ad[3])[:5]} (horario publicado).')
        cur.execute("SELECT ocupa_cupo, activo, descripcion FROM estado_cita WHERE id_estado_cita = %s", (id_estado_cita,))
        ec = cur.fetchone()
        if ec is None or not ec[1]:
            return (INVALIDO, 'id_estado_cita', 'El estado de la cita no es válido.')
        if ec[2] in ('Cancelado', 'Realizado'):
            return (INVALIDO, 'id_estado_cita', 'Una cita nueva solo puede registrarse como Reservado o Confirmado.')
        cur.execute("""SELECT 1 FROM cita_detalle cd JOIN estado_cita e ON e.id_estado_cita = cd.id_estado_cita JOIN cita_cabecera c ON c.id_cita_cabecera = cd.id_cita_cabecera
                       WHERE cd.id_agenda_detalle = %s AND c.id_paciente = %s AND e.ocupa_cupo = TRUE AND c.estado <> 'Inactivo' LIMIT 1""",
                    (id_agenda_detalle, cab[1]))
        if cur.fetchone():
            return (DUPLICADO, 'id_agenda_detalle', 'El paciente ya tiene una cita en ese horario.')
        if ec[0]:
            if ad[4] <= 0:
                return SIN_CUPOS
            cur.execute("""UPDATE agenda_detalle SET cupos_disponibles = cupos_disponibles - 1,
                           estado_detalle = CASE WHEN cupos_disponibles - 1 = 0 THEN 'Agotado' ELSE estado_detalle END
                           WHERE id_agenda_detalle = %s""", (id_agenda_detalle,))
        cur.execute("""INSERT INTO cita_detalle(id_cita_cabecera, id_agenda_detalle, fecha_cita, hora_cita, motivo_consulta, id_estado_cita)
                       VALUES (%s, %s, %s, %s, %s, %s) RETURNING id_cita_detalle""",
                    (id_cita_cabecera, id_agenda_detalle, ad[5], hora_cita, motivo_consulta, id_estado_cita))
        return cur.fetchone()[0]

    def cambiarEstadoDetalle(self, id_cita_detalle, id_estado_nuevo, motivo_consulta=None, hora_cita=None):
        """
        Cambia el estado de un horario de la cita (y opcionalmente su motivo / hora) ajustando el cupo en la MISMA transacción: de un estado que
        ocupa cupo a uno que no, lo devuelve; al revés, lo descuenta (y exige que haya). Una cita Cancelada no se reactiva; con consulta registrada
        el estado lo maneja Consultorio. Returns: True; False si no existe; "SIN_CUPOS"; ("EN_USO", motivo); ("INVALIDO", campo, mensaje).
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""SELECT cd.id_agenda_detalle, cd.id_estado_cita, ea.descripcion, ea.ocupa_cupo, cd.hora_cita
                           FROM cita_detalle cd JOIN estado_cita ea ON ea.id_estado_cita = cd.id_estado_cita WHERE cd.id_cita_detalle = %s""", (id_cita_detalle,))
            act = cur.fetchone()
            if act is None:
                con.rollback()
                return False
            id_ad = act[0]
            cur.execute("""SELECT ad.cupos_disponibles, ad.estado_detalle, ad.hora_inicio, ad.hora_fin FROM agenda_detalle ad WHERE ad.id_agenda_detalle = %s FOR UPDATE""", (id_ad,))
            ad = cur.fetchone()
            cur.execute("SELECT id_estado_cita, descripcion, ocupa_cupo, activo FROM estado_cita WHERE id_estado_cita = %s", (id_estado_nuevo,))
            nuevo = cur.fetchone()
            if nuevo is None or not nuevo[3]:
                con.rollback()
                return (INVALIDO, 'id_estado_cita', 'El estado de la cita no es válido.')
            cur.execute("SELECT id_estado_cita, descripcion, ocupa_cupo FROM estado_cita WHERE id_estado_cita = %s", (act[1],))
            ant = cur.fetchone()
            if ant[1] == 'Cancelado' and nuevo[1] != 'Cancelado':
                con.rollback()
                return (EN_USO, 'Una cita cancelada no se reactiva: registre una cita nueva.')
            cur.execute("SELECT 1 FROM consultas_cab WHERE id_cita = %s AND activo = true", (id_cita_detalle,))
            if cur.fetchone() and ant[0] != nuevo[0]:
                con.rollback()
                return (EN_USO, 'La cita ya tiene una consulta registrada: su estado lo maneja Consultorio.')
            if hora_cita is not None and hora_cita != act[4]:
                if not (ad[2] <= hora_cita < ad[3]):
                    con.rollback()
                    return (INVALIDO, 'hora_cita', f'La hora debe estar entre {str(ad[2])[:5]} y {str(ad[3])[:5]} (horario publicado).')
            if not ant[2] and nuevo[2]:      # libre -> ocupa
                if ad[0] <= 0:
                    con.rollback()
                    return SIN_CUPOS
                cur.execute("""UPDATE agenda_detalle SET cupos_disponibles = cupos_disponibles - 1,
                               estado_detalle = CASE WHEN cupos_disponibles - 1 = 0 THEN 'Agotado' ELSE estado_detalle END WHERE id_agenda_detalle = %s""", (id_ad,))
            elif ant[2] and not nuevo[2]:    # ocupa -> libre
                self._devolver_cupo(cur, id_ad)
            sets, params = ["id_estado_cita = %s", "fecha_cambio_estado = NOW()"], [id_estado_nuevo]
            if motivo_consulta is not None:
                sets.append("motivo_consulta = %s"); params.append(motivo_consulta)
            if hora_cita is not None:
                sets.append("hora_cita = %s"); params.append(hora_cita)
            cur.execute(f"UPDATE cita_detalle SET {', '.join(sets)} WHERE id_cita_detalle = %s", (*params, id_cita_detalle))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al cambiar el estado del horario de la cita: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    @staticmethod
    def _devolver_cupo(cur, id_agenda_detalle):
        cur.execute("""UPDATE agenda_detalle SET cupos_disponibles = LEAST(cupos_maximos, cupos_disponibles + 1),
                       estado_detalle = CASE WHEN estado_detalle = 'Agotado' THEN 'Disponible' ELSE estado_detalle END
                       WHERE id_agenda_detalle = %s""", (id_agenda_detalle,))

    def deleteCitaDetalle(self, id_cita_detalle):
        """Cancela un horario de la cita y devuelve el cupo si lo ocupaba. Returns: True; False si no existe o ya estaba cancelado; ("EN_USO", motivo)."""
        id_cancelado = self.getIdEstadoCancelado()
        if not id_cancelado:
            return False
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_agenda_detalle, id_estado_cita FROM cita_detalle WHERE id_cita_detalle = %s", (id_cita_detalle,))
            act = cur.fetchone()
            if act is None or act[1] == id_cancelado:
                con.rollback()
                return False
            cur.execute("SELECT 1 FROM agenda_detalle WHERE id_agenda_detalle = %s FOR UPDATE", (act[0],))
            cur.execute("SELECT 1 FROM consultas_cab WHERE id_cita = %s AND activo = true", (id_cita_detalle,))
            if cur.fetchone():
                con.rollback()
                return (EN_USO, 'La cita ya tiene una consulta registrada: no se puede cancelar desde acá.')
            cur.execute("SELECT ocupa_cupo FROM estado_cita WHERE id_estado_cita = %s", (act[1],))
            if cur.fetchone()[0]:
                self._devolver_cupo(cur, act[0])
            cur.execute("UPDATE cita_detalle SET id_estado_cita = %s, fecha_cambio_estado = NOW() WHERE id_cita_detalle = %s", (id_cancelado, id_cita_detalle))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al cancelar el horario de la cita: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def deleteCitaCabecera(self, id_cita_cabecera):
        """
        Anula la cita: cancela todos sus horarios (devolviendo el cupo de los que lo ocupaban) y la pone 'Inactivo', todo en una transacción.
        Returns: True; False si no existe o ya estaba anulada; ("EN_USO", motivo) si algún horario tiene consulta registrada.
        """
        id_cancelado = self.getIdEstadoCancelado()
        if not id_cancelado:
            return False
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT 1 FROM cita_cabecera WHERE id_cita_cabecera = %s AND estado <> 'Inactivo' FOR UPDATE", (id_cita_cabecera,))
            if cur.fetchone() is None:
                con.rollback()
                return False
            cur.execute("""SELECT cd.id_cita_detalle, cd.id_agenda_detalle, ec.ocupa_cupo, cd.id_estado_cita FROM cita_detalle cd
                           JOIN estado_cita ec ON ec.id_estado_cita = cd.id_estado_cita WHERE cd.id_cita_cabecera = %s ORDER BY cd.id_agenda_detalle""", (id_cita_cabecera,))
            filas = cur.fetchall()
            for id_cd, id_ad, ocupa, id_est in filas:
                if id_est == id_cancelado:
                    continue
                cur.execute("SELECT 1 FROM agenda_detalle WHERE id_agenda_detalle = %s FOR UPDATE", (id_ad,))
                cur.execute("SELECT 1 FROM consultas_cab WHERE id_cita = %s AND activo = true", (id_cd,))
                if cur.fetchone():
                    con.rollback()
                    return (EN_USO, 'La cita ya tiene una consulta registrada: no se puede anular desde acá.')
                if ocupa:
                    self._devolver_cupo(cur, id_ad)
                cur.execute("UPDATE cita_detalle SET id_estado_cita = %s, fecha_cambio_estado = NOW() WHERE id_cita_detalle = %s", (id_cancelado, id_cd))
            cur.execute("UPDATE cita_cabecera SET estado = 'Inactivo' WHERE id_cita_cabecera = %s", (id_cita_cabecera,))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al anular cabecera de cita: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ---------------- lookups de otras pantallas ----------------
    def obtenerCitasPacienteConfirmadas(self, id_paciente):
        """Las últimas citas vigentes de un paciente (las usa Avisos para elegir la cita a recordar)."""
        sql = """
        SELECT cc.id_cita_cabecera, cd.id_cita_detalle, cd.fecha_cita, cd.hora_cita,
               COALESCE(m.nombre || ' ' || m.apellido, 'Sin médico'), COALESCE(e.nombre_especialidad, 'Sin especialidad'),
               COALESCE(co.nombre_consultorio, 'Sin consultorio'), ec.descripcion, cd.motivo_consulta, cd.id_estado_cita, ac.id_medico, ac.id_consultorio
        FROM cita_detalle cd
        JOIN cita_cabecera cc ON cd.id_cita_cabecera = cc.id_cita_cabecera
        JOIN estado_cita ec ON cd.id_estado_cita = ec.id_estado_cita
        JOIN agenda_cabecera ac ON cc.id_agenda_cabecera = ac.id_agenda_cabecera
        LEFT JOIN medico m ON ac.id_medico = m.id_medico
        LEFT JOIN especialidades e ON ac.id_especialidad = e.id_especialidad
        LEFT JOIN consultorio co ON ac.id_consultorio = co.codigo
        WHERE cc.id_paciente = %s AND cc.estado <> 'Inactivo' AND ec.descripcion IN ('Reservado', 'Confirmado')
        ORDER BY cd.fecha_cita DESC, cd.hora_cita DESC LIMIT 10
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_paciente,))
            return [{'id_cita_cabecera': r[0], 'id_cita_detalle': r[1], 'fecha_cita': str(r[2]), 'hora_cita': str(r[3])[:5], 'medico': r[4],
                     'especialidad': r[5], 'consultorio': r[6], 'codigo': r[11], 'estado_cita': r[7], 'motivo_consulta': r[8],
                     'id_estado_cita': r[9], 'id_medico': r[10]} for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener citas del paciente: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getCitasPendientes(self):
        """Citas Reservado / Confirmado de hoy en adelante, para elegir la cita de un aviso."""
        sql = """
        SELECT cd.id_cita_detalle, cd.fecha_cita, cd.hora_cita, cc.id_paciente, (p.nombre || ' ' || p.apellido), (m.nombre || ' ' || m.apellido),
               co.nombre_consultorio, ec.descripcion,
               EXISTS(SELECT 1 FROM avisos_recordatorios a WHERE a.id_cita_detalle = cd.id_cita_detalle AND a.estado <> 'Inactivo')
        FROM cita_detalle cd
        JOIN cita_cabecera cc ON cd.id_cita_cabecera = cc.id_cita_cabecera
        JOIN estado_cita ec ON cd.id_estado_cita = ec.id_estado_cita
        JOIN agenda_cabecera ac ON cc.id_agenda_cabecera = ac.id_agenda_cabecera
        JOIN paciente p ON cc.id_paciente = p.id_paciente
        JOIN medico m ON ac.id_medico = m.id_medico
        JOIN consultorio co ON ac.id_consultorio = co.codigo
        WHERE cc.estado <> 'Inactivo' AND ec.descripcion IN ('Reservado', 'Confirmado') AND cd.fecha_cita >= CURRENT_DATE
        ORDER BY cd.fecha_cita, cd.hora_cita
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            return [{'id_cita_detalle': r[0], 'fecha_cita': str(r[1]), 'hora_cita': str(r[2])[:5], 'id_paciente': r[3], 'paciente_nombre': r[4],
                     'medico_nombre': r[5], 'nombre_consultorio': r[6], 'estado_cita': r[7], 'tiene_aviso': r[8]} for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener citas pendientes: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getCitasConfirmadasSinConsulta(self):
        """Las citas en estado 'Confirmado' sin consulta registrada: fuente del selector de 'Nueva Consulta' en Consultorio."""
        sql = """
        SELECT cd.id_cita_detalle, cd.fecha_cita, cd.hora_cita, cd.motivo_consulta, cc.id_paciente, (p.nombre || ' ' || p.apellido),
               ac.id_medico, (m.nombre || ' ' || m.apellido), ac.id_consultorio, co.nombre_consultorio
        FROM cita_detalle cd
        JOIN cita_cabecera cc ON cd.id_cita_cabecera = cc.id_cita_cabecera
        JOIN agenda_cabecera ac ON cc.id_agenda_cabecera = ac.id_agenda_cabecera
        JOIN paciente p ON cc.id_paciente = p.id_paciente
        JOIN medico m ON ac.id_medico = m.id_medico
        JOIN consultorio co ON ac.id_consultorio = co.codigo
        JOIN estado_cita ec ON cd.id_estado_cita = ec.id_estado_cita
        WHERE ec.descripcion = 'Confirmado' AND cc.estado <> 'Inactivo'
          AND NOT EXISTS (SELECT 1 FROM consultas_cab con WHERE con.id_cita = cd.id_cita_detalle AND con.activo = true)
        ORDER BY cd.fecha_cita, cd.hora_cita
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            return [{'id_cita_detalle': r[0], 'fecha_cita': str(r[1]), 'hora_cita': str(r[2]), 'motivo_consulta': r[3], 'id_paciente': r[4],
                     'paciente_nombre': r[5], 'id_medico': r[6], 'medico_nombre': r[7], 'id_consultorio': r[8], 'nombre_consultorio': r[9]}
                    for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener citas confirmadas sin consulta: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()
