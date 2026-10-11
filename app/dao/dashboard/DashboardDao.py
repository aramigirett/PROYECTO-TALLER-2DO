import datetime
from flask import current_app as app
from app.conexion.Conexion import Conexion


class DashboardDao:
    """
    DAO para el Dashboard de Inicio de OdontoClinic.
    Consulta de forma segura y optimizada los datos reales existentes en PostgreSQL:
    - Pacientes registrados
    - Citas programadas para la fecha actual
    - Consultas médicas del mes
    - Médicos registrados
    - Estadísticas mensuales para el gráfico
    - Pacientes recientes
    """

    def obtener_saludo(self):
        hora = datetime.datetime.now().hour
        if 5 <= hora < 12:
            return "Buenos días"
        elif 12 <= hora < 20:
            return "Buenas tardes"
        else:
            return "Buenas noches"

    def obtener_estadisticas(self):
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        stats = {
            'total_pacientes': 0,
            'citas_hoy': 0,
            'consultas_mes': 0,
            'medicos_activos': 0
        }
        try:
            # 1. Total pacientes registrados
            cur.execute("SELECT COUNT(*) FROM paciente")
            res_pacientes = cur.fetchone()
            stats['total_pacientes'] = res_pacientes[0] if res_pacientes else 0

            # 2. Citas programadas para hoy (excluyendo canceladas)
            cur.execute("""
                SELECT COUNT(*) 
                FROM cita_detalle cd
                JOIN estado_cita ec ON cd.id_estado_cita = ec.id_estado_cita
                WHERE cd.fecha_cita = CURRENT_DATE 
                  AND ec.descripcion <> 'Cancelado'
            """)
            res_citas = cur.fetchone()
            stats['citas_hoy'] = res_citas[0] if res_citas else 0

            # 3. Consultas realizadas en el mes actual
            cur.execute("""
                SELECT COUNT(*) 
                FROM consultas_cab 
                WHERE activo = true 
                  AND EXTRACT(MONTH FROM fecha_cita) = EXTRACT(MONTH FROM CURRENT_DATE)
                  AND EXTRACT(YEAR FROM fecha_cita) = EXTRACT(YEAR FROM CURRENT_DATE)
            """)
            res_consultas = cur.fetchone()
            stats['consultas_mes'] = res_consultas[0] if res_consultas else 0

            # 4. Médicos activos
            cur.execute("SELECT COUNT(*) FROM medico")
            res_medicos = cur.fetchone()
            stats['medicos_activos'] = res_medicos[0] if res_medicos else 0

        except Exception as e:
            app.logger.error(f"Error al obtener estadísticas del dashboard: {str(e)}")
        finally:
            cur.close()
            con.close()
        return stats

    def obtener_citas_hoy(self):
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        citas = []
        try:
            sql = """
                SELECT 
                    to_char(cd.hora_cita, 'HH24:MI') as hora,
                    p.nombre || ' ' || p.apellido as paciente,
                    m.nombre || ' ' || m.apellido as medico,
                    COALESCE(e.nombre_especialidad, 'Odontología') as especialidad,
                    ec.descripcion as estado
                FROM cita_detalle cd
                JOIN cita_cabecera cc ON cd.id_cita_cabecera = cc.id_cita_cabecera
                JOIN paciente p ON cc.id_paciente = p.id_paciente
                JOIN agenda_cabecera ac ON cc.id_agenda_cabecera = ac.id_agenda_cabecera
                JOIN medico m ON ac.id_medico = m.id_medico
                LEFT JOIN especialidades e ON ac.id_especialidad = e.id_especialidad
                JOIN estado_cita ec ON cd.id_estado_cita = ec.id_estado_cita
                WHERE cd.fecha_cita = CURRENT_DATE
                ORDER BY cd.hora_cita ASC
            """
            cur.execute(sql)
            rows = cur.fetchall()
            for r in rows:
                citas.append({
                    'hora': r[0] or '--:--',
                    'paciente': r[1],
                    'medico': r[2],
                    'especialidad': r[3],
                    'estado': r[4]
                })
        except Exception as e:
            app.logger.error(f"Error al obtener citas de hoy: {str(e)}")
        finally:
            cur.close()
            con.close()
        return citas

    def obtener_consultas_meses(self):
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        meses_nombres = {
            1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
            7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Oct', 11: 'Nov', 12: 'Dic'
        }
        labels = []
        valores = []
        try:
            cur.execute("""
                SELECT 
                    EXTRACT(YEAR FROM fecha_cita)::int as anio,
                    EXTRACT(MONTH FROM fecha_cita)::int as mes,
                    COUNT(*) as total
                FROM consultas_cab
                WHERE activo = true AND fecha_cita IS NOT NULL
                GROUP BY anio, mes
            """)
            conteo_db = {(r[0], r[1]): r[2] for r in cur.fetchall()}

            today = datetime.date.today()
            for i in range(5, -1, -1):
                m = today.month - i
                y = today.year
                while m <= 0:
                    m += 12
                    y -= 1
                labels.append(f"{meses_nombres[m]} {y}")
                valores.append(conteo_db.get((y, m), 0))
        except Exception as e:
            app.logger.error(f"Error al obtener consultas por mes: {str(e)}")
            labels = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun']
            valores = [0, 0, 0, 0, 0, 0]
        finally:
            cur.close()
            con.close()
        return {'labels': labels, 'valores': valores}

    def obtener_pacientes_recientes(self):
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        pacientes = []
        try:
            sql = """
                SELECT id_paciente, nombre, apellido, fecha_registro, telefono, correo
                FROM paciente
                ORDER BY id_paciente DESC
                LIMIT 5
            """
            cur.execute(sql)
            rows = cur.fetchall()
            now = datetime.datetime.now()
            for r in rows:
                f_reg = r[3]
                if f_reg:
                    diff_days = (now.date() - f_reg.date()).days
                    if diff_days == 0:
                        fecha_relativa = "Registrado/a hoy"
                        badge_color = "success"
                    elif diff_days == 1:
                        fecha_relativa = "Registrado/a ayer"
                        badge_color = "info"
                    elif diff_days < 7:
                        fecha_relativa = f"Hace {diff_days} días"
                        badge_color = "primary"
                    elif diff_days < 30:
                        fecha_relativa = "Este mes"
                        badge_color = "secondary"
                    else:
                        fecha_relativa = f"Registrado el {f_reg.strftime('%d/%m/%Y')}"
                        badge_color = "light"
                else:
                    fecha_relativa = "Registrado recientemente"
                    badge_color = "light"

                nom = r[1] or ''
                ape = r[2] or ''
                iniciales = f"{nom[0] if nom else ''}{ape[0] if ape else ''}".upper() or 'P'

                pacientes.append({
                    'id_paciente': r[0],
                    'nombre_completo': f"{nom} {ape}".strip(),
                    'iniciales': iniciales,
                    'fecha_relativa': fecha_relativa,
                    'badge_color': badge_color,
                    'telefono': r[4] or '',
                    'correo': r[5] or ''
                })
        except Exception as e:
            app.logger.error(f"Error al obtener pacientes recientes: {str(e)}")
        finally:
            cur.close()
            con.close()
        return pacientes

    def obtener_datos_dashboard(self):
        return {
            'saludo': self.obtener_saludo(),
            'stats': self.obtener_estadisticas(),
            'citas_hoy': self.obtener_citas_hoy(),
            'grafico_consultas': self.obtener_consultas_meses(),
            'pacientes_recientes': self.obtener_pacientes_recientes()
        }
