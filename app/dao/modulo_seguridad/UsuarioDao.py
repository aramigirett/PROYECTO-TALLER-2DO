# Data Access Object - DAO
from flask import current_app as app
from werkzeug.security import check_password_hash, generate_password_hash
from app.conexion.Conexion import Conexion


class UsuarioDao:

    def get_by_ci_ruc(self, ci_ruc):
        """
        Trae un usuario activo (con su rol) a partir del CI/RUC.
        Retorna None si no existe o está inactivo.
        """
        sql = """
            SELECT u.id_usuario, u.ci_ruc, u.password_hash, u.correo,
                   u.id_rol, r.nombre_rol, u.id_funcionario, u.id_medico,
                   u.activo
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id_rol
            WHERE u.ci_ruc = %s AND u.activo = TRUE
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (ci_ruc,))
            usuario = cur.fetchone()
            if not usuario:
                return None
            return {
                "id_usuario": usuario[0],
                "ci_ruc": usuario[1],
                "password_hash": usuario[2],
                "correo": usuario[3],
                "id_rol": usuario[4],
                "nombre_rol": usuario[5],
                "id_funcionario": usuario[6],
                "id_medico": usuario[7],
                "activo": usuario[8],
            }
        except Exception as e:
            app.logger.error(f"Error al obtener usuario por ci_ruc: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def get_by_id(self, id_usuario):
        """
        Trae un usuario activo (con su rol y el nombre completo de la persona
        vinculada -funcionario o medico, son mutuamente excluyentes-) a partir
        de su id. Se usa luego de validar el código 2FA, cuando ya no se
        cuenta con el CI/RUC.
        """
        sql = """
            SELECT u.id_usuario, u.ci_ruc, u.password_hash, u.correo,
                   u.id_rol, r.nombre_rol, u.id_funcionario, u.id_medico,
                   u.activo,
                   COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido) AS nombre_completo
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id_rol
            LEFT JOIN funcionario f ON u.id_funcionario = f.id_funcionario
            LEFT JOIN medico m ON u.id_medico = m.id_medico
            WHERE u.id_usuario = %s AND u.activo = TRUE
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_usuario,))
            usuario = cur.fetchone()
            if not usuario:
                return None
            return {
                "id_usuario": usuario[0],
                "ci_ruc": usuario[1],
                "password_hash": usuario[2],
                "correo": usuario[3],
                "id_rol": usuario[4],
                "nombre_rol": usuario[5],
                "id_funcionario": usuario[6],
                "id_medico": usuario[7],
                "activo": usuario[8],
                "nombre_completo": usuario[9],
            }
        except Exception as e:
            app.logger.error(f"Error al obtener usuario por id: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def validar_password(self, password_hash, password):
        """
        Compara una contraseña en texto plano contra el hash almacenado.
        """
        return check_password_hash(password_hash, password)

    def getUsuarios(self):
        """
        Trae todos los usuarios (activos e inactivos) con su rol y el nombre
        completo de la persona vinculada, para la grilla de administración.
        """
        sql = """
            SELECT u.id_usuario, u.ci_ruc, u.correo, u.id_rol, r.nombre_rol,
                   u.id_funcionario, u.id_medico, u.activo, u.fecha_creacion,
                   COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido) AS nombre_completo,
                   CASE WHEN u.id_funcionario IS NOT NULL THEN 'Funcionario' ELSE 'Medico' END AS tipo_persona
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id_rol
            LEFT JOIN funcionario f ON u.id_funcionario = f.id_funcionario
            LEFT JOIN medico m ON u.id_medico = m.id_medico
            ORDER BY u.id_usuario
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            usuarios = cur.fetchall()
            return [
                {
                    "id_usuario": u[0],
                    "ci_ruc": u[1],
                    "correo": u[2],
                    "id_rol": u[3],
                    "nombre_rol": u[4],
                    "id_funcionario": u[5],
                    "id_medico": u[6],
                    "activo": u[7],
                    "fecha_creacion": str(u[8]) if u[8] else None,
                    "nombre_completo": u[9],
                    "tipo_persona": u[10],
                }
                for u in usuarios
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener todos los usuarios: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getUsuarioById(self, id_usuario):
        """
        Trae un usuario por id sin filtrar por activo (para poder editar o
        reactivar usuarios dados de baja desde el panel de administración).
        """
        sql = """
            SELECT u.id_usuario, u.ci_ruc, u.correo, u.id_rol, r.nombre_rol,
                   u.id_funcionario, u.id_medico, u.activo, u.fecha_creacion,
                   COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido) AS nombre_completo
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id_rol
            LEFT JOIN funcionario f ON u.id_funcionario = f.id_funcionario
            LEFT JOIN medico m ON u.id_medico = m.id_medico
            WHERE u.id_usuario = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_usuario,))
            u = cur.fetchone()
            if not u:
                return None
            return {
                "id_usuario": u[0],
                "ci_ruc": u[1],
                "correo": u[2],
                "id_rol": u[3],
                "nombre_rol": u[4],
                "id_funcionario": u[5],
                "id_medico": u[6],
                "activo": u[7],
                "fecha_creacion": str(u[8]) if u[8] else None,
                "nombre_completo": u[9],
            }
        except Exception as e:
            app.logger.error(f"Error al obtener usuario por id: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicadoCiRuc(self, ci_ruc, excluir_id=None):
        """
        Verifica si ya existe otro usuario con el mismo CI/RUC.
        """
        sql = "SELECT 1 FROM usuarios WHERE ci_ruc = %s"
        params = [ci_ruc]
        if excluir_id:
            sql += " AND id_usuario != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de ci_ruc: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def existePersonaVinculada(self, id_funcionario, id_medico, excluir_id=None):
        """
        Verifica si el funcionario o médico indicado ya está vinculado a otro
        usuario (una persona solo puede tener un usuario de acceso).
        """
        sql = "SELECT 1 FROM usuarios WHERE "
        if id_funcionario:
            sql += "id_funcionario = %s"
            params = [id_funcionario]
        else:
            sql += "id_medico = %s"
            params = [id_medico]

        if excluir_id:
            sql += " AND id_usuario != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar persona vinculada: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarUsuario(self, ci_ruc, password, correo, id_rol, id_funcionario, id_medico):
        """
        Da de alta un usuario nuevo. La contraseña se recibe en texto plano
        y se guarda hasheada.
        """
        sql = """
            INSERT INTO usuarios (ci_ruc, password_hash, correo, id_rol, id_funcionario, id_medico)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id_usuario
        """
        password_hash = generate_password_hash(password)
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (ci_ruc, password_hash, correo, id_rol, id_funcionario, id_medico))
            id_usuario = cur.fetchone()[0]
            con.commit()
            return id_usuario
        except Exception as e:
            app.logger.error(f"Error al insertar usuario: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateUsuario(self, id_usuario, ci_ruc, correo, id_rol, id_funcionario, id_medico, password=None):
        """
        Actualiza los datos de un usuario. Si se pasa password, también se
        actualiza el hash; si no, la contraseña actual queda sin cambios.
        """
        if password:
            sql = """
                UPDATE usuarios
                SET ci_ruc=%s, correo=%s, id_rol=%s, id_funcionario=%s, id_medico=%s, password_hash=%s
                WHERE id_usuario=%s
            """
            params = (ci_ruc, correo, id_rol, id_funcionario, id_medico, generate_password_hash(password), id_usuario)
        else:
            sql = """
                UPDATE usuarios
                SET ci_ruc=%s, correo=%s, id_rol=%s, id_funcionario=%s, id_medico=%s
                WHERE id_usuario=%s
            """
            params = (ci_ruc, correo, id_rol, id_funcionario, id_medico, id_usuario)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, params)
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al actualizar usuario: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def getFuncionariosDisponibles(self, excluir_usuario=None):
        """
        Funcionarios que todavía no tienen un usuario de acceso, más el que
        ya está vinculado a excluir_usuario (para que siga apareciendo al editar).
        """
        sql = """
            SELECT f.id_funcionario, f.nombre, f.apellido
            FROM funcionario f
            WHERE NOT EXISTS (
                SELECT 1 FROM usuarios u
                WHERE u.id_funcionario = f.id_funcionario
        """
        params = []
        if excluir_usuario:
            sql += " AND u.id_usuario != %s"
            params.append(excluir_usuario)
        sql += ") ORDER BY f.nombre, f.apellido"

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            filas = cur.fetchall()
            return [
                {"id_funcionario": f[0], "nombre_completo": f"{f[1]} {f[2]}"}
                for f in filas
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener funcionarios disponibles: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getMedicosDisponibles(self, excluir_usuario=None):
        """
        Médicos que todavía no tienen un usuario de acceso, más el que ya
        está vinculado a excluir_usuario (para que siga apareciendo al editar).
        """
        sql = """
            SELECT m.id_medico, m.nombre, m.apellido
            FROM medico m
            WHERE NOT EXISTS (
                SELECT 1 FROM usuarios u
                WHERE u.id_medico = m.id_medico
        """
        params = []
        if excluir_usuario:
            sql += " AND u.id_usuario != %s"
            params.append(excluir_usuario)
        sql += ") ORDER BY m.nombre, m.apellido"

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            filas = cur.fetchall()
            return [
                {"id_medico": m[0], "nombre_completo": f"{m[1]} {m[2]}"}
                for m in filas
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener médicos disponibles: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def cambiarEstado(self, id_usuario, activo):
        """
        Da de baja (activo=False) o reactiva (activo=True) un usuario.
        No se hace DELETE físico porque token_2fa y auditoria_acceso
        referencian al usuario para mantener el historial de accesos.
        """
        sql = "UPDATE usuarios SET activo=%s WHERE id_usuario=%s"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (activo, id_usuario))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al cambiar estado del usuario: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
