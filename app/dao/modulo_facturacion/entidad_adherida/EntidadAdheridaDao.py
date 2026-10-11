# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

# Códigos de resultado de guardar/update (además de un ID o True)
DUPLICADO = "DUPLICADO"
EMISORA_INVALIDA = "EMISORA_INVALIDA"
MARCA_INVALIDA = "MARCA_INVALIDA"

_SELECT = """
SELECT a.id_entidad_adherida, a.id_entidad_emisora, e.descripcion,
       a.id_marca_tarjeta, m.descripcion,
       a.descripcion, a.direccion, a.telefono, a.correo, a.activo
FROM entidad_adherida a
JOIN entidad_emisora e ON e.id_entidad_emisora = a.id_entidad_emisora
JOIN marca_tarjeta   m ON m.id_marca_tarjeta   = a.id_marca_tarjeta
"""


def _a_dict(f):
    return {
        'id_entidad_adherida': f[0],
        'id_entidad_emisora': f[1], 'entidad_emisora': f[2],
        'id_marca_tarjeta': f[3], 'marca_tarjeta': f[4],
        'descripcion': f[5], 'direccion': f[6], 'telefono': f[7], 'correo': f[8],
        'activo': f[9]
    }


class EntidadAdheridaDao:

    def getEntidadesAdheridas(self):
        sql = _SELECT + " WHERE a.activo = true ORDER BY a.descripcion, e.descripcion, m.descripcion"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            return [_a_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener entidades adheridas: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getEntidadAdheridaById(self, id_entidad_adherida):
        sql = _SELECT + " WHERE a.id_entidad_adherida = %s AND a.activo = true"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_entidad_adherida,))
            f = cur.fetchone()
            return _a_dict(f) if f else None
        except Exception as e:
            app.logger.error(f"Error al obtener entidad adherida: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, descripcion, id_entidad_emisora, id_marca_tarjeta, excluir_id=None):
        """Indica si ya hay una adherida ACTIVA con la misma descripción + emisora + marca."""
        sql = """
        SELECT 1 FROM entidad_adherida
        WHERE activo = true AND UPPER(descripcion) = UPPER(%s)
          AND id_entidad_emisora = %s AND id_marca_tarjeta = %s
        """
        params = [descripcion, id_entidad_emisora, id_marca_tarjeta]
        if excluir_id:
            sql += " AND id_entidad_adherida != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de entidad adherida: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def _validar_referencias(self, cur, id_entidad_emisora, id_marca_tarjeta):
        """
        Bloquea (FOR SHARE) la emisora y la marca y verifica que existan y estén activas.
        El bloqueo dura hasta el commit: una baja concurrente de la emisora/marca (que toma
        FOR UPDATE) espera a que esta transacción termine. Devuelve un código de error o None.
        """
        cur.execute("SELECT 1 FROM entidad_emisora WHERE id_entidad_emisora = %s AND activo = true FOR SHARE",
                    (id_entidad_emisora,))
        if cur.fetchone() is None:
            return EMISORA_INVALIDA
        cur.execute("SELECT 1 FROM marca_tarjeta WHERE id_marca_tarjeta = %s AND activo = true FOR SHARE",
                    (id_marca_tarjeta,))
        if cur.fetchone() is None:
            return MARCA_INVALIDA
        return None

    def guardarEntidadAdherida(self, id_entidad_emisora, id_marca_tarjeta, descripcion, direccion, telefono, correo):
        """
        Returns:
            int | str | bool: ID nuevo; DUPLICADO / EMISORA_INVALIDA / MARCA_INVALIDA; False ante otro error.
        """
        sql = """
        INSERT INTO entidad_adherida(id_entidad_emisora, id_marca_tarjeta, descripcion, direccion, telefono, correo)
        VALUES(%s, %s, %s, %s, %s, %s) RETURNING id_entidad_adherida
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            error = self._validar_referencias(cur, id_entidad_emisora, id_marca_tarjeta)
            if error:
                con.rollback()
                return error
            cur.execute(sql, (id_entidad_emisora, id_marca_tarjeta, descripcion.upper(),
                              direccion, telefono, correo.lower()))
            nuevo_id = cur.fetchone()[0]
            con.commit()
            return nuevo_id
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al insertar entidad adherida: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateEntidadAdherida(self, id_entidad_adherida, id_entidad_emisora, id_marca_tarjeta,
                              descripcion, direccion, telefono, correo):
        """
        Returns:
            bool | str: True si se actualizó, False si no existe o falló;
            DUPLICADO / EMISORA_INVALIDA / MARCA_INVALIDA.
        """
        sql = """
        UPDATE entidad_adherida
        SET id_entidad_emisora = %s, id_marca_tarjeta = %s, descripcion = %s,
            direccion = %s, telefono = %s, correo = %s
        WHERE id_entidad_adherida = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            error = self._validar_referencias(cur, id_entidad_emisora, id_marca_tarjeta)
            if error:
                con.rollback()
                return error
            cur.execute(sql, (id_entidad_emisora, id_marca_tarjeta, descripcion.upper(),
                              direccion, telefono, correo.lower(), id_entidad_adherida))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al actualizar entidad adherida: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def esta_en_uso(self, id_entidad_adherida):
        """Indica si la entidad adherida está usada en algún cobro con tarjeta."""
        # TODO: debe consultar cobro_tarjeta (WHERE id_entidad_adherida = %s) cuando exista
        # la tabla. Mientras tanto no hay nada que pueda referenciarla.
        return False

    def deleteEntidadAdherida(self, id_entidad_adherida):
        """
        Anula (baja lógica) una entidad adherida, validando antes que no esté en uso.

        Returns:
            bool | tuple: True si se anuló, False si no existía o falló, ("EN_USO", motivo) si está en uso.
        """
        motivo = self.esta_en_uso(id_entidad_adherida)
        if motivo:
            app.logger.warning(f"No se puede anular entidad adherida {id_entidad_adherida}: está en uso")
            return ("EN_USO", motivo if isinstance(motivo, str) else
                    "No se puede dar de baja, la entidad adherida está usada en un cobro con tarjeta.")

        sql = """
        UPDATE entidad_adherida
        SET activo = false
        WHERE id_entidad_adherida = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_entidad_adherida,))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except Exception as e:
            app.logger.error(f"Error al anular entidad adherida: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
