"""
=====================================================
DAO: Orden de Análisis (Generar Orden de Análisis)
Descripción: Órdenes de análisis de una Consulta. Un solo Tipo de Análisis
por orden (no es cabecera+detalle). El propio `estado` hace de baja
lógica (`cancelado`), sin columna `activo` separada.
=====================================================
"""
from flask import current_app as app
from app.conexion.Conexion import Conexion

# Secuencia estricta de avance para "Actualizar Estado": no se puede saltar
# pasos ni retroceder. 'completado' y 'cancelado' son estados terminales.
SIGUIENTE_ESTADO = {
    'pendiente': 'enviado',
    'enviado': 'en_proceso',
    'en_proceso': 'completado',
}


class OrdenAnalisisDao:

    def getOrdenes(self):
        """Obtiene todas las órdenes de análisis no canceladas."""
        sql = """
        SELECT
            o.id_orden_analisis,
            o.id_consulta_cab,
            cc.id_paciente,
            (p.nombre || ' ' || p.apellido) AS nombre_paciente,
            cc.id_medico,
            (m.nombre || ' ' || m.apellido) AS nombre_medico,
            o.id_diagnostico,
            o.id_tratamiento,
            o.id_tipo_analisis,
            ta.descripcion AS tipo_analisis,
            o.motivo_orden,
            o.indicaciones,
            o.fecha_orden,
            o.estado,
            o.fecha_registro
        FROM orden_analisis o
        JOIN consultas_cab cc ON o.id_consulta_cab = cc.id_consulta_cab
        JOIN paciente p ON cc.id_paciente = p.id_paciente
        JOIN medico m ON cc.id_medico = m.id_medico
        JOIN tipo_analisis ta ON o.id_tipo_analisis = ta.id_tipo_analisis
        WHERE o.estado <> 'cancelado'
        ORDER BY o.fecha_orden DESC, o.id_orden_analisis DESC
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            return [{
                'id_orden_analisis': r[0],
                'id_consulta_cab': r[1],
                'id_paciente': r[2],
                'nombre_paciente': r[3],
                'id_medico': r[4],
                'nombre_medico': r[5],
                'id_diagnostico': r[6],
                'id_tratamiento': r[7],
                'id_tipo_analisis': r[8],
                'tipo_analisis': r[9],
                'motivo_orden': r[10],
                'indicaciones': r[11],
                'fecha_orden': str(r[12]) if r[12] else None,
                'estado': r[13],
                'fecha_registro': str(r[14]) if r[14] else None
            } for r in rows]
        except Exception as e:
            app.logger.error(f"Error al obtener órdenes de análisis: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getOrdenById(self, id_orden_analisis):
        """Obtiene una orden de análisis por ID (sin filtrar por estado)."""
        sql = """
        SELECT
            o.id_orden_analisis,
            o.id_consulta_cab,
            cc.id_paciente,
            (p.nombre || ' ' || p.apellido) AS nombre_paciente,
            cc.id_medico,
            (m.nombre || ' ' || m.apellido) AS nombre_medico,
            o.id_diagnostico,
            o.id_tratamiento,
            o.id_tipo_analisis,
            ta.descripcion AS tipo_analisis,
            o.motivo_orden,
            o.indicaciones,
            o.fecha_orden,
            o.estado,
            o.fecha_registro
        FROM orden_analisis o
        JOIN consultas_cab cc ON o.id_consulta_cab = cc.id_consulta_cab
        JOIN paciente p ON cc.id_paciente = p.id_paciente
        JOIN medico m ON cc.id_medico = m.id_medico
        JOIN tipo_analisis ta ON o.id_tipo_analisis = ta.id_tipo_analisis
        WHERE o.id_orden_analisis = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_orden_analisis,))
            r = cur.fetchone()
            if not r:
                return None
            return {
                'id_orden_analisis': r[0],
                'id_consulta_cab': r[1],
                'id_paciente': r[2],
                'nombre_paciente': r[3],
                'id_medico': r[4],
                'nombre_medico': r[5],
                'id_diagnostico': r[6],
                'id_tratamiento': r[7],
                'id_tipo_analisis': r[8],
                'tipo_analisis': r[9],
                'motivo_orden': r[10],
                'indicaciones': r[11],
                'fecha_orden': str(r[12]) if r[12] else None,
                'estado': r[13],
                'fecha_registro': str(r[14]) if r[14] else None
            }
        except Exception as e:
            app.logger.error(f"Error al obtener orden de análisis: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def guardarOrden(self, datos):
        """
        Registra una nueva orden de análisis, a partir de una Consulta activa
        (programada/en_proceso). id_diagnostico e id_tratamiento son
        opcionales; si vienen, deben pertenecer a esa misma consulta.

        Retorna un dict:
          {'id_orden_analisis': N}  en éxito
          {'error': 'CONSULTA_NO_ENCONTRADA' | 'CONSULTA_NO_ACTIVA' |
                     'DIAGNOSTICO_INVALIDO' | 'TRATAMIENTO_INVALIDO' |
                     'ERROR_INTERNO'}
        """
        id_consulta_cab = datos.get('id_consulta_cab')
        id_diagnostico = datos.get('id_diagnostico')
        id_tratamiento = datos.get('id_tratamiento')

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute("SELECT estado, activo FROM consultas_cab WHERE id_consulta_cab = %s", (id_consulta_cab,))
            consulta = cur.fetchone()

            if not consulta:
                return {'error': 'CONSULTA_NO_ENCONTRADA'}

            estado_consulta, activo_consulta = consulta
            if not activo_consulta or estado_consulta not in ('programada', 'en_proceso'):
                return {'error': 'CONSULTA_NO_ACTIVA'}

            if id_diagnostico:
                cur.execute("""
                    SELECT 1
                    FROM diagnosticos d
                    JOIN consultas_detalle cd ON d.id_consulta_detalle = cd.id_consulta_detalle
                    WHERE d.id_diagnostico = %s AND cd.id_consulta_cab = %s AND d.activo = true
                """, (id_diagnostico, id_consulta_cab))
                if not cur.fetchone():
                    return {'error': 'DIAGNOSTICO_INVALIDO'}

            if id_tratamiento:
                cur.execute("""
                    SELECT 1 FROM tratamientos
                    WHERE id_tratamiento = %s AND id_consulta_cab = %s
                """, (id_tratamiento, id_consulta_cab))
                if not cur.fetchone():
                    return {'error': 'TRATAMIENTO_INVALIDO'}

            cur.execute("""
                INSERT INTO orden_analisis(
                    id_consulta_cab, id_diagnostico, id_tratamiento, id_tipo_analisis,
                    motivo_orden, indicaciones, fecha_orden
                ) VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s, CURRENT_DATE))
                RETURNING id_orden_analisis
            """, (
                id_consulta_cab, id_diagnostico, id_tratamiento, datos.get('id_tipo_analisis'),
                datos.get('motivo_orden'), datos.get('indicaciones'), datos.get('fecha_orden')
            ))
            id_orden = cur.fetchone()[0]
            con.commit()
            return {'id_orden_analisis': id_orden}

        except Exception as e:
            app.logger.error(f"Error al guardar orden de análisis: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}

        finally:
            cur.close()
            con.close()

    def actualizarEstado(self, id_orden_analisis):
        """
        Avanza la orden al siguiente estado de la secuencia estricta
        pendiente -> enviado -> en_proceso -> completado. No acepta un
        estado arbitrario: el sistema calcula el siguiente paso.

        Returns:
            str | bool | None: el nuevo estado si avanzó, "YA_COMPLETADO"
            si ya estaba en 'completado', "CANCELADO" si estaba cancelada,
            False si no existía.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute("SELECT estado FROM orden_analisis WHERE id_orden_analisis = %s", (id_orden_analisis,))
            row = cur.fetchone()

            if not row:
                return False

            estado_actual = row[0]

            if estado_actual == 'completado':
                return "YA_COMPLETADO"

            if estado_actual == 'cancelado':
                return "CANCELADO"

            nuevo_estado = SIGUIENTE_ESTADO[estado_actual]
            cur.execute("UPDATE orden_analisis SET estado = %s WHERE id_orden_analisis = %s", (nuevo_estado, id_orden_analisis))
            con.commit()
            return nuevo_estado

        except Exception as e:
            app.logger.error(f"Error al actualizar estado de orden de análisis: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def anularOrden(self, id_orden_analisis):
        """
        Anula una orden de análisis (estado = 'cancelado'). Bloquea si ya
        está 'completado' o 'cancelado'.

        Returns:
            bool | str: True si se anuló, False si no existía,
            "YA_CERRADO" si ya estaba completado o cancelado.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute("SELECT estado FROM orden_analisis WHERE id_orden_analisis = %s", (id_orden_analisis,))
            row = cur.fetchone()

            if not row:
                return False

            if row[0] in ('completado', 'cancelado'):
                return "YA_CERRADO"

            cur.execute("UPDATE orden_analisis SET estado = 'cancelado' WHERE id_orden_analisis = %s", (id_orden_analisis,))
            con.commit()
            return True

        except Exception as e:
            app.logger.error(f"Error al anular orden de análisis: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()
