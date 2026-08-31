# Data Access Object - DAO
import secrets
from flask import current_app as app
from app.conexion.Conexion import Conexion


class TokenDao:

    def generar_codigo(self, id_usuario):
        """
        Invalida los códigos previos no usados del usuario y genera un código
        nuevo de 6 dígitos, válido por 5 minutos. Retorna el código generado.
        """
        invalidarSQL = """
            UPDATE token_2fa
            SET usado = TRUE
            WHERE id_usuario = %s AND usado = FALSE
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
            WHERE id_usuario = %s AND codigo = %s
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
