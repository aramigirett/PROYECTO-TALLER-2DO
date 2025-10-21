from flask import current_app as app
from app.conexion.Conexion import Conexion

class CitaDao:
    """
    DAO para gestionar Citas (Cabecera + Detalle + Estados)
    Maneja la lógica de cupos automáticamente
    """

    # ========================================
    # GESTIÓN DE ESTADOS Y CUPOS
    # ========================================
    
    def getEstadosQueOcupanCupo(self):
        """
        Obtiene los IDs de estados que OCUPAN cupo en la agenda
        Ejemplo: Reservado, Confirmado, Realizado
        """
        sql = "SELECT id_estado_cita FROM estado_cita WHERE ocupa_cupo = TRUE"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            ids = [row[0] for row in rows]  # Lista de IDs: [1, 2, 3]
            app.logger.info(f"🔍 Estados que ocupan cupo obtenidos: {ids}")
            return ids
        except Exception as e:
            app.logger.error(f"❌ Error al obtener estados que ocupan cupo: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def restarCupoAgendaDetalle(self, id_agenda_detalle):
        """
        Resta 1 cupo del agenda_detalle
        Si llega a 0, cambia estado_detalle a 'Agotado'
        """
        sql = """
        UPDATE agenda_detalle
        SET cupos_disponibles = cupos_disponibles - 1,
            estado_detalle = CASE 
                WHEN cupos_disponibles - 1 = 0 THEN 'Agotado'
                ELSE estado_detalle
            END
        WHERE id_agenda_detalle = %s AND cupos_disponibles > 0
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            app.logger.info(f"🔄 Ejecutando UPDATE para restar cupo en agenda_detalle {id_agenda_detalle}")
            
            cur.execute(sql, (id_agenda_detalle,))
            filas = cur.rowcount
            
            app.logger.info(f"🔄 Filas afectadas por UPDATE: {filas}")
            
            con.commit()
            
            if filas > 0:
                app.logger.info(f"✅ Cupo restado exitosamente en agenda_detalle {id_agenda_detalle}")
            else:
                app.logger.warning(f"⚠️ No se restó cupo en agenda_detalle {id_agenda_detalle} (posiblemente sin cupos)")
            
            return filas > 0
        except Exception as e:
            app.logger.error(f"❌ Error al restar cupo: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def sumarCupoAgendaDetalle(self, id_agenda_detalle):
        """
        Suma 1 cupo al agenda_detalle
        Cambia estado_detalle a 'Disponible'
        """
        sql = """
        UPDATE agenda_detalle
        SET cupos_disponibles = cupos_disponibles + 1,
            estado_detalle = 'Disponible'
        WHERE id_agenda_detalle = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            app.logger.info(f"🔄 Ejecutando UPDATE para sumar cupo en agenda_detalle {id_agenda_detalle}")
            
            cur.execute(sql, (id_agenda_detalle,))
            filas = cur.rowcount
            
            app.logger.info(f"🔄 Filas afectadas por UPDATE: {filas}")
            
            con.commit()
            
            if filas > 0:
                app.logger.info(f"✅ Cupo sumado exitosamente en agenda_detalle {id_agenda_detalle}")
            else:
                app.logger.warning(f"⚠️ No se sumó cupo en agenda_detalle {id_agenda_detalle}")
            
            return filas > 0
        except Exception as e:
            app.logger.error(f"❌ Error al sumar cupo: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def verificarCuposDisponibles(self, id_agenda_detalle):
        """
        Verifica si hay cupos disponibles en un agenda_detalle
        Retorna el número de cupos disponibles
        """
        sql = "SELECT cupos_disponibles FROM agenda_detalle WHERE id_agenda_detalle = %s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_agenda_detalle,))
            result = cur.fetchone()
            cupos = result[0] if result else 0
            app.logger.info(f"📊 Cupos disponibles en agenda_detalle {id_agenda_detalle}: {cupos}")
            return cupos
        except Exception as e:
            app.logger.error(f"❌ Error al verificar cupos: {str(e)}")
            return 0
        finally:
            cur.close()
            con.close()

    # ========================================
    # GESTIÓN DE ESTADOS DE CITA
    # ========================================

    def getEstadosCita(self):
        """Obtiene todos los estados de cita disponibles"""
        sql = """
        SELECT id_estado_cita, descripcion, ocupa_cupo
        FROM estado_cita
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
                    'id_estado_cita': r[0],
                    'descripcion': r[1],
                    'ocupa_cupo': r[2]
                } for r in rows
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener estados de cita: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    # ========================================
    # CITA CABECERA - CRUD
    # ========================================

    def getCitasCabecera(self):
        """
        Obtiene todas las cabeceras de citas con información relacionada
        """
        sql = """
        SELECT 
            cc.id_cita_cabecera,
            cc.id_paciente,
            (p.nombre || ' ' || p.apellido) AS paciente_nombre,
            cc.id_agenda_cabecera,
            ac.fecha_agenda,
            (m.nombre || ' ' || m.apellido) AS medico_nombre,
            e.nombre_especialidad AS especialidad,
            cc.fecha_registro,
            cc.observaciones,
            cc.estado,
            cc.id_funcionario
        FROM cita_cabecera cc
        JOIN paciente p ON cc.id_paciente = p.id_paciente
        JOIN agenda_cabecera ac ON cc.id_agenda_cabecera = ac.id_agenda_cabecera
        JOIN medico m ON ac.id_medico = m.id_medico
        JOIN especialidades e ON ac.id_especialidad = e.id_especialidad
        ORDER BY cc.fecha_registro DESC
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            return [
                {
                    'id_cita_cabecera': r[0],
                    'id_paciente': r[1],
                    'paciente_nombre': r[2],
                    'id_agenda_cabecera': r[3],
                    'fecha_agenda': str(r[4]) if r[4] else None,
                    'medico_nombre': r[5],
                    'especialidad': r[6],
                    'fecha_registro': str(r[7]) if r[7] else None,
                    'observaciones': r[8],
                    'estado': r[9],
                    'id_funcionario': r[10]
                } for r in rows
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener cabeceras de citas: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getCitaCabeceraById(self, id_cita_cabecera):
        """Obtiene una cabecera específica por ID"""
        sql = """
        SELECT 
            cc.id_cita_cabecera,
            cc.id_paciente,
            (p.nombre || ' ' || p.apellido) AS paciente_nombre,
            cc.id_agenda_cabecera,
            ac.fecha_agenda,
            (m.nombre || ' ' || m.apellido) AS medico_nombre,
            e.nombre_especialidad AS especialidad,
            cc.fecha_registro,
            cc.observaciones,
            cc.estado,
            cc.id_funcionario
        FROM cita_cabecera cc
        JOIN paciente p ON cc.id_paciente = p.id_paciente
        JOIN agenda_cabecera ac ON cc.id_agenda_cabecera = ac.id_agenda_cabecera
        JOIN medico m ON ac.id_medico = m.id_medico
        JOIN especialidades e ON ac.id_especialidad = e.id_especialidad
        WHERE cc.id_cita_cabecera = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_cita_cabecera,))
            r = cur.fetchone()
            if r:
                return {
                    'id_cita_cabecera': r[0],
                    'id_paciente': r[1],
                    'paciente_nombre': r[2],
                    'id_agenda_cabecera': r[3],
                    'fecha_agenda': str(r[4]) if r[4] else None,
                    'medico_nombre': r[5],
                    'especialidad': r[6],
                    'fecha_registro': str(r[7]) if r[7] else None,
                    'observaciones': r[8],
                    'estado': r[9],
                    'id_funcionario': r[10]
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener cabecera: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def guardarCitaCabecera(self, id_paciente, id_agenda_cabecera, id_funcionario, observaciones=None):
        """
        Crea una nueva cabecera de cita
        """
        sql = """
        INSERT INTO cita_cabecera(
            id_paciente, id_agenda_cabecera, id_funcionario, observaciones
        ) VALUES (%s, %s, %s, %s)
        RETURNING id_cita_cabecera
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_paciente, id_agenda_cabecera, id_funcionario, observaciones))
            new_id = cur.fetchone()[0]
            con.commit()
            app.logger.info(f"Cabecera de cita creada con ID: {new_id}")
            return new_id
        except Exception as e:
            app.logger.error(f"Error al guardar cabecera: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateCitaCabecera(self, id_cita_cabecera, id_paciente, id_agenda_cabecera, observaciones=None):
        """Actualiza una cabecera existente"""
        sql = """
        UPDATE cita_cabecera
        SET id_paciente=%s, id_agenda_cabecera=%s, observaciones=%s
        WHERE id_cita_cabecera=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_paciente, id_agenda_cabecera, observaciones, id_cita_cabecera))
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

    def deleteCitaCabecera(self, id_cita_cabecera):
        """
        Elimina una cabecera de cita
        NOTA: Por CASCADE también elimina los detalles
        IMPORTANTE: Debe devolver cupos antes de eliminar
        """
        # Primero obtenemos todos los detalles para devolver cupos
        detalles = self.getDetallesPorCabecera(id_cita_cabecera)
        
        sql = "DELETE FROM cita_cabecera WHERE id_cita_cabecera=%s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            # Devolver cupos de todos los detalles que ocupaban cupo
            estados_ocupan = self.getEstadosQueOcupanCupo()
            for detalle in detalles:
                if detalle['id_estado_cita'] in estados_ocupan:
                    self.sumarCupoAgendaDetalle(detalle['id_agenda_detalle'])
            
            # Eliminar cabecera
            cur.execute(sql, (id_cita_cabecera,))
            filas = cur.rowcount
            con.commit()
            app.logger.info(f"Cabecera de cita eliminada: {id_cita_cabecera}")
            return filas > 0
        except Exception as e:
            app.logger.error(f"Error al eliminar cabecera: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def cambiarEstadoCabecera(self, id_cita_cabecera, nuevo_estado):
        """Cambia el estado de una cabecera (Activo/Inactivo)"""
        sql = "UPDATE cita_cabecera SET estado=%s WHERE id_cita_cabecera=%s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nuevo_estado, id_cita_cabecera))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except Exception as e:
            app.logger.error(f"Error al cambiar estado cabecera: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ========================================
    # CITA DETALLE - CRUD
    # ========================================

    def getDetallesPorCabecera(self, id_cita_cabecera):
        """Obtiene todos los detalles de una cabecera específica"""
        sql = """
        SELECT 
            cd.id_cita_detalle,
            cd.id_cita_cabecera,
            cd.id_agenda_detalle,
            cd.fecha_cita,
            cd.hora_cita,
            cd.motivo_consulta,
            cd.id_estado_cita,
            ec.descripcion AS estado_descripcion,
            cd.fecha_cambio_estado,
            ad.hora_inicio,
            ad.hora_fin,
            ad.cupos_disponibles
        FROM cita_detalle cd
        JOIN estado_cita ec ON cd.id_estado_cita = ec.id_estado_cita
        JOIN agenda_detalle ad ON cd.id_agenda_detalle = ad.id_agenda_detalle
        WHERE cd.id_cita_cabecera = %s
        ORDER BY cd.fecha_cita, cd.hora_cita
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_cita_cabecera,))
            rows = cur.fetchall()
            return [
                {
                    'id_cita_detalle': r[0],
                    'id_cita_cabecera': r[1],
                    'id_agenda_detalle': r[2],
                    'fecha_cita': str(r[3]),
                    'hora_cita': str(r[4]),
                    'motivo_consulta': r[5],
                    'id_estado_cita': r[6],
                    'estado_descripcion': r[7],
                    'fecha_cambio_estado': str(r[8]) if r[8] else None,
                    'hora_inicio': str(r[9]),
                    'hora_fin': str(r[10]),
                    'cupos_disponibles': r[11]
                } for r in rows
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener detalles: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getDetalleById(self, id_cita_detalle):
        """Obtiene un detalle específico por ID"""
        sql = """
        SELECT 
            cd.id_cita_detalle,
            cd.id_cita_cabecera,
            cd.id_agenda_detalle,
            cd.fecha_cita,
            cd.hora_cita,
            cd.motivo_consulta,
            cd.id_estado_cita,
            ec.descripcion AS estado_descripcion,
            cd.fecha_cambio_estado
        FROM cita_detalle cd
        JOIN estado_cita ec ON cd.id_estado_cita = ec.id_estado_cita
        WHERE cd.id_cita_detalle = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_cita_detalle,))
            r = cur.fetchone()
            if r:
                return {
                    'id_cita_detalle': r[0],
                    'id_cita_cabecera': r[1],
                    'id_agenda_detalle': r[2],
                    'fecha_cita': str(r[3]),
                    'hora_cita': str(r[4]),
                    'motivo_consulta': r[5],
                    'id_estado_cita': r[6],
                    'estado_descripcion': r[7],
                    'fecha_cambio_estado': str(r[8]) if r[8] else None
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener detalle: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()
 
    def guardarCitaDetalle(self, id_cita_cabecera, id_agenda_detalle, fecha_cita, 
                          hora_cita, motivo_consulta, id_estado_cita):
        """
        Crea un nuevo detalle de cita
        IMPORTANTE: Gestiona cupos automáticamente según el estado
        """
        app.logger.info(f"=" * 60)
        app.logger.info(f"📝 INICIANDO GUARDADO DE CITA DETALLE")
        app.logger.info(f"=" * 60)
        app.logger.info(f"   • id_cita_cabecera: {id_cita_cabecera}")
        app.logger.info(f"   • id_agenda_detalle: {id_agenda_detalle}")
        app.logger.info(f"   • fecha_cita: {fecha_cita}")
        app.logger.info(f"   • hora_cita: {hora_cita}")
        app.logger.info(f"   • id_estado_cita: {id_estado_cita} (tipo: {type(id_estado_cita)})")
        app.logger.info(f"=" * 60)
        
        # CONVERTIR A INTEGER
        id_estado_cita = int(id_estado_cita)
        app.logger.info(f"🔄 id_estado_cita convertido a: {id_estado_cita} (tipo: {type(id_estado_cita)})")

        # Verificar cupos disponibles
        cupos = self.verificarCuposDisponibles(id_agenda_detalle)
        
        if cupos <= 0:
            app.logger.warning(f"⚠️ Sin cupos en agenda_detalle {id_agenda_detalle}")
            return "SIN_CUPOS"

        sql = """
        INSERT INTO cita_detalle(
            id_cita_cabecera, id_agenda_detalle, fecha_cita, hora_cita,
            motivo_consulta, id_estado_cita
        ) VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id_cita_detalle
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            app.logger.info(f"💾 Insertando registro en cita_detalle...")
            
            cur.execute(sql, (id_cita_cabecera, id_agenda_detalle, fecha_cita, 
                            hora_cita, motivo_consulta, id_estado_cita))
            new_id = cur.fetchone()[0]
            
            app.logger.info(f"✅ Cita detalle insertada con ID: {new_id}")
            
            # Si el estado ocupa cupo, restar
            estados_ocupan = self.getEstadosQueOcupanCupo()
            
            app.logger.info(f"🔍 Estados que ocupan cupo: {estados_ocupan}")
            app.logger.info(f"🔍 Estado seleccionado: {id_estado_cita}")
            app.logger.info(f"🔍 ¿Estado {id_estado_cita} está en {estados_ocupan}?: {id_estado_cita in estados_ocupan}")
            
            if id_estado_cita in estados_ocupan:
                app.logger.info(f"✅ Estado OCUPA CUPO - Procediendo a restar...")
                resultado = self.restarCupoAgendaDetalle(id_agenda_detalle)
                app.logger.info(f"✅ Resultado de restar cupo: {resultado}")
            else:
                app.logger.info(f"⚠️ Estado NO ocupa cupo - No se resta")
            
            con.commit()
            app.logger.info(f"✅ COMMIT EXITOSO - Detalle de cita creado con ID: {new_id}")
            app.logger.info(f"=" * 60)
            return new_id
        except Exception as e:
            app.logger.error(f"❌ ERROR al guardar detalle: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateCitaDetalle(self, id_cita_detalle, id_agenda_detalle, fecha_cita,
                         hora_cita, motivo_consulta, id_estado_cita):
        """
        Actualiza un detalle de cita
        IMPORTANTE: Gestiona cupos según cambios de estado o agenda_detalle
        """
        app.logger.info(f"=" * 60)
        app.logger.info(f"📝 INICIANDO ACTUALIZACIÓN DE CITA DETALLE")
        app.logger.info(f"=" * 60)

        # CONVERTIR A INTEGER
        id_estado_cita = int(id_estado_cita)
        
        # Obtener datos actuales del detalle
        detalle_actual = self.getDetalleById(id_cita_detalle)
        if not detalle_actual:
            app.logger.error(f"❌ No se encontró el detalle con ID: {id_cita_detalle}")
            return False

        id_agenda_anterior = detalle_actual['id_agenda_detalle']
        estado_anterior = detalle_actual['id_estado_cita']
        
        app.logger.info(f"📊 DATOS ACTUALES:")
        app.logger.info(f"   • id_agenda_anterior: {id_agenda_anterior}")
        app.logger.info(f"   • estado_anterior: {estado_anterior}")
        app.logger.info(f"📊 DATOS NUEVOS:")
        app.logger.info(f"   • id_agenda_detalle: {id_agenda_detalle}")
        app.logger.info(f"   • id_estado_cita: {id_estado_cita}")
        
        estados_ocupan = self.getEstadosQueOcupanCupo()
        
        # Determinar si los estados ocupan cupo
        estado_anterior_ocupa = estado_anterior in estados_ocupan
        estado_nuevo_ocupa = id_estado_cita in estados_ocupan
        
        app.logger.info(f"🔍 Estado anterior ocupa cupo?: {estado_anterior_ocupa}")
        app.logger.info(f"🔍 Estado nuevo ocupa cupo?: {estado_nuevo_ocupa}")
        
        # Verificar cupos si necesita ocupar un nuevo cupo
        cambio_agenda = id_agenda_detalle != id_agenda_anterior
        
        app.logger.info(f"🔍 ¿Cambió de agenda?: {cambio_agenda}")
        
        if cambio_agenda and estado_nuevo_ocupa:
            cupos = self.verificarCuposDisponibles(id_agenda_detalle)
            if cupos <= 0:
                app.logger.warning(f"⚠️ Sin cupos en nueva agenda {id_agenda_detalle}")
                return "SIN_CUPOS"
        elif not cambio_agenda and not estado_anterior_ocupa and estado_nuevo_ocupa:
            cupos = self.verificarCuposDisponibles(id_agenda_detalle)
            if cupos <= 0:
                app.logger.warning(f"⚠️ Sin cupos disponibles")
                return "SIN_CUPOS"

        sql = """
        UPDATE cita_detalle
        SET id_agenda_detalle=%s, fecha_cita=%s, hora_cita=%s,
            motivo_consulta=%s, id_estado_cita=%s, fecha_cambio_estado=NOW()
        WHERE id_cita_detalle=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_agenda_detalle, fecha_cita, hora_cita,
                            motivo_consulta, id_estado_cita, id_cita_detalle))
            
            # ========== LÓGICA DE CUPOS ==========
            
            if cambio_agenda:
                app.logger.info(f"🔄 CAMBIO DE AGENDA DETECTADO")
                # Cambió de agenda_detalle
                if estado_anterior_ocupa:
                    app.logger.info(f"➕ Sumando cupo a agenda anterior {id_agenda_anterior}")
                    self.sumarCupoAgendaDetalle(id_agenda_anterior)
                if estado_nuevo_ocupa:
                    app.logger.info(f"➖ Restando cupo de agenda nueva {id_agenda_detalle}")
                    self.restarCupoAgendaDetalle(id_agenda_detalle)
            else:
                app.logger.info(f"🔄 MISMA AGENDA - EVALUANDO CAMBIO DE ESTADO")
                # Misma agenda, cambió estado
                if estado_anterior_ocupa and not estado_nuevo_ocupa:
                    # Ocupado → Libre (ej: Confirmado → Cancelado)
                    app.logger.info(f"➕ Ocupado → Libre: Sumando cupo a agenda {id_agenda_anterior}")
                    self.sumarCupoAgendaDetalle(id_agenda_anterior)
                elif not estado_anterior_ocupa and estado_nuevo_ocupa:
                    # Libre → Ocupado (ej: Cancelado → Confirmado)
                    app.logger.info(f"➖ Libre → Ocupado: Restando cupo de agenda {id_agenda_detalle}")
                    self.restarCupoAgendaDetalle(id_agenda_detalle)
                else:
                    app.logger.info(f"⚪ Sin cambios en cupos (ambos ocupan o ambos no ocupan)")
            
            filas = cur.rowcount
            con.commit()
            app.logger.info(f"✅ COMMIT EXITOSO - Cita actualizada")
            app.logger.info(f"=" * 60)
            return filas > 0
        except Exception as e:
            app.logger.error(f"❌ Error al actualizar detalle: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def deleteCitaDetalle(self, id_cita_detalle):
        """
        Elimina un detalle de cita
        IMPORTANTE: Devuelve el cupo si el estado ocupaba cupo
        """
        app.logger.info(f"=" * 60)
        app.logger.info(f"🗑️ INICIANDO ELIMINACIÓN DE CITA DETALLE {id_cita_detalle}")
        app.logger.info(f"=" * 60)
        
        # Obtener datos antes de eliminar
        detalle = self.getDetalleById(id_cita_detalle)
        if not detalle:
            app.logger.error(f"❌ No se encontró el detalle con ID: {id_cita_detalle}")
            return False

        sql = "DELETE FROM cita_detalle WHERE id_cita_detalle=%s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            # Si ocupaba cupo, devolverlo
            estados_ocupan = self.getEstadosQueOcupanCupo()
            
            app.logger.info(f"🔍 Estado de la cita: {detalle['id_estado_cita']}")
            app.logger.info(f"🔍 ¿Ocupaba cupo?: {detalle['id_estado_cita'] in estados_ocupan}")
            
            if detalle['id_estado_cita'] in estados_ocupan:
                app.logger.info(f"➕ Devolviendo cupo a agenda {detalle['id_agenda_detalle']}")
                self.sumarCupoAgendaDetalle(detalle['id_agenda_detalle'])
            
            cur.execute( sql, (id_cita_detalle,))
            filas = cur.rowcount
            con.commit()
            app.logger.info(f"✅ COMMIT EXITOSO - Detalle de cita eliminado: {id_cita_detalle}")
            app.logger.info(f"=" * 60)
            return filas > 0
        except Exception as e:
            app.logger.error(f"❌ Error al eliminar detalle: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def obtenerCitasPacienteConfirmadas(self, id_paciente):
        """Obtiene citas confirmadas del paciente"""
        sql = """
        SELECT DISTINCT
            cc.id_cita_cabecera,
            cd.id_cita_detalle,
            cd.fecha_cita,
            cd.hora_cita,
            COALESCE(m.nombre || ' ' || m.apellido, 'Sin médico') AS medico,
            COALESCE(e.nombre_especialidad, 'Sin especialidad') AS especialidad,
            'Sin consultorio' AS consultorio,
            NULL AS codigo,
            ec.descripcion AS estado_cita,
            cd.motivo_consulta,
            cd.id_estado_cita,
            ac.id_medico
        FROM cita_detalle cd
        INNER JOIN cita_cabecera cc ON cd.id_cita_cabecera = cc.id_cita_cabecera
        INNER JOIN estado_cita ec ON cd.id_estado_cita = ec.id_estado_cita
        INNER JOIN agenda_cabecera ac ON cc.id_agenda_cabecera = ac.id_agenda_cabecera
        LEFT JOIN medico m ON ac.id_medico = m.id_medico
        LEFT JOIN especialidades e ON ac.id_especialidad = e.id_especialidad
        WHERE cc.id_paciente = %s
        ORDER BY cd.fecha_cita DESC
        LIMIT 10;
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            app.logger.info(f"🔍 Buscando citas para paciente ID: {id_paciente}")
            cur.execute(sql, (id_paciente,))
            rows = cur.fetchall()
        
            app.logger.info(f"📊 Registros encontrados: {len(rows)}")
        
            if not rows:
                return []
        
            citas = []
            for row in rows:
                hora_str = str(row[3])[:5] if row[3] else "00:00"
                fecha_str = str(row[2]) if row[2] else ""
            
                cita = {
                    'id_cita_cabecera': row[0],
                    'id_cita_detalle': row[1],
                    'fecha_cita': fecha_str,
                    'hora_cita': hora_str,
                    'medico': row[4],
                    'especialidad': row[5],
                    'consultorio': row[6],
                    'codigo': row[7],
                    'estado_cita': row[8],
                    'motivo_consulta': row[9],
                    'id_estado_cita': row[10],
                    'id_medico': row[11]
                }
                citas.append(cita)
                app.logger.info(f"✅ Cita: {fecha_str} {hora_str}")
    
            return citas
    
        except Exception as e:
            app.logger.error(f"❌ Error: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()