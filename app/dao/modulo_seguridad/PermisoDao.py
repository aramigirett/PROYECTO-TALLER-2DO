# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion


class PermisoDao:

    def getPermisosDeRol(self, id_rol):
        """
        Devuelve el set de (ventana, accion) otorgado a un rol. Se usa tanto
        para cachear en flask.g (una sola consulta por request, ver
        permisos_contexto.py) como para poblar la matriz de Roles y Permisos.
        """
        sql = "SELECT ventana, accion FROM permisos WHERE id_rol = %s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_rol,))
            return {(row[0], row[1]) for row in cur.fetchall()}
        except Exception as e:
            app.logger.error(f"Error al obtener permisos del rol: {str(e)}")
            return set()
        finally:
            cur.close()
            con.close()

    def otorgar(self, id_rol, ventana, accion):
        sql = """
            INSERT INTO permisos (id_rol, ventana, accion)
            VALUES (%s, %s, %s)
            ON CONFLICT (id_rol, ventana, accion) DO NOTHING
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_rol, ventana, accion))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al otorgar permiso: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def revocar(self, id_rol, ventana, accion):
        sql = "DELETE FROM permisos WHERE id_rol = %s AND ventana = %s AND accion = %s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_rol, ventana, accion))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al revocar permiso: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
