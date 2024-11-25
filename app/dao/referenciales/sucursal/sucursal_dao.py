# Data access object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class SucursalDao:

    def get_sucursales(self):

        sucursal_sql = """
        SELECT
            s.id_sucursal,
            s.descripcion AS nombre_sucursal
        FROM
            sucursales s
        WHERE
            EXISTS (
                SELECT 1
                FROM sucursal_depositos sd
                WHERE sd.id_sucursal = s.id_sucursal
            )
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sucursal_sql)
            sucursales = cur.fetchall() # trae datos de la bd

            # Transformar los datos en una lista de diccionarios
            return [{'id': sucursal[0], 'descripcion': sucursal[1]} for sucursal in sucursales]

        except Exception as e:
            app.logger.error(f"Error al obtener todas las sucursales: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def get_sucursal_depositos(self, id_sucursal: int):

        sucursal_sql = """
        SELECT
            sd.id_deposito
            , d.descripcion nombre_deposito
        FROM
            sucursal_depositos sd
        LEFT JOIN depositos d
            ON sd.id_deposito = d.id_deposito
        WHERE
            sd.id_sucursal = %s AND sd.estado = true
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sucursal_sql, (id_sucursal,))
            sucursales = cur.fetchall() # trae datos de la bd

            # Transformar los datos en una lista de diccionarios
            return [{'id_deposito': sucursal[0], 'nombre_deposito': sucursal[1]} for sucursal in sucursales]

        except Exception as e:
            app.logger.error(f"Error al obtener las sucursales con depositos: {str(e)}")
            return []

        finally:
            cur.close()
            con.close()

    def getCiudadById(self, id):

        ciudadSQL = """
        SELECT id, descripcion
        FROM ciudades WHERE id=%s
        """
        # objeto conexion
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(ciudadSQL, (id,))
            ciudadEncontrada = cur.fetchone() # Obtener una sola fila
            if ciudadEncontrada:
                return {
                        "id": ciudadEncontrada[0],
                        "descripcion": ciudadEncontrada[1]
                    }  # Retornar los datos de la ciudad
            else:
                return None # Retornar None si no se encuentra la ciudad
        except Exception as e:
            app.logger.error(f"Error al obtener ciudad: {str(e)}")
            return None

        finally:
            cur.close()
            con.close()

    def guardarCiudad(self, descripcion):

        insertCiudadSQL = """
        INSERT INTO ciudades(descripcion) VALUES(%s) RETURNING id
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        # Ejecucion exitosa
        try:
            cur.execute(insertCiudadSQL, (descripcion,))
            ciudad_id = cur.fetchone()[0]
            con.commit() # se confirma la insercion
            return ciudad_id

        # Si algo fallo entra aqui
        except Exception as e:
            app.logger.error(f"Error al insertar ciudad: {str(e)}")
            con.rollback() # retroceder si hubo error
            return False

        # Siempre se va ejecutar
        finally:
            cur.close()
            con.close()

    def updateCiudad(self, id, descripcion):

        updateCiudadSQL = """
        UPDATE ciudades
        SET descripcion=%s
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateCiudadSQL, (descripcion, id,))
            filas_afectadas = cur.rowcount # Obtener el número de filas afectadas
            con.commit()

            return filas_afectadas > 0 # Retornar True si se actualizó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al actualizar ciudad: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()

    def deleteCiudad(self, id):

        updateCiudadSQL = """
        DELETE FROM ciudades
        WHERE id=%s
        """

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()

        try:
            cur.execute(updateCiudadSQL, (id,))
            rows_affected = cur.rowcount
            con.commit()

            return rows_affected > 0  # Retornar True si se eliminó al menos una fila

        except Exception as e:
            app.logger.error(f"Error al eliminar ciudad: {str(e)}")
            con.rollback()
            return False

        finally:
            cur.close()
            con.close()