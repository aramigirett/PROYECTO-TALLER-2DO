"""
=====================================================
DAO: Consulta Médica
Descripción: Manejo de consultas_cab (cabecera de consultas)

Reglas (Registrar Consulta):
  - Se registra desde una cita en estado "Confirmado" sin consulta ACTIVA; paciente, médico y consultorio (y el funcionario que la
    registra) deben estar activos. Paciente, médico, consultorio, fecha y hora se derivan siempre de la cita.
  - Estados: programada -> en_proceso -> finalizada, y programada | en_proceso -> cancelada. finalizada y cancelada son finales.
    Inician y finalizan la atención el médico de la consulta; cancela el funcionario (Recepción) o el médico de la consulta.
  - Anular (baja por error, definitiva): bloqueada si la consulta está finalizada o tiene datos clínicos vigentes (Ficha Médica,
    Diagnóstico, Odontograma, Tratamiento, Receta, Órdenes de Estudio o de Análisis, Justificativo). La cita vuelve a "Confirmado".
  - cancelada != anulada: cancelada = la atención no se realizó y queda en el historial; su cita pasa de 'Realizado' a 'Cancelado' (no vuelve a
    'Confirmado') y se devuelve el cupo de la agenda. Anulada = baja por error: la cita vuelve a 'Confirmado'.
Toda operación que cambia datos toma bloqueos de fila (la consulta primero, la cita después) dentro de una transacción.
=====================================================
"""
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

ESTADOS = ('programada', 'en_proceso', 'finalizada', 'cancelada')
TRANSICIONES = {
    'programada': ('en_proceso', 'cancelada'),
    'en_proceso': ('finalizada', 'cancelada'),
}
DURACION_MIN, DURACION_MAX = 1, 480
POR_PAGINA_MAX = 100


def numero_consulta(id_consulta_cab):
    """N.º de consulta visible, derivado del id (sin columna nueva): CON-0000017."""
    return f'CON-{int(id_consulta_cab):07d}'


def duracion_valida(valor):
    """Devuelve (duración|None, error). Vacío = sin duración."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None, None
    try:
        n = int(str(valor).strip())
    except (ValueError, TypeError):
        return None, 'DURACION_INVALIDA'
    if isinstance(valor, float) and valor != n:
        return None, 'DURACION_INVALIDA'
    if not DURACION_MIN <= n <= DURACION_MAX:
        return None, 'DURACION_INVALIDA'
    return n, None


class ConsultaDao:

    # ------------------------------------------------------------------ lectura
    def listar(self, estado=None, texto=None, desde=None, hasta=None, id_medico=None, pagina=1, por_pagina=25):
        """Consultas ACTIVAS (las anuladas no se listan) con filtros; paginadas en el servidor. Devuelve (filas, total)."""
        where, params = ["cc.activo = true"], []
        if estado:
            where.append("cc.estado = %s"); params.append(estado)
        if texto:
            where.append("(CONCAT(p.nombre, ' ', p.apellido) ILIKE %s OR p.cedula_entidad ILIKE %s)")
            params += [f'%{texto}%', f'%{texto}%']
        if desde:
            where.append("cc.fecha_cita >= %s"); params.append(desde)
        if hasta:
            where.append("cc.fecha_cita <= %s"); params.append(hasta)
        if id_medico:
            where.append("cc.id_medico = %s"); params.append(id_medico)
        cond = ' AND '.join(where)
        por_pagina = max(1, min(int(por_pagina), POR_PAGINA_MAX))
        pagina = max(1, int(pagina))
        sql = f"""
        SELECT cc.id_consulta_cab, cc.id_paciente, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad,
               cc.id_medico, CONCAT(m.nombre, ' ', m.apellido), cc.id_consultorio, co.nombre_consultorio,
               cc.fecha_cita, cc.hora_cita, cc.duracion_minutos, cc.estado, cc.activo,
               EXISTS(SELECT 1 FROM ficha_medica_consulta fm WHERE fm.id_consulta_cab = cc.id_consulta_cab AND fm.activo = true)
        FROM consultas_cab cc
        JOIN paciente p ON cc.id_paciente = p.id_paciente
        JOIN medico m ON cc.id_medico = m.id_medico
        JOIN consultorio co ON cc.id_consultorio = co.codigo
        WHERE {cond}
        ORDER BY cc.fecha_cita DESC, cc.hora_cita DESC, cc.id_consulta_cab DESC
        LIMIT %s OFFSET %s"""
        sql_total = f"""SELECT COUNT(*) FROM consultas_cab cc JOIN paciente p ON cc.id_paciente = p.id_paciente WHERE {cond}"""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql_total, tuple(params))
            total = cur.fetchone()[0]
            cur.execute(sql, tuple(params) + (por_pagina, (pagina - 1) * por_pagina))
            filas = [{
                'id_consulta_cab': c[0], 'numero': numero_consulta(c[0]),
                'id_paciente': c[1], 'nombre_paciente': c[2], 'cedula_paciente': c[3],
                'id_medico': c[4], 'nombre_medico': c[5],
                'id_consultorio': c[6], 'nombre_consultorio': c[7],
                'fecha_cita': c[8].isoformat() if c[8] else None, 'hora_cita': str(c[9]) if c[9] else None,
                'duracion_minutos': c[10], 'estado': c[11], 'activo': c[12], 'tiene_ficha': c[13],
            } for c in cur.fetchall()]
            return filas, total
        except Exception as e:
            app.logger.error(f"Error al listar consultas: {str(e)}")
            return [], 0
        finally:
            cur.close()
            con.close()

    def indicadores(self, id_medico=None):
        """Contadores para las tarjetas del listado (consultas activas; las de un médico si se pasa su id)."""
        sql = """
        SELECT COUNT(*) FILTER (WHERE fecha_cita = CURRENT_DATE),
               COUNT(*) FILTER (WHERE estado = 'programada'), COUNT(*) FILTER (WHERE estado = 'en_proceso'),
               COUNT(*) FILTER (WHERE estado = 'finalizada'), COUNT(*) FILTER (WHERE estado = 'cancelada'), COUNT(*)
        FROM consultas_cab WHERE activo = true""" + (" AND id_medico = %s" if id_medico else "")
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_medico,) if id_medico else ())
            r = cur.fetchone()
            return {'hoy': r[0], 'programadas': r[1], 'en_proceso': r[2], 'finalizadas': r[3], 'canceladas': r[4], 'total': r[5]}
        except Exception as e:
            app.logger.error(f"Error al calcular indicadores de consultas: {str(e)}")
            return {'hoy': 0, 'programadas': 0, 'en_proceso': 0, 'finalizadas': 0, 'canceladas': 0, 'total': 0}
        finally:
            cur.close()
            con.close()

    def getConsultasActivas(self):
        """Consultas activas en estado 'programada' o 'en_proceso': las únicas desde las que se carga un movimiento clínico."""
        sql = """
        SELECT cc.id_consulta_cab, cc.id_paciente, CONCAT(p.nombre, ' ', p.apellido), cc.id_medico, CONCAT(m.nombre, ' ', m.apellido),
               cc.id_consultorio, co.nombre_consultorio, cc.fecha_cita, cc.hora_cita, cc.estado
        FROM consultas_cab cc
        JOIN paciente p ON cc.id_paciente = p.id_paciente
        JOIN medico m ON cc.id_medico = m.id_medico
        JOIN consultorio co ON cc.id_consultorio = co.codigo
        WHERE cc.activo = true AND cc.estado IN ('programada', 'en_proceso')
        ORDER BY cc.fecha_cita DESC, cc.hora_cita DESC"""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            return [{
                'id_consulta_cab': c[0], 'numero': numero_consulta(c[0]), 'id_paciente': c[1], 'nombre_paciente': c[2],
                'id_medico': c[3], 'nombre_medico': c[4], 'id_consultorio': c[5], 'nombre_consultorio': c[6],
                'fecha_cita': c[7].isoformat() if c[7] else None, 'hora_cita': str(c[8]) if c[8] else None, 'estado': c[9],
            } for c in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener consultas activas: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getConsultaById(self, id_consulta_cab):
        """Una consulta por ID (activa o anulada: quien la pide decide qué hacer con `activo`)."""
        sql = """
        SELECT cc.id_consulta_cab, cc.id_cita, cc.id_paciente, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad,
               cc.id_medico, CONCAT(m.nombre, ' ', m.apellido), cc.id_consultorio, con.nombre_consultorio,
               cc.id_funcionario, CONCAT(f.nombre, ' ', f.apellido), cc.fecha_cita, cc.hora_cita, cc.duracion_minutos,
               cc.estado, cc.fecha_registro, cc.activo
        FROM consultas_cab cc
        JOIN paciente p ON cc.id_paciente = p.id_paciente
        JOIN medico m ON cc.id_medico = m.id_medico
        JOIN consultorio con ON cc.id_consultorio = con.codigo
        LEFT JOIN funcionario f ON cc.id_funcionario = f.id_funcionario
        WHERE cc.id_consulta_cab = %s"""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_consulta_cab,))
            c = cur.fetchone()
            if not c:
                return None
            return {
                'id_consulta_cab': c[0], 'numero': numero_consulta(c[0]), 'id_cita': c[1],
                'id_paciente': c[2], 'nombre_paciente': c[3], 'cedula_paciente': c[4],
                'id_medico': c[5], 'nombre_medico': c[6], 'id_consultorio': c[7], 'nombre_consultorio': c[8],
                'id_funcionario': c[9], 'nombre_funcionario': c[10],
                'fecha_cita': c[11].isoformat() if c[11] else None, 'hora_cita': str(c[12]) if c[12] else None,
                'duracion_minutos': c[13], 'estado': c[14],
                'fecha_registro': c[15].isoformat() if c[15] else None, 'activo': c[16],
            }
        except Exception as e:
            app.logger.error(f"Error al obtener consulta por ID: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def getResumen(self, id_consulta_cab):
        """Contadores de registros VIGENTES colgados de la consulta (solo cantidades, nunca contenido clínico)."""
        sql = """
        SELECT (SELECT COUNT(*) FROM ficha_medica_consulta WHERE id_consulta_cab = %(c)s AND activo = true),
               (SELECT COUNT(*) FROM diagnosticos WHERE id_consulta_cab = %(c)s AND activo = true),
               (SELECT COUNT(*) FROM odontograma WHERE id_consulta_cab = %(c)s AND activo = true),
               (SELECT COUNT(*) FROM tratamientos WHERE id_consulta_cab = %(c)s AND estado <> 'cancelado'),
               (SELECT COUNT(*) FROM recetas WHERE id_consulta_cab = %(c)s AND activo = true),
               (SELECT COUNT(*) FROM orden_estudios WHERE id_consulta_cab = %(c)s AND estado <> 'cancelado'),
               (SELECT COUNT(*) FROM orden_analisis WHERE id_consulta_cab = %(c)s AND estado <> 'cancelado'),
               (SELECT COUNT(*) FROM justificativo_medico WHERE id_consulta_cab = %(c)s AND estado <> 'anulado')"""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, {'c': id_consulta_cab})
            r = cur.fetchone()
            return {'ficha': r[0], 'diagnosticos': r[1], 'odontogramas': r[2], 'tratamientos': r[3], 'recetas': r[4],
                    'ordenes_estudio': r[5], 'ordenes_analisis': r[6], 'justificativos': r[7]}
        except Exception as e:
            app.logger.error(f"Error al obtener el resumen de la consulta: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def citasDisponibles(self, texto=None, limite=50):
        """Citas 'Confirmado' sin consulta activa cuyo paciente, médico y consultorio están activos (las que SÍ se pueden consultar)."""
        sql = """
        SELECT cd.id_cita_detalle, cd.fecha_cita, cd.hora_cita, cd.motivo_consulta, cc.id_paciente, CONCAT(p.nombre, ' ', p.apellido),
               p.cedula_entidad, ac.id_medico, CONCAT(m.nombre, ' ', m.apellido), ac.id_consultorio, co.nombre_consultorio
        FROM cita_detalle cd
        JOIN cita_cabecera cc ON cd.id_cita_cabecera = cc.id_cita_cabecera
        JOIN agenda_cabecera ac ON cc.id_agenda_cabecera = ac.id_agenda_cabecera
        JOIN paciente p ON cc.id_paciente = p.id_paciente
        JOIN medico m ON ac.id_medico = m.id_medico
        JOIN consultorio co ON ac.id_consultorio = co.codigo
        JOIN estado_cita ec ON cd.id_estado_cita = ec.id_estado_cita
        WHERE ec.descripcion = 'Confirmado' AND cc.estado <> 'Inactivo'
          AND p.activo = true AND m.activo = true AND co.activo = true
          AND NOT EXISTS (SELECT 1 FROM consultas_cab con WHERE con.id_cita = cd.id_cita_detalle AND con.activo = true)"""
        params = []
        if texto:
            sql += " AND (CONCAT(p.nombre, ' ', p.apellido) ILIKE %s OR p.cedula_entidad ILIKE %s OR CONCAT(m.nombre, ' ', m.apellido) ILIKE %s)"
            params += [f'%{texto}%'] * 3
        sql += " ORDER BY cd.fecha_cita, cd.hora_cita LIMIT %s"
        params.append(max(1, min(int(limite), 100)))
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return [{
                'id_cita_detalle': r[0], 'fecha_cita': r[1].isoformat(), 'hora_cita': str(r[2]), 'motivo_consulta': r[3],
                'id_paciente': r[4], 'paciente_nombre': r[5], 'cedula_paciente': r[6], 'id_medico': r[7], 'medico_nombre': r[8],
                'id_consultorio': r[9], 'nombre_consultorio': r[10],
            } for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al buscar citas disponibles: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ alta
    def guardarConsulta(self, datos):
        """
        Registra una consulta desde una cita 'Confirmado'. Una transacción: bloquea la cita, valida (cita sin consulta activa, paciente,
        médico, consultorio y funcionario activos), inserta la consulta (estado inicial SIEMPRE 'programada') y pasa la cita a 'Realizado'.

        Devuelve {'id_consulta_cab': N, 'contexto': {...para la auditoría...}} o {'error': CÓDIGO, 'detalle': nombre|None}.
        """
        id_cita = datos.get('id_cita')
        id_funcionario = datos.get('id_funcionario')
        if not id_funcionario:
            return {'error': 'SIN_FUNCIONARIO'}
        duracion, err = duracion_valida(datos.get('duracion_minutos'))
        if err:
            return {'error': err}

        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            # Primero se bloquea SOLO la cita (consulta simple). Bloquearla con el JOIN a estado_cita haría que, tras esperar a otra alta
            # que ya la pasó a Realizado, PostgreSQL re-evalúe el JOIN contra el estado viejo y devuelva "no encontrada" en vez de
            # "ya no está Confirmado".
            cur.execute("SELECT 1 FROM cita_detalle WHERE id_cita_detalle = %s FOR UPDATE", (id_cita,))
            if not cur.fetchone():
                con.rollback()
                return {'error': 'CITA_NO_ENCONTRADA'}
            cur.execute("""
                SELECT cd.fecha_cita, cd.hora_cita, ec.descripcion, cc.estado,
                       cc.id_paciente, p.activo, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad,
                       ac.id_medico, m.activo, CONCAT(m.nombre, ' ', m.apellido),
                       ac.id_consultorio, co.activo, co.nombre_consultorio
                FROM cita_detalle cd
                JOIN estado_cita ec ON cd.id_estado_cita = ec.id_estado_cita
                JOIN cita_cabecera cc ON cd.id_cita_cabecera = cc.id_cita_cabecera
                JOIN agenda_cabecera ac ON cc.id_agenda_cabecera = ac.id_agenda_cabecera
                JOIN paciente p ON cc.id_paciente = p.id_paciente
                JOIN medico m ON ac.id_medico = m.id_medico
                JOIN consultorio co ON ac.id_consultorio = co.codigo
                WHERE cd.id_cita_detalle = %s""", (id_cita,))
            cita = cur.fetchone()
            if not cita:
                con.rollback()
                return {'error': 'CITA_NO_ENCONTRADA'}
            (fecha_cita, hora_cita, estado_cita, estado_cab, id_paciente, pac_activo, pac_nombre, pac_ci,
             id_medico, med_activo, med_nombre, id_consultorio, cons_activo, cons_nombre) = cita

            if estado_cita != 'Confirmado' or estado_cab == 'Inactivo':
                con.rollback()
                return {'error': 'CITA_NO_CONFIRMADA'}
            cur.execute("SELECT 1 FROM consultas_cab WHERE id_cita = %s AND activo = true", (id_cita,))
            if cur.fetchone():
                con.rollback()
                return {'error': 'CITA_YA_TIENE_CONSULTA'}
            if not pac_activo:
                con.rollback()
                return {'error': 'PACIENTE_INACTIVO', 'detalle': pac_nombre}
            if not med_activo:
                con.rollback()
                return {'error': 'MEDICO_INACTIVO', 'detalle': med_nombre}
            if not cons_activo:
                con.rollback()
                return {'error': 'CONSULTORIO_INACTIVO', 'detalle': cons_nombre}
            cur.execute("SELECT activo FROM funcionario WHERE id_funcionario = %s", (id_funcionario,))
            fila = cur.fetchone()
            if not fila or not fila[0]:
                con.rollback()
                return {'error': 'FUNCIONARIO_INACTIVO'}

            cur.execute("""
                INSERT INTO consultas_cab(id_cita, id_paciente, id_medico, id_consultorio, id_funcionario,
                                          fecha_cita, hora_cita, duracion_minutos, estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'programada') RETURNING id_consulta_cab""",
                        (id_cita, id_paciente, id_medico, id_consultorio, id_funcionario, fecha_cita, hora_cita, duracion))
            id_consulta = cur.fetchone()[0]

            cur.execute("SELECT id_estado_cita FROM estado_cita WHERE descripcion = 'Realizado'")
            realizado = cur.fetchone()
            if not realizado:
                raise Exception("No existe el estado 'Realizado' en estado_cita")
            cur.execute("UPDATE cita_detalle SET id_estado_cita = %s, fecha_cambio_estado = NOW() WHERE id_cita_detalle = %s",
                        (realizado[0], id_cita))
            con.commit()
            return {'id_consulta_cab': id_consulta,
                    'contexto': {'paciente': pac_nombre, 'cedula': pac_ci, 'medico': med_nombre, 'consultorio': cons_nombre,
                                 'fecha': fecha_cita, 'hora': hora_cita, 'id_cita': id_cita}}
        except psycopg2.errors.UniqueViolation:
            con.rollback()   # dos altas simultáneas sobre la misma cita: gana una, la otra cae acá
            return {'error': 'CITA_YA_TIENE_CONSULTA'}
        except Exception as e:
            app.logger.error(f"Error al guardar consulta: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ estado
    def cambiarEstado(self, id_consulta_cab, nuevo, duracion=None, id_medico_actor=None, id_funcionario_actor=None):
        """
        Cambia el estado de la consulta (transiciones y quién puede hacerlo, ver el encabezado). Consulta bloqueada FOR UPDATE.
        La duración (opcional) solo se registra al finalizar.
        Devuelve {'ok': True, 'anterior', 'nuevo', 'contexto'} o {'error': CÓDIGO, ...}.
        """
        if nuevo not in ESTADOS:
            return {'error': 'ESTADO_INVALIDO'}
        dur, err = duracion_valida(duracion)
        if err:
            return {'error': err}
        if dur is not None and nuevo != 'finalizada':
            return {'error': 'DURACION_SOLO_AL_FINALIZAR'}

        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""SELECT cc.estado, cc.activo, cc.id_medico, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad, cc.id_cita
                           FROM consultas_cab cc JOIN paciente p ON cc.id_paciente = p.id_paciente
                           WHERE cc.id_consulta_cab = %s FOR UPDATE OF cc""", (id_consulta_cab,))
            fila = cur.fetchone()
            if not fila or not fila[1]:
                con.rollback()
                return {'error': 'NO_ENCONTRADA'}
            actual, _, id_medico, pac_nombre, pac_ci, id_cita = fila
            if nuevo not in TRANSICIONES.get(actual, ()):
                con.rollback()
                return {'error': 'TRANSICION_INVALIDA', 'anterior': actual, 'nuevo': nuevo}
            es_su_medico = id_medico_actor is not None and id_medico_actor == id_medico
            if nuevo in ('en_proceso', 'finalizada') and not es_su_medico:
                con.rollback()
                return {'error': 'SOLO_MEDICO_DE_LA_CONSULTA'}
            if nuevo == 'cancelada' and not (es_su_medico or id_funcionario_actor):
                con.rollback()
                return {'error': 'NO_AUTORIZADO'}

            if dur is not None:
                cur.execute("UPDATE consultas_cab SET estado = %s, duracion_minutos = %s WHERE id_consulta_cab = %s",
                            (nuevo, dur, id_consulta_cab))
            else:
                cur.execute("UPDATE consultas_cab SET estado = %s WHERE id_consulta_cab = %s", (nuevo, id_consulta_cab))

            cita_cancelada, estado_cita = False, None
            if nuevo == 'cancelada':
                # la atención no se hizo: la cita deja de estar 'Realizado' y pasa a 'Cancelado' (NO vuelve a 'Confirmado'), en la misma
                # transacción y devolviendo el cupo (Realizado ocupa cupo, Cancelado no). La cita se bloquea después de la consulta.
                cur.execute("SELECT id_agenda_detalle FROM cita_detalle WHERE id_cita_detalle = %s FOR UPDATE", (id_cita,))
                cita = cur.fetchone()
                cur.execute("""SELECT ec.descripcion FROM cita_detalle cd JOIN estado_cita ec ON cd.id_estado_cita = ec.id_estado_cita
                               WHERE cd.id_cita_detalle = %s""", (id_cita,))
                fila_estado = cur.fetchone()
                estado_cita = fila_estado[0] if fila_estado else None
                if cita and estado_cita == 'Realizado':
                    cur.execute("SELECT id_estado_cita FROM estado_cita WHERE descripcion = 'Cancelado'")
                    cancelado = cur.fetchone()
                    if not cancelado:
                        raise Exception("No existe el estado 'Cancelado' en estado_cita")
                    cur.execute("UPDATE cita_detalle SET id_estado_cita = %s, fecha_cambio_estado = NOW() WHERE id_cita_detalle = %s",
                                (cancelado[0], id_cita))
                    cur.execute("""UPDATE agenda_detalle
                                   SET cupos_disponibles = LEAST(cupos_maximos, cupos_disponibles + 1),
                                       estado_detalle = CASE WHEN estado_detalle = 'Agotado' THEN 'Disponible' ELSE estado_detalle END
                                   WHERE id_agenda_detalle = %s""", (cita[0],))
                    cita_cancelada = True
            con.commit()
            return {'ok': True, 'anterior': actual, 'nuevo': nuevo, 'duracion': dur, 'id_cita': id_cita,
                    'cita_cancelada': cita_cancelada, 'estado_cita': estado_cita,
                    'contexto': {'paciente': pac_nombre, 'cedula': pac_ci}}
        except Exception as e:
            app.logger.error(f"Error al cambiar el estado de la consulta: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ anular
    def anular(self, id_consulta_cab):
        """
        Baja por error (definitiva). Una transacción con la consulta bloqueada: se rechaza si está finalizada o tiene datos clínicos
        vigentes; si no, queda activo = false y la cita vuelve de 'Realizado' a 'Confirmado' (los dos estados ocupan el cupo: no se toca).
        Devuelve {'ok': True, 'cita_revertida': bool, 'id_cita', 'contexto'} o {'error': CÓDIGO, ...}.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""SELECT cc.activo, cc.estado, cc.id_cita, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad
                           FROM consultas_cab cc JOIN paciente p ON cc.id_paciente = p.id_paciente
                           WHERE cc.id_consulta_cab = %s FOR UPDATE OF cc""", (id_consulta_cab,))
            fila = cur.fetchone()
            if not fila or not fila[0]:
                con.rollback()
                return {'error': 'NO_ENCONTRADA'}
            _, estado, id_cita, pac_nombre, pac_ci = fila
            if estado == 'finalizada':
                con.rollback()
                return {'error': 'CONSULTA_FINALIZADA'}

            cur.execute("""
                SELECT EXISTS(SELECT 1 FROM ficha_medica_consulta WHERE id_consulta_cab = %(c)s AND activo = true),
                       EXISTS(SELECT 1 FROM diagnosticos WHERE id_consulta_cab = %(c)s AND activo = true),
                       EXISTS(SELECT 1 FROM odontograma WHERE id_consulta_cab = %(c)s AND activo = true),
                       EXISTS(SELECT 1 FROM tratamientos WHERE id_consulta_cab = %(c)s AND estado <> 'cancelado'),
                       EXISTS(SELECT 1 FROM recetas WHERE id_consulta_cab = %(c)s AND activo = true),
                       EXISTS(SELECT 1 FROM orden_estudios WHERE id_consulta_cab = %(c)s AND estado <> 'cancelado'),
                       EXISTS(SELECT 1 FROM orden_analisis WHERE id_consulta_cab = %(c)s AND estado <> 'cancelado'),
                       EXISTS(SELECT 1 FROM justificativo_medico WHERE id_consulta_cab = %(c)s AND estado <> 'anulado')""",
                        {'c': id_consulta_cab})
            nombres = ('Ficha Médica', 'Diagnóstico', 'Odontograma', 'Tratamiento', 'Receta', 'Orden de Estudios',
                       'Orden de Análisis', 'Justificativo Médico')
            con_datos = [n for n, tiene in zip(nombres, cur.fetchone()) if tiene]
            if con_datos:
                con.rollback()
                app.logger.warning(f"No se puede anular la consulta {id_consulta_cab}: tiene datos clínicos vigentes")
                return {'error': 'EN_USO', 'detalle': ', '.join(con_datos)}

            cur.execute("UPDATE consultas_cab SET activo = false WHERE id_consulta_cab = %s", (id_consulta_cab,))
            # la cita: se bloquea después de la consulta (mismo orden que el alta)
            cur.execute("SELECT 1 FROM cita_detalle WHERE id_cita_detalle = %s FOR UPDATE", (id_cita,))
            cur.execute("""SELECT ec.descripcion FROM cita_detalle cd JOIN estado_cita ec ON cd.id_estado_cita = ec.id_estado_cita
                           WHERE cd.id_cita_detalle = %s""", (id_cita,))
            estado_cita = cur.fetchone()
            revertida = False
            if estado_cita and estado_cita[0] == 'Realizado':
                cur.execute("SELECT id_estado_cita FROM estado_cita WHERE descripcion = 'Confirmado'")
                confirmado = cur.fetchone()
                if not confirmado:
                    raise Exception("No existe el estado 'Confirmado' en estado_cita")
                cur.execute("UPDATE cita_detalle SET id_estado_cita = %s, fecha_cambio_estado = NOW() WHERE id_cita_detalle = %s",
                            (confirmado[0], id_cita))
                revertida = True
            con.commit()
            return {'ok': True, 'cita_revertida': revertida, 'id_cita': id_cita,
                    'estado_cita': estado_cita[0] if estado_cita else None, 'contexto': {'paciente': pac_nombre, 'cedula': pac_ci}}
        except Exception as e:
            app.logger.error(f"Error al anular consulta: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()
