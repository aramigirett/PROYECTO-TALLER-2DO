"""
=====================================================
DAO: Diagnóstico
Descripción: Manejo de diagnósticos médicos
=====================================================
"""

from flask import current_app as app
from app.conexion.Conexion import Conexion

class DiagnosticoDao:

    def getDiagnosticos(self):
        """
        Obtiene todos los diagnósticos con información relacionada
        """
        diagnosticoSQL = """
        SELECT 
            d.id_diagnostico,
            d.codigo,
            d.id_consulta_detalle,
            d.id_paciente,
            CONCAT(p.nombre, ' ', p.apellido) as nombre_paciente,
            d.id_medico,
            CONCAT(m.nombre, ' ', m.apellido) as nombre_medico,
            d.id_tipo_diagnostico,
            td.descripcion_diagnostico as tipo_diagnostico,
            d.descripcion_diagnostico,
            d.pieza_dental,
            d.fecha_diagnostico,
            d.sintomas,
            d.observaciones,
            d.fecha_registro
        FROM diagnosticos d
        INNER JOIN paciente p ON d.id_paciente = p.id_paciente
        INNER JOIN medico m ON d.id_medico = m.id_medico
        INNER JOIN tipo_diagnostico td ON d.id_tipo_diagnostico = td.id_tipo_diagnostico
        WHERE d.activo = true
        ORDER BY d.fecha_diagnostico DESC, d.fecha_registro DESC
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(diagnosticoSQL)
            diagnosticos = cur.fetchall()
            
            return [{
                'id_diagnostico': d[0],
                'codigo': d[1],
                'id_consulta_detalle': d[2],
                'id_paciente': d[3],
                'nombre_paciente': d[4],
                'id_medico': d[5],
                'nombre_medico': d[6],
                'id_tipo_diagnostico': d[7],
                'tipo_diagnostico': d[8],
                'descripcion_diagnostico': d[9],
                'pieza_dental': d[10],
                'fecha_diagnostico': d[11].isoformat() if d[11] else None,
                'sintomas': d[12],
                'observaciones': d[13],
                'fecha_registro': d[14].isoformat() if d[14] else None
            } for d in diagnosticos]
            
        except Exception as e:
            app.logger.error(f"Error al obtener diagnósticos: {str(e)}")
            return []
            
        finally:
            cur.close()
            con.close()

    def getDiagnosticoById(self, id_diagnostico):
        """
        Obtiene un diagnóstico específico por ID
        """
        diagnosticoSQL = """
        SELECT 
            d.id_diagnostico,
            d.codigo,
            d.id_consulta_detalle,
            d.id_paciente,
            CONCAT(p.nombre, ' ', p.apellido) as nombre_paciente,
            d.id_medico,
            CONCAT(m.nombre, ' ', m.apellido) as nombre_medico,
            d.id_tipo_diagnostico,
            td.descripcion_diagnostico as tipo_diagnostico,
            d.descripcion_diagnostico,
            d.pieza_dental,
            d.fecha_diagnostico,
            d.sintomas,
            d.observaciones,
            d.fecha_registro
        FROM diagnosticos d
        INNER JOIN paciente p ON d.id_paciente = p.id_paciente
        INNER JOIN medico m ON d.id_medico = m.id_medico
        INNER JOIN tipo_diagnostico td ON d.id_tipo_diagnostico = td.id_tipo_diagnostico
        WHERE d.id_diagnostico = %s AND d.activo = true
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(diagnosticoSQL, (id_diagnostico,))
            d = cur.fetchone()
            
            if d:
                return {
                    'id_diagnostico': d[0],
                    'codigo': d[1],
                    'id_consulta_detalle': d[2],
                    'id_paciente': d[3],
                    'nombre_paciente': d[4],
                    'id_medico': d[5],
                    'nombre_medico': d[6],
                    'id_tipo_diagnostico': d[7],
                    'tipo_diagnostico': d[8],
                    'descripcion_diagnostico': d[9],
                    'pieza_dental': d[10],
                    'fecha_diagnostico': d[11].isoformat() if d[11] else None,
                    'sintomas': d[12],
                    'observaciones': d[13],
                    'fecha_registro': d[14].isoformat() if d[14] else None
                }
            else:
                return None
                
        except Exception as e:
            app.logger.error(f"Error al obtener diagnóstico por ID: {str(e)}")
            return None
            
        finally:
            cur.close()
            con.close()

    def getDiagnosticosByPaciente(self, id_paciente):
        """
        Obtiene todos los diagnósticos de un paciente
        """
        diagnosticoSQL = """
        SELECT 
            d.id_diagnostico,
            d.codigo,
            d.pieza_dental,
            d.fecha_diagnostico,
            td.descripcion_diagnostico as tipo_diagnostico,
            d.descripcion_diagnostico,
            CONCAT(m.nombre, ' ', m.apellido) as nombre_medico
        FROM diagnosticos d
        INNER JOIN tipo_diagnostico td ON d.id_tipo_diagnostico = td.id_tipo_diagnostico
        INNER JOIN medico m ON d.id_medico = m.id_medico
        WHERE d.id_paciente = %s AND d.activo = true
        ORDER BY d.fecha_diagnostico DESC
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(diagnosticoSQL, (id_paciente,))
            diagnosticos = cur.fetchall()
            
            return [{
                'id_diagnostico': d[0],
                'codigo': d[1],
                'pieza_dental': d[2],
                'fecha_diagnostico': d[3].isoformat() if d[3] else None,
                'tipo_diagnostico': d[4],
                'descripcion_diagnostico': d[5],
                'nombre_medico': d[6]
            } for d in diagnosticos]
            
        except Exception as e:
            app.logger.error(f"Error al obtener diagnósticos del paciente: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getDiagnosticosByConsulta(self, id_consulta_cab):
        """
        Obtiene los diagnósticos activos vinculados a una consulta específica
        (vía consultas_detalle).
        """
        diagnosticoSQL = """
        SELECT
            d.id_diagnostico,
            d.codigo,
            d.descripcion_diagnostico,
            td.descripcion_diagnostico as tipo_diagnostico
        FROM diagnosticos d
        JOIN consultas_detalle cd ON d.id_consulta_detalle = cd.id_consulta_detalle
        JOIN tipo_diagnostico td ON d.id_tipo_diagnostico = td.id_tipo_diagnostico
        WHERE cd.id_consulta_cab = %s AND d.activo = true
        ORDER BY d.fecha_registro DESC
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(diagnosticoSQL, (id_consulta_cab,))
            diagnosticos = cur.fetchall()
            return [{
                'id_diagnostico': d[0],
                'codigo': d[1],
                'descripcion_diagnostico': d[2],
                'tipo_diagnostico': d[3]
            } for d in diagnosticos]
        except Exception as e:
            app.logger.error(f"Error al obtener diagnósticos de la consulta: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def generarCodigo(self):
        """
        Genera un código único para el diagnóstico (DX-NNNN).

        `codigo` es único a nivel de TODA la tabla, no por año, así que el
        siguiente número se calcula a partir del máximo ya usado en toda la
        tabla (no solo los registrados este año — eso chocaba con códigos
        de años anteriores, ej. DX-0001 de 2025 vs. el DX-0001 recién
        calculado para 2026).
        """
        codigoSQL = r"""
        SELECT COALESCE(MAX(CAST(SUBSTRING(codigo FROM 'DX-(\d+)') AS INTEGER)), 0) + 1 AS siguiente
        FROM diagnosticos
        WHERE codigo LIKE 'DX-%'
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(codigoSQL)
            resultado = cur.fetchone()
            numero = resultado[0] if resultado else 1

            # Código más corto: DX-0001 (7 caracteres)
            codigo = f"DX-{str(numero).zfill(4)}"

            return codigo

        except Exception as e:
            app.logger.error(f"Error al generar código: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarDiagnostico(self, datos):
        """
        Inserta un nuevo diagnóstico
        """
        # Generar código automáticamente
        codigo = self.generarCodigo()
        
        insertSQL = """
        INSERT INTO diagnosticos(
            codigo,
            id_consulta_detalle,
            id_paciente,
            id_medico,
            id_tipo_diagnostico,
            descripcion_diagnostico,
            pieza_dental,
            fecha_diagnostico,
            sintomas,
            observaciones
        ) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id_diagnostico
        """
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        
        try:
            cur.execute(insertSQL, (
                codigo,
                datos.get('id_consulta_detalle'),
                datos['id_paciente'],
                datos['id_medico'],
                datos['id_tipo_diagnostico'],
                datos['descripcion_diagnostico'],
                datos.get('pieza_dental'),
                datos['fecha_diagnostico'],
                datos.get('sintomas'),
                datos.get('observaciones')
            ))
            
            diagnostico_id = cur.fetchone()[0]
            con.commit()
            return diagnostico_id
            
        except Exception as e:
            app.logger.error(f"Error al guardar diagnóstico: {str(e)}")
            con.rollback()
            return None
            
        finally:
            cur.close()
            con.close()

    def deleteDiagnostico(self, id_diagnostico):
        """
        Anula (baja lógica) un diagnóstico, validando antes que:
          1) no tenga un Tratamiento asociado, y
          2) la Consulta a la que pertenece (si tiene una vinculada) no esté
             'finalizada'.

        Returns:
            bool | str: True si se anuló, False si no existía, "EN_USO" si
            tiene un tratamiento asociado, "CONSULTA_FINALIZADA" si la
            consulta asociada ya está finalizada.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute("""
                SELECT
                    EXISTS(SELECT 1 FROM tratamientos WHERE id_diagnostico = %s) AS tiene_tratamiento,
                    EXISTS(
                        SELECT 1 FROM diagnosticos d
                        JOIN consultas_detalle cd ON d.id_consulta_detalle = cd.id_consulta_detalle
                        JOIN consultas_cab cc ON cd.id_consulta_cab = cc.id_consulta_cab
                        WHERE d.id_diagnostico = %s AND cc.estado = 'finalizada'
                    ) AS consulta_finalizada
            """, (id_diagnostico, id_diagnostico))
            tiene_tratamiento, consulta_finalizada = cur.fetchone()

            if tiene_tratamiento:
                app.logger.warning(f"No se puede anular diagnóstico {id_diagnostico}: tiene un tratamiento asociado")
                return "EN_USO"

            if consulta_finalizada:
                app.logger.warning(f"No se puede anular diagnóstico {id_diagnostico}: la consulta asociada está finalizada")
                return "CONSULTA_FINALIZADA"

            cur.execute(
                "UPDATE diagnosticos SET activo = false WHERE id_diagnostico = %s AND activo = true",
                (id_diagnostico,)
            )
            rows_affected = cur.rowcount
            con.commit()
            return rows_affected > 0

        except Exception as e:
            app.logger.error(f"Error al anular diagnóstico: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()