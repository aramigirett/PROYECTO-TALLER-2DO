"""
=====================================================
DAO: Receta (recetas + receta_medicamento) — Generar Recetas e Indicaciones

Reglas (Ver / Nuevo / Anular; no hay edición; ver documento_clinico.py para las comunes):
  - Cabecera (indicaciones generales) + AL MENOS UN medicamento con dosis, frecuencia y duración; el mismo medicamento no se repite.
  - Los medicamentos ACTIVOS se bloquean FOR SHARE en orden de id (los inactivos se rechazan); los ya recetados se siguen mostrando aunque el
    medicamento se anule después.
  - La receta no tiene estado: la baja es lógica y definitiva (`activo`), con cascada a sus medicamentos; no se anula con la consulta finalizada.
Dato de salud: la auditoría no recibe medicamentos, dosis ni indicaciones; el PDF sí.
=====================================================
"""
import psycopg2.errors
from flask import current_app as app
from app.conexion.Conexion import Conexion
from app.dao.referenciales_consultorio.consulta.ConsultaDao import numero_consulta
from app.dao.referenciales_consultorio.documento_clinico import (
    ESTADOS_ABIERTOS, PREFIJO_RECETA, bloquear_consulta, bloquear_vinculos, datos_para_pdf, numero_documento)

_SELECT = """
    SELECT r.id_receta, r.id_consulta_cab, cc.estado, r.id_diagnostico, d.codigo, r.id_tratamiento, ttr.descripcion, r.indicaciones_generales, r.fecha_receta,
           r.activo, r.fecha_registro, cc.id_paciente, CONCAT(p.nombre, ' ', p.apellido), p.cedula_entidad, cc.id_medico, CONCAT(m.nombre, ' ', m.apellido)
    FROM recetas r
    JOIN consultas_cab cc ON r.id_consulta_cab = cc.id_consulta_cab
    JOIN paciente p ON cc.id_paciente = p.id_paciente
    JOIN medico m ON cc.id_medico = m.id_medico
    LEFT JOIN diagnosticos d ON d.id_diagnostico = r.id_diagnostico
    LEFT JOIN tratamientos tr ON tr.id_tratamiento = r.id_tratamiento
    LEFT JOIN tipos_tratamiento ttr ON ttr.id_tipo_tratamiento = tr.id_tipo_tratamiento"""


def _receta(r, medicamentos):
    return {
        'id_receta': r[0], 'id_consulta_cab': r[1], 'numero_consulta': numero_consulta(r[1]), 'estado_consulta': r[2], 'id_diagnostico': r[3], 'codigo_diagnostico': r[4],
        'id_tratamiento': r[5], 'tipo_tratamiento': r[6], 'indicaciones_generales': r[7], 'fecha_receta': r[8].isoformat() if r[8] else None, 'activo': r[9],
        'fecha_registro': r[10].isoformat() if r[10] else None, 'id_paciente': r[11], 'nombre_paciente': r[12], 'cedula_paciente': r[13], 'id_medico': r[14],
        'nombre_medico': r[15], 'numero': numero_documento(PREFIJO_RECETA, r[0]), 'medicamentos': medicamentos,
    }


class RecetaDao:

    # ------------------------------------------------------------------ lectura
    def _medicamentos(self, cur, ids):
        por_receta = {}
        if ids:
            cur.execute("""SELECT rm.id_receta, rm.id_receta_medicamento, mo.id_medicamento, mo.nombre_comercial, mo.presentacion, rm.dosis, rm.frecuencia, rm.duracion
                           FROM receta_medicamento rm JOIN medicamentos mo ON mo.id_medicamento = rm.id_medicamento
                           WHERE rm.id_receta = ANY(%s) AND rm.activo = true ORDER BY mo.nombre_comercial""", (list(ids),))
            for rec, rid, mid, nombre, pres, dosis, frec, dur in cur.fetchall():
                por_receta.setdefault(rec, []).append({'id_receta_medicamento': rid, 'id_medicamento': mid, 'nombre_comercial': nombre, 'presentacion': pres,
                                                       'dosis': dosis, 'frecuencia': frec, 'duracion': dur})
        return por_receta

    def listar(self, texto=None, desde=None, hasta=None, id_medico=None, id_consulta=None, pagina=1, por_pagina=25):
        """Recetas VIGENTES con filtros, paginadas en el servidor. Devuelve (filas, total)."""
        where, params = ["r.activo = true", "cc.activo = true"], []
        if texto:
            where.append("(CONCAT(p.nombre, ' ', p.apellido) ILIKE %s OR p.cedula_entidad ILIKE %s)")
            params += [f'%{texto}%'] * 2
        if desde:
            where.append("r.fecha_receta >= %s"); params.append(desde)
        if hasta:
            where.append("r.fecha_receta <= %s"); params.append(hasta)
        if id_medico:
            where.append("cc.id_medico = %s"); params.append(id_medico)
        if id_consulta:
            where.append("r.id_consulta_cab = %s"); params.append(id_consulta)
        cond = ' AND '.join(where)
        por_pagina = max(1, min(int(por_pagina), 100))
        pagina = max(1, int(pagina))
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(f"""SELECT COUNT(*) FROM recetas r JOIN consultas_cab cc ON r.id_consulta_cab = cc.id_consulta_cab
                            JOIN paciente p ON cc.id_paciente = p.id_paciente WHERE {cond}""", tuple(params))
            total = cur.fetchone()[0]
            cur.execute(f"{_SELECT} WHERE {cond} ORDER BY r.fecha_receta DESC, r.id_receta DESC LIMIT %s OFFSET %s", tuple(params) + (por_pagina, (pagina - 1) * por_pagina))
            filas = cur.fetchall()
            meds = self._medicamentos(cur, [f[0] for f in filas])
            return [_receta(f, meds.get(f[0], [])) for f in filas], total
        except Exception as e:
            app.logger.error(f"Error al listar recetas: {str(e)}")
            return [], 0
        finally:
            cur.close()
            con.close()

    def getRecetaById(self, id_receta, solo_vigentes=True):
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(_SELECT + " WHERE r.id_receta = %s" + (" AND r.activo = true" if solo_vigentes else ""), (id_receta,))
            f = cur.fetchone()
            return _receta(f, self._medicamentos(cur, [f[0]]).get(f[0], [])) if f else None
        except Exception as e:
            app.logger.error(f"Error al obtener receta: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    def getParaPdf(self, id_receta):
        """La receta (aunque esté anulada: se descarga con la marca) con la clínica y el médico (especialidad, N.º de registro) para el PDF."""
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute(_SELECT + " WHERE r.id_receta = %s", (id_receta,))
            f = cur.fetchone()
            if not f:
                return None
            d = _receta(f, [])
            # una receta anulada conserva sus medicamentos (dados de baja): el PDF los muestra igual
            cur.execute("""SELECT mo.nombre_comercial, mo.presentacion, rm.dosis, rm.frecuencia, rm.duracion FROM receta_medicamento rm
                           JOIN medicamentos mo ON mo.id_medicamento = rm.id_medicamento WHERE rm.id_receta = %s ORDER BY mo.nombre_comercial""", (id_receta,))
            d['medicamentos'] = [{'nombre_comercial': a, 'presentacion': b, 'dosis': c, 'frecuencia': e, 'duracion': g} for a, b, c, e, g in cur.fetchall()]
            d['empresa'], d['medico'] = datos_para_pdf(cur, f[1])
            return d
        except Exception as e:
            app.logger.error(f"Error al leer la receta para el PDF: {str(e)}")
            return None
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ alta
    def guardarReceta(self, datos, id_medico_actor):
        """
        Crea la receta con sus medicamentos en UNA transacción. `datos` ya viene validado (validar_receta) y trae id_consulta_cab.
        Devuelve {'id_receta', 'contexto'} o {'error': CÓDIGO, ...}.
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
            ids = [m['id_medicamento'] for m in datos['medicamentos']]
            cur.execute("SELECT id_medicamento, nombre_comercial, activo FROM medicamentos WHERE id_medicamento = ANY(%s) ORDER BY id_medicamento FOR SHARE", (ids,))
            filas = cur.fetchall()
            if len(filas) != len(ids):
                con.rollback()
                return {'error': 'MEDICAMENTO_NO_EXISTE'}
            inactivos = [f[1] for f in filas if not f[2]]
            if inactivos:
                con.rollback()
                return {'error': 'MEDICAMENTO_INACTIVO', 'detalle': ', '.join(inactivos)}
            cur.execute("""INSERT INTO recetas(id_consulta_cab, id_diagnostico, id_tratamiento, indicaciones_generales, fecha_receta)
                           VALUES (%s, %s, %s, %s, CURRENT_DATE) RETURNING id_receta""",
                        (datos['id_consulta_cab'], datos.get('id_diagnostico'), datos.get('id_tratamiento'), datos['indicaciones_generales']))
            id_receta = cur.fetchone()[0]
            for m in datos['medicamentos']:
                cur.execute("INSERT INTO receta_medicamento(id_receta, id_medicamento, dosis, frecuencia, duracion) VALUES (%s, %s, %s, %s, %s)",
                            (id_receta, m['id_medicamento'], m['dosis'], m['frecuencia'], m['duracion']))
            con.commit()
            return {'id_receta': id_receta, 'contexto': {'paciente': consulta['paciente'], 'cedula': consulta['cedula']}}
        except psycopg2.errors.CheckViolation as e:
            app.logger.error(f"Datos de receta rechazados por la base: {str(e)}")
            con.rollback()
            return {'error': 'DATOS_INVALIDOS'}
        except Exception as e:
            app.logger.error(f"Error al guardar receta: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()

    # ------------------------------------------------------------------ anulación
    def anularReceta(self, id_receta, id_medico_actor):
        """
        Anula (baja lógica definitiva) la receta, con cascada a sus medicamentos. Bloquea la consulta y después la receta. Rechaza si el actor no es el médico
        de la consulta o la consulta no está abierta (finalizada incluida). Devuelve {'ok', 'id_consulta_cab', 'contexto'} o {'error': CÓDIGO, ...}.
        """
        con = Conexion().getConexion()
        cur = con.cursor()
        try:
            cur.execute("SELECT id_consulta_cab FROM recetas WHERE id_receta = %s AND activo = true", (id_receta,))
            fila = cur.fetchone()
            if not fila:
                con.rollback()
                return {'error': 'RECETA_NO_ENCONTRADA'}
            id_consulta = fila[0]
            consulta = bloquear_consulta(cur, id_consulta, 'UPDATE')
            cur.execute("SELECT 1 FROM recetas WHERE id_receta = %s AND activo = true FOR UPDATE", (id_receta,))
            if not cur.fetchone():
                con.rollback()
                return {'error': 'RECETA_NO_ENCONTRADA'}
            if not consulta:
                con.rollback()
                return {'error': 'CONSULTA_NO_ENCONTRADA'}
            if id_medico_actor is None or id_medico_actor != consulta['id_medico']:
                con.rollback()
                return {'error': 'NO_ES_SU_MEDICO'}
            if consulta['estado'] not in ESTADOS_ABIERTOS:
                con.rollback()
                return {'error': 'CONSULTA_NO_ABIERTA', 'estado': consulta['estado']}
            cur.execute("UPDATE recetas SET activo = false WHERE id_receta = %s", (id_receta,))
            cur.execute("UPDATE receta_medicamento SET activo = false WHERE id_receta = %s AND activo = true", (id_receta,))
            con.commit()
            return {'ok': True, 'id_consulta_cab': id_consulta, 'contexto': {'paciente': consulta['paciente'], 'cedula': consulta['cedula']}}
        except Exception as e:
            app.logger.error(f"Error al anular receta: {str(e)}")
            con.rollback()
            return {'error': 'ERROR_INTERNO'}
        finally:
            cur.close()
            con.close()
