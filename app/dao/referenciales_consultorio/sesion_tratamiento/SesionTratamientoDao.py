"""
=====================================================
DAO: Sesión de Tratamiento (Gestionar Procedimientos e Insumos Utilizados)
Tablas: sesiones_tratamiento + sesion_procedimientos (uno o más) + sesion_insumos (cero o más, con cantidad).

Reglas:
  - Cada sesión se registra DENTRO de una consulta (`id_consulta_cab`): puede ser posterior a la que creó el tratamiento, pero debe ser del MISMO paciente y
    del MISMO médico que el tratamiento. La registra SOLO el médico de esa consulta, con la consulta 'programada' o 'en_proceso', revalidado en la
    transacción con la consulta bloqueada (FOR UPDATE); después se bloquea el tratamiento (mismo orden que anular / finalizar / vender).
  - El tratamiento debe estar 'pendiente' o 'en_seguimiento'; la 1.ª sesión lo pasa a 'en_seguimiento'.
  - Procedimientos (al menos uno) e insumos (opcionales, sin repetir, cantidad 1–999): tipos ACTIVOS, bloqueados FOR SHARE en orden de id.
  - `numero_sesion` correlativo entre las vigentes. La fecha de la sesión la fija el servidor.
  - Anular (definitiva): solo la ÚLTIMA sesión vigente, desde su consulta abierta, médico de esa consulta; cascada a procedimientos e insumos. Si el
    tratamiento queda sin sesiones vuelve a 'pendiente'. Un tratamiento finalizado no admite cambios.
Dato de salud: la auditoría no recibe descripciones ni observaciones.
=====================================================
"""
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion
from app.dao.referenciales_consultorio.consulta.ConsultaDao import numero_consulta

ESTADOS_ABIERTOS = ('programada', 'en_proceso')

_SELECT = """
    SELECT s.id_sesion, s.id_tratamiento, s.id_consulta_cab, cc.estado, s.numero_sesion, s.fecha_sesion, s.descripcion_procedimiento, s.observaciones,
           s.proxima_cita, s.activo, s.fecha_registro, t.id_paciente, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad, t.id_medico, t.estado, tt.descripcion
    FROM sesiones_tratamiento s
    JOIN tratamientos t ON t.id_tratamiento = s.id_tratamiento
    JOIN consultas_cab cc ON cc.id_consulta_cab = s.id_consulta_cab
    JOIN paciente p ON p.id_paciente = t.id_paciente
    JOIN tipos_tratamiento tt ON tt.id_tipo_tratamiento = t.id_tipo_tratamiento"""


def _sesion(r, procedimientos, insumos):
    return {
        'id_sesion': r[0], 'id_tratamiento': r[1], 'id_consulta_cab': r[2], 'numero_consulta': numero_consulta(r[2]), 'estado_consulta': r[3],
        'numero_sesion': r[4], 'fecha_sesion': r[5].isoformat() if r[5] else None, 'descripcion_procedimiento': r[6], 'observaciones': r[7],
        'proxima_cita': r[8].isoformat() if r[8] else None, 'activo': r[9], 'fecha_registro': r[10].isoformat() if r[10] else None,
        'id_paciente': r[11], 'nombre_paciente': r[12], 'cedula_paciente': r[13], 'id_medico': r[14], 'estado_tratamiento': r[15], 'tipo_tratamiento': r[16],
        'procedimientos': procedimientos, 'insumos': insumos,
    }


class SesionTratamientoDao:

    # ------------------------------------------------------------------ lectura
    def _detalles(self, cur, ids):
        proc, ins = {}, {}
        if ids:
            cur.execute("""SELECT sp.id_sesion, tp.id_tipo_procedimiento, tp.descripcion FROM sesion_procedimientos sp
                           JOIN tipo_procedimiento_medico tp ON tp.id_tipo_procedimiento = sp.id_tipo_procedimiento
                           WHERE sp.id_sesion = ANY(%s) AND sp.activo = true ORDER BY tp.descripcion""", (list(ids),))
            for s, i, d in cur.fetchall():
                proc.setdefault(s, []).append({'id_tipo_procedimiento': i, 'descripcion': d})
            cur.execute("""SELECT si.id_sesion, si.id_sesion_insumo, i.id_insumo, i.descripcion, si.cantidad FROM sesion_insumos si
                           JOIN insumos i ON i.id_insumo = si.id_insumo WHERE si.id_sesion = ANY(%s) AND si.activo = true ORDER BY i.descripcion""", (list(ids),))
            for s, sid, i, d, c in cur.fetchall():
                ins.setdefault(s, []).append({'id_sesion_insumo': sid, 'id_insumo': i, 'descripcion_insumo': d, 'cantidad': c})
        return proc, ins

    def _leer(self, sql, params):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, params)
            filas = cur.fetchall()
            proc, ins = self._detalles(cur, [f[0] for f in filas])
            return [_sesion(f, proc.get(f[0], []), ins.get(f[0], [])) for f in filas]
        except Exception as e:
            app.logger.error(f"Error al leer sesiones de tratamiento: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getSesionesByTratamiento(self, id_tratamiento):
        """Las sesiones VIGENTES de un tratamiento (de la primera a la última), con sus procedimientos e insumos."""
        return self._leer(_SELECT + " WHERE s.id_tratamiento = %s AND s.activo = true ORDER BY s.numero_sesion", (id_tratamiento,))

    def getSesionById(self, id_sesion):
        filas = self._leer(_SELECT + " WHERE s.id_sesion = %s AND s.activo = true", (id_sesion,))
        return filas[0] if filas else None

    # ------------------------------------------------------------------ alta
    def guardarSesion(self, datos, id_medico_actor):
        """
        Crea la sesión con sus procedimientos e insumos en UNA transacción. `datos` ya viene validado (validar_sesion) y trae id_tratamiento e id_consulta_cab.
        Devuelve {'id_sesion', 'numero_sesion', 'contexto'} o {'error': CÓDIGO, ...}.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""SELECT cc.activo, cc.estado, cc.id_medico, cc.id_paciente, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad
                           FROM consultas_cab cc JOIN paciente p ON cc.id_paciente = p.id_paciente
                           WHERE cc.id_consulta_cab = %s FOR UPDATE OF cc""", (datos['id_consulta_cab'],))
            consulta = cur.fetchone()
            if not consulta or not consulta[0]:
                con.rollback()
                return {'error': 'CONSULTA_NO_ENCONTRADA'}
            _, estado, id_medico, id_paciente, paciente, cedula = consulta
            if id_medico_actor is None or id_medico_actor != id_medico:
                con.rollback()
                return {'error': 'NO_ES_SU_MEDICO'}
            if estado not in ESTADOS_ABIERTOS:
                con.rollback()
                return {'error': 'CONSULTA_NO_ABIERTA', 'estado': estado}
            cur.execute("""SELECT t.estado, t.id_paciente, t.id_medico, tt.descripcion FROM tratamientos t
                           JOIN tipos_tratamiento tt ON tt.id_tipo_tratamiento = t.id_tipo_tratamiento
                           WHERE t.id_tratamiento = %s FOR UPDATE OF t""", (datos['id_tratamiento'],))
            trat = cur.fetchone()
            if not trat or trat[0] == 'cancelado':
                con.rollback()
                return {'error': 'TRATAMIENTO_NO_ENCONTRADO'}
            if trat[1] != id_paciente or trat[2] != id_medico:
                con.rollback()
                return {'error': 'TRATAMIENTO_OTRA_CONSULTA'}
            if trat[0] not in ('pendiente', 'en_seguimiento'):
                con.rollback()
                return {'error': 'TRATAMIENTO_NO_ACTIVO', 'estado': trat[0]}
            # los tipos se bloquean FOR SHARE en orden de id (sin deadlocks): una baja concurrente espera a que esta sesión termine
            cur.execute("""SELECT id_tipo_procedimiento, descripcion, activo FROM tipo_procedimiento_medico
                           WHERE id_tipo_procedimiento = ANY(%s) ORDER BY id_tipo_procedimiento FOR SHARE""", (datos['procedimientos'],))
            filas = cur.fetchall()
            if len(filas) != len(datos['procedimientos']):
                con.rollback()
                return {'error': 'PROCEDIMIENTO_NO_EXISTE'}
            inactivos = [f[1] for f in filas if not f[2]]
            if inactivos:
                con.rollback()
                return {'error': 'PROCEDIMIENTO_INACTIVO', 'detalle': ', '.join(inactivos)}
            if datos['insumos']:
                ids = [i['id_insumo'] for i in datos['insumos']]
                cur.execute("SELECT id_insumo, descripcion, activo FROM insumos WHERE id_insumo = ANY(%s) ORDER BY id_insumo FOR SHARE", (ids,))
                filas = cur.fetchall()
                if len(filas) != len(ids):
                    con.rollback()
                    return {'error': 'INSUMO_NO_EXISTE'}
                inactivos = [f[1] for f in filas if not f[2]]
                if inactivos:
                    con.rollback()
                    return {'error': 'INSUMO_INACTIVO', 'detalle': ', '.join(inactivos)}
            cur.execute("SELECT COALESCE(MAX(numero_sesion), 0) + 1 FROM sesiones_tratamiento WHERE id_tratamiento = %s AND activo = true", (datos['id_tratamiento'],))
            numero = cur.fetchone()[0]
            cur.execute("""INSERT INTO sesiones_tratamiento(id_tratamiento, id_consulta_cab, numero_sesion, fecha_sesion, descripcion_procedimiento, observaciones, proxima_cita)
                           VALUES (%s, %s, %s, CURRENT_DATE, %s, %s, %s) RETURNING id_sesion""",
                        (datos['id_tratamiento'], datos['id_consulta_cab'], numero, datos['descripcion_procedimiento'], datos['observaciones'], datos['proxima_cita']))
            id_sesion = cur.fetchone()[0]
            for id_tipo in datos['procedimientos']:
                cur.execute("INSERT INTO sesion_procedimientos(id_sesion, id_tipo_procedimiento) VALUES (%s, %s)", (id_sesion, id_tipo))
            for item in datos['insumos']:
                cur.execute("INSERT INTO sesion_insumos(id_sesion, id_insumo, cantidad) VALUES (%s, %s, %s)", (id_sesion, item['id_insumo'], item['cantidad']))
            if trat[0] == 'pendiente':
                cur.execute("UPDATE tratamientos SET estado = 'en_seguimiento' WHERE id_tratamiento = %s", (datos['id_tratamiento'],))
            con.commit()
            return {'id_sesion': id_sesion, 'numero_sesion': numero,
                    'contexto': {'paciente': paciente, 'cedula': cedula, 'tipo': trat[3], 'pasa_a_seguimiento': trat[0] == 'pendiente'}}
        except psycopg2.errors.CheckViolation as e:
            app.logger.error(f"Datos de sesión rechazados por la base: {str(e)}")
            con.rollback()
            return {'error': 'DATOS_INVALIDOS'}
        except Exception as e:
            app.logger.error(f"Error al guardar sesión de tratamiento: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ anulación
    def anularSesion(self, id_sesion, id_medico_actor):
        """
        Anula (baja lógica definitiva) la sesión, con cascada a sus procedimientos e insumos. Bloquea la consulta de la sesión, el tratamiento y la sesión.
        Solo la última vigente, desde su consulta abierta y por el médico de esa consulta; un tratamiento finalizado no admite cambios.
        Devuelve {'ok', 'numero_sesion', 'id_consulta_cab', 'vuelve_a_pendiente', 'contexto'} o {'error': CÓDIGO, ...}.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_consulta_cab, id_tratamiento FROM sesiones_tratamiento WHERE id_sesion = %s AND activo = true", (id_sesion,))
            fila = cur.fetchone()
            if not fila:
                con.rollback()
                return {'error': 'SESION_NO_ENCONTRADA'}
            id_consulta, id_tratamiento = fila
            cur.execute("""SELECT cc.estado, cc.id_medico, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad
                           FROM consultas_cab cc JOIN paciente p ON cc.id_paciente = p.id_paciente
                           WHERE cc.id_consulta_cab = %s FOR UPDATE OF cc""", (id_consulta,))
            estado, id_medico, paciente, cedula = cur.fetchone()
            cur.execute("""SELECT t.estado, tt.descripcion FROM tratamientos t JOIN tipos_tratamiento tt ON tt.id_tipo_tratamiento = t.id_tipo_tratamiento
                           WHERE t.id_tratamiento = %s FOR UPDATE OF t""", (id_tratamiento,))
            trat = cur.fetchone()
            cur.execute("SELECT numero_sesion FROM sesiones_tratamiento WHERE id_sesion = %s AND activo = true FOR UPDATE", (id_sesion,))
            sesion = cur.fetchone()
            if not sesion:
                con.rollback()
                return {'error': 'SESION_NO_ENCONTRADA'}
            if id_medico_actor is None or id_medico_actor != id_medico:
                con.rollback()
                return {'error': 'NO_ES_SU_MEDICO'}
            if estado not in ESTADOS_ABIERTOS:
                con.rollback()
                return {'error': 'CONSULTA_NO_ABIERTA', 'estado': estado}
            if trat[0] == 'finalizado':
                con.rollback()
                return {'error': 'TRATAMIENTO_FINALIZADO'}
            cur.execute("SELECT MAX(numero_sesion) FROM sesiones_tratamiento WHERE id_tratamiento = %s AND activo = true", (id_tratamiento,))
            if cur.fetchone()[0] != sesion[0]:
                con.rollback()
                return {'error': 'NO_ES_ULTIMA'}
            cur.execute("UPDATE sesiones_tratamiento SET activo = false WHERE id_sesion = %s", (id_sesion,))
            cur.execute("UPDATE sesion_procedimientos SET activo = false WHERE id_sesion = %s AND activo = true", (id_sesion,))
            cur.execute("UPDATE sesion_insumos SET activo = false WHERE id_sesion = %s AND activo = true", (id_sesion,))
            cur.execute("SELECT 1 FROM sesiones_tratamiento WHERE id_tratamiento = %s AND activo = true LIMIT 1", (id_tratamiento,))
            vuelve = cur.fetchone() is None and trat[0] == 'en_seguimiento'
            if vuelve:
                cur.execute("UPDATE tratamientos SET estado = 'pendiente' WHERE id_tratamiento = %s", (id_tratamiento,))
            con.commit()
            return {'ok': True, 'numero_sesion': sesion[0], 'id_consulta_cab': id_consulta, 'id_tratamiento': id_tratamiento, 'vuelve_a_pendiente': vuelve,
                    'contexto': {'paciente': paciente, 'cedula': cedula, 'tipo': trat[1]}}
        except Exception as e:
            app.logger.error(f"Error al anular sesión de tratamiento: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()
