"""
=====================================================
DAO: Sesión de Tratamiento (Gestionar Procedimientos e Insumos Utilizados)
Descripción: Sesiones clínicas de un Tratamiento, con sus insumos utilizados.
=====================================================
"""
from flask import current_app as app
from app.conexion.Conexion import Conexion


class SesionTratamientoDao:

    def getSesionesByTratamiento(self, id_tratamiento):
        """
        Obtiene las sesiones activas de un tratamiento, cada una con su
        lista de insumos activos.
        """
        sql = """
        SELECT
            s.id_sesion,
            s.id_tratamiento,
            s.numero_sesion,
            s.id_tipo_procedimiento,
            tp.descripcion AS tipo_procedimiento,
            s.fecha_sesion,
            s.descripcion_procedimiento,
            s.observaciones,
            s.proxima_cita,
            s.fecha_registro
        FROM sesiones_tratamiento s
        JOIN tipo_procedimiento_medico tp ON s.id_tipo_procedimiento = tp.id_tipo_procedimiento
        WHERE s.id_tratamiento = %s AND s.activo = true
        ORDER BY s.numero_sesion ASC
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_tratamiento,))
            rows = cur.fetchall()
            sesiones = [{
                'id_sesion': r[0],
                'id_tratamiento': r[1],
                'numero_sesion': r[2],
                'id_tipo_procedimiento': r[3],
                'tipo_procedimiento': r[4],
                'fecha_sesion': str(r[5]) if r[5] else None,
                'descripcion_procedimiento': r[6],
                'observaciones': r[7],
                'proxima_cita': str(r[8]) if r[8] else None,
                'fecha_registro': str(r[9]) if r[9] else None,
                'insumos': self._getInsumosBySesion(cur, r[0])
            } for r in rows]
            return sesiones
        except Exception as e:
            app.logger.error(f"Error al obtener sesiones de tratamiento: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def _getInsumosBySesion(self, cur, id_sesion):
        """Helper interno: lista de insumos activos de una sesión, usando el cursor ya abierto."""
        cur.execute("""
            SELECT si.id_sesion_insumo, si.id_insumo, i.descripcion, si.cantidad
            FROM sesion_insumos si
            JOIN insumos i ON si.id_insumo = i.id_insumo
            WHERE si.id_sesion = %s AND si.activo = true
            ORDER BY si.id_sesion_insumo ASC
        """, (id_sesion,))
        return [{
            'id_sesion_insumo': i[0],
            'id_insumo': i[1],
            'descripcion_insumo': i[2],
            'cantidad': i[3]
        } for i in cur.fetchall()]

    def getSesionById(self, id_sesion):
        """Obtiene el detalle completo de una sesión (para el botón Ver)."""
        sql = """
        SELECT
            s.id_sesion,
            s.id_tratamiento,
            s.numero_sesion,
            s.id_tipo_procedimiento,
            tp.descripcion AS tipo_procedimiento,
            s.fecha_sesion,
            s.descripcion_procedimiento,
            s.observaciones,
            s.proxima_cita,
            s.activo,
            s.fecha_registro
        FROM sesiones_tratamiento s
        JOIN tipo_procedimiento_medico tp ON s.id_tipo_procedimiento = tp.id_tipo_procedimiento
        WHERE s.id_sesion = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_sesion,))
            r = cur.fetchone()
            if not r:
                return None
            return {
                'id_sesion': r[0],
                'id_tratamiento': r[1],
                'numero_sesion': r[2],
                'id_tipo_procedimiento': r[3],
                'tipo_procedimiento': r[4],
                'fecha_sesion': str(r[5]) if r[5] else None,
                'descripcion_procedimiento': r[6],
                'observaciones': r[7],
                'proxima_cita': str(r[8]) if r[8] else None,
                'activo': r[9],
                'fecha_registro': str(r[10]) if r[10] else None,
                'insumos': self._getInsumosBySesion(cur, r[0])
            }
        except Exception as e:
            app.logger.error(f"Error al obtener sesión: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def guardarSesion(self, datos):
        """
        Registra una nueva sesión de tratamiento con sus insumos.

        Valida que el tratamiento exista y esté en estado 'pendiente' o
        'en_seguimiento'; calcula numero_sesion correlativo (reutilizando
        números liberados por sesiones anuladas); inserta la sesión y sus
        insumos; si el tratamiento estaba 'pendiente', lo pasa a
        'en_seguimiento'. Todo en una sola transacción.

        Retorna un dict:
          {'id_sesion': N}  en éxito
          {'error': 'TRATAMIENTO_NO_ENCONTRADO' | 'TRATAMIENTO_NO_ACTIVO' |
                     'SIN_INSUMOS' | 'ERROR_INTERNO'}
        """
        id_tratamiento = datos.get('id_tratamiento')
        insumos = datos.get('insumos') or []

        if not insumos:
            return {'error': 'SIN_INSUMOS'}

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute("SELECT estado FROM tratamientos WHERE id_tratamiento = %s FOR UPDATE", (id_tratamiento,))
            tratamiento = cur.fetchone()

            if not tratamiento:
                return {'error': 'TRATAMIENTO_NO_ENCONTRADO'}

            estado_tratamiento = tratamiento[0]
            if estado_tratamiento not in ('pendiente', 'en_seguimiento'):
                return {'error': 'TRATAMIENTO_NO_ACTIVO'}

            cur.execute("""
                SELECT COALESCE(MAX(numero_sesion), 0) + 1
                FROM sesiones_tratamiento
                WHERE id_tratamiento = %s AND activo = true
            """, (id_tratamiento,))
            numero_sesion = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO sesiones_tratamiento(
                    id_tratamiento, numero_sesion, id_tipo_procedimiento,
                    fecha_sesion, descripcion_procedimiento, observaciones, proxima_cita
                ) VALUES (%s, %s, %s, COALESCE(%s, CURRENT_DATE), %s, %s, %s)
                RETURNING id_sesion
            """, (
                id_tratamiento, numero_sesion, datos.get('id_tipo_procedimiento'),
                datos.get('fecha_sesion'), datos.get('descripcion_procedimiento'),
                datos.get('observaciones'), datos.get('proxima_cita')
            ))
            id_sesion = cur.fetchone()[0]

            for insumo in insumos:
                cur.execute("""
                    INSERT INTO sesion_insumos(id_sesion, id_insumo, cantidad)
                    VALUES (%s, %s, %s)
                """, (id_sesion, insumo.get('id_insumo'), insumo.get('cantidad')))

            if estado_tratamiento == 'pendiente':
                cur.execute("UPDATE tratamientos SET estado = 'en_seguimiento' WHERE id_tratamiento = %s", (id_tratamiento,))

            con.commit()
            return {'id_sesion': id_sesion}

        except Exception as e:
            app.logger.error(f"Error al guardar sesión de tratamiento: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}

        finally:
            cur.close()
            con.close()

    def anularSesion(self, id_sesion):
        """
        Anula (baja lógica) una sesión, solo si es la más reciente (numero_sesion
        más alto activo) de su tratamiento. Cascada de baja lógica a sus insumos.

        Returns:
            bool | str: True si se anuló, False si no existía o ya estaba
            anulada, "NO_ES_ULTIMA" si no es la sesión más reciente activa.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute("""
                SELECT id_tratamiento, numero_sesion
                FROM sesiones_tratamiento
                WHERE id_sesion = %s AND activo = true
            """, (id_sesion,))
            sesion = cur.fetchone()

            if not sesion:
                return False

            id_tratamiento, numero_sesion = sesion

            cur.execute("""
                SELECT MAX(numero_sesion) FROM sesiones_tratamiento
                WHERE id_tratamiento = %s AND activo = true
            """, (id_tratamiento,))
            max_numero = cur.fetchone()[0]

            if numero_sesion != max_numero:
                return "NO_ES_ULTIMA"

            cur.execute("UPDATE sesiones_tratamiento SET activo = false WHERE id_sesion = %s", (id_sesion,))
            cur.execute("UPDATE sesion_insumos SET activo = false WHERE id_sesion = %s", (id_sesion,))
            con.commit()
            return True

        except Exception as e:
            app.logger.error(f"Error al anular sesión de tratamiento: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()
