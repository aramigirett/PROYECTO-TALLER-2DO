"""
=====================================================
DAO base de las Órdenes de Estudios y de Análisis (estructuralmente idénticas: tabla única, un solo tipo por orden, solo cambia el catálogo).

Reglas (ver documento_clinico.py para las comunes):
  - Estado inicial 'pendiente'; el propio `estado` hace de baja lógica ('cancelado' = anulada, definitiva). Sin columna `activo`.
  - Avanzar el estado (permiso `estado`): UN paso por vez (pendiente -> enviado -> en_proceso -> completado), lo calcula el sistema. Lo hace SOLO el médico
    de la orden (el de su consulta) y SE PERMITE con la consulta FINALIZADA (el paciente trae el resultado días después); no con la consulta cancelada ni
    anulada. Una orden completada o cancelada no avanza.
  - Anular: médico de la consulta, consulta programada / en proceso y orden no completada ni cancelada.
  - El tipo (estudio / análisis) ACTIVO se bloquea FOR SHARE (los inactivos se rechazan); los ya cargados se siguen mostrando aunque el tipo se anule después.
Dato de salud: la auditoría no recibe tipo, motivo ni indicaciones; el PDF sí.
=====================================================
"""
from flask import current_app as app
from app.conexion.Conexion import Conexion
from app.dao.referenciales_consultorio.consulta.ConsultaDao import numero_consulta
from app.dao.referenciales_consultorio.documento_clinico import (
    ESTADOS_ABIERTOS, bloquear_consulta, bloquear_vinculos, datos_para_pdf, numero_documento)

SIGUIENTE_ESTADO = {'pendiente': 'enviado', 'enviado': 'en_proceso', 'en_proceso': 'completado'}
ESTADOS = ('pendiente', 'enviado', 'en_proceso', 'completado', 'cancelado')


class OrdenBaseDao:
    TABLA = None          # orden_estudios
    PK = None             # id_orden_estudio
    TIPO_TABLA = None     # tipo_estudio
    TIPO_PK = None        # id_tipo_estudio
    TIPO_COL = None       # id_tipo_estudio (columna de la orden)
    PREFIJO = None        # OES

    # ------------------------------------------------------------------ lectura
    def _select(self):
        return f"""
        SELECT o.{self.PK}, o.id_consulta_cab, cc.estado, o.id_diagnostico, d.codigo, o.id_tratamiento, ttr.descripcion, o.{self.TIPO_COL}, t.descripcion,
               o.motivo_orden, o.indicaciones, o.fecha_orden, o.estado, o.fecha_registro, cc.id_paciente, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad,
               cc.id_medico, CONCAT(m.nombre, ' ', m.apellido)
        FROM {self.TABLA} o
        JOIN consultas_cab cc ON o.id_consulta_cab = cc.id_consulta_cab
        JOIN paciente p ON cc.id_paciente = p.id_paciente
        JOIN medico m ON cc.id_medico = m.id_medico
        JOIN {self.TIPO_TABLA} t ON t.{self.TIPO_PK} = o.{self.TIPO_COL}
        LEFT JOIN diagnosticos d ON d.id_diagnostico = o.id_diagnostico
        LEFT JOIN tratamientos tr ON tr.id_tratamiento = o.id_tratamiento
        LEFT JOIN tipos_tratamiento ttr ON ttr.id_tipo_tratamiento = tr.id_tipo_tratamiento"""   # sin filtrar activo del tipo: las viejas se siguen viendo

    def _dict(self, r):
        return {
            self.PK: r[0], 'id_consulta_cab': r[1], 'numero_consulta': numero_consulta(r[1]), 'estado_consulta': r[2], 'id_diagnostico': r[3], 'codigo_diagnostico': r[4],
            'id_tratamiento': r[5], 'tipo_tratamiento': r[6], self.TIPO_COL: r[7], 'tipo': r[8], 'motivo_orden': r[9], 'indicaciones': r[10],
            'fecha_orden': r[11].isoformat() if r[11] else None, 'estado': r[12], 'fecha_registro': r[13].isoformat() if r[13] else None,
            'id_paciente': r[14], 'nombre_paciente': r[15], 'cedula_paciente': r[16], 'id_medico': r[17], 'nombre_medico': r[18],
            'numero': numero_documento(self.PREFIJO, r[0]),
        }

    def listar(self, texto=None, estado=None, desde=None, hasta=None, id_medico=None, id_consulta=None, pagina=1, por_pagina=25):
        """Órdenes NO canceladas (salvo que se pida el estado) con filtros, paginadas en el servidor. Devuelve (filas, total)."""
        where, params = ["cc.activo = true"], []
        if estado:
            where.append("o.estado = %s"); params.append(estado)
        else:
            where.append("o.estado <> 'cancelado'")
        if texto:
            where.append("(CONCAT(p.nombre, ' ', p.apellido) ILIKE %s OR p.cedula_entidad ILIKE %s OR t.descripcion ILIKE %s)")
            params += [f'%{texto}%'] * 3
        if desde:
            where.append("o.fecha_orden >= %s"); params.append(desde)
        if hasta:
            where.append("o.fecha_orden <= %s"); params.append(hasta)
        if id_medico:
            where.append("cc.id_medico = %s"); params.append(id_medico)
        if id_consulta:
            where.append("o.id_consulta_cab = %s"); params.append(id_consulta)
        cond = ' AND '.join(where)
        por_pagina = max(1, min(int(por_pagina), 100))
        pagina = max(1, int(pagina))
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"""SELECT COUNT(*) FROM {self.TABLA} o JOIN consultas_cab cc ON o.id_consulta_cab = cc.id_consulta_cab
                            JOIN paciente p ON cc.id_paciente = p.id_paciente JOIN {self.TIPO_TABLA} t ON t.{self.TIPO_PK} = o.{self.TIPO_COL} WHERE {cond}""", tuple(params))
            total = cur.fetchone()[0]
            cur.execute(f"{self._select()} WHERE {cond} ORDER BY o.fecha_orden DESC, o.{self.PK} DESC LIMIT %s OFFSET %s",
                        tuple(params) + (por_pagina, (pagina - 1) * por_pagina))
            return [self._dict(f) for f in cur.fetchall()], total
        except Exception as e:
            app.logger.error(f"Error al listar {self.TABLA}: {str(e)}")
            return [], 0
        finally:
            cur.close()
            con.close()

    def getById(self, id_orden, solo_vigentes=True):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(self._select() + f" WHERE o.{self.PK} = %s" + (" AND o.estado <> 'cancelado'" if solo_vigentes else ""), (id_orden,))
            r = cur.fetchone()
            return self._dict(r) if r else None
        except Exception as e:
            app.logger.error(f"Error al obtener {self.TABLA}: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def getParaPdf(self, id_orden):
        """La orden (aunque esté cancelada: se descarga con la marca) con la clínica y el médico (especialidad, N.º de registro) para el PDF."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(self._select() + f" WHERE o.{self.PK} = %s", (id_orden,))
            r = cur.fetchone()
            if not r:
                return None
            d = self._dict(r)
            d['empresa'], d['medico'] = datos_para_pdf(cur, r[1])
            return d
        except Exception as e:
            app.logger.error(f"Error al leer {self.TABLA} para el PDF: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ alta
    def guardar(self, datos, id_medico_actor):
        """
        Crea la orden en UNA transacción. `datos` ya viene validado y trae id_consulta_cab y la columna del tipo.
        Devuelve {PK, 'contexto'} o {'error': CÓDIGO, ...}.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            consulta = bloquear_consulta(cur, datos['id_consulta_cab'], 'UPDATE')
            if not consulta:
                con.rollback()
                return {'error': 'CONSULTA_NO_ENCONTRADA'}
            if id_medico_actor is None or id_medico_actor != consulta['id_medico']:
                con.rollback()
                return {'error': 'NO_ES_SU_MEDICO'}
            if consulta['estado'] not in ESTADOS_ABIERTOS:
                con.rollback()
                return {'error': 'CONSULTA_NO_ABIERTA', 'estado': consulta['estado']}
            error = bloquear_vinculos(cur, datos['id_consulta_cab'], datos.get('id_diagnostico'), datos.get('id_tratamiento'))
            if error:
                con.rollback()
                return {'error': error}
            cur.execute(f"SELECT activo, descripcion FROM {self.TIPO_TABLA} WHERE {self.TIPO_PK} = %s FOR SHARE", (datos[self.TIPO_COL],))
            tipo = cur.fetchone()
            if not tipo:
                con.rollback()
                return {'error': 'TIPO_NO_EXISTE'}
            if not tipo[0]:
                con.rollback()
                return {'error': 'TIPO_INACTIVO'}
            cur.execute(f"""INSERT INTO {self.TABLA}(id_consulta_cab, id_diagnostico, id_tratamiento, {self.TIPO_COL}, motivo_orden, indicaciones, fecha_orden, estado)
                            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_DATE, 'pendiente') RETURNING {self.PK}""",
                        (datos['id_consulta_cab'], datos.get('id_diagnostico'), datos.get('id_tratamiento'), datos[self.TIPO_COL], datos['motivo_orden'], datos.get('indicaciones')))
            nuevo = cur.fetchone()[0]
            con.commit()
            return {self.PK: nuevo, 'contexto': {'paciente': consulta['paciente'], 'cedula': consulta['cedula']}}
        except Exception as e:
            app.logger.error(f"Error al guardar {self.TABLA}: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ avanzar el estado
    def avanzarEstado(self, id_orden, id_medico_actor):
        """
        Pasa la orden al SIGUIENTE estado. Bloquea la consulta (FOR SHARE: no hace falta que esté abierta, solo que no se cancele / anule mientras se avanza)
        y después la orden. Devuelve {'ok', 'anterior', 'nuevo', 'id_consulta_cab', 'contexto'} o {'error': CÓDIGO, ...}.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"SELECT id_consulta_cab FROM {self.TABLA} WHERE {self.PK} = %s", (id_orden,))
            fila = cur.fetchone()
            if not fila:
                con.rollback()
                return {'error': 'ORDEN_NO_ENCONTRADA'}
            id_consulta = fila[0]
            consulta = bloquear_consulta(cur, id_consulta, 'SHARE')
            cur.execute(f"SELECT estado FROM {self.TABLA} WHERE {self.PK} = %s FOR UPDATE", (id_orden,))
            estado = cur.fetchone()[0]
            if estado == 'cancelado':
                con.rollback()
                return {'error': 'ORDEN_NO_ENCONTRADA'}
            if not consulta:
                con.rollback()
                return {'error': 'CONSULTA_NO_ENCONTRADA'}
            if id_medico_actor is None or id_medico_actor != consulta['id_medico']:
                con.rollback()
                return {'error': 'NO_ES_SU_MEDICO'}
            if consulta['estado'] == 'cancelada':
                con.rollback()
                return {'error': 'CONSULTA_CANCELADA'}
            if estado == 'completado':
                con.rollback()
                return {'error': 'YA_COMPLETADA'}
            nuevo = SIGUIENTE_ESTADO[estado]
            cur.execute(f"UPDATE {self.TABLA} SET estado = %s WHERE {self.PK} = %s", (nuevo, id_orden))
            con.commit()
            return {'ok': True, 'anterior': estado, 'nuevo': nuevo, 'id_consulta_cab': id_consulta,
                    'contexto': {'paciente': consulta['paciente'], 'cedula': consulta['cedula']}}
        except Exception as e:
            app.logger.error(f"Error al avanzar el estado de {self.TABLA}: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ anulación
    def anular(self, id_orden, id_medico_actor):
        """
        Anula (estado 'cancelado', definitivo). Bloquea la consulta y después la orden. Rechaza si el actor no es el médico de la consulta, la consulta no está
        abierta o la orden ya está completada / cancelada. Devuelve {'ok', 'id_consulta_cab', 'contexto'} o {'error': CÓDIGO, ...}.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"SELECT id_consulta_cab FROM {self.TABLA} WHERE {self.PK} = %s AND estado <> 'cancelado'", (id_orden,))
            fila = cur.fetchone()
            if not fila:
                con.rollback()
                return {'error': 'ORDEN_NO_ENCONTRADA'}
            id_consulta = fila[0]
            consulta = bloquear_consulta(cur, id_consulta, 'UPDATE')
            cur.execute(f"SELECT estado FROM {self.TABLA} WHERE {self.PK} = %s FOR UPDATE", (id_orden,))
            estado = cur.fetchone()[0]
            if estado == 'cancelado':
                con.rollback()
                return {'error': 'ORDEN_NO_ENCONTRADA'}
            if not consulta:
                con.rollback()
                return {'error': 'CONSULTA_NO_ENCONTRADA'}
            if id_medico_actor is None or id_medico_actor != consulta['id_medico']:
                con.rollback()
                return {'error': 'NO_ES_SU_MEDICO'}
            if consulta['estado'] not in ESTADOS_ABIERTOS:
                con.rollback()
                return {'error': 'CONSULTA_NO_ABIERTA', 'estado': consulta['estado']}
            if estado == 'completado':
                con.rollback()
                return {'error': 'YA_COMPLETADA'}
            cur.execute(f"UPDATE {self.TABLA} SET estado = 'cancelado' WHERE {self.PK} = %s", (id_orden,))
            con.commit()
            return {'ok': True, 'id_consulta_cab': id_consulta, 'contexto': {'paciente': consulta['paciente'], 'cedula': consulta['cedula']}}
        except Exception as e:
            app.logger.error(f"Error al anular {self.TABLA}: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()
