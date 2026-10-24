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
        sql = """
            SELECT m.clave, p.accion
            FROM permisos p
            JOIN menu m ON m.id_menu = p.id_menu
            WHERE p.id_rol = %s AND m.activo = true
        """
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
            INSERT INTO permisos (id_rol, id_menu, accion)
            SELECT %s, m.id_menu, %s
            FROM menu m
            WHERE m.clave = %s AND m.activo = true
            ON CONFLICT (id_rol, id_menu, accion) DO NOTHING
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_rol, accion, ventana))
            if cur.rowcount == 0:
                cur.execute("SELECT 1 FROM permisos p JOIN menu m ON m.id_menu = p.id_menu WHERE p.id_rol = %s AND m.clave = %s AND p.accion = %s", (id_rol, ventana, accion))
                if cur.fetchone() is None:
                    con.rollback()
                    app.logger.error(f"Error al otorgar permiso: no hay una entrada de menu activa con clave {ventana}")
                    return False
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
        sql = """
            DELETE FROM permisos
            WHERE id_rol = %s AND accion = %s
              AND id_menu = (SELECT id_menu FROM menu WHERE clave = %s AND activo = true)
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_rol, accion, ventana))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al revocar permiso: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
