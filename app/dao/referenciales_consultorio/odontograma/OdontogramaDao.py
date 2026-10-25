"""
=====================================================
DAO: Odontograma (odontograma + odontograma_detalle + estado_dental)

Reglas (Gestionar Odontograma):
  - UNO por consulta (único parcial por consulta ACTIVA). Lo crea SOLO el médico de la consulta, con la consulta 'programada' o 'en_proceso'.
  - Se crea PRECARGADO: en la misma transacción se copian los hallazgos ACTIVOS del último odontograma vigente del paciente de una consulta
    ANTERIOR (por fecha y hora; no se mira una consulta cancelada). Lo que se cambie después no toca el anterior. Sin previo, queda sin hallazgos.
  - Un hallazgo (odontograma_detalle) es pieza FDI + superficie (O V L M D, o T = pieza completa) + estado dental. Un estado de `aplica_a = PIEZA`
    va con la superficie T; uno de `aplica_a = SUPERFICIE`, con O V L M o D. Un registro idéntico ACTIVO (misma pieza, superficie y estado) se rechaza.
  - Agregar y quitar hallazgos: solo el médico de la consulta, con la consulta abierta, revalidado en la transacción (consulta bloqueada FOR UPDATE).
    Quitar es una BAJA LÓGICA del renglón (`activo = false`): se conserva la trazabilidad clínica.
  - Anular el odontograma: definitiva (`activo = false`); sus hallazgos quedan como historial. Se puede crear otro para la consulta.
Orden de bloqueos (igual que en las otras operaciones): la consulta primero, después el odontograma y el hallazgo.
Dato de salud: la auditoría no recibe piezas, superficies ni estados.
=====================================================
"""
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion
from app.dao.referenciales_consultorio.consulta.ConsultaDao import numero_consulta

ESTADOS_ABIERTOS = ('programada', 'en_proceso')
SUPERFICIES_DE_SUPERFICIE = ('O', 'V', 'L', 'M', 'D')


def _hallazgo(r):
    return {
        'id_odontograma_detalle': r[0], 'id_odontograma': r[1], 'numero_diente': r[2], 'superficie': r[3], 'id_estado_dental': r[4],
        'estado_descripcion': r[5], 'estado_color': r[6], 'estado_simbolo': r[7], 'aplica_a': r[8], 'observacion': r[9],
    }


_SELECT_HALLAZGOS = """
    SELECT od.id_odontograma_detalle, od.id_odontograma, od.numero_diente, od.superficie, od.id_estado_dental,
           ed.descripcion, ed.color, ed.simbolo, ed.aplica_a, od.observacion
    FROM odontograma_detalle od JOIN estado_dental ed ON ed.id_estado_dental = od.id_estado_dental"""   # sin filtrar el activo del estado dental

_SELECT_CABECERA = """
    SELECT o.id_odontograma, o.id_consulta_cab, o.id_paciente, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad, o.id_medico,
           CONCAT(m.nombre, ' ', m.apellido), o.fecha_registro, o.observaciones, o.activo, cc.estado, cc.fecha_cita, cc.hora_cita
    FROM odontograma o
    JOIN consultas_cab cc ON o.id_consulta_cab = cc.id_consulta_cab
    JOIN paciente p ON o.id_paciente = p.id_paciente
    JOIN medico m ON o.id_medico = m.id_medico"""


def _cabecera(r):
    return {
        'id_odontograma': r[0], 'id_consulta_cab': r[1], 'numero_consulta': numero_consulta(r[1]), 'id_paciente': r[2], 'nombre_paciente': r[3],
        'cedula_paciente': r[4], 'id_medico': r[5], 'nombre_medico': r[6], 'fecha_registro': r[7].isoformat() if r[7] else None,
        'observaciones': r[8], 'activo': r[9], 'estado_consulta': r[10], 'fecha_consulta': r[11].isoformat() if r[11] else None,
        'hora_consulta': str(r[12]) if r[12] else None,
    }


class OdontogramaDao:

    # ------------------------------------------------------------------ lectura
    def getEstadosDentales(self):
        """Catálogo de estados dentales activos (color, símbolo y a qué se aplica: PIEZA o SUPERFICIE)."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_estado_dental, descripcion, color, simbolo, aplica_a FROM estado_dental WHERE activo = true ORDER BY id_estado_dental")
            return [{'id_estado_dental': r[0], 'descripcion': r[1], 'color': r[2], 'simbolo': r[3], 'aplica_a': r[4]} for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener los estados dentales: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def _hallazgos(self, cur, ids_odontograma):
        if not ids_odontograma:
            return {}
        cur.execute(_SELECT_HALLAZGOS + " WHERE od.id_odontograma = ANY(%s) AND od.activo = true ORDER BY od.numero_diente, od.superficie, od.id_odontograma_detalle",
                    (list(ids_odontograma),))
        por_odo = {}
        for r in cur.fetchall():
            por_odo.setdefault(r[1], []).append(_hallazgo(r))
        return por_odo

    def _leer(self, sql, params, con_hallazgos):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, params)
            filas = cur.fetchall()
            hall = self._hallazgos(cur, [f[0] for f in filas]) if con_hallazgos else {}
            out = []
            for f in filas:
                c = _cabecera(f)
                if con_hallazgos:
                    c['hallazgos'] = hall.get(f[0], [])
                out.append(c)
            return out
        except Exception as e:
            app.logger.error(f"Error al leer odontogramas: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getOdontogramaById(self, id_odontograma, solo_vigente=True):
        filas = self._leer(_SELECT_CABECERA + " WHERE o.id_odontograma = %s" + (" AND o.activo = true" if solo_vigente else ""), (id_odontograma,), True)
        return filas[0] if filas else None

    def getOdontogramaByConsulta(self, id_consulta_cab):
        """El odontograma VIGENTE de la consulta (con sus hallazgos activos) o None."""
        filas = self._leer(_SELECT_CABECERA + " WHERE o.id_consulta_cab = %s AND o.activo = true", (id_consulta_cab,), True)
        return filas[0] if filas else None

    def listar(self, texto=None, desde=None, hasta=None, id_medico=None, id_paciente=None, pagina=1, por_pagina=25):
        """Odontogramas VIGENTES (sin hallazgos) con filtros, paginados en el servidor. Devuelve (filas, total)."""
        where, params = ["o.activo = true", "cc.activo = true"], []
        if texto:
            where.append("(CONCAT(p.nombre, ' ', p.apellido) ILIKE %s OR p.cedula_entidad ILIKE %s)")
            params += [f'%{texto}%'] * 2
        if desde:
            where.append("cc.fecha_cita >= %s"); params.append(desde)
        if hasta:
            where.append("cc.fecha_cita <= %s"); params.append(hasta)
        if id_medico:
            where.append("cc.id_medico = %s"); params.append(id_medico)
        if id_paciente:
            where.append("o.id_paciente = %s"); params.append(id_paciente)
        cond = ' AND '.join(where)
        por_pagina = max(1, min(int(por_pagina), 100))
        pagina = max(1, int(pagina))
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"""SELECT COUNT(*) FROM odontograma o JOIN consultas_cab cc ON o.id_consulta_cab = cc.id_consulta_cab
                            JOIN paciente p ON o.id_paciente = p.id_paciente WHERE {cond}""", tuple(params))
            total = cur.fetchone()[0]
            cur.execute(f"""{_SELECT_CABECERA} WHERE {cond} ORDER BY cc.fecha_cita DESC, cc.hora_cita DESC, o.id_odontograma DESC LIMIT %s OFFSET %s""",
                        tuple(params) + (por_pagina, (pagina - 1) * por_pagina))
            filas = cur.fetchall()
            cur.execute("""SELECT id_odontograma, COUNT(*) FROM odontograma_detalle WHERE id_odontograma = ANY(%s) AND activo = true GROUP BY 1""",
                        ([f[0] for f in filas],))
            cuentas = dict(cur.fetchall())
            out = []
            for f in filas:
                c = _cabecera(f)
                c['cantidad_hallazgos'] = cuentas.get(f[0], 0)
                out.append(c)
            return out, total
        except Exception as e:
            app.logger.error(f"Error al listar odontogramas: {str(e)}")
            return [], 0
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ bloqueo común
    def _consulta_bloqueada(self, cur, id_consulta_cab, id_medico_actor):
        """Bloquea la consulta y revalida: existe y está activa, el actor es su médico y está programada / en_proceso."""
        cur.execute("""SELECT cc.activo, cc.estado, cc.id_medico, cc.id_paciente, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad,
                              cc.fecha_cita, cc.hora_cita
                       FROM consultas_cab cc JOIN paciente p ON cc.id_paciente = p.id_paciente
                       WHERE cc.id_consulta_cab = %s FOR UPDATE OF cc""", (id_consulta_cab,))
        f = cur.fetchone()
        if not f or not f[0]:
            return None, {'error': 'CONSULTA_NO_ENCONTRADA'}
        _, estado, id_medico, id_paciente, paciente, cedula, fecha, hora = f
        if id_medico_actor is None or id_medico_actor != id_medico:
            return None, {'error': 'NO_ES_SU_MEDICO'}
        if estado not in ESTADOS_ABIERTOS:
            return None, {'error': 'CONSULTA_NO_ABIERTA', 'estado': estado}
        return {'estado': estado, 'id_medico': id_medico, 'id_paciente': id_paciente, 'paciente': paciente, 'cedula': cedula,
                'fecha': fecha, 'hora': hora}, None

    # ------------------------------------------------------------------ alta (con precarga)
    def crearOdontograma(self, id_consulta_cab, id_medico_actor):
        """
        Crea el odontograma de la consulta y le copia, en la misma transacción, los hallazgos activos del último odontograma vigente del paciente
        de una consulta anterior. Devuelve {'id_odontograma', 'precargado_de': {...}|None, 'contexto'} o {'error': CÓDIGO}.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            info, err = self._consulta_bloqueada(cur, id_consulta_cab, id_medico_actor)
            if err:
                con.rollback()
                return err
            cur.execute("SELECT 1 FROM odontograma WHERE id_consulta_cab = %s AND activo = true", (id_consulta_cab,))
            if cur.fetchone():
                con.rollback()
                return {'error': 'YA_EXISTE'}
            cur.execute("INSERT INTO odontograma(id_paciente, id_medico, id_consulta_cab, fecha_registro) VALUES (%s, %s, %s, NOW()) RETURNING id_odontograma",
                        (info['id_paciente'], info['id_medico'], id_consulta_cab))
            id_odo = cur.fetchone()[0]

            # el último vigente del paciente de una consulta ANTERIOR (no cancelada)
            cur.execute("""SELECT o.id_odontograma, o.id_consulta_cab
                           FROM odontograma o JOIN consultas_cab c ON c.id_consulta_cab = o.id_consulta_cab
                           WHERE o.id_paciente = %s AND o.activo = true AND c.activo = true AND c.estado <> 'cancelada'
                             AND o.id_consulta_cab <> %s AND (c.fecha_cita, c.hora_cita) < (%s, %s)
                           ORDER BY c.fecha_cita DESC, c.hora_cita DESC, o.id_odontograma DESC LIMIT 1""",
                        (info['id_paciente'], id_consulta_cab, info['fecha'], info['hora']))
            previo = cur.fetchone()
            precargado = None
            if previo:
                cur.execute("""INSERT INTO odontograma_detalle(id_odontograma, numero_diente, id_estado_dental, superficie, observacion)
                               SELECT %s, numero_diente, id_estado_dental, superficie, observacion FROM odontograma_detalle
                               WHERE id_odontograma = %s AND activo = true""", (id_odo, previo[0]))
                precargado = {'id_odontograma': previo[0], 'id_consulta_cab': previo[1], 'numero_consulta': numero_consulta(previo[1]), 'copiados': cur.rowcount}
            con.commit()
            return {'id_odontograma': id_odo, 'precargado_de': precargado, 'contexto': info}
        except psycopg2.errors.UniqueViolation:
            con.rollback()   # dos altas simultáneas: gana una
            return {'error': 'YA_EXISTE'}
        except Exception as e:
            app.logger.error(f"Error al crear el odontograma: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ hallazgos
    def _odontograma_de_consulta(self, cur, id_odontograma):
        cur.execute("SELECT id_consulta_cab FROM odontograma WHERE id_odontograma = %s AND activo = true", (id_odontograma,))
        r = cur.fetchone()
        return r[0] if r else None

    def agregarHallazgo(self, id_odontograma, numero_diente, superficie, id_estado_dental, observacion, id_medico_actor):
        """Agrega un hallazgo. `numero_diente` y `superficie` ya vienen validados. Devuelve {'id_odontograma_detalle', 'contexto'} o {'error'}."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            id_consulta = self._odontograma_de_consulta(cur, id_odontograma)
            if id_consulta is None:
                con.rollback()
                return {'error': 'ODONTOGRAMA_NO_ENCONTRADO'}
            info, err = self._consulta_bloqueada(cur, id_consulta, id_medico_actor)
            if err:
                con.rollback()
                return err
            cur.execute("SELECT 1 FROM odontograma WHERE id_odontograma = %s AND activo = true FOR UPDATE", (id_odontograma,))
            if not cur.fetchone():
                con.rollback()
                return {'error': 'ODONTOGRAMA_NO_ENCONTRADO'}
            cur.execute("SELECT descripcion, aplica_a, activo FROM estado_dental WHERE id_estado_dental = %s FOR SHARE", (id_estado_dental,))
            estado = cur.fetchone()
            if not estado:
                con.rollback()
                return {'error': 'ESTADO_NO_EXISTE'}
            descripcion, aplica_a, activo = estado
            if not activo:
                con.rollback()
                return {'error': 'ESTADO_INACTIVO', 'detalle': descripcion}
            if aplica_a == 'PIEZA' and superficie != 'T':
                con.rollback()
                return {'error': 'ESTADO_DE_PIEZA', 'detalle': descripcion}
            if aplica_a == 'SUPERFICIE' and superficie == 'T':
                con.rollback()
                return {'error': 'ESTADO_DE_SUPERFICIE', 'detalle': descripcion}
            cur.execute("""SELECT 1 FROM odontograma_detalle WHERE id_odontograma = %s AND numero_diente = %s AND superficie = %s
                           AND id_estado_dental = %s AND activo = true""", (id_odontograma, numero_diente, superficie, id_estado_dental))
            if cur.fetchone():
                con.rollback()
                return {'error': 'DUPLICADO', 'detalle': descripcion}
            cur.execute("""INSERT INTO odontograma_detalle(id_odontograma, numero_diente, id_estado_dental, superficie, observacion)
                           VALUES (%s, %s, %s, %s, %s) RETURNING id_odontograma_detalle""",
                        (id_odontograma, numero_diente, id_estado_dental, superficie, observacion))
            id_detalle = cur.fetchone()[0]
            cur.execute("UPDATE odontograma SET updated_at = NOW() WHERE id_odontograma = %s", (id_odontograma,))
            con.commit()
            return {'id_odontograma_detalle': id_detalle, 'id_consulta_cab': id_consulta, 'contexto': info}
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return {'error': 'DUPLICADO'}
        except Exception as e:
            app.logger.error(f"Error al agregar el hallazgo: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()

    def quitarHallazgo(self, id_detalle, id_medico_actor):
        """Quita un hallazgo (baja lógica del renglón). Devuelve {'ok', 'id_odontograma', 'id_consulta_cab', 'contexto'} o {'error'}."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""SELECT od.id_odontograma, o.id_consulta_cab FROM odontograma_detalle od JOIN odontograma o ON o.id_odontograma = od.id_odontograma
                           WHERE od.id_odontograma_detalle = %s AND od.activo = true AND o.activo = true""", (id_detalle,))
            f = cur.fetchone()
            if not f:
                con.rollback()
                return {'error': 'HALLAZGO_NO_ENCONTRADO'}
            id_odo, id_consulta = f
            info, err = self._consulta_bloqueada(cur, id_consulta, id_medico_actor)
            if err:
                con.rollback()
                return err
            cur.execute("SELECT 1 FROM odontograma WHERE id_odontograma = %s AND activo = true FOR UPDATE", (id_odo,))
            cur.execute("UPDATE odontograma_detalle SET activo = false WHERE id_odontograma_detalle = %s AND activo = true", (id_detalle,))
            if cur.rowcount == 0:
                con.rollback()
                return {'error': 'HALLAZGO_NO_ENCONTRADO'}
            cur.execute("UPDATE odontograma SET updated_at = NOW() WHERE id_odontograma = %s", (id_odo,))
            con.commit()
            return {'ok': True, 'id_odontograma': id_odo, 'id_consulta_cab': id_consulta, 'contexto': info}
        except Exception as e:
            app.logger.error(f"Error al quitar el hallazgo: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ anular
    def anularOdontograma(self, id_odontograma, id_medico_actor):
        """Anula el odontograma (definitivo). Sus hallazgos quedan como historial. Devuelve {'ok', 'id_consulta_cab', 'contexto'} o {'error'}."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            id_consulta = self._odontograma_de_consulta(cur, id_odontograma)
            if id_consulta is None:
                con.rollback()
                return {'error': 'ODONTOGRAMA_NO_ENCONTRADO'}
            info, err = self._consulta_bloqueada(cur, id_consulta, id_medico_actor)
            if err:
                con.rollback()
                return err
            cur.execute("UPDATE odontograma SET activo = false, updated_at = NOW() WHERE id_odontograma = %s AND activo = true", (id_odontograma,))
            if cur.rowcount == 0:
                con.rollback()
                return {'error': 'ODONTOGRAMA_NO_ENCONTRADO'}
            con.commit()
            return {'ok': True, 'id_consulta_cab': id_consulta, 'contexto': info}
        except Exception as e:
            app.logger.error(f"Error al anular el odontograma: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()
