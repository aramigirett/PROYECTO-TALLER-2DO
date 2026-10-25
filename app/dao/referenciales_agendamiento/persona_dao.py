# Data Access Object - DAO base de las personas de Agendamiento (Paciente, Médico, Funcionario)
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

# Códigos de resultado (además de un ID o True)
DUPLICADO = "DUPLICADO"      # ("DUPLICADO", campo) cuando se conoce el campo repetido
NO_EXISTE = "NO_EXISTE"
YA_ACTIVO = "YA_ACTIVO"
INVALIDO = "INVALIDO"        # ("INVALIDO", campo, mensaje): un referencial padre no existe o está anulado


class PersonaDao:
    """
    Comportamiento común de las tres personas (no existe una tabla Persona: cada una tiene la suya) con borrado lógico (`activo`),
    únicos parciales por documento (WHERE activo), Estado / Reactivar y baja bloqueada si está en uso. SQL crudo con psycopg2, una
    conexión por llamada. Cada persona hereda y declara solo lo suyo:

        TABLA, PK, DOC     tabla, clave primaria y columna del documento (cédula)
        CAMPOS             columnas editables, en el orden en que las recibe guardar() / actualizar()
        PADRES             referenciales que usa: (columna, tabla, pk, columna_texto, clave_de_salida, etiqueta)
        DUPLICADOS         columnas únicas entre los ACTIVOS: (columna, frase para el mensaje)
        MINIMO             columnas que ve quien no tiene 'ver' en la ventana (lo usan los buscadores de otras pantallas)
        USUARIO            columna de `usuarios` que apunta a la persona (médico y funcionario), o None
        NOMBRE             texto para los mensajes de log y de uso
        _motivo_en_uso()   el motivo (texto para el usuario) si tiene trabajo en curso, o False

    La fecha de alta (`fecha_registro`) la pone el servidor. Al guardar o modificar, cada padre se bloquea FOR SHARE (siempre en el mismo
    orden) y se rechaza si está anulado. La baja y la reactivación van en una transacción con la fila bloqueada (FOR UPDATE).
    """
    TABLA = PK = DOC = NOMBRE = USUARIO = None
    CAMPOS = ()
    PADRES = ()
    DUPLICADOS = ()
    MINIMO = ()

    # ---- lectura ----
    def _select(self):
        cols = [f"t.{self.PK}", *[f"t.{c}" for c in self.CAMPOS], "t.fecha_registro", "t.activo"]
        joins = []
        for i, (col, tabla, pk, texto, salida, _) in enumerate(self.PADRES):
            cols.append(f"p{i}.{texto}")
            joins.append(f"LEFT JOIN {tabla} p{i} ON p{i}.{pk} = t.{col}")
        return f"SELECT {', '.join(cols)} FROM {self.TABLA} t " + " ".join(joins)

    def _claves(self):
        return [self.PK, *self.CAMPOS, "fecha_registro", "activo", *[p[4] for p in self.PADRES]]

    def _fila(self, r):
        d = dict(zip(self._claves(), r))
        for k in ("fecha_nacimiento", "fecha_registro"):
            if k in d:
                d[k] = str(d[k]) if d[k] else None
        return d

    def minimo(self, fila):
        """Lo que se muestra a quien solo busca la persona para elegirla (sin datos de contacto)."""
        return {k: fila.get(k) for k in (self.PK, *self.MINIMO)}

    def listar(self, incluir_inactivos=False):
        sql = self._select() + ("" if incluir_inactivos else " WHERE t.activo = true") + f" ORDER BY t.activo DESC, t.nombre, t.apellido, t.{self.PK}"
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
        sql = self._select() + f" WHERE t.{self.PK} = %s" + ("" if incluir_inactivos else " AND t.activo = true")
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

    def duplicado(self, valores, excluir_id=None):
        """(campo, frase) del primer valor repetido entre los ACTIVOS (sin distinguir mayúsculas), o None."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            return self._duplicado(cur, valores, excluir_id)
        except Exception as e:
            app.logger.error(f"Error al verificar duplicado de {self.NOMBRE}: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def _duplicado(self, cur, valores, excluir_id=None):
        for col, frase in self.DUPLICADOS:
            valor = valores.get(col)
            if valor in (None, ''):
                continue
            sql = f"SELECT 1 FROM {self.TABLA} WHERE activo = true AND UPPER(TRIM({col})) = UPPER(TRIM(%s))"
            params = [valor]
            if excluir_id:
                sql += f" AND {self.PK} != %s"
                params.append(excluir_id)
            cur.execute(sql, params)
            if cur.fetchone():
                return (col, frase)
        return None

    def cedulaUsadaPorOtro(self, cedula, excluir_funcionario=None, excluir_medico=None):
        """
        La cédula es el CI/RUC de login del usuario vinculado: no puede repetirse entre médico y funcionario ACTIVOS (la base no garantiza
        la unicidad entre tablas). Devuelve 'funcionario' / 'medico' según dónde esté usada, o None si está libre.
        """
        sql = """
            SELECT 'funcionario' FROM funcionario
            WHERE activo = true AND TRIM(cedula) = %s AND (%s::int IS NULL OR id_funcionario <> %s::int)
            UNION ALL
            SELECT 'medico' FROM medico
            WHERE activo = true AND TRIM(cedula) = %s AND (%s::int IS NULL OR id_medico <> %s::int)
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql, (cedula, excluir_funcionario, excluir_funcionario, cedula, excluir_medico, excluir_medico))
            fila = cur.fetchone()
            return fila[0] if fila else None
        except Exception as e:
            app.logger.error(f"Error al verificar cédula: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def getUsuarioVinculado(self, id_registro):
        """id_usuario del usuario de acceso vinculado a esta persona, o None."""
        if not self.USUARIO:
            return None
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"SELECT id_usuario FROM usuarios WHERE {self.USUARIO} = %s", (id_registro,))
            fila = cur.fetchone()
            return fila[0] if fila else None
        except Exception as e:
            app.logger.error(f"Error al buscar usuario vinculado: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    # ---- escritura ----
    def _bloquear_padres(self, cur, valores):
        """FOR SHARE sobre cada referencial padre (siempre en el mismo orden). Devuelve ("INVALIDO", columna, mensaje) o None."""
        for col, tabla, pk, texto, salida, etiqueta in self.PADRES:
            cur.execute(f"SELECT activo FROM {tabla} WHERE {pk} = %s FOR SHARE", (valores.get(col),))
            f = cur.fetchone()
            if f is None or not f[0]:
                g = 'a' if etiqueta in ('ciudad', 'especialidad') else 'o'
                return (INVALIDO, col, f"{'La' if g == 'a' else 'El'} {etiqueta} seleccionad{g} no existe o está anulad{g}.")
        return None

    def _duplicado_por_indice(self, e):
        nombre = getattr(getattr(e, 'diag', None), 'constraint_name', '') or ''
        for col, frase in self.DUPLICADOS:
            if col in nombre or (col == 'cedula_entidad' and 'cedula' in nombre):
                return (DUPLICADO, col, frase)
        return (DUPLICADO, self.DOC, 'ese documento')

    def guardar(self, valores):
        """
        Returns: ID nuevo; ("DUPLICADO", campo, frase) si el índice único lo rechaza (carrera entre dos altas);
        ("INVALIDO", columna, mensaje) si un padre no existe o está anulado; False ante otro error.
        """
        cols = list(self.CAMPOS)
        sql = f"INSERT INTO {self.TABLA}({', '.join(cols)}) VALUES({', '.join(['%s'] * len(cols))}) RETURNING {self.PK}"
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            invalido = self._bloquear_padres(cur, valores)
            if invalido:
                con.rollback()
                return invalido
            cur.execute(sql, tuple(valores.get(c) for c in cols))
            nuevo = cur.fetchone()[0]
            con.commit()
            return nuevo
        except psycopg2.errors.UniqueViolation as e:
            con.rollback()
            return self._duplicado_por_indice(e)
        except Exception as e:
            app.logger.error(f"Error al insertar {self.NOMBRE}: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def actualizar(self, id_registro, valores):
        """Returns: True; False si no existe (o está anulado) o falló; ("DUPLICADO", campo, frase); ("INVALIDO", columna, mensaje)."""
        cols = list(self.CAMPOS)
        sql = f"UPDATE {self.TABLA} SET {', '.join(c + ' = %s' for c in cols)} WHERE {self.PK} = %s AND activo = true"
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"SELECT 1 FROM {self.TABLA} WHERE {self.PK} = %s AND activo = true FOR UPDATE", (id_registro,))
            if cur.fetchone() is None:
                con.rollback()
                return False
            invalido = self._bloquear_padres(cur, valores)
            if invalido:
                con.rollback()
                return invalido
            cur.execute(sql, (*[valores.get(c) for c in cols], id_registro))
            filas = cur.rowcount
            con.commit()
            return filas > 0
        except psycopg2.errors.UniqueViolation as e:
            con.rollback()
            return self._duplicado_por_indice(e)
        except Exception as e:
            app.logger.error(f"Error al actualizar {self.NOMBRE}: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    # ---- baja / reactivación ----
    def _motivo_en_uso(self, cur, id_registro, quien):
        """A implementar: el texto del motivo (con `quien` = nombre de la persona) si tiene trabajo en curso, o False."""
        raise NotImplementedError

    def _cuenta(self, cur, sql, id_registro):
        cur.execute(sql, (id_registro,))
        return cur.fetchone()[0]

    def esta_en_uso(self, id_registro):
        """False si se puede anular; si no, el texto con el motivo (truthy)."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"SELECT nombre || ' ' || apellido FROM {self.TABLA} WHERE {self.PK} = %s", (id_registro,))
            f = cur.fetchone()
            return self._motivo_en_uso(cur, id_registro, f[0] if f else '')
        except Exception as e:
            app.logger.error(f"Error al verificar uso de {self.NOMBRE}: {str(e)}")
            return "No se pudo verificar si el registro está en uso."  # ante la duda, bloquear
        finally:
            cur.close()
            con.close()

    def anular(self, id_registro):
        """Baja lógica. Returns: True, False (no existía o ya estaba anulado / falló) o ("EN_USO", motivo)."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"SELECT nombre || ' ' || apellido FROM {self.TABLA} WHERE {self.PK} = %s AND activo = true FOR UPDATE", (id_registro,))
            f = cur.fetchone()
            if f is None:
                con.rollback()
                return False
            motivo = self._motivo_en_uso(cur, id_registro, f[0])
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
        Reactiva una persona anulada en una sola transacción: la bloquea, exige que sus referenciales sigan activos y que no haya otra
        persona ACTIVA con el mismo documento (ni, médico / funcionario, la misma cédula en la otra tabla).
        Returns: True; NO_EXISTE, YA_ACTIVO, ("DUPLICADO", campo, frase), ("INVALIDO", columna, mensaje); False ante otro error.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cols = [self.DOC, *[p[0] for p in self.PADRES], *[c for c, _ in self.DUPLICADOS if c != self.DOC]]
            cur.execute(f"SELECT activo, {', '.join(dict.fromkeys(cols))} FROM {self.TABLA} WHERE {self.PK} = %s FOR UPDATE", (id_registro,))
            f = cur.fetchone()
            if f is None:
                con.rollback()
                return NO_EXISTE
            if f[0]:
                con.rollback()
                return YA_ACTIVO
            valores = dict(zip(dict.fromkeys(cols), f[1:]))
            invalido = self._bloquear_padres(cur, valores)
            if invalido:
                con.rollback()
                return invalido
            dup = self._duplicado(cur, valores, id_registro)
            if dup:
                con.rollback()
                return (DUPLICADO, *dup)
            if self.USUARIO and valores.get(self.DOC):
                donde = self.cedulaUsadaPorOtro(str(valores[self.DOC]).strip(),
                                                excluir_funcionario=id_registro if self.TABLA == 'funcionario' else None,
                                                excluir_medico=id_registro if self.TABLA == 'medico' else None)
                if donde:
                    con.rollback()
                    return (DUPLICADO, self.DOC, 'esa cédula (ya pertenece a un ' + ('funcionario' if donde == 'funcionario' else 'médico') + ' activo)')
            cur.execute(f"UPDATE {self.TABLA} SET activo = true WHERE {self.PK} = %s", (id_registro,))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation as e:
            con.rollback()
            return self._duplicado_por_indice(e)
        except Exception as e:
            app.logger.error(f"Error al reactivar {self.NOMBRE}: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

