# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion

class ConsultorioDao:

    def getConsultorios(self):
        sql = """
        SELECT 
            LPAD(id_consultorio::TEXT, 4, '0') AS codigo,
            nombre_consultorio,
            direccion,
            telefono,
            correo
        FROM consultorios
        ORDER BY id_consultorio
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            consultorios = cur.fetchall()
            return [
                {
                    "codigo": c[0],
                    "nombre_consultorio": c[1],
                    "direccion": c[2],
                    "telefono": c[3],
                    "correo": c[4]
                }
                for c in consultorios
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener consultorios: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getConsultorioById(self, id_consultorio):
        sql = """
        SELECT 
            LPAD(id_consultorio::TEXT, 4, '0') AS codigo,
            nombre_consultorio,
            direccion,
            telefono,
            correo
        FROM consultorios
        WHERE id_consultorio = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_consultorio,))
            row = cur.fetchone()
            if row:
                return {
                    "codigo": row[0],
                    "nombre_consultorio": row[1],
                    "direccion": row[2],
                    "telefono": row[3],
                    "correo": row[4]
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener consultorio: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, nombre_consultorio, correo):
        sql = """
        SELECT 1 FROM consultorios
        WHERE UPPER(nombre_consultorio) = UPPER(%s) 
           OR UPPER(correo) = UPPER(%s)
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nombre_consultorio, correo))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de consultorio: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarConsultorio(self, nombre_consultorio, direccion, telefono, correo):
        sql = """
        INSERT INTO consultorios(nombre_consultorio, direccion, telefono, correo)
        VALUES (%s, %s, %s, %s) RETURNING id_consultorio
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nombre_consultorio, direccion, telefono, correo))
            id_consultorio = cur.fetchone()[0]
            con.commit()
            return id_consultorio
        except Exception as e:
            app.logger.error(f"Error al insertar consultorio: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateConsultorio(self, id_consultorio, nombre_consultorio, direccion, telefono, correo):
        sql = """
        UPDATE consultorios
        SET nombre_consultorio=%s,
            direccion=%s,
            telefono=%s,
            correo=%s
        WHERE id_consultorio=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nombre_consultorio, direccion, telefono, correo, id_consultorio))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar consultorio: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def deleteConsultorio(self, id_consultorio):
        sql = "DELETE FROM consultorios WHERE id_consultorio=%s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_consultorio,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al eliminar consultorio: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
