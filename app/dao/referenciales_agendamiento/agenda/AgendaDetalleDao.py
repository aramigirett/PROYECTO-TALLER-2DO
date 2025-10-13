from flask import current_app as app
from app.conexion.Conexion import Conexion

class AgendaDetalleDao:

    def getDetallesPorCabecera(self, id_agenda_cabecera):
        """Obtiene todos los detalles de una cabecera específica"""
        sql = """
        SELECT 
            ad.id_agenda_detalle,
            ad.id_agenda_cabecera,
            ad.id_disponibilidad_horaria,
            ad.id_dia,
            dia.descripcion AS des_dia,
            ad.id_turno,
            t.descripcion AS des_turno,
            ad.hora_inicio,
            ad.hora_fin,
            ad.cupos_disponibles,
            ad.cupos_maximos,
            ad.estado_detalle
        FROM agenda_detalle ad
        JOIN dias dia ON ad.id_dia = dia.id_dia
        JOIN turnos t ON ad.id_turno = t.id_turno
        WHERE ad.id_agenda_cabecera = %s
        ORDER BY ad.hora_inicio
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_agenda_cabecera,))
            rows = cur.fetchall()
            return [
                {
                    'id_agenda_detalle': r[0],
                    'id_agenda_cabecera': r[1],
                    'id_disponibilidad_horaria': r[2],
                    'id_dia': r[3],
                    'des_dia': r[4],
                    'id_turno': r[5],
                    'des_turno': r[6],
                    'hora_inicio': str(r[7]),
                    'hora_fin': str(r[8]),
                    'cupos_disponibles': r[9],
                    'cupos_maximos': r[10],
                    'estado_detalle': r[11]
                } for r in rows
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener detalles: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getDetalleById(self, id_agenda_detalle):
        """Obtiene un detalle específico por ID"""
        sql = """
        SELECT 
            ad.id_agenda_detalle,
            ad.id_agenda_cabecera,
            ad.id_disponibilidad_horaria,
            ad.id_dia,
            dia.descripcion AS des_dia,
            ad.id_turno,
            t.descripcion AS des_turno,
            ad.hora_inicio,
            ad.hora_fin,
            ad.cupos_disponibles,
            ad.cupos_maximos,
            ad.estado_detalle
        FROM agenda_detalle ad
        JOIN dias dia ON ad.id_dia = dia.id_dia
        JOIN turnos t ON ad.id_turno = t.id_turno
        WHERE ad.id_agenda_detalle = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_agenda_detalle,))
            r = cur.fetchone()
            if r:
                return {
                    'id_agenda_detalle': r[0],
                    'id_agenda_cabecera': r[1],
                    'id_disponibilidad_horaria': r[2],
                    'id_dia': r[3],
                    'des_dia': r[4],
                    'id_turno': r[5],
                    'des_turno': r[6],
                    'hora_inicio': str(r[7]),
                    'hora_fin': str(r[8]),
                    'cupos_disponibles': r[9],
                    'cupos_maximos': r[10],
                    'estado_detalle': r[11]
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener detalle: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDetalle(self, id_agenda_cabecera, id_disponibilidad_horaria):
        """Valida si ya existe un detalle con esa disponibilidad en la cabecera"""
        sql = """
        SELECT id_agenda_detalle
        FROM agenda_detalle
        WHERE id_agenda_cabecera = %s AND id_disponibilidad_horaria = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_agenda_cabecera, id_disponibilidad_horaria))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error en existeDetalle: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarDetalle(self, id_agenda_cabecera, disponibilidad):
        """
        Crea un detalle copiando los datos de una disponibilidad.
        disponibilidad es un dict con los datos de DisponibilidadDao.getDisponibilidadById()
        """
        # Validar que no esté duplicado
        if self.existeDetalle(id_agenda_cabecera, disponibilidad['id_disponibilidad']):
            app.logger.warning(f"Detalle duplicado: cabecera {id_agenda_cabecera}, disponibilidad {disponibilidad['id_disponibilidad']}")
            return False

        sql = """
        INSERT INTO agenda_detalle(
            id_agenda_cabecera,
            id_disponibilidad_horaria,
            id_dia,
            id_turno,
            hora_inicio,
            hora_fin,
            cupos_disponibles,
            cupos_maximos,
            estado_detalle
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id_agenda_detalle
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cupos = disponibilidad['dispo_cupos']
            
            cur.execute(sql, (
                id_agenda_cabecera,
                disponibilidad['id_disponibilidad'],
                disponibilidad['id_dia'],
                disponibilidad['id_turno'],
                disponibilidad['dispo_hora_inicio'],
                disponibilidad['dispo_hora_fin'],
                cupos,  # cupos_disponibles
                cupos,  # cupos_maximos
                'Disponible'  # estado inicial
            ))
            new_id = cur.fetchone()[0]
            con.commit()
            return new_id
        except Exception as e:
            app.logger.error(f"Error al insertar detalle: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def guardarDetallesMultiples(self, id_agenda_cabecera, lista_disponibilidades):
        """
        Guarda múltiples detalles a la vez.
        lista_disponibilidades es una lista de dicts de disponibilidades.
        Retorna lista de IDs creados o False si hubo error.
        """
        ids_creados = []
        for disponibilidad in lista_disponibilidades:
            detalle_id = self.guardarDetalle(id_agenda_cabecera, disponibilidad)
            if detalle_id:
                ids_creados.append(detalle_id)
            else:
                # Si uno falla, podrías hacer rollback de todos
                # Por ahora continúa con los demás
                app.logger.warning(f"No se pudo guardar detalle para disponibilidad {disponibilidad.get('id_disponibilidad')}")
        
        return ids_creados if ids_creados else False

    def deleteDetalle(self, id_agenda_detalle):
        """Elimina un detalle específico"""
        sql = "DELETE FROM agenda_detalle WHERE id_agenda_detalle=%s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_agenda_detalle,))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except Exception as e:
            app.logger.error(f"Error al eliminar detalle: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def actualizarCuposDisponibles(self, id_agenda_detalle, nuevos_cupos):
        """Actualiza los cupos disponibles (cuando se reserva una cita)"""
        sql = """
        UPDATE agenda_detalle
        SET cupos_disponibles = %s,
            estado_detalle = CASE 
                WHEN %s = 0 THEN 'Agotado'
                ELSE 'Disponible'
            END
        WHERE id_agenda_detalle = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nuevos_cupos, nuevos_cupos, id_agenda_detalle))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar cupos: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def cambiarEstadoDetalle(self, id_agenda_detalle, nuevo_estado):
        """Cambia el estado de un detalle (Disponible/Agotado/Cancelado)"""
        sql = "UPDATE agenda_detalle SET estado_detalle=%s WHERE id_agenda_detalle=%s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nuevo_estado, id_agenda_detalle))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except Exception as e:
            app.logger.error(f"Error al cambiar estado detalle: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()