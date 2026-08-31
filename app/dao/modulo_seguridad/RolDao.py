# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion


class RolDao:

    def getRoles(self):
        sql = """
            SELECT id_rol, nombre_rol
            FROM roles
            WHERE activo = TRUE
            ORDER BY nombre_rol
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            roles = cur.fetchall()
            return [{"id_rol": r[0], "nombre_rol": r[1]} for r in roles]
        except Exception as e:
            app.logger.error(f"Error al obtener roles: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getRolesConConteoPermisos(self):
        """
        Trae los roles con la cantidad de permisos asociados a cada uno,
        para el panel de solo lectura de "Mantener Roles y Permisos".
        """
        sql = """
            SELECT r.id_rol, r.nombre_rol, r.activo, COUNT(p.id_permiso) AS cantidad_permisos
            FROM roles r
            LEFT JOIN permisos p ON p.id_rol = r.id_rol
            GROUP BY r.id_rol, r.nombre_rol, r.activo
            ORDER BY r.nombre_rol
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            roles = cur.fetchall()
            return [
                {
                    "id_rol": r[0],
                    "nombre_rol": r[1],
                    "activo": r[2],
                    "cantidad_permisos": r[3],
                }
                for r in roles
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener roles con conteo de permisos: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()
