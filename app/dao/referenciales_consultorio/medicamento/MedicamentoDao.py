# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class MedicamentoDao:
    """
    DAO para la referencial 'Medicamentos' (tabla `medicamentos`).

    Nombre Comercial es el único campo descriptivo (no hay campo Código) y
    es el identificador de negocio: se valida duplicado sobre él.

    NOTA: `estaEnUso()` todavía no valida nada real: depende de
    `receta_medicamento` (tabla de "Generar Recetas e Indicaciones"), que no
    existe en la base todavía. Cuando se programe ese movimiento, agregar
    acá el chequeo contra esa tabla, igual que se documentó en
    TipoInsumoDao/TipoProcedimientoMedicoDao.
    """

    def getMedicamentos(self):
        sql = """
        SELECT id_medicamento, nombre_comercial, presentacion, fecha_registro
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
                    'nombre_comercial': m[1],
                    'presentacion': m[2],
                    'fecha_registro': str(m[3]) if m[3] else None
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
        SELECT id_medicamento, nombre_comercial, presentacion, fecha_registro
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
                    'nombre_comercial': m[1],
                    'presentacion': m[2],
                    'fecha_registro': str(m[3]) if m[3] else None
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener medicamento: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, nombre_comercial, excluir_id=None):
        """
        Verifica si ya existe (entre los activos) un medicamento con el
        mismo nombre comercial (ignorando mayúsculas/minúsculas).
        """
        sql = "SELECT 1 FROM medicamentos WHERE activo = true AND UPPER(nombre_comercial) = UPPER(%s)"
        params = [nombre_comercial]

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

    def guardarMedicamento(self, nombre_comercial, presentacion=None):
        sql = """
        INSERT INTO medicamentos(nombre_comercial, presentacion)
        VALUES(%s, %s) RETURNING id_medicamento
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nombre_comercial, presentacion))
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

    def updateMedicamento(self, id_medicamento, nombre_comercial, presentacion=None):
        sql = """
        UPDATE medicamentos
        SET nombre_comercial = %s, presentacion = %s
        WHERE id_medicamento = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nombre_comercial, presentacion, id_medicamento))
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
