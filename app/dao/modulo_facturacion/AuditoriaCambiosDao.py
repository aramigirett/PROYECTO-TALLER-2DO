# Data Access Object - DAO
import json

from flask import current_app as app
from app.conexion.Conexion import Conexion


class AuditoriaCambiosDao:
    """
    Auditoría de cambios sobre datos (ALTA / MODIFICACION / BAJA / REACTIVACION / CIERRE / EXPORTACION).
    Distinta de AuditoriaDao, que registra solo intentos de acceso. La lectura (pantalla Auditoría de Cambios) está en
    app/dao/modulo_seguridad/AuditoriaConsultaDao.py: este DAO solo inserta.
    """

    def registrar(self, id_usuario, entidad, id_registro, accion, detalle, ip,
                  modulo=None, valores_anteriores=None, valores_nuevos=None):
        """
        id_usuario e ip los debe tomar quien llama de la sesión y del request
        (nunca del cliente). Un fallo al auditar se loguea pero no debe tirar
        abajo la operación ya confirmada: devuelve False en ese caso.
        modulo: módulo de la entidad. valores_anteriores / valores_nuevos: dict {campo: valor} con solo lo que
        cambió (se guardan como JSONB; None = sin dato). El detalle de texto ya no se corta (columna TEXT).
        """
        sql = """
        INSERT INTO auditoria_cambios (id_usuario, entidad, id_registro, accion, detalle, ip,
                                       modulo, valores_anteriores, valores_nuevos)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
        RETURNING id_auditoria_cambio
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_usuario, entidad, id_registro, accion, str(detalle or ''), (ip or '')[:45], modulo,
                              json.dumps(valores_anteriores, ensure_ascii=False) if valores_anteriores is not None else None,
                              json.dumps(valores_nuevos, ensure_ascii=False) if valores_nuevos is not None else None))
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
