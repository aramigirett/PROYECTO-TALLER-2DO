# Data access object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class HistorialMedicoDao:

    def getHistorialByPaciente(self, id_paciente):
        """
        Obtiene TODO el historial médico de un paciente
        """
        historialSQL = """
        SELECT 
            h.id_historial,
            h.id_paciente,
            h.tipo_documento,
            h.descripcion,
            h.tipo_alergia,
            h.gravedad_alergia,
            h.nombre_medicamento,
            h.dosis_medicamento,
            h.frecuencia_medicamento,
            h.fecha_inicio_medicamento,
            h.archivo_url,
            h.archivo_nombre,
            h.archivo_tipo,
            h.archivo_tamano,
            h.fecha_registro,
            h.id_usuario_registro,
            h.estado,
            p.nombre || ' ' || p.apellido as nombre_paciente
        FROM historial_medico_paciente h
        INNER JOIN paciente p ON h.id_paciente = p.id_paciente
        WHERE h.id_paciente = %s AND h.estado = 'activo'
        ORDER BY h.fecha_registro DESC
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(historialSQL, (id_paciente,))
            historiales = cur.fetchall()
            
            return [{
                'id_historial': h[0],
                'id_paciente': h[1],
                'tipo_documento': h[2],
                'descripcion': h[3],
                'tipo_alergia': h[4],
                'gravedad_alergia': h[5],
                'nombre_medicamento': h[6],
                'dosis_medicamento': h[7],
                'frecuencia_medicamento': h[8],
                'fecha_inicio_medicamento': h[9].isoformat() if h[9] else None,
                'archivo_url': h[10],
                'archivo_nombre': h[11],
                'archivo_tipo': h[12],
                'archivo_tamano': h[13],
                'fecha_registro': h[14].isoformat() if h[14] else None,
                'id_usuario_registro': h[15],
                'estado': h[16],
                'nombre_paciente': h[17]
            } for h in historiales]
            
        except Exception as e:
            app.logger.error(f"Error al obtener historial del paciente: {str(e)}")
            return []
            
        finally:
            cur.close()
            con.close()

    def getHistorialByTipo(self, id_paciente, tipo_documento):
        """
        Obtiene historial filtrado por tipo de documento
        """
        historialSQL = """
        SELECT 
            id_historial,
            id_paciente,
            tipo_documento,
            descripcion,
            tipo_alergia,
            gravedad_alergia,
            nombre_medicamento,
            dosis_medicamento,
            frecuencia_medicamento,
            fecha_inicio_medicamento,
            archivo_url,
            archivo_nombre,
            archivo_tipo,
            archivo_tamano,
            fecha_registro,
            estado
        FROM historial_medico_paciente
        WHERE id_paciente = %s AND tipo_documento = %s AND estado = 'activo'
        ORDER BY fecha_registro DESC
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(historialSQL, (id_paciente, tipo_documento))
            historiales = cur.fetchall()
            
            return [{
                'id_historial': h[0],
                'id_paciente': h[1],
                'tipo_documento': h[2],
                'descripcion': h[3],
                'tipo_alergia': h[4],
                'gravedad_alergia': h[5],
                'nombre_medicamento': h[6],
                'dosis_medicamento': h[7],
                'frecuencia_medicamento': h[8],
                'fecha_inicio_medicamento': h[9].isoformat() if h[9] else None,
                'archivo_url': h[10],
                'archivo_nombre': h[11],
                'archivo_tipo': h[12],
                'archivo_tamano': h[13],
                'fecha_registro': h[14].isoformat() if h[14] else None,
                'estado': h[15]
            } for h in historiales]
            
        except Exception as e:
            app.logger.error(f"Error al obtener historial por tipo: {str(e)}")
            return []
            
        finally:
            cur.close()
            con.close()

    def getHistorialById(self, id_historial):
        """
        Obtiene un documento específico por ID
        """
        historialSQL = """
        SELECT 
            id_historial,
            id_paciente,
            tipo_documento,
            descripcion,
            tipo_alergia,
            gravedad_alergia,
            nombre_medicamento,
            dosis_medicamento,
            frecuencia_medicamento,
            fecha_inicio_medicamento,
            archivo_url,
            archivo_nombre,
            archivo_tipo,
            archivo_tamano,
            fecha_registro,
            id_usuario_registro,
            estado
        FROM historial_medico_paciente
        WHERE id_historial = %s
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(historialSQL, (id_historial,))
            h = cur.fetchone()
            
            if h:
                return {
                    'id_historial': h[0],
                    'id_paciente': h[1],
                    'tipo_documento': h[2],
                    'descripcion': h[3],
                    'tipo_alergia': h[4],
                    'gravedad_alergia': h[5],
                    'nombre_medicamento': h[6],
                    'dosis_medicamento': h[7],
                    'frecuencia_medicamento': h[8],
                    'fecha_inicio_medicamento': h[9].isoformat() if h[9] else None,
                    'archivo_url': h[10],
                    'archivo_nombre': h[11],
                    'archivo_tipo': h[12],
                    'archivo_tamano': h[13],
                    'fecha_registro': h[14].isoformat() if h[14] else None,
                    'id_usuario_registro': h[15],
                    'estado': h[16]
                }
            else:
                return None
                
        except Exception as e:
            app.logger.error(f"Error al obtener historial por ID: {str(e)}")
            return None
            
        finally:
            cur.close()
            con.close()

    def guardarHistorial(self, datos):
        """
        Inserta un nuevo documento en el historial
        """
        insertSQL = """
        INSERT INTO historial_medico_paciente(
            id_paciente,
            tipo_documento,
            descripcion,
            tipo_alergia,
            gravedad_alergia,
            nombre_medicamento,
            dosis_medicamento,
            frecuencia_medicamento,
            fecha_inicio_medicamento,
            archivo_url,
            archivo_nombre,
            archivo_tipo,
            archivo_tamano,
            id_usuario_registro
        ) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id_historial
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(insertSQL, (
                datos['id_paciente'],
                datos['tipo_documento'],
                datos['descripcion'],
                datos.get('tipo_alergia'),
                datos.get('gravedad_alergia'),
                datos.get('nombre_medicamento'),
                datos.get('dosis_medicamento'),
                datos.get('frecuencia_medicamento'),
                datos.get('fecha_inicio_medicamento'),
                datos.get('archivo_url'),
                datos.get('archivo_nombre'),
                datos.get('archivo_tipo'),
                datos.get('archivo_tamano'),
                datos.get('id_usuario_registro')
            ))
            
            historial_id = cur.fetchone()[0]
            con.commit()
            return historial_id
            
        except Exception as e:
            app.logger.error(f"Error al guardar historial: {str(e)}")
            con.rollback()
            return None
            
        finally:
            cur.close()
            con.close()

    def updateHistorial(self, id_historial, datos):
        """
        Actualiza un documento existente
        """
        updateSQL = """
        UPDATE historial_medico_paciente
        SET 
            tipo_documento = %s,
            descripcion = %s,
            tipo_alergia = %s,
            gravedad_alergia = %s,
            nombre_medicamento = %s,
            dosis_medicamento = %s,
            frecuencia_medicamento = %s,
            fecha_inicio_medicamento = %s,
            archivo_url = %s,
            archivo_nombre = %s,
            archivo_tipo = %s,
            archivo_tamano = %s,
            fecha_modificacion = CURRENT_TIMESTAMP,
            id_usuario_modificacion = %s
        WHERE id_historial = %s
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(updateSQL, (
                datos['tipo_documento'],
                datos['descripcion'],
                datos.get('tipo_alergia'),
                datos.get('gravedad_alergia'),
                datos.get('nombre_medicamento'),
                datos.get('dosis_medicamento'),
                datos.get('frecuencia_medicamento'),
                datos.get('fecha_inicio_medicamento'),
                datos.get('archivo_url'),
                datos.get('archivo_nombre'),
                datos.get('archivo_tipo'),
                datos.get('archivo_tamano'),
                datos.get('id_usuario_modificacion'),
                id_historial
            ))
            
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
            
        except Exception as e:
            app.logger.error(f"Error al actualizar historial: {str(e)}")
            con.rollback()
            return False
            
        finally:
            cur.close()
            con.close()

    def deleteHistorial(self, id_historial):
        """
        Elimina (inactiva) un documento del historial
        """
        deleteSQL = """
        UPDATE historial_medico_paciente
        SET estado = 'inactivo'
        WHERE id_historial = %s
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(deleteSQL, (id_historial,))
            rows_affected = cur.rowcount
            con.commit()
            return rows_affected > 0
            
        except Exception as e:
            app.logger.error(f"Error al eliminar historial: {str(e)}")
            con.rollback()
            return False
            
        finally:
            cur.close()
            con.close()

    def contarDocumentosPorTipo(self, id_paciente):
        """
        Cuenta documentos por tipo para mostrar en badges
        """
        countSQL = """
        SELECT 
            tipo_documento,
            COUNT(*) as total
        FROM historial_medico_paciente
        WHERE id_paciente = %s AND estado = 'activo'
        GROUP BY tipo_documento
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(countSQL, (id_paciente,))
            counts = cur.fetchall()
            
            return {c[0]: c[1] for c in counts}
            
        except Exception as e:
            app.logger.error(f"Error al contar documentos: {str(e)}")
            return {}
            
        finally:
            cur.close()
            con.close()