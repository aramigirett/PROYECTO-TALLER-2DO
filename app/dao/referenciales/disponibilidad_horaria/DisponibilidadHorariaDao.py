from flask import current_app as app
from app.conexion.Conexion import Conexion

class DisponibilidadDao:

    def getDisponibilidades(self):
        # Ahora seleccionamos nombre y apellido del médico de la tabla 'pacientes'
        sql = """
        SELECT 
            d.id_disponibilidad, 
            d.id_medico, 
            d.disponibilidad_hora_inicio, 
            d.disponibilidad_hora_fin, 
            d.disponibilidad_fecha, 
            d.disponibilidad_cupos, 
            p.nombre AS medico_nombre,  -- Nombre del médico
            p.apellido AS medico_apellido  -- Apellido del médico
        FROM disponibilidad_horaria d
        JOIN medicos m ON d.id_medico = m.id_medico
        JOIN pacientes p ON m.id_paciente = p.id_paciente  -- Unimos con la tabla pacientes
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            disponibilidades = cur.fetchall()
            return [
                {
                    'id_disponibilidad': d[0],
                    'id_medico': d[1],
                    'disponibilidad_hora_inicio': str(d[2]),
                    'disponibilidad_hora_fin': str(d[3]),
                    'disponibilidad_fecha': str(d[4]),
                    'disponibilidad_cupos': d[5],
                    'medico_nombre': d[6],  # Nombre del médico
                    'medico_apellido': d[7]  # Apellido del médico
                } for d in disponibilidades
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener disponibilidades: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getDisponibilidadById(self, id_disponibilidad):
        sql = """
        SELECT 
            d.id_disponibilidad, 
            d.id_medico, 
            d.disponibilidad_hora_inicio, 
            d.disponibilidad_hora_fin, 
            d.disponibilidad_fecha, 
            d.disponibilidad_cupos, 
            p.nombre AS medico_nombre,  -- Nombre del médico
            p.apellido AS medico_apellido  -- Apellido del médico
        FROM disponibilidad_horaria d
        JOIN medicos m ON d.id_medico = m.id_medico
        JOIN pacientes p ON m.id_paciente = p.id_paciente
        WHERE d.id_disponibilidad = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_disponibilidad,))
            d = cur.fetchone()
            if d:
                return {
                    'id_disponibilidad': d[0],
                    'id_medico': d[1],
                    'disponibilidad_hora_inicio': str(d[2]),
                    'disponibilidad_hora_fin': str(d[3]),
                    'disponibilidad_fecha': str(d[4]),
                    'disponibilidad_cupos': d[5],
                    'medico_nombre': d[6],  # Nombre del médico
                    'medico_apellido': d[7]  # Apellido del médico
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener disponibilidad: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()