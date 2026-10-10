# Data Access Object - DAO
from flask import current_app as app
from werkzeug.security import check_password_hash, generate_password_hash
from app.conexion.Conexion import Conexion


# Bloqueo de cuenta por intentos fallidos consecutivos
MAX_INTENTOS_FALLIDOS = 3
BLOQUEO_MINUTOS = 15

# CI/RUC y correo NO se guardan en usuarios: viven en la persona vinculada
# (funcionario o medico, mutuamente excluyentes). Estas expresiones requieren
# los alias f (funcionario) y m (medico) con LEFT JOIN en la consulta.
SQL_CI_RUC = "COALESCE(f.cedula, m.cedula)"
SQL_CORREO = "NULLIF(TRIM(COALESCE(f.correo, m.correo)), '')"


class UsuarioDao:

    def get_by_ci_ruc(self, ci_ruc):
        """
        Trae un usuario activo (con su rol) a partir del CI/RUC.
        Retorna None si no existe o está inactivo. Incluye el estado de
        bloqueo: `bloqueado` (flag guardado) y `bloqueo_vencido` (el flag está
        puesto pero ya pasaron BLOQUEO_MINUTOS, o sea se puede liberar solo).
        """
        sql = """
            SELECT u.id_usuario, {ci} AS ci_ruc, u.password_hash, {correo} AS correo,
                   u.id_rol, r.nombre_rol, u.id_funcionario, u.id_medico,
                   u.activo, u.bloqueado,
                   (u.bloqueado AND u.fecha_bloqueo <= NOW()::timestamp - make_interval(mins => %s)) AS bloqueo_vencido
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id_rol
            LEFT JOIN funcionario f ON u.id_funcionario = f.id_funcionario
            LEFT JOIN medico m ON u.id_medico = m.id_medico
            WHERE {ci} = %s AND u.activo = TRUE
        """.format(ci=SQL_CI_RUC, correo=SQL_CORREO)
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (BLOQUEO_MINUTOS, ci_ruc))
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
                "bloqueado": usuario[9],
                "bloqueo_vencido": bool(usuario[10]),
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
            SELECT u.id_usuario, {ci}, u.password_hash, {correo},
                   u.id_rol, r.nombre_rol, u.id_funcionario, u.id_medico,
                   u.activo,
                   COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido) AS nombre_completo
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id_rol
            LEFT JOIN funcionario f ON u.id_funcionario = f.id_funcionario
            LEFT JOIN medico m ON u.id_medico = m.id_medico
            WHERE u.id_usuario = %s AND u.activo = TRUE
        """.format(ci=SQL_CI_RUC, correo=SQL_CORREO)
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

    def getCorreosAdministradores(self, excluir_id=None):
        """
        Correos de los usuarios activos con rol Administrador (destinatarios de
        las alertas de bloqueo). excluir_id evita avisarle dos veces al propio
        usuario bloqueado si él es administrador.
        """
        sql = """
            SELECT {correo}
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id_rol
            LEFT JOIN funcionario f ON u.id_funcionario = f.id_funcionario
            LEFT JOIN medico m ON u.id_medico = m.id_medico
            WHERE r.nombre_rol = 'Administrador' AND u.activo = TRUE
              AND (%s::int IS NULL OR u.id_usuario <> %s::int)
        """.format(correo=SQL_CORREO)
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (excluir_id, excluir_id))
            return sorted({f[0] for f in cur.fetchall() if f[0]})
        except Exception as e:
            app.logger.error(f"Error al obtener correos de administradores: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def _ejecutar_update(self, sql, params, mensaje_error):
        """Ejecuta un UPDATE puntual y retorna las filas afectadas (0 si falla)."""
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, params)
            filas = cur.rowcount
            con.commit()
            return filas
        except Exception as e:
            app.logger.error(f"{mensaje_error}: {str(e)}")
            con.rollback()
            return 0
        finally:
            cur.close()
            con.close()

    def registrar_fallo(self, id_usuario):
        """
        Suma un intento fallido y bloquea la cuenta al llegar a
        MAX_INTENTOS_FALLIDOS. El incremento y el bloqueo se hacen en una sola
        sentencia (atómica ante intentos concurrentes). Retorna
        {"intentos": n, "bloqueado": bool} o None si falló.
        """
        sql = """
            UPDATE usuarios
            SET intentos_fallidos = intentos_fallidos + 1,
                bloqueado = (intentos_fallidos + 1 >= %s),
                fecha_bloqueo = CASE WHEN intentos_fallidos + 1 >= %s
                                     THEN NOW() ELSE fecha_bloqueo END
            WHERE id_usuario = %s
            RETURNING intentos_fallidos, bloqueado
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (MAX_INTENTOS_FALLIDOS, MAX_INTENTOS_FALLIDOS, id_usuario))
            fila = cur.fetchone()
            con.commit()
            return {"intentos": fila[0], "bloqueado": fila[1]} if fila else None
        except Exception as e:
            app.logger.error(f"Error al registrar intento fallido: {str(e)}")
            con.rollback()
            return None
        finally:
            cur.close()
            con.close()

    def liberar_bloqueo_vencido(self, id_usuario):
        """
        Levanta el bloqueo si ya pasaron BLOQUEO_MINUTOS (desbloqueo por tiempo).
        """
        sql = """
            UPDATE usuarios
            SET bloqueado = FALSE, intentos_fallidos = 0, fecha_bloqueo = NULL
            WHERE id_usuario = %s AND bloqueado
              AND fecha_bloqueo <= NOW()::timestamp - make_interval(mins => %s)
        """
        return self._ejecutar_update(
            sql, (id_usuario, BLOQUEO_MINUTOS), "Error al liberar bloqueo vencido"
        ) > 0

    def reiniciar_intentos(self, id_usuario):
        """
        Pone el contador en 0 al completar el login (después del 2FA). No toca
        cuentas bloqueadas: ese estado solo lo levanta el tiempo o el admin.
        """
        sql = """
            UPDATE usuarios SET intentos_fallidos = 0
            WHERE id_usuario = %s AND NOT bloqueado AND intentos_fallidos <> 0
        """
        return self._ejecutar_update(sql, (id_usuario,), "Error al reiniciar intentos fallidos") > 0

    def restablecer_password(self, id_usuario, password):
        """
        Cambia la contraseña por recuperación (texto plano -> hash) y, en la
        misma sentencia, desbloquea la cuenta y reinicia el contador de intentos.
        """
        sql = """
            UPDATE usuarios
            SET password_hash = %s, bloqueado = FALSE, intentos_fallidos = 0, fecha_bloqueo = NULL
            WHERE id_usuario = %s AND activo = TRUE
        """
        return self._ejecutar_update(
            sql, (generate_password_hash(password), id_usuario), "Error al restablecer contraseña"
        ) > 0

    def desbloquear(self, id_usuario):
        """
        Desbloqueo manual (Administrador) o por recuperación de contraseña.
        Retorna True si la cuenta estaba bloqueada y se liberó.
        """
        sql = """
            UPDATE usuarios
            SET bloqueado = FALSE, intentos_fallidos = 0, fecha_bloqueo = NULL
            WHERE id_usuario = %s AND bloqueado
        """
        return self._ejecutar_update(sql, (id_usuario,), "Error al desbloquear usuario") > 0

    def getUsuarios(self):
        """
        Trae todos los usuarios (activos e inactivos) con su rol y el nombre
        completo de la persona vinculada, para la grilla de administración.
        """
        sql = """
            SELECT u.id_usuario, {ci}, {correo}, u.id_rol, r.nombre_rol,
                   u.id_funcionario, u.id_medico, u.activo, u.fecha_creacion,
                   COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido) AS nombre_completo,
                   CASE WHEN u.id_funcionario IS NOT NULL THEN 'Funcionario' ELSE 'Medico' END AS tipo_persona,
                   (u.bloqueado AND u.fecha_bloqueo > NOW()::timestamp - make_interval(mins => %s)) AS bloqueado_vigente
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id_rol
            LEFT JOIN funcionario f ON u.id_funcionario = f.id_funcionario
            LEFT JOIN medico m ON u.id_medico = m.id_medico
            ORDER BY u.id_usuario
        """.format(ci=SQL_CI_RUC, correo=SQL_CORREO)
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (BLOQUEO_MINUTOS,))
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
                    "bloqueado": bool(u[11]),
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
            SELECT u.id_usuario, {ci}, {correo}, u.id_rol, r.nombre_rol,
                   u.id_funcionario, u.id_medico, u.activo, u.fecha_creacion,
                   COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido) AS nombre_completo
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id_rol
            LEFT JOIN funcionario f ON u.id_funcionario = f.id_funcionario
            LEFT JOIN medico m ON u.id_medico = m.id_medico
            WHERE u.id_usuario = %s
        """.format(ci=SQL_CI_RUC, correo=SQL_CORREO)
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

    def getDatosPersona(self, id_funcionario, id_medico):
        """
        CI/RUC y correo actuales de la persona a vincular (la fuente de verdad).
        Retorna None si la persona no existe; si existe, {"ci_ruc", "correo"}
        con None en lo que no tenga cargado. El alta/edición de usuario exige
        ambos antes de vincular.
        """
        if id_funcionario:
            sql = "SELECT cedula, NULLIF(TRIM(correo), '') FROM funcionario WHERE id_funcionario = %s"
            param = id_funcionario
        else:
            sql = "SELECT cedula, NULLIF(TRIM(correo), '') FROM medico WHERE id_medico = %s"
            param = id_medico

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (param,))
            fila = cur.fetchone()
            if not fila:
                return None
            return {"ci_ruc": (fila[0] or '').strip() or None, "correo": fila[1]}
        except Exception as e:
            app.logger.error(f"Error al obtener datos de la persona: {str(e)}")
            return None
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

    def guardarUsuario(self, password, id_rol, id_funcionario, id_medico):
        """
        Da de alta un usuario nuevo. La contraseña se recibe en texto plano
        y se guarda hasheada. CI/RUC y correo no se guardan: salen de la persona.
        """
        sql = """
            INSERT INTO usuarios (password_hash, id_rol, id_funcionario, id_medico)
            VALUES (%s, %s, %s, %s)
            RETURNING id_usuario
        """
        password_hash = generate_password_hash(password)
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (password_hash, id_rol, id_funcionario, id_medico))
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

    def updateUsuario(self, id_usuario, id_rol, id_funcionario, id_medico, password=None):
        """
        Actualiza los datos de un usuario. Si se pasa password, también se
        actualiza el hash; si no, la contraseña actual queda sin cambios.
        """
        if password:
            sql = """
                UPDATE usuarios
                SET id_rol=%s, id_funcionario=%s, id_medico=%s, password_hash=%s
                WHERE id_usuario=%s
            """
            params = (id_rol, id_funcionario, id_medico, generate_password_hash(password), id_usuario)
        else:
            sql = """
                UPDATE usuarios
                SET id_rol=%s, id_funcionario=%s, id_medico=%s
                WHERE id_usuario=%s
            """
            params = (id_rol, id_funcionario, id_medico, id_usuario)

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
            SELECT f.id_funcionario, f.nombre, f.apellido, f.cedula, NULLIF(TRIM(f.correo), '')
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
                {"id_funcionario": f[0], "nombre_completo": f"{f[1]} {f[2]}", "ci_ruc": f[3], "correo": f[4]}
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
            SELECT m.id_medico, m.nombre, m.apellido, m.cedula, NULLIF(TRIM(m.correo), '')
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
                {"id_medico": m[0], "nombre_completo": f"{m[1]} {m[2]}", "ci_ruc": m[3], "correo": m[4]}
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
