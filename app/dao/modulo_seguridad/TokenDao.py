# Data Access Object - DAO
import secrets
from flask import current_app as app
from app.conexion.Conexion import Conexion

# Recuperación de contraseña
RECUPERACION_MINUTOS = 10
RECUPERACION_MAX_INTENTOS = 5
RECUPERACION_COOLDOWN_SEGUNDOS = 60


class TokenDao:

    def generar_codigo(self, id_usuario):
        """
        Invalida los códigos previos no usados del usuario y genera un código
        nuevo de 6 dígitos, válido por 5 minutos. Retorna el código generado.
        """
        invalidarSQL = """
            UPDATE token_2fa
            SET usado = TRUE
            WHERE id_usuario = %s AND usado = FALSE AND proposito = 'LOGIN'
        """
        insertSQL = """
            INSERT INTO token_2fa (id_usuario, codigo, fecha_expiracion)
            VALUES (%s, %s, NOW() + INTERVAL '5 minutes')
            RETURNING codigo
        """
        codigo = str(secrets.randbelow(900000) + 100000)
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(invalidarSQL, (id_usuario,))
            cur.execute(insertSQL, (id_usuario, codigo))
            codigo_generado = cur.fetchone()[0]
            con.commit()
            return codigo_generado
        except Exception as e:
            app.logger.error(f"Error al generar código 2FA: {str(e)}")
            con.rollback()
            return None
        finally:
            cur.close()
            con.close()

    def validar_codigo(self, id_usuario, codigo):
        """
        Valida el código 2FA ingresado por el usuario.
        Retorna 'OK', 'INVALIDO' o 'EXPIRADO'.
        Si es válido y vigente, lo marca como usado.
        """
        sql = """
            SELECT id_token, fecha_expiracion, usado
            FROM token_2fa
            WHERE id_usuario = %s AND codigo = %s AND proposito = 'LOGIN'
            ORDER BY fecha_generacion DESC
            LIMIT 1
        """
        marcarUsadoSQL = """
            UPDATE token_2fa SET usado = TRUE WHERE id_token = %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_usuario, codigo))
            token = cur.fetchone()
            if not token:
                return "INVALIDO"

            id_token, fecha_expiracion, usado = token

            if usado:
                return "INVALIDO"

            cur.execute("SELECT NOW()::timestamp")
            ahora = cur.fetchone()[0]
            if fecha_expiracion < ahora:
                return "EXPIRADO"

            cur.execute(marcarUsadoSQL, (id_token,))
            con.commit()
            return "OK"
        except Exception as e:
            app.logger.error(f"Error al validar código 2FA: {str(e)}")
            con.rollback()
            return "INVALIDO"
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------
    # Recuperación de contraseña (mismo mecanismo, propósito 'RECUPERACION')
    # ------------------------------------------------------------------

    def hay_codigo_reciente(self, id_usuario, proposito, segundos):
        """
        True si ya se generó un código de ese propósito hace menos de `segundos`
        (evita que /recuperar se use para llenar de correos a un usuario).
        """
        sql = """
            SELECT 1 FROM token_2fa
            WHERE id_usuario = %s AND proposito = %s
              AND fecha_generacion > NOW()::timestamp - make_interval(secs => %s)
            LIMIT 1
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_usuario, proposito, segundos))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al consultar código reciente: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def generar_codigo_recuperacion(self, id_usuario):
        """
        Invalida los códigos de recuperación previos sin usar del usuario y
        genera uno nuevo de 6 dígitos, válido por RECUPERACION_MINUTOS.
        No toca los códigos de login (2FA). Retorna el código o None.
        """
        invalidarSQL = """
            UPDATE token_2fa SET usado = TRUE
            WHERE id_usuario = %s AND proposito = 'RECUPERACION' AND usado = FALSE
        """
        insertSQL = """
            INSERT INTO token_2fa (id_usuario, codigo, fecha_expiracion, proposito)
            VALUES (%s, %s, NOW() + make_interval(mins => %s), 'RECUPERACION')
        """
        codigo = str(secrets.randbelow(900000) + 100000)
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(invalidarSQL, (id_usuario,))
            cur.execute(insertSQL, (id_usuario, codigo, RECUPERACION_MINUTOS))
            con.commit()
            return codigo
        except Exception as e:
            app.logger.error(f"Error al generar código de recuperación: {str(e)}")
            con.rollback()
            return None
        finally:
            cur.close()
            con.close()

    def validar_codigo_recuperacion(self, id_usuario, codigo):
        """
        Valida el código de recuperación contra el ÚLTIMO código vigente del
        usuario. Es de un solo uso (se marca usado al validar) y se invalida
        tras RECUPERACION_MAX_INTENTOS códigos erróneos.
        Retorna 'OK' o 'INVALIDO' (inexistente, usado, vencido o agotado: la
        interfaz muestra un único mensaje para no filtrar información).
        """
        sql = """
            SELECT id_token, codigo, intentos_fallidos, fecha_expiracion >= NOW()::timestamp
            FROM token_2fa
            WHERE id_usuario = %s AND proposito = 'RECUPERACION' AND usado = FALSE
            ORDER BY fecha_generacion DESC
            LIMIT 1
            FOR UPDATE
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_usuario,))
            token = cur.fetchone()
            if not token:
                return "INVALIDO"
            id_token, codigo_real, intentos, vigente = token

            if not vigente or intentos >= RECUPERACION_MAX_INTENTOS:
                cur.execute("UPDATE token_2fa SET usado = TRUE WHERE id_token = %s", (id_token,))
                con.commit()
                return "INVALIDO"

            if secrets.compare_digest(str(codigo_real), str(codigo)):
                cur.execute("UPDATE token_2fa SET usado = TRUE WHERE id_token = %s", (id_token,))
                con.commit()
                return "OK"

            cur.execute("""
                UPDATE token_2fa
                SET intentos_fallidos = intentos_fallidos + 1,
                    usado = (intentos_fallidos + 1 >= %s)
                WHERE id_token = %s
            """, (RECUPERACION_MAX_INTENTOS, id_token))
            con.commit()
            return "INVALIDO"
        except Exception as e:
            app.logger.error(f"Error al validar código de recuperación: {str(e)}")
            con.rollback()
            return "INVALIDO"
        finally:
            cur.close()
            con.close()

    def invalidar_codigos_recuperacion(self, id_usuario):
        """Marca como usados todos los códigos de recuperación pendientes."""
        sql = """
            UPDATE token_2fa SET usado = TRUE
            WHERE id_usuario = %s AND proposito = 'RECUPERACION' AND usado = FALSE
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_usuario,))
            con.commit()
        except Exception as e:
            app.logger.error(f"Error al invalidar códigos de recuperación: {str(e)}")
            con.rollback()
        finally:
            cur.close()
            con.close()
