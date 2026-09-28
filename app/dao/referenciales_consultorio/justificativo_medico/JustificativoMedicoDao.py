"""
=====================================================
DAO: Justificativo Médico (Generar Justificativo Médico)
Descripción: Justificativos médicos de una Consulta (días de reposo +
recomendaciones). Vinculación opcional SOLO a Diagnóstico (sin
Tratamiento). El propio `estado` hace de baja lógica (`anulado`), sin
columna `activo` separada.
=====================================================
"""
from flask import current_app as app
from app.conexion.Conexion import Conexion


class JustificativoMedicoDao:

    def getJustificativos(self):
        """Obtiene todos los justificativos activos, con datos de paciente y médico."""
        sql = """
        SELECT
            j.id_justificativo,
            j.id_consulta_cab,
            cc.id_paciente,
            (p.nombre || ' ' || p.apellido) AS nombre_paciente,
            cc.id_medico,
            (m.nombre || ' ' || m.apellido) AS nombre_medico,
            j.id_diagnostico,
            j.dias_reposo,
            j.recomendaciones,
            j.fecha_justificativo,
            j.estado,
            j.fecha_registro
        FROM justificativo_medico j
        JOIN consultas_cab cc ON j.id_consulta_cab = cc.id_consulta_cab
        JOIN paciente p ON cc.id_paciente = p.id_paciente
        JOIN medico m ON cc.id_medico = m.id_medico
        WHERE j.estado = 'activo'
        ORDER BY j.fecha_justificativo DESC, j.id_justificativo DESC
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            return [{
                'id_justificativo': r[0],
                'id_consulta_cab': r[1],
                'id_paciente': r[2],
                'nombre_paciente': r[3],
                'id_medico': r[4],
                'nombre_medico': r[5],
                'id_diagnostico': r[6],
                'dias_reposo': r[7],
                'recomendaciones': r[8],
                'fecha_justificativo': str(r[9]) if r[9] else None,
                'estado': r[10],
                'fecha_registro': str(r[11]) if r[11] else None
            } for r in rows]
        except Exception as e:
            app.logger.error(f"Error al obtener justificativos médicos: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getJustificativoById(self, id_justificativo):
        """
        Obtiene un justificativo por ID (sin filtrar por estado), con datos
        completos de paciente/médico (cédulas incluidas, para el PDF).
        """
        sql = """
        SELECT
            j.id_justificativo,
            j.id_consulta_cab,
            cc.id_paciente,
            (p.nombre || ' ' || p.apellido) AS nombre_paciente,
            p.cedula_entidad AS cedula_paciente,
            cc.id_medico,
            (m.nombre || ' ' || m.apellido) AS nombre_medico,
            m.cedula AS cedula_medico,
            j.id_diagnostico,
            j.dias_reposo,
            j.recomendaciones,
            j.fecha_justificativo,
            j.estado,
            j.fecha_registro
        FROM justificativo_medico j
        JOIN consultas_cab cc ON j.id_consulta_cab = cc.id_consulta_cab
        JOIN paciente p ON cc.id_paciente = p.id_paciente
        JOIN medico m ON cc.id_medico = m.id_medico
        WHERE j.id_justificativo = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_justificativo,))
            r = cur.fetchone()
            if not r:
                return None
            return {
                'id_justificativo': r[0],
                'id_consulta_cab': r[1],
                'id_paciente': r[2],
                'nombre_paciente': r[3],
                'cedula_paciente': r[4],
                'id_medico': r[5],
                'nombre_medico': r[6],
                'cedula_medico': r[7],
                'id_diagnostico': r[8],
                'dias_reposo': r[9],
                'recomendaciones': r[10],
                'fecha_justificativo': str(r[11]) if r[11] else None,
                'estado': r[12],
                'fecha_registro': str(r[13]) if r[13] else None
            }
        except Exception as e:
            app.logger.error(f"Error al obtener justificativo médico: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def guardarJustificativo(self, datos):
        """
        Registra un nuevo justificativo médico, a partir de una Consulta
        activa (programada/en_proceso). id_diagnostico es opcional; si
        viene, debe pertenecer a esa misma consulta.

        Retorna un dict:
          {'id_justificativo': N}  en éxito
          {'error': 'CONSULTA_NO_ENCONTRADA' | 'CONSULTA_NO_ACTIVA' |
                     'DIAGNOSTICO_INVALIDO' | 'ERROR_INTERNO'}
        """
        id_consulta_cab = datos.get('id_consulta_cab')
        id_diagnostico = datos.get('id_diagnostico')

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

            cur.execute("""
                INSERT INTO justificativo_medico(
                    id_consulta_cab, id_diagnostico, dias_reposo, recomendaciones, fecha_justificativo
                ) VALUES (%s, %s, %s, %s, COALESCE(%s, CURRENT_DATE))
                RETURNING id_justificativo
            """, (
                id_consulta_cab, id_diagnostico, datos.get('dias_reposo'),
                datos.get('recomendaciones'), datos.get('fecha_justificativo')
            ))
            id_justificativo = cur.fetchone()[0]
            con.commit()
            return {'id_justificativo': id_justificativo}

        except Exception as e:
            app.logger.error(f"Error al guardar justificativo médico: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}

        finally:
            cur.close()
            con.close()

    def anularJustificativo(self, id_justificativo):
        """
        Anula un justificativo médico (estado = 'anulado'). Bloquea solo si
        ya estaba anulado (sin chequeo de estado de la consulta).

        Returns:
            bool | str: True si se anuló, False si no existía,
            "YA_ANULADO" si ya estaba anulado.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute("SELECT estado FROM justificativo_medico WHERE id_justificativo = %s", (id_justificativo,))
            row = cur.fetchone()

            if not row:
                return False

            if row[0] == 'anulado':
                return "YA_ANULADO"

            cur.execute("UPDATE justificativo_medico SET estado = 'anulado' WHERE id_justificativo = %s", (id_justificativo,))
            con.commit()
            return True

        except Exception as e:
            app.logger.error(f"Error al anular justificativo médico: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()
