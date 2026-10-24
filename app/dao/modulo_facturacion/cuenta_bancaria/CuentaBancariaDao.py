# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

# Códigos de resultado de guardar/update (además de un ID o True)
DUPLICADO = "DUPLICADO"
EMISORA_INVALIDA = "EMISORA_INVALIDA"
NO_EXISTE = "NO_EXISTE"
YA_ACTIVO = "YA_ACTIVO"
EMISORA_INACTIVA = "EMISORA_INACTIVA"

TIPOS_CUENTA = ('CORRIENTE', 'CAJA DE AHORRO')
MSG_BAJA_EN_USO = "No se puede dar de baja, la cuenta bancaria está usada en el depósito de una recaudación."
MSG_EDICION_EN_USO = "No se puede cambiar el banco, el tipo ni el número: la cuenta ya recibió depósitos de recaudación."

_SELECT = """
SELECT c.id_cuenta_bancaria, c.id_entidad_emisora, e.descripcion, c.tipo_cuenta, c.numero_cuenta, c.titular, c.activo
FROM cuenta_bancaria c
JOIN entidad_emisora e ON e.id_entidad_emisora = c.id_entidad_emisora
"""


def _a_dict(f):
    return {
        'id_cuenta_bancaria': f[0], 'id_entidad_emisora': f[1], 'entidad_emisora': f[2],
        'tipo_cuenta': f[3], 'numero_cuenta': f[4], 'titular': f[5], 'activo': f[6],
        'descripcion': f'{f[3]} {f[2]} {f[4]}',   # texto para combos y mensajes: "CORRIENTE BANCO ITAÚ 1020304050"
    }


class CuentaBancariaDao:

    def getCuentasBancarias(self, incluir_inactivos=False):
        sql = _SELECT + ("" if incluir_inactivos else " WHERE c.activo = true") + " ORDER BY c.activo DESC, e.descripcion, c.numero_cuenta"
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            return [_a_dict(f) for f in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener cuentas bancarias: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def getCuentaBancariaById(self, id_cuenta_bancaria, incluir_inactivos=False):
        sql = _SELECT + " WHERE c.id_cuenta_bancaria = %s" + ("" if incluir_inactivos else " AND c.activo = true")
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_cuenta_bancaria,))
            f = cur.fetchone()
            return _a_dict(f) if f else None
        except Exception as e:
            app.logger.error(f"Error al obtener cuenta bancaria: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, id_entidad_emisora, numero_cuenta, excluir_id=None):
        """Indica si ya hay una cuenta ACTIVA con el mismo banco y número."""
        sql = "SELECT 1 FROM cuenta_bancaria WHERE activo = true AND id_entidad_emisora = %s AND numero_cuenta = %s"
        params = [id_entidad_emisora, numero_cuenta]
        if excluir_id:
            sql += " AND id_cuenta_bancaria != %s"
            params.append(excluir_id)
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de cuenta bancaria: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    def _validar_banco(self, cur, id_entidad_emisora):
        """Bloquea (FOR SHARE) el banco y verifica que exista y esté activo: una baja concurrente del banco espera. Código de error o None."""
        cur.execute("SELECT 1 FROM entidad_emisora WHERE id_entidad_emisora = %s AND activo = true FOR SHARE", (id_entidad_emisora,))
        return None if cur.fetchone() else EMISORA_INVALIDA

    def guardarCuentaBancaria(self, id_entidad_emisora, tipo_cuenta, numero_cuenta, titular):
        """
        Returns:
            int | str | bool: ID nuevo; DUPLICADO / EMISORA_INVALIDA; False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            error = self._validar_banco(cur, id_entidad_emisora)
            if error:
                con.rollback()
                return error
            cur.execute("""INSERT INTO cuenta_bancaria(id_entidad_emisora, tipo_cuenta, numero_cuenta, titular)
                           VALUES (%s, %s, %s, %s) RETURNING id_cuenta_bancaria""",
                        (id_entidad_emisora, tipo_cuenta, numero_cuenta, titular.upper()))
            nuevo_id = cur.fetchone()[0]
            con.commit()
            return nuevo_id
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al insertar cuenta bancaria: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def updateCuentaBancaria(self, id_cuenta_bancaria, id_entidad_emisora, tipo_cuenta, numero_cuenta, titular):
        """
        Una cuenta que ya recibió depósitos solo puede cambiar de titular (el banco, el tipo y el número son parte del historial).

        Returns:
            bool | str | tuple: True si se actualizó, False si no existe o falló; DUPLICADO / EMISORA_INVALIDA;
            ("EN_USO", motivo) si se intenta cambiar banco/tipo/número de una cuenta con depósitos.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""SELECT id_entidad_emisora, tipo_cuenta, numero_cuenta FROM cuenta_bancaria
                           WHERE id_cuenta_bancaria = %s AND activo = true FOR UPDATE""", (id_cuenta_bancaria,))
            actual = cur.fetchone()
            if actual is None:
                con.rollback()
                return False
            if (actual[0], actual[1], actual[2]) != (id_entidad_emisora, tipo_cuenta, numero_cuenta):
                cur.execute("SELECT 1 FROM recaudacion_depositar WHERE id_cuenta_bancaria = %s AND estado <> 'ANULADA' LIMIT 1", (id_cuenta_bancaria,))
                if cur.fetchone():
                    con.rollback()
                    return ("EN_USO", MSG_EDICION_EN_USO)
            error = self._validar_banco(cur, id_entidad_emisora)
            if error:
                con.rollback()
                return error
            cur.execute("""UPDATE cuenta_bancaria SET id_entidad_emisora = %s, tipo_cuenta = %s, numero_cuenta = %s, titular = %s
                           WHERE id_cuenta_bancaria = %s""",
                        (id_entidad_emisora, tipo_cuenta, numero_cuenta, titular.upper(), id_cuenta_bancaria))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al actualizar cuenta bancaria: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def _motivo_en_uso(self, cur, id_cuenta_bancaria):
        """Devuelve el motivo (texto para el usuario) si la cuenta recibió el depósito de una recaudación, o False."""
        cur.execute("SELECT 1 FROM recaudacion_depositar WHERE id_cuenta_bancaria = %s AND estado <> 'ANULADA' LIMIT 1", (id_cuenta_bancaria,))
        return MSG_BAJA_EN_USO if cur.fetchone() else False

    def esta_en_uso(self, id_cuenta_bancaria):
        """False si se puede anular; si no, el texto con el motivo (truthy)."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            return self._motivo_en_uso(cur, id_cuenta_bancaria)
        except Exception as e:
            app.logger.error(f"Error al verificar uso de cuenta bancaria: {str(e)}")
            return "No se pudo verificar si la cuenta bancaria está en uso."  # ante la duda, bloquear
        finally:
            cur.close()
            con.close()

    def deleteCuentaBancaria(self, id_cuenta_bancaria):
        """
        Anula (baja lógica). Verificación de uso y UPDATE en la misma transacción, con la fila bloqueada (FOR UPDATE; marcar una
        recaudación como depositada toma FOR SHARE sobre la cuenta, así que no puede colarse).

        Returns:
            bool | tuple: True si se anuló, False si no existía o falló, ("EN_USO", motivo) si está en uso.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT 1 FROM cuenta_bancaria WHERE id_cuenta_bancaria = %s AND activo = true FOR UPDATE", (id_cuenta_bancaria,))
            if cur.fetchone() is None:
                con.rollback()
                return False
            motivo = self._motivo_en_uso(cur, id_cuenta_bancaria)
            if motivo:
                con.rollback()
                return ("EN_USO", motivo)
            cur.execute("UPDATE cuenta_bancaria SET activo = false WHERE id_cuenta_bancaria = %s", (id_cuenta_bancaria,))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al anular cuenta bancaria: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def reactivarCuentaBancaria(self, id_cuenta_bancaria):
        """
        Reactiva una cuenta anulada. En una sola transacción: bloquea la cuenta, bloquea (FOR SHARE) su banco y exige que esté ACTIVO,
        y que no haya otra cuenta ACTIVA con el mismo banco y número.

        Returns:
            bool | str: True si se reactivó; NO_EXISTE, YA_ACTIVO, EMISORA_INACTIVA o DUPLICADO; False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_entidad_emisora, numero_cuenta, activo FROM cuenta_bancaria WHERE id_cuenta_bancaria = %s FOR UPDATE", (id_cuenta_bancaria,))
            fila = cur.fetchone()
            if fila is None:
                con.rollback()
                return NO_EXISTE
            id_emisora, numero, activo = fila
            if activo:
                con.rollback()
                return YA_ACTIVO
            cur.execute("SELECT activo FROM entidad_emisora WHERE id_entidad_emisora = %s FOR SHARE", (id_emisora,))
            if not cur.fetchone()[0]:
                con.rollback()
                return EMISORA_INACTIVA
            cur.execute("""SELECT 1 FROM cuenta_bancaria WHERE activo = true AND id_entidad_emisora = %s AND numero_cuenta = %s
                           AND id_cuenta_bancaria != %s""", (id_emisora, numero, id_cuenta_bancaria))
            if cur.fetchone() is not None:
                con.rollback()
                return DUPLICADO
            cur.execute("UPDATE cuenta_bancaria SET activo = true WHERE id_cuenta_bancaria = %s", (id_cuenta_bancaria,))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al reactivar cuenta bancaria: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
