from flask import current_app as app
from app.conexion.Conexion import Conexion

class OdontogramaDao:
    """
    DAO para gestionar Odontogramas
    Maneja cabecera (odontograma) y detalle (dientes/superficies)
    """

    # ========================================
    # GESTIÓN DE ESTADOS DENTALES
    # ========================================

    def getEstadosDentales(self):
        """
        Obtiene todos los estados dentales activos
        Retorna lista de diccionarios con id, descripcion, color, simbolo
        """
        sql = """
        SELECT 
            id_estado_dental,
            descripcion,
            color,
            simbolo,
            activo
        FROM estado_dental
        WHERE activo = TRUE
        ORDER BY descripcion
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            return [
                {
                    'id_estado_dental': r[0],
                    'descripcion': r[1],
                    'color': r[2],
                    'simbolo': r[3],
                    'activo': r[4]
                } for r in rows
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener estados dentales: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getEstadoDentalById(self, id_estado_dental):
        """Obtiene un estado dental específico por ID"""
        sql = """
        SELECT 
            id_estado_dental,
            descripcion,
            color,
            simbolo,
            activo
        FROM estado_dental
        WHERE id_estado_dental = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_estado_dental,))
            r = cur.fetchone()
            if r:
                return {
                    'id_estado_dental': r[0],
                    'descripcion': r[1],
                    'color': r[2],
                    'simbolo': r[3],
                    'activo': r[4]
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener estado dental: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    # ========================================
    # ODONTOGRAMA CABECERA - CRUD
    # ========================================

    def getOdontogramas(self):
        """
        Obtiene todos los odontogramas con información relacionada
        """
        sql = """
        SELECT 
            o.id_odontograma,
            o.id_paciente,
            (p.nombre || ' ' || p.apellido) AS paciente_nombre,
            p.cedula_entidad AS paciente_cedula,
            EXTRACT(YEAR FROM AGE(p.fecha_nacimiento)) AS paciente_edad,
            o.id_medico,
            (m.nombre || ' ' || m.apellido) AS medico_nombre,
            o.fecha_registro,
            o.observaciones,
            o.estado,
            o.id_consulta_cab,
            o.created_at,
            o.updated_at
        FROM odontograma o
        JOIN paciente p ON o.id_paciente = p.id_paciente
        JOIN medico m ON o.id_medico = m.id_medico
        WHERE o.activo = true
        ORDER BY o.fecha_registro DESC, o.id_odontograma DESC
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            return [
                {
                    'id_odontograma': r[0],
                    'id_paciente': r[1],
                    'paciente': r[2],
                    'cedula': r[3],
                    'edad': int(r[4]) if r[4] else 0,
                    'id_medico': r[5],
                    'medico': r[6],
                    'fecha_registro': str(r[7]) if r[7] else None,
                    'observaciones': r[8],
                    'estado': r[9],
                    'id_consulta_cab': r[10],
                    'created_at': str(r[11]) if r[11] else None,
                    'updated_at': str(r[12]) if r[12] else None
                } for r in rows
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener odontogramas: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getOdontogramaById(self, id_odontograma):
        """
        Obtiene un odontograma específico por ID
        """
        sql = """
        SELECT 
            o.id_odontograma,
            o.id_paciente,
            (p.nombre || ' ' || p.apellido) AS paciente_nombre,
            p.cedula_entidad AS paciente_cedula,
            EXTRACT(YEAR FROM AGE(p.fecha_nacimiento)) AS paciente_edad,
            o.id_medico,
            (m.nombre || ' ' || m.apellido) AS medico_nombre,
            o.fecha_registro,
            o.observaciones,
            o.estado,
            o.id_consulta_cab,
            o.created_at,
            o.updated_at
        FROM odontograma o
        JOIN paciente p ON o.id_paciente = p.id_paciente
        JOIN medico m ON o.id_medico = m.id_medico
        WHERE o.id_odontograma = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_odontograma,))
            r = cur.fetchone()
            if r:
                return {
                    'id_odontograma': r[0],
                    'id_paciente': r[1],
                    'paciente': r[2],
                    'cedula': r[3],
                    'edad': int(r[4]) if r[4] else 0,
                    'id_medico': r[5],
                    'medico': r[6],
                    'fecha_registro': str(r[7]) if r[7] else None,
                    'observaciones': r[8],
                    'estado': r[9],
                    'id_consulta_cab': r[10],
                    'created_at': str(r[11]) if r[11] else None,
                    'updated_at': str(r[12]) if r[12] else None
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener odontograma: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def getOdontogramasByPaciente(self, id_paciente):
        """
        Obtiene todos los odontogramas de un paciente específico
        Ordenados del más reciente al más antiguo
        """
        sql = """
        SELECT 
            o.id_odontograma,
            o.id_paciente,
            (p.nombre || ' ' || p.apellido) AS paciente_nombre,
            p.cedula_entidad AS paciente_cedula,
            EXTRACT(YEAR FROM AGE(p.fecha_nacimiento)) AS paciente_edad,
            o.id_medico,
            (m.nombre || ' ' || m.apellido) AS medico_nombre,
            o.fecha_registro,
            o.observaciones,
            o.estado,
            o.id_consulta_cab
        FROM odontograma o
        JOIN paciente p ON o.id_paciente = p.id_paciente
        JOIN medico m ON o.id_medico = m.id_medico
        WHERE o.id_paciente = %s AND o.activo = true
        ORDER BY o.fecha_registro DESC
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_paciente,))
            rows = cur.fetchall()
            return [
                {
                    'id_odontograma': r[0],
                    'id_paciente': r[1],
                    'paciente': r[2],
                    'cedula': r[3],
                    'edad': int(r[4]) if r[4] else 0,
                    'id_medico': r[5],
                    'medico': r[6],
                    'fecha_registro': str(r[7]) if r[7] else None,
                    'observaciones': r[8],
                    'estado': r[9],
                    'id_consulta_cab': r[10]
                } for r in rows
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener odontogramas del paciente: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def guardarOdontograma(self, id_consulta_cab, fecha_registro,
                           observaciones=None, estado='Activo'):
        """
        Crea un nuevo odontograma (cabecera) para una Consulta. Hay UNO por
        consulta (único parcial ux_odontograma_consulta_vigente).

        Paciente y Médico se derivan de la consulta (no se toman del
        formulario). La consulta tiene que existir, estar activa y no estar
        finalizada.

        Retorna un dict: {'id_odontograma': N} o {'error': 'CONSULTA_NO_ENCONTRADA'
        | 'CONSULTA_FINALIZADA' | 'YA_EXISTE' | 'ERROR_INTERNO'}
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("""
                SELECT id_paciente, id_medico, estado
                FROM consultas_cab
                WHERE id_consulta_cab = %s AND activo = true
                FOR UPDATE
            """, (id_consulta_cab,))
            consulta = cur.fetchone()
            if not consulta:
                con.rollback()
                return {'error': 'CONSULTA_NO_ENCONTRADA'}
            id_paciente, id_medico, estado_consulta = consulta
            if estado_consulta == 'finalizada':
                con.rollback()
                return {'error': 'CONSULTA_FINALIZADA'}

            cur.execute("""
                SELECT 1 FROM odontograma
                WHERE id_consulta_cab = %s AND activo = true
            """, (id_consulta_cab,))
            if cur.fetchone():
                con.rollback()
                return {'error': 'YA_EXISTE'}

            cur.execute("""
                INSERT INTO odontograma(
                    id_paciente, id_medico, id_consulta_cab,
                    fecha_registro, observaciones, estado
                ) VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id_odontograma
            """, (id_paciente, id_medico, id_consulta_cab, fecha_registro, observaciones, estado))
            new_id = cur.fetchone()[0]
            con.commit()

            app.logger.info(f"Odontograma creado con ID: {new_id}")
            return {'id_odontograma': new_id}
        except Exception as e:
            app.logger.error(f"Error al guardar odontograma: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()

    def getOdontogramaVigentePaciente(self, id_paciente, excluir_consulta=None):
        """
        Odontograma vigente de un paciente: el de su ÚLTIMA consulta (por fecha
        y hora de la consulta) entre los que no están Inactivos. excluir_consulta
        permite ignorar la consulta que se está registrando.
        Devuelve la cabecera con sus 'detalles', o None si el paciente no tiene.
        """
        sql = """
        SELECT o.id_odontograma
        FROM odontograma o
        JOIN consultas_cab c ON c.id_consulta_cab = o.id_consulta_cab
        WHERE o.id_paciente = %s
          AND o.activo = true
          AND (%s::int IS NULL OR o.id_consulta_cab <> %s::int)
        ORDER BY c.fecha_cita DESC, c.hora_cita DESC, o.id_odontograma DESC
        LIMIT 1
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_paciente, excluir_consulta, excluir_consulta))
            fila = cur.fetchone()
        except Exception as e:
            app.logger.error(f"Error al buscar el odontograma vigente: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()
        if not fila:
            return None
        odontograma = self.getOdontogramaById(fila[0])
        if odontograma:
            odontograma['detalles'] = self.getDetallesPorOdontograma(fila[0])
        return odontograma

    def updateOdontograma(self, id_odontograma, fecha_registro, 
                         observaciones=None, estado='Activo'):
        """
        Actualiza un odontograma existente (solo cabecera)
        """
        sql = """
        UPDATE odontograma
        SET fecha_registro = %s,
            observaciones = %s,
            estado = %s
        WHERE id_odontograma = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            app.logger.info(f"🔄 Actualizando odontograma {id_odontograma}")
            
            cur.execute(sql, (
                fecha_registro,
                observaciones,
                estado,
                id_odontograma
            ))
            filas = cur.rowcount
            con.commit()
            
            if filas > 0:
                app.logger.info(f"✅ Odontograma {id_odontograma} actualizado")
            else:
                app.logger.warning(f"⚠️ Odontograma {id_odontograma} no encontrado")
            
            return filas > 0
        except Exception as e:
            app.logger.error(f"❌ Error al actualizar odontograma: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def deleteOdontograma(self, id_odontograma):
        """
        Anula (baja lógica) un odontograma: lo pasa a estado 'Inactivo'
        en vez de borrarlo físicamente, para no perder el historial clínico.
        """
        return self.cambiarEstadoOdontograma(id_odontograma, 'Inactivo')

    def cambiarEstadoOdontograma(self, id_odontograma, nuevo_estado):
        """
        Cambia el estado de un odontograma (Activo/Finalizado/Inactivo)
        """
        sql = "UPDATE odontograma SET estado = %s, activo = (%s <> 'Inactivo') WHERE id_odontograma = %s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nuevo_estado, nuevo_estado, id_odontograma))
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

    # ========================================
    # ODONTOGRAMA DETALLE - CRUD
    # ========================================

    def getDetallesPorOdontograma(self, id_odontograma):
        """
        Obtiene todos los detalles (dientes/superficies) de un odontograma
        """
        sql = """
        SELECT 
            od.id_odontograma_detalle,
            od.id_odontograma,
            od.numero_diente,
            od.id_estado_dental,
            ed.descripcion AS estado_descripcion,
            ed.color AS estado_color,
            ed.simbolo AS estado_simbolo,
            od.superficie,
            od.observacion,
            od.created_at
        FROM odontograma_detalle od
        JOIN estado_dental ed ON od.id_estado_dental = ed.id_estado_dental
        WHERE od.id_odontograma = %s
        ORDER BY od.numero_diente, od.superficie
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_odontograma,))
            rows = cur.fetchall()
            return [
                {
                    'id_odontograma_detalle': r[0],
                    'id_odontograma': r[1],
                    'numero_diente': r[2],
                    'id_estado_dental': r[3],
                    'estado_descripcion': r[4],
                    'color': r[5],
                    'simbolo': r[6],
                    'superficie': r[7],
                    'observacion': r[8],
                    'created_at': str(r[9]) if r[9] else None
                } for r in rows
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener detalles: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getDetalleById(self, id_odontograma_detalle):
        """Obtiene un detalle específico por ID"""
        sql = """
        SELECT 
            od.id_odontograma_detalle,
            od.id_odontograma,
            od.numero_diente,
            od.id_estado_dental,
            ed.descripcion AS estado_descripcion,
            ed.color AS estado_color,
            ed.simbolo AS estado_simbolo,
            od.superficie,
            od.observacion
        FROM odontograma_detalle od
        JOIN estado_dental ed ON od.id_estado_dental = ed.id_estado_dental
        WHERE od.id_odontograma_detalle = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_odontograma_detalle,))
            r = cur.fetchone()
            if r:
                return {
                    'id_odontograma_detalle': r[0],
                    'id_odontograma': r[1],
                    'numero_diente': r[2],
                    'id_estado_dental': r[3],
                    'estado_descripcion': r[4],
                    'color': r[5],
                    'simbolo': r[6],
                    'superficie': r[7],
                    'observacion': r[8]
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener detalle: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def guardarDetalle(self, id_odontograma, numero_diente, 
                      id_estado_dental, superficie, observacion=None):
        """
        Agrega un detalle al odontograma
        Si ya existe (mismo odontograma, diente, superficie y estado), lo actualiza
        """
        sql = """
        INSERT INTO odontograma_detalle(
            id_odontograma, numero_diente, id_estado_dental, 
            superficie, observacion
        ) VALUES (%s, %s, %s, %s, %s)
        RETURNING id_odontograma_detalle
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            app.logger.info(f"💾 Guardando detalle: Diente {numero_diente}, Superficie {superficie}")
            
            cur.execute(sql, (
                id_odontograma,
                numero_diente,
                id_estado_dental,
                superficie,
                observacion
            ))
            new_id = cur.fetchone()[0]
            con.commit()
            
            app.logger.info(f"✅ Detalle guardado con ID: {new_id}")
            return new_id
        except Exception as e:
            app.logger.error(f"❌ Error al guardar detalle: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def guardarDetallesMultiples(self, id_odontograma, lista_detalles):
        """
        Guarda múltiples detalles a la vez
        lista_detalles = [
            {'numero_diente': 11, 'id_estado_dental': 2, 'superficie': 'O'},
            ...
        ]
        """
        if not lista_detalles:
            return []

        ids_creados = []
        for detalle in lista_detalles:
            detalle_id = self.guardarDetalle(
                id_odontograma,
                detalle.get('numero_diente') or detalle.get('diente'),
                detalle.get('id_estado_dental') or detalle.get('estado'),
                detalle.get('superficie', 'C'),
                detalle.get('observacion')
            )
            if detalle_id:
                ids_creados.append(detalle_id)

        app.logger.info(f"✅ {len(ids_creados)} detalles guardados de {len(lista_detalles)} intentos")
        return ids_creados

    def updateDetalle(self, id_odontograma_detalle, id_estado_dental, 
                     superficie, observacion=None):
        """
        Actualiza un detalle existente
        """
        sql = """
        UPDATE odontograma_detalle
        SET id_estado_dental = %s,
            superficie = %s,
            observacion = %s
        WHERE id_odontograma_detalle = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (
                id_estado_dental,
                superficie,
                observacion,
                id_odontograma_detalle
            ))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar detalle: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def deleteDetalle(self, id_odontograma_detalle):
        """Elimina un detalle específico"""
        sql = "DELETE FROM odontograma_detalle WHERE id_odontograma_detalle = %s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_odontograma_detalle,))
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

    def deleteDetallesPorOdontograma(self, id_odontograma):
        """
        Elimina TODOS los detalles de un odontograma
        Útil para actualizar completamente un odontograma
        """
        sql = "DELETE FROM odontograma_detalle WHERE id_odontograma = %s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            app.logger.info(f"🗑️ Eliminando todos los detalles del odontograma {id_odontograma}")
            
            cur.execute(sql, (id_odontograma,))
            filas = cur.rowcount
            con.commit()
            
            app.logger.info(f"✅ {filas} detalles eliminados")
            return True
        except Exception as e:
            app.logger.error(f"❌ Error al eliminar detalles: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ========================================
    # MÉTODOS AUXILIARES Y VALIDACIONES
    # ========================================

    def existeOdontogramaConsulta(self, id_consulta_cab, excluir_id=None):
        """
        Verifica si una consulta ya tiene un odontograma vigente (no Inactivo).
        excluir_id: para excluir un odontograma específico (útil en edición)
        """
        sql = """
        SELECT COUNT(*)
        FROM odontograma
        WHERE id_consulta_cab = %s
          AND activo = true
        """
        params = [id_consulta_cab]
        if excluir_id:
            sql += " AND id_odontograma <> %s"
            params.append(excluir_id)
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, params)
            return cur.fetchone()[0] > 0
        except Exception as e:
            app.logger.error(f"Error al verificar odontograma de la consulta: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def contarDetallesPorOdontograma(self, id_odontograma):
        """Cuenta cuántos detalles tiene un odontograma"""
        sql = "SELECT COUNT(*) FROM odontograma_detalle WHERE id_odontograma = %s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_odontograma,))
            count = cur.fetchone()[0]
            return count
        except Exception as e:
            app.logger.error(f"Error al contar detalles: {str(e)}")
            return 0
        finally:
            cur.close()
            con.close()