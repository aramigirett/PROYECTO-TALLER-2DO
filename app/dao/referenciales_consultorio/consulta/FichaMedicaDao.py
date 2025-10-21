"""
=====================================================
DAO: Ficha Médica de Consulta
Descripción: Manejo de ficha_medica_consulta (signos vitales y examen físico)
=====================================================
"""

from flask import current_app as app
from app.conexion.Conexion import Conexion

class FichaMedicaDao:

    def getFichaByConsulta(self, id_consulta_cab):
        """
        Obtiene la ficha médica de una consulta específica
        (Solo puede haber UNA ficha por consulta)
        """
        fichaSQL = """
        SELECT 
            id_ficha_medica,
            id_consulta_cab,
            presion_arterial,
            temperatura,
            frecuencia_cardiaca,
            frecuencia_respiratoria,
            peso,
            talla,
            imc,
            examen_fisico_general,
            examen_bucal,
            observaciones_medico,
            fecha_registro
        FROM ficha_medica_consulta
        WHERE id_consulta_cab = %s
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(fichaSQL, (id_consulta_cab,))
            f = cur.fetchone()
            
            if f:
                return {
                    'id_ficha_medica': f[0],
                    'id_consulta_cab': f[1],
                    'presion_arterial': f[2],
                    'temperatura': float(f[3]) if f[3] else None,
                    'frecuencia_cardiaca': f[4],
                    'frecuencia_respiratoria': f[5],
                    'peso': float(f[6]) if f[6] else None,
                    'talla': float(f[7]) if f[7] else None,
                    'imc': float(f[8]) if f[8] else None,
                    'examen_fisico_general': f[9],
                    'examen_bucal': f[10],
                    'observaciones_medico': f[11],
                    'fecha_registro': f[12].isoformat() if f[12] else None
                }
            else:
                return None
                
        except Exception as e:
            app.logger.error(f"Error al obtener ficha médica: {str(e)}")
            return None
            
        finally:
            cur.close()
            con.close()

    def getFichaById(self, id_ficha_medica):
        """
        Obtiene una ficha médica por su ID
        """
        fichaSQL = """
        SELECT 
            id_ficha_medica,
            id_consulta_cab,
            presion_arterial,
            temperatura,
            frecuencia_cardiaca,
            frecuencia_respiratoria,
            peso,
            talla,
            imc,
            examen_fisico_general,
            examen_bucal,
            observaciones_medico,
            fecha_registro
        FROM ficha_medica_consulta
        WHERE id_ficha_medica = %s
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(fichaSQL, (id_ficha_medica,))
            f = cur.fetchone()
            
            if f:
                return {
                    'id_ficha_medica': f[0],
                    'id_consulta_cab': f[1],
                    'presion_arterial': f[2],
                    'temperatura': float(f[3]) if f[3] else None,
                    'frecuencia_cardiaca': f[4],
                    'frecuencia_respiratoria': f[5],
                    'peso': float(f[6]) if f[6] else None,
                    'talla': float(f[7]) if f[7] else None,
                    'imc': float(f[8]) if f[8] else None,
                    'examen_fisico_general': f[9],
                    'examen_bucal': f[10],
                    'observaciones_medico': f[11],
                    'fecha_registro': f[12].isoformat() if f[12] else None
                }
            else:
                return None
                
        except Exception as e:
            app.logger.error(f"Error al obtener ficha médica por ID: {str(e)}")
            return None
            
        finally:
            cur.close()
            con.close()

    def guardarFicha(self, datos):
        """
        Inserta una nueva ficha médica
        """
        insertSQL = """
        INSERT INTO ficha_medica_consulta(
            id_consulta_cab,
            presion_arterial,
            temperatura,
            frecuencia_cardiaca,
            frecuencia_respiratoria,
            peso,
            talla,
            imc,
            examen_fisico_general,
            examen_bucal,
            observaciones_medico
        ) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id_ficha_medica
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(insertSQL, (
                datos['id_consulta_cab'],
                datos.get('presion_arterial'),
                datos.get('temperatura'),
                datos.get('frecuencia_cardiaca'),
                datos.get('frecuencia_respiratoria'),
                datos.get('peso'),
                datos.get('talla'),
                datos.get('imc'),
                datos.get('examen_fisico_general'),
                datos.get('examen_bucal'),
                datos.get('observaciones_medico')
            ))
            
            ficha_id = cur.fetchone()[0]
            con.commit()
            return ficha_id
            
        except Exception as e:
            app.logger.error(f"Error al guardar ficha médica: {str(e)}")
            con.rollback()
            return None
            
        finally:
            cur.close()
            con.close()

    def updateFicha(self, id_ficha_medica, datos):
        """
        Actualiza una ficha médica existente
        """
        updateSQL = """
        UPDATE ficha_medica_consulta
        SET 
            presion_arterial = %s,
            temperatura = %s,
            frecuencia_cardiaca = %s,
            frecuencia_respiratoria = %s,
            peso = %s,
            talla = %s,
            imc = %s,
            examen_fisico_general = %s,
            examen_bucal = %s,
            observaciones_medico = %s
        WHERE id_ficha_medica = %s
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(updateSQL, (
                datos.get('presion_arterial'),
                datos.get('temperatura'),
                datos.get('frecuencia_cardiaca'),
                datos.get('frecuencia_respiratoria'),
                datos.get('peso'),
                datos.get('talla'),
                datos.get('imc'),
                datos.get('examen_fisico_general'),
                datos.get('examen_bucal'),
                datos.get('observaciones_medico'),
                id_ficha_medica
            ))
            
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
            
        except Exception as e:
            app.logger.error(f"Error al actualizar ficha médica: {str(e)}")
            con.rollback()
            return False
            
        finally:
            cur.close()
            con.close()

    def deleteFicha(self, id_ficha_medica):
        """
        Elimina una ficha médica
        """
        deleteSQL = """
        DELETE FROM ficha_medica_consulta
        WHERE id_ficha_medica = %s
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(deleteSQL, (id_ficha_medica,))
            rows_affected = cur.rowcount
            con.commit()
            return rows_affected > 0
            
        except Exception as e:
            app.logger.error(f"Error al eliminar ficha médica: {str(e)}")
            con.rollback()
            return False
            
        finally:
            cur.close()
            con.close()