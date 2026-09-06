from flask import current_app as app
from app.conexion.Conexion import Conexion
from app.dao.referenciales_agendamiento.agenda.AgendaDetalleDao import AgendaDetalleDao

class AgendaCabeceraDao:

    def getCabeceras(self):
        """Obtiene todas las cabeceras de agenda con datos relacionados"""
        sql = """
        SELECT
            ac.id_agenda_cabecera,
            ac.id_medico,
            (m.nombre || ' ' || m.apellido) AS medico_nombre,
            ac.id_especialidad,
            e.nombre_especialidad AS especialidad,
            ac.id_consultorio,
            co.nombre_consultorio,
            ac.fecha_agenda,
            ac.estado,
            ac.id_funcionario,
            ac.fecha_registro,
            ac.observaciones
        FROM agenda_cabecera ac
        JOIN medico m ON ac.id_medico = m.id_medico
        JOIN especialidades e ON ac.id_especialidad = e.id_especialidad
        JOIN consultorio co ON ac.id_consultorio = co.codigo
        WHERE ac.estado <> 'Inactivo'
        ORDER BY ac.fecha_agenda DESC, ac.id_agenda_cabecera DESC
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            return [
                {
                    'id_agenda_cabecera': r[0],
                    'id_medico': r[1],
                    'medico_nombre': r[2],
                    'id_especialidad': r[3],
                    'especialidad': r[4],
                    'id_consultorio': r[5],
                    'nombre_consultorio': r[6],
                    'fecha_agenda': str(r[7]),
                    'estado': r[8],
                    'id_funcionario': r[9],
                    'fecha_registro': str(r[10]) if r[10] else None,
                    'observaciones': r[11]
                } for r in rows
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener cabeceras: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getCabeceraById(self, id_agenda_cabecera):
        """Obtiene una cabecera por ID"""
        sql = """
        SELECT
            ac.id_agenda_cabecera,
            ac.id_medico,
            (m.nombre || ' ' || m.apellido) AS medico_nombre,
            ac.id_especialidad,
            e.nombre_especialidad AS especialidad,
            ac.id_consultorio,
            co.nombre_consultorio,
            ac.fecha_agenda,
            ac.estado,
            ac.id_funcionario,
            ac.fecha_registro,
            ac.observaciones
        FROM agenda_cabecera ac
        JOIN medico m ON ac.id_medico = m.id_medico
        JOIN especialidades e ON ac.id_especialidad = e.id_especialidad
        JOIN consultorio co ON ac.id_consultorio = co.codigo
        WHERE ac.id_agenda_cabecera = %s AND ac.estado <> 'Inactivo'
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_agenda_cabecera,))
            r = cur.fetchone()
            if r:
                return {
                    'id_agenda_cabecera': r[0],
                    'id_medico': r[1],
                    'medico_nombre': r[2],
                    'id_especialidad': r[3],
                    'especialidad': r[4],
                    'id_consultorio': r[5],
                    'nombre_consultorio': r[6],
                    'fecha_agenda': str(r[7]),
                    'estado': r[8],
                    'id_funcionario': r[9],
                    'fecha_registro': str(r[10]) if r[10] else None,
                    'observaciones': r[11]
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener cabecera: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeCabecera(self, id_medico, fecha_agenda, excluir_id=None):
        """
        Valida si ya existe una cabecera para ese médico en esa fecha.
        Un médico solo puede tener UNA agenda por día.
        """
        sql = """
        SELECT id_agenda_cabecera
        FROM agenda_cabecera
        WHERE id_medico = %s AND fecha_agenda = %s AND estado <> 'Inactivo'
        """
        params = [id_medico, fecha_agenda]
        
        if excluir_id:
            sql += " AND id_agenda_cabecera != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error en existeCabecera: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarCabecera(self, id_medico, id_especialidad, id_consultorio, fecha_agenda, estado, id_funcionario, observaciones=None):
        """Crea una nueva cabecera de agenda"""
        # Validar duplicado
        if self.existeCabecera(id_medico, fecha_agenda):
            app.logger.warning(f"Ya existe agenda para médico {id_medico} en fecha {fecha_agenda}")
            return False

        sql = """
        INSERT INTO agenda_cabecera(
            id_medico, id_especialidad, id_consultorio, fecha_agenda, estado, id_funcionario, observaciones
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id_agenda_cabecera
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_medico, id_especialidad, id_consultorio, fecha_agenda, estado, id_funcionario, observaciones))
            new_id = cur.fetchone()[0]
            con.commit()
            return new_id
        except Exception as e:
            app.logger.error(f"Error al insertar cabecera: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateCabecera(self, id_agenda_cabecera, id_medico, id_especialidad, id_consultorio, fecha_agenda, estado, id_funcionario, observaciones=None):
        """Actualiza una cabecera existente"""
        # Validar duplicado (excluyendo el registro actual)
        if self.existeCabecera(id_medico, fecha_agenda, excluir_id=id_agenda_cabecera):
            app.logger.warning(f"Ya existe otra agenda para médico {id_medico} en fecha {fecha_agenda}")
            return False

        sql = """
        UPDATE agenda_cabecera
        SET id_medico=%s, id_especialidad=%s, id_consultorio=%s, fecha_agenda=%s,
            estado=%s, id_funcionario=%s, observaciones=%s
        WHERE id_agenda_cabecera=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_medico, id_especialidad, id_consultorio, fecha_agenda, estado, id_funcionario, observaciones, id_agenda_cabecera))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar cabecera: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def deleteCabecera(self, id_agenda_cabecera):
        """
        Anula (baja lógica) una cabecera de agenda y, en cascada, todos
        sus detalles (agenda_detalle) asociados.
        """
        sql = "UPDATE agenda_cabecera SET estado='Inactivo' WHERE id_agenda_cabecera=%s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_agenda_cabecera,))
            filas = cur.rowcount
            con.commit()
            if filas > 0:
                AgendaDetalleDao().cancelarDetallesPorCabecera(id_agenda_cabecera)
            return filas > 0
        except Exception as e:
            app.logger.error(f"Error al anular cabecera: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def cambiarEstado(self, id_agenda_cabecera, nuevo_estado):
        """Cambia el estado de una cabecera (Activo/Inactivo)"""
        sql = "UPDATE agenda_cabecera SET estado=%s WHERE id_agenda_cabecera=%s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nuevo_estado, id_agenda_cabecera))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except Exception as e:
            app.logger.error(f"Error al cambiar estado: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()