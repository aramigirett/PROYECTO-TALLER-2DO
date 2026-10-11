# Data Access Object - DAO
from flask import current_app as app
from app.conexion.Conexion import Conexion


class AuditoriaCambiosDao:
    """
    Auditoría de cambios sobre datos (ALTA / MODIFICACION / BAJA).
    Distinta de AuditoriaDao, que registra solo intentos de acceso.
    """

    def registrar(self, id_usuario, entidad, id_registro, accion, detalle, ip):
        """
        id_usuario e ip los debe tomar quien llama de la sesión y del request
        (nunca del cliente). Un fallo al auditar se loguea pero no debe tirar
        abajo la operación ya confirmada: devuelve False en ese caso.
        """
        sql = """
        INSERT INTO auditoria_cambios (id_usuario, entidad, id_registro, accion, detalle, ip)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id_auditoria_cambio
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_usuario, entidad, id_registro, accion,
                              (detalle or '')[:255], (ip or '')[:45]))
            nuevo_id = cur.fetchone()[0]
            con.commit()
            return nuevo_id
        except Exception as e:
            app.logger.error(f"Error al registrar auditoría de cambios: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
