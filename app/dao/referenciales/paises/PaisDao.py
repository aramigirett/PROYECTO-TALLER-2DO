# Data access object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class PaisDao:

    def getPaises(self):
        paisSQL = """
        SELECT id_pais, descripcion
        FROM paises
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(paisSQL)
            paises = cur.fetchall()
            return [{'id_pais': pais[0], 'descripcion': pais[1]} for pais in paises]
        except Exception as e:
            app.logger.error(f"Error al obtener todas las paises: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getPaisById(self, id_pais):
        paisSQL = """
        SELECT id_pais, descripcion
        FROM paises WHERE id_pais=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(paisSQL, (id_pais,))
            paisEncontrada = cur.fetchone()
            if paisEncontrada:
                return {
                    "id_pais": paisEncontrada[0],
                    "descripcion": paisEncontrada[1]
                }
            else:
                return None
        except Exception as e:
            app.logger.error(f"Error al obtener pais: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def guardarPais(self, descripcion):
        insertPaisSQL = """
        INSERT INTO paises(descripcion) VALUES(%s) RETURNING id_pais
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(insertPaisSQL, (descripcion,))
            pais_id = cur.fetchone()[0]
            con.commit()
            return pais_id
        except Exception as e:
            app.logger.error(f"Error al insertar pais: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updatePais(self, id_pais, descripcion):
        updatePaisSQL = """
        UPDATE paises
        SET descripcion=%s
        WHERE id_pais=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(updatePaisSQL, (descripcion, id_pais,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar pais: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def deletePais(self, id_pais):
        deletePaisSQL = """
        DELETE FROM paises
        WHERE id_pais=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(deletePaisSQL, (id_pais,))
            rows_affected = cur.rowcount
            con.commit()
            return rows_affected > 0
        except Exception as e:
            app.logger.error(f"Error al eliminar pais: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def getPaisByDescripcion(self, descripcion):
        query = """
        SELECT id_pais, descripcion
        FROM paises
        WHERE UPPER(descripcion) = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(query, (descripcion,))
            return cur.fetchone()
        except Exception as e:
            app.logger.error(f"Error al buscar país por descripción: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()
