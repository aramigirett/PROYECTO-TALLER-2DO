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
        Inserta una nueva consulta
        """
        insertSQL = """
        INSERT INTO consultas_cab(
            id_cita,
            id_paciente,
            id_medico,
            id_consultorio,
            id_funcionario,
            fecha_cita,
            hora_cita,
            duracion_minutos,
            estado
        ) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id_consulta_cab
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(insertSQL, (
                datos.get('id_cita'),
                datos['id_paciente'],
                datos['id_medico'],
                datos['id_consultorio'],
                datos.get('id_funcionario'),
                datos['fecha_cita'],
                datos['hora_cita'],
                datos.get('duracion_minutos'),
                datos.get('estado', 'programada')
            ))
            
            consulta_id = cur.fetchone()[0]
            con.commit()
            return consulta_id
            
        except Exception as e:
            app.logger.error(f"Error al guardar consulta: {str(e)}")
            con.rollback()
            return None
            
        finally:
            cur.close()
            con.close()

    def updateConsulta(self, id_consulta_cab, datos):
        """
        Actualiza una consulta existente
        """
        updateSQL = """
        UPDATE consultas_cab
        SET 
            id_paciente = %s,
            id_medico = %s,
            id_consultorio = %s,
            id_funcionario = %s,
            fecha_cita = %s,
            hora_cita = %s,
            duracion_minutos = %s,
            estado = %s
        WHERE id_consulta_cab = %s
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(updateSQL, (
                datos['id_paciente'],
                datos['id_medico'],
                datos['id_consultorio'],
                datos.get('id_funcionario'),
                datos['fecha_cita'],
                datos['hora_cita'],
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
        Soft Delete: marca como inactivo en lugar de eliminar
        """
        deleteSQL = """
        UPDATE consultas_cab
        SET activo = false
        WHERE id_consulta_cab = %s
        """
        
        deleteFichaSQL = """
        UPDATE ficha_medica_consulta
        SET activo = false
        WHERE id_consulta_cab = %s
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            # Marcar ficha como inactiva
            cur.execute(deleteFichaSQL, (id_consulta_cab,))
            
            # Marcar consulta como inactiva
            cur.execute(deleteSQL, (id_consulta_cab,))
            
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