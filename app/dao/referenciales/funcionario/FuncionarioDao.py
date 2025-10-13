from flask import current_app as app
from app.conexion.Conexion import Conexion

class FuncionarioDao:

    def getFuncionarios(self):
        sql = """
            SELECT f.id_funcionario, f.nombre, f.apellido,
                   f.cedula, f.fecha_nacimiento, f.fecha_registro,
                   f.telefono, f.direccion, f.correo,
                   f.id_cargo, c.descripcion AS cargo
            FROM funcionario f
            LEFT JOIN cargo c ON f.id_cargo = c.id_cargo
            ORDER BY f.id_funcionario
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            funcionarios = cur.fetchall()
            return [
                {
                    "id_funcionario": f[0],
                    "nombre": f[1],
                    "apellido": f[2],
                    "cedula": f[3],
                    "fecha_nacimiento": str(f[4]) if f[4] else None,
                    "fecha_registro": str(f[5]) if f[5] else None,
                    "telefono": f[6],
                    "direccion": f[7],
                    "correo": f[8],
                    "id_cargo": f[9],
                    "cargo": f[10]
                }
                for f in funcionarios
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener funcionarios: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getFuncionarioById(self, funcionario_id):
        sql = """
            SELECT f.id_funcionario, f.nombre, f.apellido,
                   f.cedula, f.fecha_nacimiento, f.fecha_registro,
                   f.telefono, f.direccion, f.correo,
                   f.id_cargo, c.descripcion AS cargo
            FROM funcionario f
            LEFT JOIN cargo c ON f.id_cargo = c.id_cargo
            WHERE f.id_funcionario = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (funcionario_id,))
            f = cur.fetchone()
            if f:
                return {
                    "id_funcionario": f[0],
                    "nombre": f[1],
                    "apellido": f[2],
                    "cedula": f[3],
                    "fecha_nacimiento": str(f[4]) if f[4] else None,
                    "fecha_registro": str(f[5]) if f[5] else None,
                    "telefono": f[6],
                    "direccion": f[7],
                    "correo": f[8],
                    "id_cargo": f[9],
                    "cargo": f[10]
                }
            return None
        except Exception as e:
            app.logger.error(f"Error al obtener funcionario por ID: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def guardarFuncionario(self, nombre, apellido, cedula, fecha_nacimiento,
                            telefono, direccion, correo, id_cargo, fecha_registro=None):
        sql = """
            INSERT INTO funcionario (nombre, apellido, cedula, fecha_nacimiento,
                                     telefono, direccion, correo, id_cargo, fecha_registro)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id_funcionario
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nombre, apellido, cedula, fecha_nacimiento,
                              telefono, direccion, correo, id_cargo, fecha_registro))
            funcionario_id = cur.fetchone()[0]
            con.commit()
            return funcionario_id
        except Exception as e:
            app.logger.error(f"Error al insertar funcionario: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
    
    def updateFuncionario(self, funcionario_id, nombre, apellido, cedula, fecha_nacimiento,
                          telefono, direccion, correo, id_cargo, fecha_registro=None):
        sql = """
            UPDATE funcionario
            SET nombre=%s, apellido=%s, cedula=%s, fecha_nacimiento=%s,
                telefono=%s, direccion=%s, correo=%s, id_cargo=%s, fecha_registro=%s
            WHERE id_funcionario=%s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (nombre, apellido, cedula, fecha_nacimiento,
                              telefono, direccion, correo, id_cargo, fecha_registro, funcionario_id))
            actualizado = cur.rowcount > 0
            con.commit()
            return actualizado
        except Exception as e:
            app.logger.error(f"Error al actualizar funcionario: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def deleteFuncionario(self, funcionario_id):
        sql = "DELETE FROM funcionario WHERE id_funcionario=%s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (funcionario_id,))
            eliminado = cur.rowcount > 0
            con.commit()
            return eliminado
        except Exception as e:
            app.logger.error(f"Error al eliminar funcionario: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, cedula, correo):
        """Verifica si ya existe un funcionario con la misma cédula o correo"""
        sql = "SELECT COUNT(*) FROM funcionario WHERE cedula = %s OR correo = %s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (cedula, correo))
            result = cur.fetchone()[0]
            return result > 0
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()