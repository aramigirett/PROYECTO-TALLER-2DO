# Data Access Object - DAO base de los referenciales de Consultorio (Estándar de referenciales)
from decimal import Decimal

import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

# Códigos de resultado (además de un ID o True)
DUPLICADO = "DUPLICADO"
NO_EXISTE = "NO_EXISTE"
YA_ACTIVO = "YA_ACTIVO"


class CatalogoDao:
    """
    Comportamiento común de los referenciales con borrado lógico (`activo`) y único parcial por texto: listar (con o sin
    inactivos), obtener, duplicado, alta, modificación, baja bloqueada si está en uso y reactivación. SQL crudo con psycopg2,
    una conexión por llamada (como el resto de los DAO). Cada referencial hereda y declara solo lo suyo:

        TABLA, PK          tabla y clave primaria
        CLAVE              columna de texto única entre los activos (descripcion / nombre_comercial)
        EXTRAS             otras columnas editables, en el orden en que las recibe guardar()/actualizar()
        NOMBRE             texto para los registros de log
        _motivo_en_uso()   el motivo (texto para el usuario) si hay registros vigentes que lo usan, o False

    Protocolo de baja: la verificación de uso y el UPDATE van en la MISMA transacción con la fila bloqueada (FOR UPDATE).
    Los registros que lo usan (tratamientos, sesiones, recetas, órdenes) deben tomar FOR SHARE sobre esta fila al
    guardarse, para que una baja concurrente espere (se agrega en las etapas de esos movimientos).
    """
    TABLA = PK = CLAVE = NOMBRE = None
    EXTRAS = ()

    # ---- lectura ----
    def _columnas(self):
        return [self.PK, self.CLAVE, *self.EXTRAS, 'fecha_registro', 'activo']

    @staticmethod
    def _valor(v):
        if isinstance(v, Decimal):
            return int(v)
        return v

    def _fila(self, r):
        cols = self._columnas()
        d = {c: self._valor(v) for c, v in zip(cols, r)}
        d['fecha_registro'] = str(d['fecha_registro']) if d['fecha_registro'] else None
        return d

    def listar(self, incluir_inactivos=False):
        sql = f"SELECT {', '.join(self._columnas())} FROM {self.TABLA}"
        if not incluir_inactivos:
            sql += " WHERE activo = true"
        sql += f" ORDER BY activo DESC, UPPER({self.CLAVE})"
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            return [self._fila(r) for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al listar {self.NOMBRE}: {str(e)}")
            return []
        finally:
            cur.close()
            con.close()

    def obtener(self, id_registro, incluir_inactivos=False):
        sql = f"SELECT {', '.join(self._columnas())} FROM {self.TABLA} WHERE {self.PK} = %s"
        if not incluir_inactivos:
            sql += " AND activo = true"
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (id_registro,))
            r = cur.fetchone()
            return self._fila(r) if r else None
        except Exception as e:
            app.logger.error(f"Error al obtener {self.NOMBRE}: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def existeDuplicado(self, valor, excluir_id=None):
        """Indica si ya hay un registro ACTIVO con ese texto (sin distinguir mayúsculas)."""
        sql = f"SELECT 1 FROM {self.TABLA} WHERE activo = true AND UPPER({self.CLAVE}) = UPPER(%s)"
        params = [valor]
        if excluir_id:
            sql += f" AND {self.PK} != %s"
            params.append(excluir_id)
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchone() is not None
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de {self.NOMBRE}: {str(e)}")
            return False
        finally:
            cur.close()
            con.close()

    # ---- escritura ----
    def guardar(self, valor, *extras):
        """Returns: ID nuevo, "DUPLICADO" si el índice único lo rechaza (carrera entre dos altas), False ante otro error."""
        cols = [self.CLAVE, *self.EXTRAS]
        sql = (f"INSERT INTO {self.TABLA}({', '.join(cols)}) VALUES({', '.join(['%s'] * len(cols))}) "
               f"RETURNING {self.PK}")
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (valor, *extras))
            nuevo_id = cur.fetchone()[0]
            con.commit()
            return nuevo_id
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al insertar {self.NOMBRE}: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def actualizar(self, id_registro, valor, *extras):
        """Returns: True si se actualizó, False si no existe (o está anulado) o falló, "DUPLICADO" si el único lo rechaza."""
        cols = [self.CLAVE, *self.EXTRAS]
        sql = (f"UPDATE {self.TABLA} SET {', '.join(c + ' = %s' for c in cols)} "
               f"WHERE {self.PK} = %s AND activo = true")
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (valor, *extras, id_registro))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al actualizar {self.NOMBRE}: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ---- baja / reactivación ----
    def _motivo_en_uso(self, cur, id_registro):
        """A implementar en cada referencial: el texto del motivo si está en uso, o False."""
        raise NotImplementedError

    def esta_en_uso(self, id_registro):
        """False si se puede anular; si no, el texto con el motivo (truthy)."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            return self._motivo_en_uso(cur, id_registro)
        except Exception as e:
            app.logger.error(f"Error al verificar uso de {self.NOMBRE}: {str(e)}")
            return "No se pudo verificar si el registro está en uso."  # ante la duda, bloquear
        finally:
            cur.close()
            con.close()

    def anular(self, id_registro):
        """Baja lógica. Returns: True si se anuló, False si no existía (o ya estaba anulado) o falló, ("EN_USO", motivo)."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"SELECT 1 FROM {self.TABLA} WHERE {self.PK} = %s AND activo = true FOR UPDATE", (id_registro,))
            if cur.fetchone() is None:
                con.rollback()
                return False
            motivo = self._motivo_en_uso(cur, id_registro)
            if motivo:
                con.rollback()
                app.logger.warning(f"No se puede anular {self.NOMBRE} {id_registro}: está en uso")
                return ("EN_USO", motivo)
            cur.execute(f"UPDATE {self.TABLA} SET activo = false WHERE {self.PK} = %s", (id_registro,))
            con.commit()
            return True
        except Exception as e:
            app.logger.error(f"Error al anular {self.NOMBRE}: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def reactivar(self, id_registro):
        """
        Reactiva un registro anulado: una sola transacción que lo bloquea y valida que no haya otro ACTIVO con el mismo texto.
        Returns: True si se reactivó; NO_EXISTE, YA_ACTIVO o DUPLICADO; False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"SELECT {self.CLAVE}, activo FROM {self.TABLA} WHERE {self.PK} = %s FOR UPDATE", (id_registro,))
            fila = cur.fetchone()
            if fila is None:
                con.rollback()
                return NO_EXISTE
            valor, activo = fila
            if activo:
                con.rollback()
                return YA_ACTIVO
            cur.execute(f"SELECT 1 FROM {self.TABLA} WHERE activo = true AND UPPER({self.CLAVE}) = UPPER(%s) AND {self.PK} != %s",
                        (valor, id_registro))
            if cur.fetchone() is not None:
                con.rollback()
                return DUPLICADO
            cur.execute(f"UPDATE {self.TABLA} SET activo = true WHERE {self.PK} = %s", (id_registro,))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation:
            con.rollback()
            return DUPLICADO
        except Exception as e:
            app.logger.error(f"Error al reactivar {self.NOMBRE}: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
