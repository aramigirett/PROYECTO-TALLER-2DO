# Data Access Object - DAO
import re

from flask import current_app as app
from app.conexion.Conexion import Conexion

# Un identificador que NO corresponde a ningún usuario solo se audita si tiene
# forma de CI/RUC (dígitos, con dígito verificador opcional). Así, si alguien
# escribe su contraseña en el campo CI/RUC, no queda guardada en la auditoría.
_FORMATO_CI_RUC = re.compile(r'^[0-9]{1,12}(-[0-9A-Za-z])?$')
CI_RUC_NO_VALIDO = '[formato inválido]'

class AuditoriaDao:

    def registrar(self, id_usuario, ci_ruc_ingresado, resultado, ip, accion, id_usuario_actor=None):
        """
        Registra un intento de acceso (login, verificación 2FA o logout).
        id_usuario puede ser None cuando el CI/RUC ingresado no existe.
        id_usuario_actor: quien ejecutó la acción cuando no es el propio
        usuario (ej. el Administrador que desbloquea una cuenta).
        NUNCA recibe ni guarda contraseñas: ci_ruc_ingresado se trunca a 20
        caracteres y, si no hay usuario, se descarta lo que no parezca un CI/RUC.
        """
        ci_ruc_ingresado = (ci_ruc_ingresado or '').strip()
        if id_usuario is None and not _FORMATO_CI_RUC.match(ci_ruc_ingresado):
            ci_ruc_ingresado = CI_RUC_NO_VALIDO
        ci_ruc_ingresado = ci_ruc_ingresado[:20]

        sql = """
            INSERT INTO auditoria_acceso (id_usuario, ci_ruc_ingresado, resultado, ip, accion, id_usuario_actor)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id_auditoria
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_usuario, ci_ruc_ingresado, resultado, ip, accion, id_usuario_actor))
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

    def registrar_cambio_cedula(self, id_usuario, cedula_anterior, cedula_nueva, ip, id_usuario_actor):
        """
        Registra que cambió el CI/RUC de login de un usuario porque se editó la
        cédula de su persona vinculada. ci_ruc_ingresado guarda la cédula nueva
        (la que vale desde ahora para entrar) y resultado la anterior.
        """
        return self.registrar(id_usuario, cedula_nueva, f"ANTES: {cedula_anterior}"[:30],
                              ip, 'CAMBIO_CEDULA', id_usuario_actor)

    def get_ultimos_intentos(self, limite, desde=None, hasta=None):
        """
        Trae los últimos intentos de acceso (exitosos y fallidos) para el
        tablero de administrador, del más reciente al más antiguo. desde/hasta
        son objetos date (ambos inclusive) y son opcionales.
        """
        filtros = []
        params = []
        if desde:
            filtros.append("a.fecha_hora >= %s")
            params.append(desde)
        if hasta:
            filtros.append("a.fecha_hora < %s::date + 1")
            params.append(hasta)
        where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
        params.append(limite)

        sql = f"""
            SELECT a.id_auditoria, a.id_usuario, a.ci_ruc_ingresado, a.fecha_hora,
                   a.resultado, a.ip, a.accion, COALESCE(af.cedula, am.cedula)
            FROM auditoria_acceso a
            LEFT JOIN usuarios act ON a.id_usuario_actor = act.id_usuario
            LEFT JOIN funcionario af ON act.id_funcionario = af.id_funcionario
            LEFT JOIN medico am ON act.id_medico = am.id_medico
            {where}
            ORDER BY a.fecha_hora DESC
            LIMIT %s
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
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
                    "actor_ci_ruc": i[7],
                }
                for i in intentos
            ]
        except Exception as e:
            app.logger.error(f"Error al obtener últimos intentos de acceso: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()
