"""
=====================================================
DAO: Consulta Detalle
Descripción: Manejo de consultas_detalle (detalles clínicos)
=====================================================
"""

from flask import current_app as app
from app.conexion.Conexion import Conexion

class ConsultaDetalleDao:

    def getDetallesByConsulta(self, id_consulta_cab):
        """
        Obtiene todos los detalles clínicos de una consulta
        """
        detalleSQL = """
        SELECT 
            cd.id_consulta_detalle,
            cd.id_consulta_cab,
            cd.id_sintoma,
            s.descripcion_sintoma,
            cd.pieza_dental,
            cd.diagnostico,
            cd.tratamiento,
            cd.procedimiento,
            cd.id_tipo_diagnostico,
            cd.id_tipo_procedimiento,
            cd.fecha_registro
        FROM consultas_detalle cd
        LEFT JOIN sintoma s ON cd.id_sintoma = s.id_sintoma
        WHERE cd.id_consulta_cab = %s
        ORDER BY cd.fecha_registro DESC
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(detalleSQL, (id_consulta_cab,))
            detalles = cur.fetchall()
            
            return [{
                'id_consulta_detalle': d[0],
                'id_consulta_cab': d[1],
                'id_sintoma': d[2],
                'descripcion_sintoma': d[3],
                'pieza_dental': d[4],
                'diagnostico': d[5],
                'tratamiento': d[6],
                'procedimiento': d[7],
                'id_tipo_diagnostico': d[8],
                'id_tipo_procedimiento': d[9],
                'fecha_registro': d[10].isoformat() if d[10] else None
            } for d in detalles]
            
        except Exception as e:
            app.logger.error(f"Error al obtener detalles de consulta: {str(e)}")
            return []
            
        finally:
            cur.close()
            con.close()

    def getDetalleById(self, id_consulta_detalle):
        """
        Obtiene un detalle específico por ID
        """
        detalleSQL = """
        SELECT 
            cd.id_consulta_detalle,
            cd.id_consulta_cab,
            cd.id_sintoma,
            s.descripcion_sintoma,
            cd.pieza_dental,
            cd.diagnostico,
            cd.tratamiento,
            cd.procedimiento,
            cd.id_tipo_diagnostico,
            cd.id_tipo_procedimiento,
            cd.fecha_registro
        FROM consultas_detalle cd
        LEFT JOIN sintoma s ON cd.id_sintoma = s.id_sintoma
        WHERE cd.id_consulta_detalle = %s
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(detalleSQL, (id_consulta_detalle,))
            d = cur.fetchone()
            
            if d:
                return {
                    'id_consulta_detalle': d[0],
                    'id_consulta_cab': d[1],
                    'id_sintoma': d[2],
                    'descripcion_sintoma': d[3],
                    'pieza_dental': d[4],
                    'diagnostico': d[5],
                    'tratamiento': d[6],
                    'procedimiento': d[7],
                    'id_tipo_diagnostico': d[8],
                    'id_tipo_procedimiento': d[9],
                    'fecha_registro': d[10].isoformat() if d[10] else None
                }
            else:
                return None
                
        except Exception as e:
            app.logger.error(f"Error al obtener detalle por ID: {str(e)}")
            return None
            
        finally:
            cur.close()
            con.close()

    def guardarDetalle(self, datos):
        """
        Inserta un nuevo detalle clínico
        """
        insertSQL = """
        INSERT INTO consultas_detalle(
            id_consulta_cab,
            id_sintoma,
            pieza_dental,
            diagnostico,
            tratamiento,
            procedimiento,
            id_tipo_diagnostico,
            id_tipo_procedimiento
        ) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id_consulta_detalle
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(insertSQL, (
                datos['id_consulta_cab'],
                datos['id_sintoma'],
                datos.get('pieza_dental'),
                datos['diagnostico'],
                datos['tratamiento'],
                datos.get('procedimiento'),
                datos.get('id_tipo_diagnostico'),
                datos.get('id_tipo_procedimiento')
            ))
            
            detalle_id = cur.fetchone()[0]
            con.commit()
            return detalle_id
            
        except Exception as e:
            app.logger.error(f"Error al guardar detalle: {str(e)}")
            con.rollback()
            return None
            
        finally:
            cur.close()
            con.close()

    def updateDetalle(self, id_consulta_detalle, datos):
        """
        Actualiza un detalle clínico existente
        """
        updateSQL = """
        UPDATE consultas_detalle
        SET 
            id_sintoma = %s,
            pieza_dental = %s,
            diagnostico = %s,
            tratamiento = %s,
            procedimiento = %s,
            id_tipo_diagnostico = %s,
            id_tipo_procedimiento = %s
        WHERE id_consulta_detalle = %s
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(updateSQL, (
                datos['id_sintoma'],
                datos.get('pieza_dental'),
                datos['diagnostico'],
                datos['tratamiento'],
                datos.get('procedimiento'),
                datos.get('id_tipo_diagnostico'),
                datos.get('id_tipo_procedimiento'),
                id_consulta_detalle
            ))
            
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
            
        except Exception as e:
            app.logger.error(f"Error al actualizar detalle: {str(e)}")
            con.rollback()
            return False
            
        finally:
            cur.close()
            con.close()

    def deleteDetalle(self, id_consulta_detalle):
        """
        Elimina un detalle clínico
        """
        deleteSQL = """
        DELETE FROM consultas_detalle
        WHERE id_consulta_detalle = %s
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(deleteSQL, (id_consulta_detalle,))
            rows_affected = cur.rowcount
            con.commit()
            return rows_affected > 0
            
        except Exception as e:
            app.logger.error(f"Error al eliminar detalle: {str(e)}")
            con.rollback()
            return False
            
        finally:
            cur.close()
            con.close()