"""
=====================================================
DAO: Consulta Médica
Descripción: Manejo de consultas_cab (cabecera de consultas)
=====================================================
"""

from flask import current_app as app
from app.conexion.Conexion import Conexion

class ConsultaDao:

    def getConsultas(self):
        """
        Obtiene todas las consultas activas con información de ficha médica
        """
        consultaSQL = """
        SELECT 
            cc.id_consulta_cab,
            cc.id_paciente,
            CONCAT(p.nombre, ' ', p.apellido) as nombre_paciente,
            cc.id_medico,
            CONCAT(m.nombre, ' ', m.apellido) as nombre_medico,
            cc.id_consultorio,
            co.nombre_consultorio,
            cc.fecha_cita,
            cc.hora_cita,
            cc.duracion_minutos,
            cc.estado,
            cc.activo,
            CASE WHEN fm.id_ficha_medica IS NOT NULL THEN true ELSE false END as tiene_ficha
        FROM consultas_cab cc
        LEFT JOIN paciente p ON cc.id_paciente = p.id_paciente
        LEFT JOIN medico m ON cc.id_medico = m.id_medico
        LEFT JOIN consultorio co ON cc.id_consultorio = co.codigo
        LEFT JOIN ficha_medica_consulta fm ON cc.id_consulta_cab = fm.id_consulta_cab
        WHERE cc.activo = true
        ORDER BY cc.fecha_cita DESC, cc.hora_cita DESC
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(consultaSQL)
            consultas = cur.fetchall()
            
            return [{
                'id_consulta_cab': c[0],
                'id_paciente': c[1],
                'nombre_paciente': c[2],
                'id_medico': c[3],
                'nombre_medico': c[4],
                'id_consultorio': c[5],
                'nombre_consultorio': c[6],
                'fecha_cita': c[7].isoformat() if c[7] else None,
                'hora_cita': str(c[8]) if c[8] else None,
                'duracion_minutos': c[9],
                'estado': c[10],
                'activo': c[11],
                'tiene_ficha': c[12]
            } for c in consultas]
            
        except Exception as e:
            app.logger.error(f"Error al obtener consultas: {str(e)}")
            return []
            
        finally:
            cur.close()
            con.close()

    def getConsultaById(self, id_consulta_cab):
        """
        Obtiene UNA consulta específica por ID
        """
        consultaSQL = """
        SELECT 
            cc.id_consulta_cab,
            cc.id_cita,
            cc.id_paciente,
            CONCAT(p.nombre, ' ', p.apellido) as nombre_paciente,
            cc.id_medico,
            CONCAT(m.nombre, ' ', m.apellido) as nombre_medico,
            cc.id_consultorio,
            con.nombre_consultorio,
            cc.id_funcionario,
            cc.fecha_cita,
            cc.hora_cita,
            cc.duracion_minutos,
            cc.estado,
            cc.fecha_registro
        FROM consultas_cab cc
        INNER JOIN paciente p ON cc.id_paciente = p.id_paciente
        INNER JOIN medico m ON cc.id_medico = m.id_medico
        INNER JOIN consultorio con ON cc.id_consultorio = con.codigo
        WHERE cc.id_consulta_cab = %s
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(consultaSQL, (id_consulta_cab,))
            c = cur.fetchone()
            
            if c:
                return {
                    'id_consulta_cab': c[0],
                    'id_cita': c[1],
                    'id_paciente': c[2],
                    'nombre_paciente': c[3],
                    'id_medico': c[4],
                    'nombre_medico': c[5],
                    'id_consultorio': c[6],
                    'nombre_consultorio': c[7],
                    'id_funcionario': c[8],
                    'fecha_cita': c[9].isoformat() if c[9] else None,
                    'hora_cita': str(c[10]) if c[10] else None,
                    'duracion_minutos': c[11],
                    'estado': c[12],
                    'fecha_registro': c[13].isoformat() if c[13] else None
                }
            else:
                return None
                
        except Exception as e:
            app.logger.error(f"Error al obtener consulta por ID: {str(e)}")
            return None
            
        finally:
            cur.close()
            con.close()

    def guardarConsulta(self, datos):
        """
        Registra una nueva consulta médica a partir de una Cita ya Confirmada
        (cita_detalle.id_estado_cita = 'Confirmado').

        Paciente, Médico, Consultorio, Fecha y Hora NO se toman del formulario:
        se derivan siempre de la cita (cita_detalle -> cita_cabecera -> agenda_cabecera),
        para que no puedan quedar desincronizados de lo que realmente se reservó.

        Al registrar la consulta, la cita pasa a estado 'Realizado' en la misma
        transacción (todo o nada).

        Retorna un dict:
          {'id_consulta_cab': N}  en éxito
          {'error': 'CITA_NO_ENCONTRADA' | 'CITA_NO_CONFIRMADA' | 'CITA_YA_TIENE_CONSULTA' | 'ERROR_INTERNO'}
        """
        id_cita = datos.get('id_cita')

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute("""
                SELECT cd.fecha_cita, cd.hora_cita, ec.descripcion,
                       cc.id_paciente, ac.id_medico, ac.id_consultorio
                FROM cita_detalle cd
                JOIN estado_cita ec ON cd.id_estado_cita = ec.id_estado_cita
                JOIN cita_cabecera cc ON cd.id_cita_cabecera = cc.id_cita_cabecera
                JOIN agenda_cabecera ac ON cc.id_agenda_cabecera = ac.id_agenda_cabecera
                WHERE cd.id_cita_detalle = %s
            """, (id_cita,))
            cita = cur.fetchone()

            if not cita:
                return {'error': 'CITA_NO_ENCONTRADA'}

            fecha_cita, hora_cita, estado_descripcion, id_paciente, id_medico, id_consultorio = cita

            if estado_descripcion != 'Confirmado':
                return {'error': 'CITA_NO_CONFIRMADA'}

            cur.execute("SELECT 1 FROM consultas_cab WHERE id_cita = %s", (id_cita,))
            if cur.fetchone():
                return {'error': 'CITA_YA_TIENE_CONSULTA'}

            cur.execute("""
                INSERT INTO consultas_cab(
                    id_cita, id_paciente, id_medico, id_consultorio, id_funcionario,
                    fecha_cita, hora_cita, duracion_minutos, estado
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id_consulta_cab
            """, (
                id_cita, id_paciente, id_medico, id_consultorio,
                datos.get('id_funcionario'),
                fecha_cita, hora_cita,
                datos.get('duracion_minutos'),
                datos.get('estado', 'programada')
            ))
            consulta_id = cur.fetchone()[0]

            cur.execute("SELECT id_estado_cita FROM estado_cita WHERE descripcion = 'Realizado'")
            row = cur.fetchone()
            if not row:
                raise Exception("No existe el estado 'Realizado' en estado_cita")
            id_estado_realizado = row[0]

            cur.execute(
                "UPDATE cita_detalle SET id_estado_cita = %s, fecha_cambio_estado = NOW() WHERE id_cita_detalle = %s",
                (id_estado_realizado, id_cita)
            )

            con.commit()
            return {'id_consulta_cab': consulta_id}

        except Exception as e:
            app.logger.error(f"Error al guardar consulta: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}

        finally:
            cur.close()
            con.close()

    def updateConsulta(self, id_consulta_cab, datos):
        """
        Actualiza una consulta existente.
        Solo Duración y Estado (de la Consulta, no de la Cita) son editables:
        Cita, Paciente, Médico, Consultorio, Fecha y Hora quedan fijos desde
        el registro inicial (heredados de la Cita).
        """
        updateSQL = """
        UPDATE consultas_cab
        SET
            duracion_minutos = %s,
            estado = %s
        WHERE id_consulta_cab = %s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateSQL, (
                datos.get('duracion_minutos'),
                datos.get('estado', 'programada'),
                id_consulta_cab
            ))

            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0

        except Exception as e:
            app.logger.error(f"Error al actualizar consulta: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deleteConsulta(self, id_consulta_cab):
        """
        Anula (baja lógica) una consulta, siempre que no tenga ya registrada
        Ficha Médica, Diagnóstico o Tratamiento (en ese caso queda historial
        clínico real y no se puede deshacer el registro).

        Retorna True si anuló, False si no existía, "EN_USO" si está bloqueada.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute("""
                SELECT
                    EXISTS(SELECT 1 FROM ficha_medica_consulta WHERE id_consulta_cab = %s) AS tiene_ficha,
                    EXISTS(
                        SELECT 1 FROM diagnosticos d
                        JOIN consultas_detalle cd ON d.id_consulta_detalle = cd.id_consulta_detalle
                        WHERE cd.id_consulta_cab = %s
                    ) AS tiene_diagnostico,
                    EXISTS(SELECT 1 FROM tratamientos WHERE id_consulta_cab = %s) AS tiene_tratamiento
            """, (id_consulta_cab, id_consulta_cab, id_consulta_cab))
            tiene_ficha, tiene_diagnostico, tiene_tratamiento = cur.fetchone()

            if tiene_ficha or tiene_diagnostico or tiene_tratamiento:
                app.logger.warning(f"No se puede anular consulta {id_consulta_cab}: tiene historial clínico asociado")
                return "EN_USO"

            cur.execute("UPDATE consultas_cab SET activo = false WHERE id_consulta_cab = %s", (id_consulta_cab,))
            rows_affected = cur.rowcount
            con.commit()
            return rows_affected > 0

        except Exception as e:
            app.logger.error(f"Error al eliminar consulta: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()