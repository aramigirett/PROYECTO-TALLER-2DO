import re
from flask import current_app as app
from app.conexion.Conexion import Conexion

class ConsultorioDao:
    """
    DAO para gestionar consultorios con validaciones robustas
    """
    
    def _normalizarTelefono(self, telefono):
        """
        Normaliza el teléfono al formato internacional paraguayo
        Ejemplos:
            "0981234567" → "595981234567"
            "981234567" → "595981234567"
            "+595981234567" → "595981234567"
        """
        if not telefono:
            return None
        
        # Limpiar espacios y caracteres especiales
        telefono = telefono.strip().replace(" ", "").replace("-", "")
        
        # Quitar el + si lo tiene
        if telefono.startswith("+"):
            telefono = telefono[1:]
        
        # Si comienza con 0, quitarlo y agregar 595
        if telefono.startswith("0"):
            telefono = "595" + telefono[1:]
        # Si NO comienza con 595, agregarlo
        elif not telefono.startswith("595"):
            telefono = "595" + telefono
        
        return telefono
    
    def _esTelefonoParaguayoValido(self, telefono):
        """
        Valida que el teléfono tenga formato paraguayo válido
        Formato esperado: 595XXXXXXXXX (8 o 9 dígitos después del 595)
        """
        if not telefono:
            return False
        return bool(re.match(r'^595\d{8,9}$', telefono))
    
    def _esCorreoValido(self, correo):
        """
        Valida formato básico de correo electrónico
        """
        if not correo:
            return False
        return bool(re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', correo))
    
    def existeDuplicado(self, nombre_consultorio, correo, codigo_excluir=None):
        """
        Verifica si existe un consultorio con el mismo nombre o correo.
        
        Args:
            nombre_consultorio (str): Nombre a verificar
            correo (str): Correo a verificar
            codigo_excluir (int, optional): Código a excluir (para edición)
        
        Returns:
            bool: True si existe duplicado, False si no
        """
        if codigo_excluir:
            sql = """
            SELECT 1 FROM consultorio
            WHERE (UPPER(nombre_consultorio) = UPPER(%s) OR UPPER(correo) = UPPER(%s))
            AND codigo != %s
            """
            params = (nombre_consultorio, correo, codigo_excluir)
        else:
            sql = """
            SELECT 1 FROM consultorio
            WHERE UPPER(nombre_consultorio) = UPPER(%s) OR UPPER(correo) = UPPER(%s)
            """
            params = (nombre_consultorio, correo)
        
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, params)
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de consultorio: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()
    
    def getConsultorios(self):
        """
        Obtiene todos los consultorios ordenados por nombre
        
        Returns:
            list: Lista de diccionarios con datos de consultorios
        """
        sql = """
        SELECT codigo, nombre_consultorio, direccion, telefono, correo 
        FROM consultorio 
        ORDER BY nombre_consultorio
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            consultorios = []
            for row in cur.fetchall():
                consultorios.append({
                    'codigo': row[0],
                    'nombre_consultorio': row[1],
                    'direccion': row[2],
                    'telefono': row[3],
                    'correo': row[4]
                })
            return consultorios
        except Exception as e:
            app.logger.error(f"Error al obtener consultorios: {str(e)}")
            raise
        finally:
            cur.close()
            con.close()
    
    def getConsultorioById(self, codigo):
        """
        Obtiene un consultorio por su código
        
        Args:
            codigo (int): Código del consultorio
        
        Returns:
            dict or None: Datos del consultorio o None si no existe
        """
        sql = """
        SELECT codigo, nombre_consultorio, direccion, telefono, correo 
        FROM consultorio 
        WHERE codigo = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (codigo,))
            row = cur.fetchone()
            if row:
                return {
                    'codigo': row[0],
                    'nombre_consultorio': row[1],
                    'direccion': row[2],
                    'telefono': row[3],
                    'correo': row[4]
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener consultorio por ID: {str(e)}")
            raise
        finally:
            cur.close()
            con.close()
    
    def guardarConsultorio(self, nombre_consultorio, direccion, telefono, correo):
        """
        Guarda un nuevo consultorio con validaciones
        
        Args:
            nombre_consultorio (str): Nombre del consultorio
            direccion (str): Dirección
            telefono (str): Teléfono
            correo (str): Correo electrónico
        
        Returns:
            int: Código del consultorio creado
        
        Raises:
            ValueError: Si hay errores de validación
        """
        # Validación de nombre
        if not nombre_consultorio or len(nombre_consultorio.strip()) < 3:
            raise ValueError("El nombre del consultorio es obligatorio y debe tener al menos 3 caracteres.")
        
        # Validación de dirección
        if not direccion or len(direccion.strip()) < 5:
            raise ValueError("La dirección es obligatoria y debe tener al menos 5 caracteres.")
        
        # Validación de correo
        if not correo or not self._esCorreoValido(correo):
            raise ValueError("El correo electrónico no es válido.")
        
        # Normalizar y validar teléfono
        telefono = self._normalizarTelefono(telefono)
        if not self._esTelefonoParaguayoValido(telefono):
            raise ValueError("El número de teléfono no es válido. Debe ser paraguayo (formato: 0981234567).")
        
        # Verificar duplicados
        if self.existeDuplicado(nombre_consultorio, correo):
            raise ValueError("Ya existe un consultorio con ese nombre o correo.")
        
        sql = """
        INSERT INTO consultorio(nombre_consultorio, direccion, telefono, correo)
        VALUES (%s, %s, %s, %s) 
        RETURNING codigo
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nombre_consultorio.strip(), direccion.strip(), telefono, correo.strip()))
            codigo = cur.fetchone()[0]
            con.commit()
            return codigo
        except Exception as e:
            app.logger.error(f"Error al insertar consultorio: {str(e)}")
            con.rollback()
            raise
        finally:
            cur.close()
            con.close()
    
    def updateConsultorio(self, codigo, nombre_consultorio, direccion, telefono, correo):
        """
        Actualiza un consultorio existente con validaciones
        
        Args:
            codigo (int): Código del consultorio
            nombre_consultorio (str): Nombre del consultorio
            direccion (str): Dirección
            telefono (str): Teléfono
            correo (str): Correo electrónico
        
        Returns:
            bool: True si se actualizó correctamente
        
        Raises:
            ValueError: Si hay errores de validación
        """
        # Validación de nombre
        if not nombre_consultorio or len(nombre_consultorio.strip()) < 3:
            raise ValueError("El nombre del consultorio es obligatorio y debe tener al menos 3 caracteres.")
        
        # Validación de dirección
        if not direccion or len(direccion.strip()) < 5:
            raise ValueError("La dirección es obligatoria y debe tener al menos 5 caracteres.")
        
        # Validación de correo
        if not correo or not self._esCorreoValido(correo):
            raise ValueError("El correo electrónico no es válido.")
        
        # Normalizar y validar teléfono
        telefono = self._normalizarTelefono(telefono)
        if not self._esTelefonoParaguayoValido(telefono):
            raise ValueError("El número de teléfono no es válido. Debe ser paraguayo (formato: 0981234567).")
        
        # Verificar duplicados (excluyendo el registro actual)
        if self.existeDuplicado(nombre_consultorio, correo, codigo):
            raise ValueError("Ya existe otro consultorio con ese nombre o correo.")
        
        sql = """
        UPDATE consultorio
        SET nombre_consultorio = %s,
            direccion = %s,
            telefono = %s,
            correo = %s
        WHERE codigo = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nombre_consultorio.strip(), direccion.strip(), telefono, correo.strip(), codigo))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar consultorio: {str(e)}")
            con.rollback()
            raise
        finally:
            cur.close()
            con.close()
    
    def deleteConsultorio(self, codigo):
        """
        Elimina un consultorio por su código
        
        Args:
            codigo (int): Código del consultorio a eliminar
        
        Returns:
            bool: True si se eliminó correctamente
        """
        sql = "DELETE FROM consultorio WHERE codigo = %s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (codigo,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al eliminar consultorio: {str(e)}")
            con.rollback()
            raise
        finally:
            cur.close()
            con.close()