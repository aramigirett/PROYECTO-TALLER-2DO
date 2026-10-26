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

    def reemplazarPermisos(self, id_rol, deseados, alcance):
        """
        Guarda la matriz COMPLETA de un rol en una sola transacción (el rol queda bloqueado FOR UPDATE): da de alta los permisos nuevos y de baja los
        desmarcados. `alcance` = los (ventana, accion) que la matriz puede tocar (ventanas activas y delegables); lo que el rol tenga fuera de ese alcance
        no se toca. Devuelve (altas, bajas) como listas ordenadas de (ventana, accion); None si el rol no existe; lanza la excepción ante un error de base.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT 1 FROM roles WHERE id_rol = %s FOR UPDATE", (id_rol,))
            if cur.fetchone() is None:
                con.rollback()
                return None
            cur.execute("""SELECT m.clave, p.accion FROM permisos p JOIN menu m ON m.id_menu = p.id_menu
                           WHERE p.id_rol = %s AND m.activo = true""", (id_rol,))
            actuales = {(r[0], r[1]) for r in cur.fetchall()}
            altas = sorted((set(deseados) & set(alcance)) - actuales)
            bajas = sorted((actuales & set(alcance)) - set(deseados))
            for ventana, accion in altas:
                cur.execute("""INSERT INTO permisos (id_rol, id_menu, accion)
                               SELECT %s, m.id_menu, %s FROM menu m WHERE m.clave = %s AND m.activo = true
                               ON CONFLICT (id_rol, id_menu, accion) DO NOTHING""", (id_rol, accion, ventana))
            for ventana, accion in bajas:
                cur.execute("""DELETE FROM permisos WHERE id_rol = %s AND accion = %s
                               AND id_menu = (SELECT id_menu FROM menu WHERE clave = %s AND activo = true)""", (id_rol, accion, ventana))
            con.commit()
            return altas, bajas
        except Exception:
            con.rollback()
            raise
        finally:
            cur.close()
            con.close()
