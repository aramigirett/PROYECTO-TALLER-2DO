# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

# Códigos de resultado (además de un ID o True)
DUPLICADO = "DUPLICADO"
CONSULTORIO_INVALIDO = "CONSULTORIO_INVALIDO"
NO_EXISTE = "NO_EXISTE"
YA_ACTIVA = "YA_ACTIVA"

# Mensaje para cuando exista apertura_cierre_caja (ver esta_en_uso)
MSG_BAJA_APERTURA_ACTIVA = "No se puede dar de baja, la caja tiene una apertura activa."

# El consultorio no tiene baja lógica (tabla `consultorio`, PK `codigo`): "activo" = "existe".
_SELECT = """
SELECT c.id_caja, c.id_consultorio, k.nombre_consultorio, c.descripcion, c.activo
FROM caja c
JOIN consultorio k ON k.codigo = c.id_consultorio
"""


def _a_dict(f):
    return {'id_caja': f[0], 'id_consultorio': f[1], 'consultorio': f[2], 'descripcion': f[3], 'activo': f[4]}


class CajaDao:

    def getCajas(self, incluir_inactivas=False):
        sql = _SELECT + ("" if incluir_inactivas else " WHERE c.activo = true") + \
              " ORDER BY c.activo DESC, k.nombre_consultorio, c.descripcion"
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            return [_a_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener cajas: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getCajaById(self, id_caja, incluir_inactivas=False):
        sql = _SELECT + " WHERE c.id_caja = %s" + ("" if incluir_inactivas else " AND c.activo = true")
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_caja,))
            f = cur.fetchone()
            return _a_dict(f) if f else None
        except Exception as e:
            app.logger.error(f"Error al obtener caja: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, id_consultorio, descripcion, excluir_id=None):
        """Indica si ya hay una caja ACTIVA con esa descripción (sin distinguir mayúsculas) en el consultorio."""
        sql = """
        SELECT 1 FROM caja
        WHERE activo = true AND id_consultorio = %s AND UPPER(descripcion) = UPPER(%s)
        """
        params = [id_consultorio, descripcion]
        if excluir_id:
            sql += " AND id_caja != %s"
            params.append(excluir_id)

        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de caja: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def _consultorio_existe(self, cur, id_consultorio):
        """Bloquea (FOR SHARE) la fila del consultorio y verifica que exista."""
        cur.execute("SELECT 1 FROM consultorio WHERE codigo = %s FOR SHARE", (id_consultorio,))
        return cur.fetchone() is not None

    def guardarCaja(self, id_consultorio, descripcion):
        """
        Returns:
            int | str | bool: ID nuevo; DUPLICADO / CONSULTORIO_INVALIDO; False ante otro error.
        """
        sql = """
        INSERT INTO caja(id_consultorio, descripcion)
        VALUES(%s, %s) RETURNING id_caja
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            if not self._consultorio_existe(cur, id_consultorio):
                con.rollback()
                return CONSULTORIO_INVALIDO
            cur.execute(sql, (id_consultorio, descripcion.upper()))
            nuevo_id = cur.fetchone()[0]
            con.commit()
            return nuevo_id
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al insertar caja: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateCaja(self, id_caja, id_consultorio, descripcion):
        """
        Returns:
            bool | str: True si se actualizó, False si no existe o falló; DUPLICADO / CONSULTORIO_INVALIDO.
        """
        sql = """
        UPDATE caja SET id_consultorio = %s, descripcion = %s
        WHERE id_caja = %s AND activo = true
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            if not self._consultorio_existe(cur, id_consultorio):
                con.rollback()
                return CONSULTORIO_INVALIDO
            cur.execute(sql, (id_consultorio, descripcion.upper(), id_caja))
            filas_afectadas = cur.rowcount
            con.commit()
            return filas_afectadas > 0
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al actualizar caja: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def _motivo_en_uso(self, cur, id_caja):
        """Devuelve el motivo (texto para el usuario) si la caja está en uso, o False."""
        cur.execute("SELECT EXISTS(SELECT 1 FROM apertura_cierre_caja WHERE id_caja = %s AND estado = 'ABIERTA')",
                    (id_caja,))
        if cur.fetchone()[0]:
            return MSG_BAJA_APERTURA_ACTIVA
        return False

    def esta_en_uso(self, id_caja):
        """False si se puede anular; si no, el texto con el motivo (truthy)."""
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            return self._motivo_en_uso(cur, id_caja)
        except Exception as e:
            app.logger.error(f"Error al verificar uso de caja: {str(e)}")
            return "No se pudo verificar si la caja está en uso."  # ante la duda, bloquear
        finally:
            cur.close()
            con.close()

    def deleteCaja(self, id_caja):
        """
        Anula (baja lógica) una caja. La verificación de uso y el UPDATE van en la misma transacción, con la
        fila bloqueada (FOR UPDATE): abrir una caja toma FOR SHARE sobre ella, así que no se puede colar una
        apertura entre ambos pasos.

        Returns:
            bool | tuple: True si se anuló, False si no existía o falló, ("EN_USO", motivo) si está en uso.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT 1 FROM caja WHERE id_caja = %s AND activo = true FOR UPDATE", (id_caja,))
            if cur.fetchone() is None:
                con.rollback()
                return False

            motivo = self._motivo_en_uso(cur, id_caja)
            if motivo:
                con.rollback()
                app.logger.warning(f"No se puede anular caja {id_caja}: está en uso")
                return ("EN_USO", motivo)

            cur.execute("UPDATE caja SET activo = false WHERE id_caja = %s", (id_caja,))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al anular caja: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def reactivarCaja(self, id_caja):
        """
        Reactiva una caja anulada. En una sola transacción: bloquea la caja, verifica que el
        consultorio exista y que no haya otra caja ACTIVA con la misma descripción en él.

        Returns:
            bool | str: True si se reactivó; NO_EXISTE, YA_ACTIVA, CONSULTORIO_INVALIDO o DUPLICADO;
            False ante otro error.
        """
        conexion = Conexion()
        con = conexion.getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_consultorio, descripcion, activo FROM caja WHERE id_caja = %s FOR UPDATE",
                        (id_caja,))
            fila = cur.fetchone()
            if fila is None:
                con.rollback()
                return NO_EXISTE
            id_consultorio, descripcion, activo = fila
            if activo:
                con.rollback()
                return YA_ACTIVA

            if not self._consultorio_existe(cur, id_consultorio):
                con.rollback()
                return CONSULTORIO_INVALIDO

            cur.execute("""
                SELECT 1 FROM caja
                WHERE activo = true AND id_consultorio = %s AND UPPER(descripcion) = UPPER(%s) AND id_caja != %s
            """, (id_consultorio, descripcion, id_caja))
            if cur.fetchone() is not None:
                con.rollback()
                return DUPLICADO

            cur.execute("UPDATE caja SET activo = true WHERE id_caja = %s", (id_caja,))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al reactivar caja: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
