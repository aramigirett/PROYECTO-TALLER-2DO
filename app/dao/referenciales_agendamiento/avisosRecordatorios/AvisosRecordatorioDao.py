import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion
from app.Services.telefono import es_celular

# Códigos de resultado (además de un ID o True)
NO_EXISTE = "NO_EXISTE"
YA_ACTIVO = "YA_ACTIVO"
INVALIDO = "INVALIDO"      # ("INVALIDO", campo, mensaje): un paciente, médico, consultorio, funcionario o cita no existe o está anulado
DUPLICADO = "DUPLICADO"    # ("DUPLICADO", campo, mensaje): la cita ya tiene un aviso vigente
EN_USO = "EN_USO"          # ("EN_USO", motivo): el aviso ya fue enviado

_SELECT = """
SELECT a.id_aviso, a.id_paciente, (p.nombre || ' ' || p.apellido) AS paciente, p.telefono, p.correo,
       a.id_funcionario, (f.nombre || ' ' || f.apellido) AS funcionario,
       COALESCE(ac.id_medico, a.id_medico) AS id_medico,
       (SELECT m.nombre || ' ' || m.apellido FROM medico m WHERE m.id_medico = COALESCE(ac.id_medico, a.id_medico)) AS medico,
       COALESCE(ac.id_consultorio, a.codigo) AS codigo,
       (SELECT c.nombre_consultorio FROM consultorio c WHERE c.codigo = COALESCE(ac.id_consultorio, a.codigo)) AS nombre_consultorio,
       COALESCE(cd.fecha_cita, a.fecha_cita) AS fecha_cita, COALESCE(cd.hora_cita, a.hora_cita) AS hora_cita,
       a.forma_envio, a.mensaje, a.estado_envio, a.estado_confirmacion, a.estado, a.id_cita_detalle, a.canal_enviado, a.motivo_error, a.fecha_envio
FROM avisos_recordatorios a
JOIN paciente p ON a.id_paciente = p.id_paciente
JOIN funcionario f ON a.id_funcionario = f.id_funcionario
LEFT JOIN cita_detalle cd ON cd.id_cita_detalle = a.id_cita_detalle
LEFT JOIN cita_cabecera cc ON cc.id_cita_cabecera = cd.id_cita_cabecera
LEFT JOIN agenda_cabecera ac ON ac.id_agenda_cabecera = cc.id_agenda_cabecera
"""


def _fila(r):
    return {
        'id_aviso': r[0], 'id_paciente': r[1], 'paciente': r[2], 'telefono_paciente': r[3], 'correo_paciente': r[4], 'id_funcionario': r[5],
        'funcionario': r[6], 'id_medico': r[7], 'medico': r[8], 'codigo': r[9], 'nombre_consultorio': r[10],
        'fecha_cita': r[11].isoformat() if r[11] else None, 'hora_cita': r[12].strftime('%H:%M') if r[12] else None,
        'forma_envio': r[13], 'mensaje': r[14], 'estado_envio': r[15], 'estado_confirmacion': r[16], 'estado': r[17], 'activo': r[17] != 'Inactivo',
        'id_cita_detalle': r[18], 'canal_enviado': r[19], 'motivo_error': r[20], 'fecha_envio': r[21].strftime('%d/%m/%Y %H:%M') if r[21] else None,
    }


def sin_contacto(aviso):
    """El aviso sin el teléfono ni el correo del paciente (lo que ve la pantalla)."""
    return {k: v for k, v in aviso.items() if k not in ('telefono_paciente', 'correo_paciente')} | {
        'tiene_telefono': bool(aviso.get('telefono_paciente')), 'tiene_celular': es_celular(aviso.get('telefono_paciente')), 'tiene_correo': bool((aviso.get('correo_paciente') or '').strip())}


class AvisoRecordatorioDao:
    """
    Aviso o recordatorio de una cita (movimiento con baja lógica por `estado` Activo / Inactivo; el resultado del envío vive en
    `estado_envio` / `canal_enviado` / `motivo_error`). Si el aviso es de una cita, fecha, hora, médico y consultorio salen SIEMPRE de la cita
    (si la cita cambia, el aviso cambia). Al guardar toma FOR SHARE sobre el paciente, el funcionario, el médico, el consultorio y la cita, y
    rechaza los anulados. Un aviso ya enviado no se modifica.
    """

    # ---- lectura ----
    def getAvisos(self, incluir_inactivos=False, estado_envio=None, desde=None, hasta=None):
        sql = _SELECT + " WHERE TRUE"
        params = []
        if not incluir_inactivos:
            sql += " AND a.estado <> 'Inactivo'"
        if estado_envio:
            sql += " AND a.estado_envio = %s"; params.append(estado_envio)
        if desde:
            sql += " AND COALESCE(cd.fecha_cita, a.fecha_cita) >= %s"; params.append(desde)
        if hasta:
            sql += " AND COALESCE(cd.fecha_cita, a.fecha_cita) <= %s"; params.append(hasta)
        sql += " ORDER BY COALESCE(cd.fecha_cita, a.fecha_cita) DESC, COALESCE(cd.hora_cita, a.hora_cita) DESC, a.id_aviso DESC"
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, params)
            return [_fila(r) for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error en AvisoRecordatorioDao.getAvisos: {e}")
            return []
        finally:
            cur.close()
            con.close()

    def getAvisoById(self, id_aviso, incluir_inactivos=False):
        sql = _SELECT + " WHERE a.id_aviso = %s" + ("" if incluir_inactivos else " AND a.estado <> 'Inactivo'")
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_aviso,))
            r = cur.fetchone()
            return _fila(r) if r else None
        except Exception as e:
            app.logger.error(f"Error en AvisoRecordatorioDao.getAvisoById: {e}")
            return None
        finally:
            cur.close()
            con.close()

    # ---- escritura ----
    def _validar_y_resolver(self, cur, v, id_funcionario, excluir_aviso=None):
        """
        Bloquea (FOR SHARE) lo que el aviso referencia y resuelve los datos: con cita, paciente / médico / consultorio / fecha / hora salen de ella.
        Devuelve (valores_resueltos, None) o (None, ("INVALIDO"|"DUPLICADO", campo, mensaje)).
        """
        r = dict(v)
        if v.get('id_cita_detalle'):
            cur.execute("""SELECT cc.id_paciente, ac.id_medico, ac.id_consultorio, cd.fecha_cita, cd.hora_cita, ec.descripcion, cc.estado
                           FROM cita_detalle cd JOIN cita_cabecera cc ON cc.id_cita_cabecera = cd.id_cita_cabecera
                           JOIN agenda_cabecera ac ON ac.id_agenda_cabecera = cc.id_agenda_cabecera
                           JOIN estado_cita ec ON ec.id_estado_cita = cd.id_estado_cita WHERE cd.id_cita_detalle = %s FOR SHARE OF cd""", (v['id_cita_detalle'],))
            c = cur.fetchone()
            if c is None or c[6] == 'Inactivo' or c[5] not in ('Reservado', 'Confirmado'):
                return None, (INVALIDO, 'id_cita_detalle', 'La cita seleccionada no existe o ya no está pendiente (Reservado o Confirmado).')
            r.update({'id_paciente': c[0], 'id_medico': c[1], 'codigo': c[2], 'fecha_cita': c[3], 'hora_cita': c[4]})
            cur.execute("SELECT 1 FROM avisos_recordatorios WHERE id_cita_detalle = %s AND estado <> 'Inactivo' AND id_aviso <> COALESCE(%s, 0)",
                        (v['id_cita_detalle'], excluir_aviso))
            if cur.fetchone():
                return None, (DUPLICADO, 'id_cita_detalle', 'Esa cita ya tiene un aviso vigente.')
        for tabla, pk, valor, campo, msg, opcional in (
                ('paciente', 'id_paciente', r.get('id_paciente'), 'id_paciente', 'El paciente seleccionado no existe o está anulado.', False),
                ('medico', 'id_medico', r.get('id_medico'), 'id_medico', 'El médico seleccionado no existe o está anulado.', True),
                ('consultorio', 'codigo', r.get('codigo'), 'codigo', 'El consultorio seleccionado no existe o está anulado.', True),
                ('funcionario', 'id_funcionario', id_funcionario, 'id_funcionario', 'Su usuario no está vinculado a un funcionario activo.', False)):
            if valor is None and opcional:
                continue
            cur.execute(f"SELECT activo FROM {tabla} WHERE {pk} = %s FOR SHARE", (valor,))
            f = cur.fetchone()
            if f is None or not f[0]:
                return None, (INVALIDO, campo, msg)
        return r, None

    def addAviso(self, v, id_funcionario):
        """
        v = {id_paciente, id_cita_detalle?, id_medico?, codigo?, fecha_cita, hora_cita, forma_envio, mensaje?}. Returns: ID nuevo; ("INVALIDO", campo, msg);
        ("DUPLICADO", campo, msg); False.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            r, error = self._validar_y_resolver(cur, v, id_funcionario)
            if error:
                con.rollback()
                return error
            cur.execute("""INSERT INTO avisos_recordatorios(id_paciente, id_funcionario, id_medico, codigo, fecha_cita, hora_cita, forma_envio, mensaje, id_cita_detalle)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id_aviso""",
                        (r['id_paciente'], id_funcionario, r.get('id_medico'), r.get('codigo'), r['fecha_cita'], r['hora_cita'], r['forma_envio'],
                         r.get('mensaje'), r.get('id_cita_detalle')))
            nuevo = cur.fetchone()[0]
            con.commit()
            return nuevo
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return (DUPLICADO, 'id_cita_detalle', 'Esa cita ya tiene un aviso vigente.')
        except Exception as e:
            app.logger.error(f"Error al crear el aviso: {e}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateAviso(self, id_aviso, v):
        """Modifica los DATOS de un aviso vigente que todavía no se envió. Returns: True; False si no existe; ("EN_USO", motivo); ("INVALIDO"|"DUPLICADO", campo, msg)."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT estado_envio, id_funcionario FROM avisos_recordatorios WHERE id_aviso = %s AND estado <> 'Inactivo' FOR UPDATE", (id_aviso,))
            f = cur.fetchone()
            if f is None:
                con.rollback()
                return False
            if f[0] == 'Enviado':
                con.rollback()
                return (EN_USO, 'El aviso ya fue enviado: no se puede modificar.')
            r, error = self._validar_y_resolver(cur, v, f[1], excluir_aviso=id_aviso)
            if error:
                con.rollback()
                return error
            cur.execute("""UPDATE avisos_recordatorios SET id_paciente=%s, id_medico=%s, codigo=%s, fecha_cita=%s, hora_cita=%s, forma_envio=%s, mensaje=%s,
                           id_cita_detalle=%s WHERE id_aviso=%s""",
                        (r['id_paciente'], r.get('id_medico'), r.get('codigo'), r['fecha_cita'], r['hora_cita'], r['forma_envio'], r.get('mensaje'),
                         r.get('id_cita_detalle'), id_aviso))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return (DUPLICADO, 'id_cita_detalle', 'Esa cita ya tiene un aviso vigente.')
        except Exception as e:
            app.logger.error(f"Error al actualizar el aviso: {e}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def deleteAviso(self, id_aviso):
        """Anula (baja lógica). Returns: True; False si no existía o ya estaba anulado."""
        return self._cambiar_estado(id_aviso, 'Inactivo')

    def reactivarAviso(self, id_aviso):
        """
        Reactiva un aviso anulado. Exige que el paciente (y médico / consultorio, si los tiene) sigan activos y que su cita siga pendiente y sin otro
        aviso vigente. Returns: True; NO_EXISTE; YA_ACTIVO; ("INVALIDO"|"DUPLICADO", campo, msg); False.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""SELECT estado, id_paciente, id_cita_detalle, id_medico, codigo, id_funcionario, fecha_cita, hora_cita, forma_envio, mensaje
                           FROM avisos_recordatorios WHERE id_aviso = %s FOR UPDATE""", (id_aviso,))
            f = cur.fetchone()
            if f is None:
                con.rollback()
                return NO_EXISTE
            if f[0] != 'Inactivo':
                con.rollback()
                return YA_ACTIVO
            _, error = self._validar_y_resolver(cur, {'id_paciente': f[1], 'id_cita_detalle': f[2], 'id_medico': f[3], 'codigo': f[4]}, f[5], excluir_aviso=id_aviso)
            if error and error[1] != 'id_funcionario':
                con.rollback()
                return error
            cur.execute("UPDATE avisos_recordatorios SET estado = 'Activo' WHERE id_aviso = %s", (id_aviso,))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return (DUPLICADO, 'id_cita_detalle', 'Esa cita ya tiene otro aviso vigente.')
        except Exception as e:
            app.logger.error(f"Error al reactivar el aviso: {e}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def _cambiar_estado(self, id_aviso, nuevo):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("UPDATE avisos_recordatorios SET estado = %s WHERE id_aviso = %s AND estado <> %s", (nuevo, id_aviso, nuevo))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except Exception as e:
            app.logger.error(f"Error al cambiar el estado del aviso: {e}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def cambiarConfirmacion(self, id_aviso, nuevo):
        """Estado de confirmación del paciente (Pendiente / Confirmado / Cancelado). Returns: True; False si no existe o está anulado."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("UPDATE avisos_recordatorios SET estado_confirmacion = %s WHERE id_aviso = %s AND estado <> 'Inactivo'", (nuevo, id_aviso))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except Exception as e:
            app.logger.error(f"Error al cambiar la confirmación del aviso: {e}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def registrarEnvio(self, id_aviso, estado_envio, canal, motivo, mensaje):
        """Deja asentado el resultado del envío: 'Enviado' / 'Error', por qué canal salió y el motivo del fallo o del respaldo. Returns: bool."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""UPDATE avisos_recordatorios SET estado_envio = %s, canal_enviado = %s, motivo_error = %s, mensaje = %s,
                           fecha_envio = CASE WHEN %s = 'Enviado' THEN NOW() ELSE fecha_envio END WHERE id_aviso = %s AND estado <> 'Inactivo'""",
                        (estado_envio, canal, (motivo or None) and motivo[:200], mensaje, estado_envio, id_aviso))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except Exception as e:
            app.logger.error(f"Error al registrar el envío del aviso: {e}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def datosParaMensaje(self, v):
        """
        Los datos que arman el mensaje ANTES de que exista el aviso: con cita salen de ella; sin cita, del paciente / fecha / hora / médico / consultorio elegidos.
        Solo lectura. Devuelve el dict que entiende construir_mensaje() o None si la cita / el paciente no existen o están anulados.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            if v.get('id_cita_detalle'):
                cur.execute("""SELECT cc.id_paciente, ac.id_medico, ac.id_consultorio, cd.fecha_cita, cd.hora_cita
                               FROM cita_detalle cd JOIN cita_cabecera cc ON cc.id_cita_cabecera = cd.id_cita_cabecera
                               JOIN agenda_cabecera ac ON ac.id_agenda_cabecera = cc.id_agenda_cabecera
                               WHERE cd.id_cita_detalle = %s AND cc.estado <> 'Inactivo'""", (v['id_cita_detalle'],))
                c = cur.fetchone()
                if c is None:
                    return None
                id_paciente, id_medico, codigo, fecha, hora = c
            else:
                id_paciente, id_medico, codigo, fecha, hora = v.get('id_paciente'), v.get('id_medico'), v.get('codigo'), v.get('fecha_cita'), v.get('hora_cita')
            cur.execute("SELECT nombre || ' ' || apellido FROM paciente WHERE id_paciente = %s AND activo", (id_paciente,))
            p = cur.fetchone()
            if p is None:
                return None
            medico = consultorio = None
            if id_medico:
                cur.execute("SELECT nombre || ' ' || apellido FROM medico WHERE id_medico = %s AND activo", (id_medico,))
                m = cur.fetchone(); medico = m[0] if m else None
            if codigo:
                cur.execute("SELECT nombre_consultorio FROM consultorio WHERE codigo = %s AND activo", (codigo,))
                k = cur.fetchone(); consultorio = k[0] if k else None
            return {'paciente': p[0], 'medico': medico, 'nombre_consultorio': consultorio, 'fecha_cita': fecha, 'hora_cita': hora}
        except Exception as e:
            app.logger.error(f"Error al preparar el mensaje del aviso: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def estadisticas(self):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""SELECT COUNT(*), COUNT(*) FILTER (WHERE estado_envio='Pendiente'), COUNT(*) FILTER (WHERE estado_envio='Enviado'),
                                  COUNT(*) FILTER (WHERE estado_envio='Error'), COUNT(*) FILTER (WHERE canal_enviado='WhatsApp'),
                                  COUNT(*) FILTER (WHERE canal_enviado='Correo'), COUNT(*) FILTER (WHERE estado_confirmacion='Confirmado'),
                                  COUNT(*) FILTER (WHERE estado_confirmacion='Pendiente'), COUNT(*) FILTER (WHERE estado_confirmacion='Cancelado')
                           FROM avisos_recordatorios WHERE estado <> 'Inactivo'""")
            r = cur.fetchone()
            return {'total': r[0], 'por_estado': {'pendientes': r[1], 'enviados': r[2], 'errores': r[3]},
                    'por_canal': {'whatsapp': r[4], 'correo': r[5]}, 'por_confirmacion': {'confirmados': r[6], 'pendientes': r[7], 'cancelados': r[8]}}
        except Exception as e:
            app.logger.error(f"Error en estadísticas de avisos: {e}")
            return {}
        finally:
            cur.close()
            con.close()
