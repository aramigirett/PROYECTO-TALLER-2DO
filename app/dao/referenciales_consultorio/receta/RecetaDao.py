"""
=====================================================
DAO: Receta (Generar Recetas e Indicaciones)
Descripción: Recetas médicas de una Consulta, con sus medicamentos.
=====================================================
"""
from flask import current_app as app
from app.conexion.Conexion import Conexion


class RecetaDao:

    def getRecetas(self):
        """
        Obtiene todas las recetas activas, con datos de paciente y médico
        de la consulta a la que pertenecen.
        """
        sql = """
        SELECT
            r.id_receta,
            r.id_consulta_cab,
            cc.id_paciente,
            (p.nombre || ' ' || p.apellido) AS nombre_paciente,
            cc.id_medico,
            (m.nombre || ' ' || m.apellido) AS nombre_medico,
            r.id_diagnostico,
            r.id_tratamiento,
            r.indicaciones_generales,
            r.fecha_receta,
            r.fecha_registro
        FROM recetas r
        JOIN consultas_cab cc ON r.id_consulta_cab = cc.id_consulta_cab
        JOIN paciente p ON cc.id_paciente = p.id_paciente
        JOIN medico m ON cc.id_medico = m.id_medico
        WHERE r.activo = true
        ORDER BY r.fecha_receta DESC, r.id_receta DESC
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            return [{
                'id_receta': r[0],
                'id_consulta_cab': r[1],
                'id_paciente': r[2],
                'nombre_paciente': r[3],
                'id_medico': r[4],
                'nombre_medico': r[5],
                'id_diagnostico': r[6],
                'id_tratamiento': r[7],
                'indicaciones_generales': r[8],
                'fecha_receta': str(r[9]) if r[9] else None,
                'fecha_registro': str(r[10]) if r[10] else None
            } for r in rows]
        except Exception as e:
            app.logger.error(f"Error al obtener recetas: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def _getMedicamentosByReceta(self, cur, id_receta):
        """Helper interno: lista de medicamentos activos de una receta, usando el cursor ya abierto."""
        cur.execute("""
            SELECT rm.id_receta_medicamento, rm.id_medicamento, med.nombre_comercial,
                   rm.dosis, rm.frecuencia, rm.duracion
            FROM receta_medicamento rm
            JOIN medicamentos med ON rm.id_medicamento = med.id_medicamento
            WHERE rm.id_receta = %s AND rm.activo = true
            ORDER BY rm.id_receta_medicamento ASC
        """, (id_receta,))
        return [{
            'id_receta_medicamento': m[0],
            'id_medicamento': m[1],
            'nombre_comercial': m[2],
            'dosis': m[3],
            'frecuencia': m[4],
            'duracion': m[5]
        } for m in cur.fetchall()]

    def getRecetaById(self, id_receta):
        """Obtiene el detalle completo de una receta (para el botón Ver), con sus medicamentos."""
        sql = """
        SELECT
            r.id_receta,
            r.id_consulta_cab,
            cc.id_paciente,
            (p.nombre || ' ' || p.apellido) AS nombre_paciente,
            cc.id_medico,
            (m.nombre || ' ' || m.apellido) AS nombre_medico,
            r.id_diagnostico,
            r.id_tratamiento,
            r.indicaciones_generales,
            r.fecha_receta,
            r.activo,
            r.fecha_registro
        FROM recetas r
        JOIN consultas_cab cc ON r.id_consulta_cab = cc.id_consulta_cab
        JOIN paciente p ON cc.id_paciente = p.id_paciente
        JOIN medico m ON cc.id_medico = m.id_medico
        WHERE r.id_receta = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_receta,))
            r = cur.fetchone()
            if not r:
                return None
            return {
                'id_receta': r[0],
                'id_consulta_cab': r[1],
                'id_paciente': r[2],
                'nombre_paciente': r[3],
                'id_medico': r[4],
                'nombre_medico': r[5],
                'id_diagnostico': r[6],
                'id_tratamiento': r[7],
                'indicaciones_generales': r[8],
                'fecha_receta': str(r[9]) if r[9] else None,
                'activo': r[10],
                'fecha_registro': str(r[11]) if r[11] else None,
                'medicamentos': self._getMedicamentosByReceta(cur, r[0])
            }
        except Exception as e:
            app.logger.error(f"Error al obtener receta: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def guardarReceta(self, datos):
        """
        Registra una nueva receta con sus medicamentos, a partir de una
        Consulta activa (programada/en_proceso). id_diagnostico e
        id_tratamiento son opcionales; si vienen, deben pertenecer a esa
        misma consulta.

        Retorna un dict:
          {'id_receta': N}  en éxito
          {'error': 'CONSULTA_NO_ENCONTRADA' | 'CONSULTA_NO_ACTIVA' |
                     'DIAGNOSTICO_INVALIDO' | 'TRATAMIENTO_INVALIDO' |
                     'SIN_MEDICAMENTOS' | 'ERROR_INTERNO'}
        """
        id_consulta_cab = datos.get('id_consulta_cab')
        id_diagnostico = datos.get('id_diagnostico')
        id_tratamiento = datos.get('id_tratamiento')
        medicamentos = datos.get('medicamentos') or []

        if not medicamentos:
            return {'error': 'SIN_MEDICAMENTOS'}

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute("""
                SELECT estado, activo FROM consultas_cab WHERE id_consulta_cab = %s
            """, (id_consulta_cab,))
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
                    WHERE d.id_diagnostico = %s AND d.id_consulta_cab = %s AND d.activo = true
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
                INSERT INTO recetas(
                    id_consulta_cab, id_diagnostico, id_tratamiento,
                    indicaciones_generales, fecha_receta
                ) VALUES (%s, %s, %s, %s, COALESCE(%s, CURRENT_DATE))
                RETURNING id_receta
            """, (
                id_consulta_cab, id_diagnostico, id_tratamiento,
                datos.get('indicaciones_generales'), datos.get('fecha_receta')
            ))
            id_receta = cur.fetchone()[0]

            for med in medicamentos:
                cur.execute("""
                    INSERT INTO receta_medicamento(id_receta, id_medicamento, dosis, frecuencia, duracion)
                    VALUES (%s, %s, %s, %s, %s)
                """, (id_receta, med.get('id_medicamento'), med.get('dosis'), med.get('frecuencia'), med.get('duracion')))

            con.commit()
            return {'id_receta': id_receta}

        except Exception as e:
            app.logger.error(f"Error al guardar receta: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}

        finally:
            cur.close()
            con.close()

    def deleteReceta(self, id_receta):
        """
        Anula (baja lógica) una receta, bloqueando si la consulta a la que
        pertenece ya está finalizada. Cascada de baja lógica a sus
        medicamentos.

        Returns:
            bool | str: True si se anuló, False si no existía,
            "CONSULTA_FINALIZADA" si la consulta asociada ya está finalizada.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM recetas r
                    JOIN consultas_cab cc ON r.id_consulta_cab = cc.id_consulta_cab
                    WHERE r.id_receta = %s AND cc.estado = 'finalizada'
                )
            """, (id_receta,))
            consulta_finalizada = cur.fetchone()[0]

            if consulta_finalizada:
                app.logger.warning(f"No se puede anular receta {id_receta}: la consulta asociada está finalizada")
                return "CONSULTA_FINALIZADA"

            cur.execute("UPDATE recetas SET activo = false WHERE id_receta = %s AND activo = true", (id_receta,))
            rows_affected = cur.rowcount

            if rows_affected:
                cur.execute("UPDATE receta_medicamento SET activo = false WHERE id_receta = %s", (id_receta,))

            con.commit()
            return rows_affected > 0

        except Exception as e:
            app.logger.error(f"Error al anular receta: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()
