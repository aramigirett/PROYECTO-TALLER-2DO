# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion


class PermisoDao:

    def getPermisos(self):
        sql = """
            SELECT p.id_permiso, p.nombre_permiso, p.descripcion, p.id_rol, r.nombre_rol
            FROM permisos p
            JOIN roles r ON p.id_rol = r.id_rol
            ORDER BY r.nombre_rol, p.nombre_permiso
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            permisos = cur.fetchall()
            return [
                {
                    "id_permiso": p[0],
                    "nombre_permiso": p[1],
                    "descripcion": p[2],
                    "id_rol": p[3],
                    "nombre_rol": p[4],
                }
                for p in permisos
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener todos los permisos: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getPermisoById(self, id_permiso):
        sql = """
            SELECT p.id_permiso, p.nombre_permiso, p.descripcion, p.id_rol, r.nombre_rol
            FROM permisos p
            JOIN roles r ON p.id_rol = r.id_rol
            WHERE p.id_permiso = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_permiso,))
            p = cur.fetchone()
            if not p:
                return None
            return {
                "id_permiso": p[0],
                "nombre_permiso": p[1],
                "descripcion": p[2],
                "id_rol": p[3],
                "nombre_rol": p[4],
            }
        except Exception as e:
            app.logger.error(f"Error al obtener permiso: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, id_rol, nombre_permiso, excluir_id=None):
        """
        Verifica si ya existe un permiso con el mismo nombre dentro del mismo rol.
        """
        sql = "SELECT 1 FROM permisos WHERE id_rol = %s AND UPPER(nombre_permiso) = UPPER(%s)"
        params = [id_rol, nombre_permiso]
        if excluir_id:
            sql += " AND id_permiso != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de permiso: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarPermiso(self, nombre_permiso, descripcion, id_rol):
        sql = """
            INSERT INTO permisos (nombre_permiso, descripcion, id_rol)
            VALUES (%s, %s, %s)
            RETURNING id_permiso
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nombre_permiso, descripcion, id_rol))
            id_permiso = cur.fetchone()[0]
            con.commit()
            return id_permiso
        except Exception as e:
            app.logger.error(f"Error al insertar permiso: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updatePermiso(self, id_permiso, nombre_permiso, descripcion, id_rol):
        sql = """
            UPDATE permisos
            SET nombre_permiso=%s, descripcion=%s, id_rol=%s
            WHERE id_permiso=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nombre_permiso, descripcion, id_rol, id_permiso))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar permiso: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def deletePermiso(self, id_permiso):
        sql = "DELETE FROM permisos WHERE id_permiso=%s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_permiso,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al eliminar permiso: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
