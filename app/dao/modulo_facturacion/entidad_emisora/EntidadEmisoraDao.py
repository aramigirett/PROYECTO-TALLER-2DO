# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

# Códigos de resultado (además de un ID o True)
DUPLICADO = "DUPLICADO"
NO_EXISTE = "NO_EXISTE"
YA_ACTIVO = "YA_ACTIVO"

_COLUMNAS = "id_entidad_emisora, descripcion, direccion, telefono, correo, activo"


def _a_dict(f):
    return {
        'id_entidad_emisora': f[0], 'descripcion': f[1], 'direccion': f[2],
        'telefono': f[3], 'correo': f[4], 'activo': f[5]
    }


class EntidadEmisoraDao:

    def getEntidadesEmisoras(self, incluir_inactivos=False):
        sql = f"SELECT {_COLUMNAS} FROM entidad_emisora" + ("" if incluir_inactivos else " WHERE activo = true") + " ORDER BY activo DESC, descripcion"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            return [_a_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener entidades emisoras: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getEntidadEmisoraById(self, id_entidad_emisora, incluir_inactivos=False):
        sql = f"SELECT {_COLUMNAS} FROM entidad_emisora WHERE id_entidad_emisora = %s" + ("" if incluir_inactivos else " AND activo = true")
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_entidad_emisora,))
            f = cur.fetchone()
            return _a_dict(f) if f else None
        except Exception as e:
            app.logger.error(f"Error al obtener entidad emisora: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, descripcion, excluir_id=None):
        """Indica si ya hay una entidad emisora ACTIVA con esa descripción (sin distinguir mayúsculas)."""
        sql = "SELECT 1 FROM entidad_emisora WHERE activo = true AND UPPER(descripcion) = UPPER(%s)"
        params = [descripcion]
        if excluir_id:
            sql += " AND id_entidad_emisora != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de entidad emisora: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def guardarEntidadEmisora(self, descripcion, direccion, telefono, correo):
        """
        Returns:
            int | str | bool: ID nuevo, "DUPLICADO" si el índice único lo rechaza, False ante otro error.
        """
        sql = """
        INSERT INTO entidad_emisora(descripcion, direccion, telefono, correo)
        VALUES(%s, %s, %s, %s) RETURNING id_entidad_emisora
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion.upper(), direccion, telefono, correo.lower()))
            nuevo_id = cur.fetchone()[0]
            con.commit()
            return nuevo_id
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return "DUPLICADO"
        except Exception as e:
            app.logger.error(f"Error al insertar entidad emisora: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateEntidadEmisora(self, id_entidad_emisora, descripcion, direccion, telefono, correo):
        """
        Returns:
            bool | str: True si se actualizó, False si no existe o falló, "DUPLICADO" si el índice lo rechaza.
        """
        sql = """
        UPDATE entidad_emisora
        SET descripcion = %s, direccion = %s, telefono = %s, correo = %s
        WHERE id_entidad_emisora = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (descripcion.upper(), direccion, telefono, correo.lower(), id_entidad_emisora))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return "DUPLICADO"
        except Exception as e:
            app.logger.error(f"Error al actualizar entidad emisora: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def _motivo_en_uso(self, cur, id_entidad_emisora):
        """Devuelve el motivo (texto para el usuario) si la entidad emisora está en uso, o False."""
        cur.execute(
            "SELECT EXISTS(SELECT 1 FROM entidad_adherida WHERE id_entidad_emisora = %s AND activo = true)",
            (id_entidad_emisora,))
        if cur.fetchone()[0]:
            return "No se puede dar de baja, el banco está asociado a una entidad adherida."
        # TODO: debe consultar cobro_tarjeta y cobro_cheque (WHERE id_entidad_emisora = %s)
        # cuando existan esas tablas. Mientras tanto no hay nada más que pueda referenciarla.
        return False

    def esta_en_uso(self, id_entidad_emisora):
        """False si se puede anular; si no, el texto con el motivo (truthy)."""
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            return self._motivo_en_uso(cur, id_entidad_emisora)
        except Exception as e:
            app.logger.error(f"Error al verificar uso de entidad emisora: {str(e)}")
            return "No se pudo verificar si el banco está en uso."  # ante la duda, bloquear
        finally:
            cur.close()
            con.close()

    def deleteEntidadEmisora(self, id_entidad_emisora):
        """
        Anula (baja lógica) una entidad emisora. Verificación de uso y UPDATE en la misma
        transacción, con la fila bloqueada, para que no se cuele una entidad adherida nueva.

        Returns:
            bool | tuple: True si se anuló, False si no existía o falló, ("EN_USO", motivo) si está en uso.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(
                "SELECT 1 FROM entidad_emisora WHERE id_entidad_emisora = %s AND activo = true FOR UPDATE",
                (id_entidad_emisora,))
            if cur.fetchone() is None:
                con.rollback()
                return False

            motivo = self._motivo_en_uso(cur, id_entidad_emisora)
            if motivo:
                con.rollback()
                app.logger.warning(f"No se puede anular entidad emisora {id_entidad_emisora}: está en uso")
                return ("EN_USO", motivo)

            cur.execute("UPDATE entidad_emisora SET activo = false WHERE id_entidad_emisora = %s",
                        (id_entidad_emisora,))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al anular entidad emisora: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def reactivarEntidadEmisora(self, id_entidad_emisora):
        """
        Reactiva la entidad emisora anulada. En una sola transacción: bloquea el registro y valida que no haya otro
        ACTIVO con la misma descripción.

        Returns:
            bool | str: True si se reactivó; NO_EXISTE, YA_ACTIVO o DUPLICADO; False ante otro error.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT descripcion, activo FROM entidad_emisora WHERE id_entidad_emisora = %s FOR UPDATE", (id_entidad_emisora,))
            fila = cur.fetchone()
            if fila is None:
                con.rollback()
                return NO_EXISTE
            descripcion, activo = fila
            if activo:
                con.rollback()
                return YA_ACTIVO

            cur.execute("""
                SELECT 1 FROM entidad_emisora
                WHERE activo = true AND UPPER(descripcion) = UPPER(%s) AND id_entidad_emisora != %s
            """, (descripcion, id_entidad_emisora))
            if cur.fetchone() is not None:
                con.rollback()
                return DUPLICADO

            cur.execute("UPDATE entidad_emisora SET activo = true WHERE id_entidad_emisora = %s", (id_entidad_emisora,))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al reactivar la entidad emisora: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
