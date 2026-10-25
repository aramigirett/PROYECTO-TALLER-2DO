# Data Access Object - DAO
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion

# Códigos de resultado (además de un ID o True)
NO_EXISTE = "NO_EXISTE"
YA_ACTIVO = "YA_ACTIVO"
DUPLICADO = "DUPLICADO"        # ("DUPLICADO", campo, mensaje)
INVALIDO = "INVALIDO"          # ("INVALIDO", campo, mensaje): el módulo elegido no existe o está anulado
PROTEGIDA = "PROTEGIDA"        # ("PROTEGIDA", motivo)
EN_USO = "EN_USO"              # ("EN_USO", motivo)

_COLUMNAS = """m.id_menu, m.id_menu_padre, m.clave, m.descripcion, m.ruta, m.icono, m.orden, m.activo, m.visible_en_menu, m.solo_admin, m.protegida,
               p.descripcion AS modulo"""
_FROM = "FROM menu m LEFT JOIN menu p ON p.id_menu = m.id_menu_padre"


def _fila(r):
    return {'id_menu': r[0], 'id_menu_padre': r[1], 'clave': r[2], 'descripcion': r[3], 'ruta': r[4], 'icono': r[5], 'orden': r[6], 'activo': r[7],
            'visible_en_menu': r[8], 'solo_admin': r[9], 'protegida': r[10], 'modulo': r[11] if r[1] else r[3],
            'tipo': 'ventana' if r[1] else 'modulo'}


class MenuDao:
    """
    Tabla `menu` (Mantener Menú): un MÓDULO es una fila sin padre ni clave; una VENTANA cuelga de su módulo y tiene clave (la que usan los @require_permiso, no
    se cambia) y ruta (endpoint de Flask). Baja lógica con `activo` e índices únicos parciales (clave entre las activas; descripción dentro de su módulo).
    Las filas protegidas (Mantener Menú, Usuarios, Roles y Permisos y el módulo Seguridad) no se anulan, mueven ni pierden la exclusividad del Administrador:
    lo impide también un trigger en la base. Anular un módulo se bloquea si tiene ventanas activas.
    """

    # ---- lectura ----
    def getFilas(self, incluir_inactivos=True):
        """Todas las filas (módulos y ventanas) ordenadas por módulo y orden."""
        sql = f"SELECT {_COLUMNAS} {_FROM}" + ("" if incluir_inactivos else " WHERE m.activo = true") + \
              " ORDER BY COALESCE(p.orden, m.orden), COALESCE(p.id_menu, m.id_menu), (m.id_menu_padre IS NOT NULL), m.orden, m.id_menu"
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(sql)
            return [_fila(r) for r in cur.fetchall()]
        finally:
            cur.close()
            con.close()

    def getFila(self, id_menu):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"SELECT {_COLUMNAS} {_FROM} WHERE m.id_menu = %s", (id_menu,))
            r = cur.fetchone()
            return _fila(r) if r else None
        except Exception as e:
            app.logger.error(f"Error al obtener la entrada de menú: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    # ---- escritura ----
    def _padre_valido(self, cur, id_padre):
        cur.execute("SELECT activo FROM menu WHERE id_menu = %s AND id_menu_padre IS NULL AND clave IS NULL FOR SHARE", (id_padre,))
        f = cur.fetchone()
        return f is not None and f[0]

    def _duplicado(self, e, v):
        nombre = getattr(getattr(e, 'diag', None), 'constraint_name', '') or ''
        if 'clave' in nombre:
            return (DUPLICADO, 'clave', 'Ya existe una ventana activa con esa clave.')
        return (DUPLICADO, 'descripcion', 'Ya existe una entrada activa con esa descripción en el mismo módulo.')

    def guardar(self, v):
        """
        v = {tipo, id_menu_padre (ventanas), clave (ventanas), descripcion, ruta (ventanas), icono, orden, visible_en_menu, solo_admin}.
        Returns: ID nuevo; ("INVALIDO", campo, msg); ("DUPLICADO", campo, msg); False.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            if v['tipo'] == 'ventana' and not self._padre_valido(cur, v['id_menu_padre']):
                con.rollback()
                return (INVALIDO, 'id_menu_padre', 'El módulo seleccionado no existe o está anulado.')
            cur.execute("""INSERT INTO menu (id_menu_padre, clave, descripcion, ruta, icono, orden, visible_en_menu, solo_admin)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id_menu""",
                        (v.get('id_menu_padre'), v.get('clave'), v['descripcion'], v.get('ruta'), v.get('icono'), v['orden'],
                         v.get('visible_en_menu', True), v.get('solo_admin', False)))
            nuevo = cur.fetchone()[0]
            con.commit()
            return nuevo
        except psycopg2.errors.UniqueViolation as e:
            con.rollback()
            return self._duplicado(e, v)
        except Exception as e:
            app.logger.error(f"Error al crear la entrada de menú: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def actualizar(self, id_menu, v):
        """
        Modifica descripción, ícono, orden, visibilidad y, en ventanas, ruta, módulo y exclusividad. La clave no se cambia. Una fila protegida no cambia de módulo,
        de ruta ni deja de ser exclusiva del Administrador. Returns: True; False si no existe o está anulada; ("PROTEGIDA", motivo); ("INVALIDO"|"DUPLICADO", campo, msg).
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_menu_padre, ruta, solo_admin, protegida, clave FROM menu WHERE id_menu = %s AND activo = true FOR UPDATE", (id_menu,))
            f = cur.fetchone()
            if f is None:
                con.rollback()
                return False
            padre, ruta, solo_admin, protegida, clave = f
            if padre is None:     # módulo
                cur.execute("UPDATE menu SET descripcion=%s, icono=%s, orden=%s WHERE id_menu=%s", (v['descripcion'], v.get('icono'), v['orden'], id_menu))
            else:
                if protegida and (v.get('id_menu_padre') != padre or v.get('ruta') != ruta or v.get('solo_admin') is False):
                    con.rollback()
                    return (PROTEGIDA, 'Esta ventana está protegida: no se puede mover, cambiar su ruta ni quitarle la exclusividad del Administrador.')
                if v.get('id_menu_padre') != padre and not self._padre_valido(cur, v['id_menu_padre']):
                    con.rollback()
                    return (INVALIDO, 'id_menu_padre', 'El módulo seleccionado no existe o está anulado.')
                cur.execute("""UPDATE menu SET id_menu_padre=%s, descripcion=%s, ruta=%s, icono=%s, orden=%s, visible_en_menu=%s, solo_admin=%s WHERE id_menu=%s""",
                            (v['id_menu_padre'], v['descripcion'], v['ruta'], v.get('icono'), v['orden'], v.get('visible_en_menu', True), v.get('solo_admin', False), id_menu))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation as e:
            con.rollback()
            return self._duplicado(e, v)
        except psycopg2.errors.RaiseException as e:
            con.rollback()
            return (PROTEGIDA, str(e).split('\n')[0].replace('ERROR:  ', ''))
        except Exception as e:
            app.logger.error(f"Error al actualizar la entrada de menú: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def anular(self, id_menu):
        """Baja lógica. Returns: True; False si no existe o ya estaba anulada; ("PROTEGIDA", motivo); ("EN_USO", motivo) si un módulo todavía tiene ventanas activas."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_menu_padre, protegida, descripcion FROM menu WHERE id_menu = %s AND activo = true FOR UPDATE", (id_menu,))
            f = cur.fetchone()
            if f is None:
                con.rollback()
                return False
            if f[1]:
                con.rollback()
                return (PROTEGIDA, f'"{f[2]}" está protegida: es parte de la administración del sistema y no se puede anular.')
            if f[0] is None:
                cur.execute("SELECT COUNT(*) FROM menu WHERE id_menu_padre = %s AND activo = true", (id_menu,))
                n = cur.fetchone()[0]
                if n:
                    con.rollback()
                    return (EN_USO, f'No se puede anular el módulo "{f[2]}": todavía tiene {n} ventana(s) activa(s). Anúlelas o muévalas primero.')
            cur.execute("UPDATE menu SET activo = false WHERE id_menu = %s", (id_menu,))
            con.commit()
            return True
        except psycopg2.errors.RaiseException as e:
            con.rollback()
            return (PROTEGIDA, str(e).split('\n')[0].replace('ERROR:  ', ''))
        except Exception as e:
            app.logger.error(f"Error al anular la entrada de menú: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()

    def reactivar(self, id_menu):
        """Reactiva una entrada anulada: su módulo tiene que estar activo y no puede haber otra activa con la misma clave o descripción. Returns: True; NO_EXISTE; YA_ACTIVO; tuplas de error."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT activo, id_menu_padre FROM menu WHERE id_menu = %s FOR UPDATE", (id_menu,))
            f = cur.fetchone()
            if f is None:
                con.rollback()
                return NO_EXISTE
            if f[0]:
                con.rollback()
                return YA_ACTIVO
            if f[1] is not None and not self._padre_valido(cur, f[1]):
                con.rollback()
                return (INVALIDO, 'id_menu_padre', 'Su módulo está anulado: reactívelo primero.')
            cur.execute("UPDATE menu SET activo = true WHERE id_menu = %s", (id_menu,))
            con.commit()
            return True
        except psycopg2.errors.UniqueViolation as e:
            con.rollback()
            return self._duplicado(e, {})
        except Exception as e:
            app.logger.error(f"Error al reactivar la entrada de menú: {str(e)}")
            con.rollback()
            return False
        finally:
            cur.close()
            con.close()
