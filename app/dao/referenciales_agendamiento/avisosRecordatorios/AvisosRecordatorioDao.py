from flask import current_app as app
from app.conexion.Conexion import Conexion
from datetime import datetime

class AvisoRecordatorioDao:

    # ==============================
    #   LISTAR TODOS LOS AVISOS
    # ==============================
    def getAvisos(self):
        sql = """
        SELECT a.id_aviso,
               p.nombre || ' ' || p.apellido AS paciente,
               p.telefono AS telefono_paciente,
               f.nombre || ' ' || f.apellido AS funcionario,
               COALESCE(m.nombre || ' ' || m.apellido, 'Sin médico') AS medico,
               COALESCE(c.nombre_consultorio, 'Sin consultorio') AS nombre_consultorio,
               a.fecha_cita,
               a.hora_cita,
               a.forma_envio,
               a.mensaje,
               a.estado_envio,
               a.estado_confirmacion,
               a.id_paciente,
               a.id_funcionario,
               a.id_medico,
               a.codigo
        FROM avisos_recordatorios a
        JOIN paciente p ON a.id_paciente = p.id_paciente
        JOIN funcionario f ON a.id_funcionario = f.id_funcionario
        LEFT JOIN medico m ON a.id_medico = m.id_medico
        LEFT JOIN consultorio c ON a.codigo = c.codigo
        ORDER BY a.fecha_cita DESC, a.hora_cita DESC;
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            
            app.logger.info(f"🔍 Total avisos encontrados: {len(rows)}")
            
            avisos = []
            for row in rows:
                aviso = {
                    'id_aviso': row[0],
                    'paciente': row[1],
                    'telefono_paciente': row[2],
                    'funcionario': row[3],
                    'medico': row[4],
                    'nombre_consultorio': row[5],
                    'fecha_cita': row[6].isoformat() if row[6] else None,
                    'hora_cita': row[7].strftime("%H:%M") if row[7] else None,
                    'forma_envio': row[8],
                    'mensaje': row[9],
                    'estado_envio': row[10],
                    'estado_confirmacion': row[11],
                    'id_paciente': row[12],
                    'id_funcionario': row[13],
                    'id_medico': row[14],
                    'codigo': row[15]
                }
                avisos.append(aviso)
            
            app.logger.info(f"✅ Avisos procesados correctamente")
            return avisos
            
        except Exception as e:
            app.logger.error(f"❌ Error en AvisoRecordatorioDao.getAvisos: {e}")
            import traceback
            app.logger.error(traceback.format_exc())
            return []
        finally:
            cur.close()
            con.close()

    # ==============================
    #   OBTENER UN AVISO POR ID
    # ==============================
    def getAvisoById(self, id_aviso):
        sql = """
        SELECT a.id_aviso,
            p.id_paciente,
            p.nombre || ' ' || p.apellido AS paciente,
            p.telefono AS telefono_paciente,
            f.id_funcionario,
            f.nombre || ' ' || f.apellido AS funcionario,
            a.id_medico,
            COALESCE(m.nombre || ' ' || m.apellido, 'Sin médico') AS medico,
            a.codigo,
            COALESCE(c.nombre_consultorio, 'Sin consultorio') AS nombre_consultorio,
            a.fecha_cita,
            a.hora_cita,
            a.forma_envio,
            a.mensaje,
            a.estado_envio,
            a.estado_confirmacion
        FROM avisos_recordatorios a
        JOIN paciente p ON a.id_paciente = p.id_paciente
        JOIN funcionario f ON a.id_funcionario = f.id_funcionario
        LEFT JOIN medico m ON a.id_medico = m.id_medico
        LEFT JOIN consultorio c ON a.codigo = c.codigo
        WHERE a.id_aviso = %s;
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_aviso,))
            row = cur.fetchone()
            if not row:
                return None

            aviso = {
                'id_aviso': row[0],
                'id_paciente': row[1],
                'paciente': row[2],
                'telefono_paciente': row[3],
                'id_funcionario': row[4],
                'funcionario': row[5],
                'id_medico': row[6],
                'medico': row[7],
                'codigo': row[8],
                'nombre_consultorio': row[9],
                'fecha_cita': row[10].isoformat() if row[10] else None,
                'hora_cita': row[11].strftime("%H:%M") if row[11] else None,
                'forma_envio': row[12],
                'mensaje': row[13],
                'estado_envio': row[14],
                'estado_confirmacion': row[15]
            }
            
            return aviso
            
        except Exception as e:
            app.logger.error(f"❌ Error en AvisoRecordatorioDao.getAvisoById: {e}")
            import traceback
            app.logger.error(traceback.format_exc())
            return None
        finally:
            cur.close()
            con.close()

    # ==============================
    #   AGREGAR AVISO
    # ==============================
    def addAviso(self, aviso):
        sql = """
        INSERT INTO avisos_recordatorios (
            id_paciente, id_funcionario, id_medico, codigo,
            fecha_cita, hora_cita,
            forma_envio, mensaje, estado_envio, estado_confirmacion
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id_aviso;
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            fecha_cita = aviso.get("fecha_cita")
            if fecha_cita:
                fecha_cita = datetime.strptime(fecha_cita, "%Y-%m-%d").date()

            hora_cita = aviso.get("hora_cita")
            if hora_cita:
                hora_cita = datetime.strptime(hora_cita, "%H:%M").time()

            # ✅ Sanitizar codigo
            codigo = aviso.get("codigo")
            if codigo in ("", None):
                codigo = None
            else:
                codigo = int(codigo)

            # ✅ Sanitizar id_medico
            id_medico = aviso.get("id_medico")
            if id_medico in ("", None):
                id_medico = None
            else:
                id_medico = int(id_medico)

            cur.execute(sql, (
                aviso["id_paciente"],
                aviso["id_funcionario"],
                id_medico,
                codigo,
                fecha_cita,
                hora_cita,
                aviso["forma_envio"],
                aviso.get("mensaje", ""),
                aviso.get("estado_envio", "Pendiente"),
                aviso.get("estado_confirmacion", "Pendiente")
            ))
            id_aviso = cur.fetchone()[0]
            con.commit()
            
            app.logger.info(f"✅ Aviso creado con ID: {id_aviso}")
            return id_aviso
            
        except Exception as e:
            con.rollback()
            app.logger.error(f"❌ Error en AvisoRecordatorioDao.addAviso: {e}")
            import traceback
            app.logger.error(traceback.format_exc())
            return None
        finally:
            cur.close()
            con.close()

    # ==============================
    #   ACTUALIZAR AVISO
    # ==============================
    def updateAviso(self, id_aviso, aviso):
        app.logger.info(f"🔄 Actualizando aviso {id_aviso}")
        
        # ✅ Primero obtenemos el aviso actual para preservar campos
        aviso_actual = self.getAvisoById(id_aviso)
        if not aviso_actual:
            app.logger.error(f"❌ No se encontró el aviso {id_aviso}")
            return False
        
        # ✅ Usar valores del aviso actual como fallback
        id_paciente = aviso.get("id_paciente", aviso_actual.get("id_paciente"))
        id_funcionario = aviso.get("id_funcionario", aviso_actual.get("id_funcionario"))
        id_medico = aviso.get("id_medico", aviso_actual.get("id_medico"))
        codigo = aviso.get("codigo", aviso_actual.get("codigo"))
        fecha_cita = aviso.get("fecha_cita", aviso_actual.get("fecha_cita"))
        hora_cita = aviso.get("hora_cita", aviso_actual.get("hora_cita"))
        forma_envio = aviso.get("forma_envio", aviso_actual.get("forma_envio"))
        estado_envio = aviso.get("estado_envio", aviso_actual.get("estado_envio", "Pendiente"))
        estado_confirmacion = aviso.get("estado_confirmacion", aviso_actual.get("estado_confirmacion", "Pendiente"))
        
        # ✅ CRÍTICO: El mensaje puede venir como string vacío '' o None
        if 'mensaje' in aviso:
            mensaje = aviso['mensaje'] if aviso['mensaje'] is not None else ''
        else:
            mensaje = aviso_actual.get('mensaje', '')
        
        sql = """
        UPDATE avisos_recordatorios SET
            id_paciente = %s,
            id_funcionario = %s,
            id_medico = %s,
            codigo = %s,
            fecha_cita = %s,
            hora_cita = %s,
            forma_envio = %s,
            mensaje = %s,
            estado_envio = %s,
            estado_confirmacion = %s
        WHERE id_aviso = %s;
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            # Procesar fecha_cita
            if fecha_cita:
                if isinstance(fecha_cita, str):
                    fecha_cita = datetime.strptime(fecha_cita, "%Y-%m-%d").date()

            # Procesar hora_cita
            if hora_cita:
                if isinstance(hora_cita, str):
                    hora_cita = datetime.strptime(hora_cita, "%H:%M").time()

            # Sanitizar codigo
            if codigo in ("", None):
                codigo = None
            else:
                codigo = int(codigo)

            # Sanitizar id_medico
            if id_medico in ("", None):
                id_medico = None
            else:
                id_medico = int(id_medico)

            cur.execute(sql, (
                id_paciente,
                id_funcionario,
                id_medico,
                codigo,
                fecha_cita,
                hora_cita,
                forma_envio,
                mensaje,
                estado_envio,
                estado_confirmacion,
                id_aviso
            ))
            
            filas_afectadas = cur.rowcount
            con.commit()
            
            app.logger.info(f"✅ Aviso {id_aviso} actualizado. Filas afectadas: {filas_afectadas}")
            return True
            
        except Exception as e:
            con.rollback()
            app.logger.error(f"❌ Error en AvisoRecordatorioDao.updateAviso {id_aviso}: {e}")
            import traceback
            app.logger.error(traceback.format_exc())
            return False
        finally:
            cur.close()
            con.close()

    # ==============================
    #   ELIMINAR AVISO
    # ==============================
    def deleteAviso(self, id_aviso):
        sql = "DELETE FROM avisos_recordatorios WHERE id_aviso = %s;"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_aviso,))
            con.commit()
            app.logger.info(f"✅ Aviso {id_aviso} eliminado correctamente")
            return True
        except Exception as e:
            con.rollback()
            app.logger.error(f"❌ Error en AvisoRecordatorioDao.deleteAviso {id_aviso}: {e}")
            import traceback
            app.logger.error(traceback.format_exc())
            return False
        finally:
            cur.close()
            con.close()