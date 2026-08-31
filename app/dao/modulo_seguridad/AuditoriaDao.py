# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion


class AuditoriaDao:

    def registrar(self, id_usuario, ci_ruc_ingresado, resultado, ip, accion):
        """
        Registra un intento de acceso (login, verificación 2FA o logout).
        id_usuario puede ser None cuando el CI/RUC ingresado no existe.
        """
        sql = """
            INSERT INTO auditoria_acceso (id_usuario, ci_ruc_ingresado, resultado, ip, accion)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id_auditoria
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_usuario, ci_ruc_ingresado, resultado, ip, accion))
            id_auditoria = cur.fetchone()[0]
            con.commit()
            return id_auditoria
        except Exception as e:
            app.logger.error(f"Error al registrar auditoría de acceso: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def get_ultimos_intentos(self, limite):
        """
        Trae los últimos intentos de acceso (exitosos y fallidos) para el
        tablero de administrador, del más reciente al más antiguo.
        """
        sql = """
            SELECT id_auditoria, id_usuario, ci_ruc_ingresado, fecha_hora,
                   resultado, ip, accion
            FROM auditoria_acceso
            ORDER BY fecha_hora DESC
            LIMIT %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (limite,))
            intentos = cur.fetchall()
            return [
                {
                    "id_auditoria": i[0],
                    "id_usuario": i[1],
                    "ci_ruc_ingresado": i[2],
                    "fecha_hora": str(i[3]) if i[3] else None,
                    "resultado": i[4],
                    "ip": i[5],
                    "accion": i[6],
                }
                for i in intentos
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener últimos intentos de acceso: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()
