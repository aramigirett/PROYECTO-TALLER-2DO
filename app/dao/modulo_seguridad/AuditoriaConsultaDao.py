# Data Access Object - DAO
"""Consulta (solo lectura) de auditoria_cambios para la pantalla "Auditoría de Cambios", sus exportaciones y las alertas.
Nada de lo que hay acá modifica la auditoría: solo SELECT."""
from flask import current_app as app
from app.conexion.Conexion import Conexion
from app.Services.auditoria_detalle import (MODULO_DESCONOCIDO, MODULO_POR_ENTIDAD, MODULOS, entidades_de_modulo,
                                            etiqueta_entidad)

TOPE_EXPORTACION = 5000     # filas máximas por exportación (PDF / CSV)

_SELECT = """
    SELECT a.id_auditoria_cambio, a.fecha_hora, a.id_usuario,
           COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido) AS usuario,
           COALESCE(f.cedula, m.cedula) AS ci_ruc,
           a.ip, a.modulo, a.entidad, a.id_registro, a.accion, a.detalle, a.valores_anteriores, a.valores_nuevos
    FROM auditoria_cambios a
    LEFT JOIN usuarios u ON u.id_usuario = a.id_usuario
    LEFT JOIN funcionario f ON f.id_funcionario = u.id_funcionario
    LEFT JOIN medico m ON m.id_medico = u.id_medico
"""


def _where(f):
    """WHERE y parámetros de los filtros (desde / hasta inclusivos, id_usuario, modulo, entidad, accion, id_registro).
    Las filas anteriores a la Etapa C tienen modulo NULL: el filtro por módulo también las alcanza por su entidad."""
    cond, params = [], []
    if f.get('desde'):
        cond.append("a.fecha_hora >= %s"); params.append(f['desde'])
    if f.get('hasta'):
        cond.append("a.fecha_hora < %s::date + 1"); params.append(f['hasta'])
    if f.get('id_usuario'):
        cond.append("a.id_usuario = %s"); params.append(f['id_usuario'])
    if f.get('modulo'):
        cond.append("(a.modulo = %s OR (a.modulo IS NULL AND a.entidad = ANY(%s)))")
        params += [f['modulo'], entidades_de_modulo(f['modulo'])]
    if f.get('entidad'):
        cond.append("a.entidad = %s"); params.append(f['entidad'])
    if f.get('accion'):
        cond.append("a.accion = %s"); params.append(f['accion'])
    if f.get('id_registro') is not None:
        cond.append("a.id_registro = %s"); params.append(f['id_registro'])
    return ("WHERE " + " AND ".join(cond)) if cond else "", params


def _fila(r, con_json=True):
    modulo = r[6] or MODULO_POR_ENTIDAD.get(r[7]) or MODULO_DESCONOCIDO
    fila = {
        'id_auditoria_cambio': r[0], 'fecha_hora': r[1].strftime('%Y-%m-%d %H:%M:%S') if r[1] else None,
        'id_usuario': r[2], 'usuario': r[3], 'ci_ruc': r[4], 'ip': r[5], 'modulo': modulo,
        'entidad': r[7], 'entidad_etiqueta': etiqueta_entidad(r[7]), 'id_registro': r[8], 'accion': r[9],
        'detalle': r[10],
    }
    if con_json:
        fila['valores_anteriores'], fila['valores_nuevos'] = r[11], r[12]
    return fila


class AuditoriaConsultaDao:

    def listar(self, filtros, pagina=1, por_pagina=25):
        """(filas, total) del más reciente al más antiguo. Sin el JSON (el detalle se pide por id)."""
        where, params = _where(filtros)
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"SELECT count(*) FROM auditoria_cambios a {where}", tuple(params))
            total = cur.fetchone()[0]
            cur.execute(f"{_SELECT} {where} ORDER BY a.fecha_hora DESC, a.id_auditoria_cambio DESC LIMIT %s OFFSET %s",
                        tuple(params + [por_pagina, (pagina - 1) * por_pagina]))
            return [_fila(r, con_json=False) for r in cur.fetchall()], total
        except Exception as e:
            app.logger.error(f"Error al listar la auditoría de cambios: {str(e)}")
            raise
        finally:
            cur.close()
            con.close()

    def listar_para_exportar(self, filtros, tope=TOPE_EXPORTACION):
        """(filas, total, recortado): hasta `tope` filas CON el JSON, más reciente primero; `total` = lo que cumple el filtro."""
        where, params = _where(filtros)
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"SELECT count(*) FROM auditoria_cambios a {where}", tuple(params))
            total = cur.fetchone()[0]
            cur.execute(f"{_SELECT} {where} ORDER BY a.fecha_hora DESC, a.id_auditoria_cambio DESC LIMIT %s",
                        tuple(params + [tope]))
            return [_fila(r) for r in cur.fetchall()], total, total > tope
        except Exception as e:
            app.logger.error(f"Error al exportar la auditoría de cambios: {str(e)}")
            raise
        finally:
            cur.close()
            con.close()

    def get_by_id(self, id_auditoria):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"{_SELECT} WHERE a.id_auditoria_cambio = %s", (id_auditoria,))
            r = cur.fetchone()
            return _fila(r) if r else None
        except Exception as e:
            app.logger.error(f"Error al obtener el registro de auditoría: {str(e)}")
            raise
        finally:
            cur.close()
            con.close()

    def get_opciones_filtros(self):
        """Opciones de los combos: usuarios que registraron cambios, módulos y entidades (las del mapa + las de la tabla)."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""
                SELECT DISTINCT u.id_usuario,
                       COALESCE(f.nombre || ' ' || f.apellido, m.nombre || ' ' || m.apellido, 'Usuario ' || u.id_usuario),
                       COALESCE(f.cedula, m.cedula)
                FROM auditoria_cambios a JOIN usuarios u ON u.id_usuario = a.id_usuario
                LEFT JOIN funcionario f ON f.id_funcionario = u.id_funcionario
                LEFT JOIN medico m ON m.id_medico = u.id_medico
                ORDER BY 2
            """)
            usuarios = [{'id_usuario': r[0], 'nombre': r[1], 'ci_ruc': r[2]} for r in cur.fetchall()]
            cur.execute("SELECT DISTINCT entidad FROM auditoria_cambios")
            entidades = sorted({r[0] for r in cur.fetchall()} | set(MODULO_POR_ENTIDAD))
            return {'usuarios': usuarios, 'modulos': list(MODULOS),
                    'entidades': [{'valor': e, 'etiqueta': etiqueta_entidad(e)} for e in entidades]}
        except Exception as e:
            app.logger.error(f"Error al obtener las opciones de filtro de auditoría: {str(e)}")
            raise
        finally:
            cur.close()
            con.close()

    def get_empresa(self):
        """Datos de la empresa para el encabezado de los informes (None si no está cargada)."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT razon_social, ruc, direccion, telefono FROM empresa LIMIT 1")
            e = cur.fetchone()
            return {'razon_social': e[0], 'ruc': e[1], 'direccion': e[2], 'telefono': e[3]} if e else None
        finally:
            cur.close()
            con.close()

    def get_alertas(self):
        """Alertas de la vista v_auditoria_anomalias, las más recientes primero."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("""
                SELECT tipo, id_usuario, usuario, fecha_desde, fecha_hasta, entidad, id_registro, accion, cantidad, descripcion
                FROM v_auditoria_anomalias ORDER BY fecha_hasta DESC, tipo, id_usuario NULLS LAST
            """)
            return [{'tipo': r[0], 'id_usuario': r[1], 'usuario': r[2], 'desde': r[3].isoformat(), 'hasta': r[4].isoformat(),
                     'entidad': r[5], 'id_registro': r[6], 'accion': r[7], 'cantidad': r[8], 'descripcion': r[9]}
                    for r in cur.fetchall()]
        except Exception as e:
            app.logger.error(f"Error al obtener las alertas de auditoría: {str(e)}")
            raise
        finally:
            cur.close()
            con.close()
