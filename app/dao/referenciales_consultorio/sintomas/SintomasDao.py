# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class SintomaDao:

    def getSintomas(self):
        sql = """
        SELECT id_sintoma, descripcion_sintoma
        FROM sintoma
        ORDER BY id_sintoma
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            sintomas = cur.fetchall()
            return [{'id_sintoma': s[0], 'descripcion_sintoma': s[1]} for s in sintomas]
        except Exception as e:
            app.logger.error(f"Error al obtener todos los síntomas: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def sintomaExiste(self, descripcion):
        """
        Verifica si ya existe un síntoma con la misma descripción (ignora mayúsculas/minúsculas).
        """
        sql = """
        SELECT 1 FROM sintoma WHERE UPPER(descripcion_sintoma) = UPPER(%s)
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion,))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar existencia del síntoma: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def getSintomaById(self, id_sintoma):
        sql = """
        SELECT id_sintoma, descripcion_sintoma
        FROM sintoma WHERE id_sintoma = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_sintoma,))
            sintoma = cur.fetchone()
            if sintoma:
                return {
                    "id_sintoma": sintoma[0],
                    "descripcion_sintoma": sintoma[1]
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener síntoma: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def guardarSintoma(self, descripcion):
        """
        Inserta un síntoma si no existe duplicado.
        """
        if self.sintomaExiste(descripcion):
            app.logger.warning(f"Duplicado detectado: {descripcion}")
            return False

        sql = """
        INSERT INTO sintoma(descripcion_sintoma)
        VALUES(%s) RETURNING id_sintoma
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion,))
            id_sintoma = cur.fetchone()[0]
            con.commit()
            return id_sintoma
        except Exception as e:
            app.logger.error(f"Error al insertar síntoma: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateSintoma(self, id_sintoma, descripcion):
        """
        Actualiza la descripción de un síntoma validando duplicados.
        """
        if self.sintomaExiste(descripcion):
            app.logger.warning(f"Duplicado detectado al actualizar: {descripcion}")
            return False

        sql = """
        UPDATE sintoma
        SET descripcion_sintoma = %s
        WHERE id_sintoma = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion, id_sintoma))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar síntoma: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def deleteSintoma(self, id_sintoma):
        sql = """
        DELETE FROM sintoma WHERE id_sintoma = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_sintoma,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al eliminar síntoma: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()