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
