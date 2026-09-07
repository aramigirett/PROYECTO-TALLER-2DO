# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class MedicamentoDao:
    """
    DAO para la referencial 'Medicamentos' (tabla `medicamentos`).

    A diferencia de las demás referenciales de Consultorio, acá solo se
    valida duplicado de Código (no de Nombre Comercial): dos medicamentos
    distintos pueden compartir nombre comercial (ej. mismo principio activo
    en presentaciones distintas).

    NOTA: `estaEnUso()` todavía no valida nada real: depende de
    `receta_medicamento` (tabla de "Generar Recetas e Indicaciones"), que no
    existe en la base todavía. Cuando se programe ese movimiento, agregar
    acá el chequeo contra esa tabla, igual que se documentó en
    TipoInsumoDao/TipoProcedimientoMedicoDao.
    """

    def getMedicamentos(self):
        sql = """
        SELECT id_medicamento, codigo, nombre_comercial, presentacion, fecha_registro
        FROM medicamentos
        WHERE activo = true
        ORDER BY nombre_comercial
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            medicamentos = cur.fetchall()
            return [
                {
                    'id_medicamento': m[0],
                    'codigo': m[1],
                    'nombre_comercial': m[2],
                    'presentacion': m[3],
                    'fecha_registro': str(m[4]) if m[4] else None
                }
                for m in medicamentos
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener medicamentos: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getMedicamentoById(self, id_medicamento):
        sql = """
        SELECT id_medicamento, codigo, nombre_comercial, presentacion, fecha_registro
        FROM medicamentos
        WHERE id_medicamento = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_medicamento,))
            m = cur.fetchone()
            if m:
                return {
                    'id_medicamento': m[0],
                    'codigo': m[1],
                    'nombre_comercial': m[2],
                    'presentacion': m[3],
                    'fecha_registro': str(m[4]) if m[4] else None
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener medicamento: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, codigo, excluir_id=None):
        """
        Verifica si ya existe (entre los activos) un medicamento con el
        mismo código (ignorando mayúsculas/minúsculas). No valida
        Nombre Comercial: puede repetirse.
        """
        sql = "SELECT 1 FROM medicamentos WHERE activo = true AND UPPER(codigo) = UPPER(%s)"
        params = [codigo]

        if excluir_id:
            sql += " AND id_medicamento != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de medicamento: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarMedicamento(self, codigo, nombre_comercial, presentacion=None):
        sql = """
        INSERT INTO medicamentos(codigo, nombre_comercial, presentacion)
        VALUES(%s, %s, %s) RETURNING id_medicamento
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (codigo, nombre_comercial, presentacion))
            nuevo_id = cur.fetchone()[0]
            con.commit()
            return nuevo_id
        except Exception as e:
            app.logger.error(f"Error al insertar medicamento: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateMedicamento(self, id_medicamento, codigo, nombre_comercial, presentacion=None):
        sql = """
        UPDATE medicamentos
        SET codigo = %s, nombre_comercial = %s, presentacion = %s
        WHERE id_medicamento = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (codigo, nombre_comercial, presentacion, id_medicamento))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar medicamento: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def estaEnUso(self, id_medicamento):
        """
        Pendiente: todavía no hay tabla `receta_medicamento` para chequear.
        Cuando se programe "Generar Recetas e Indicaciones", reemplazar este
        método por un chequeo real contra esa tabla.
        """
        return False

    def deleteMedicamento(self, id_medicamento):
        """
        Anula (baja lógica) un medicamento, validando antes que no esté en
        uso (ver nota de `estaEnUso()`: hoy esa validación no chequea nada
        real todavía).

        Returns:
            bool | str: True si se anuló, False si no existía, "EN_USO" si
            está en uso.
        """
        if self.estaEnUso(id_medicamento):
            app.logger.warning(f"No se puede eliminar medicamento {id_medicamento}: está en uso")
            return "EN_USO"

        sql = """
        UPDATE medicamentos
        SET activo = false
        WHERE id_medicamento = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_medicamento,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al eliminar medicamento: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
